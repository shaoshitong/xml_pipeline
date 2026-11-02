"""Immutable clean-owned closed-TikZ candidate bundles; no database writes."""
import base64,datetime,hashlib,json,os,re,sys,xml.etree.ElementTree as E
from pathlib import Path

ROOT=Path('/backup/shaoshitong/img2code_20261029')
FIELD='tikz_closed_paint_source_v1'
ROOT_ATTRIBUTE='tikzClosedPaintSourceProofV1'
VERSION='clean_closed_tikz_fixed_projection_candidate_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
canonical=lambda x:(json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()
LOADED_SHA256=sha(Path(__file__).read_bytes())
CORE_NAMES=('tikz_execution_graph.py','tikz_execution_graph_hooks.tex','tikz_execution_source_profile.py','tectonic_compile.py','sandbox_runner.py','pdf_to_native.py','pdf_fonts.py')

def require(ok,why):
 if not ok:raise ValueError(why)
def clean_path(root,value):
 root=Path(root).resolve();raw=root/value;path=raw.resolve();require(path.is_relative_to(root/'clean') and path.is_file(),'missing/outside-clean payload: '+str(value))
 for p in [raw,*raw.parents]:
  if p==root.parent:break
  require(not p.is_symlink(),'symlink in final payload path')
 return path
def checked(root,item):
 path=clean_path(root,item['file']);blob=path.read_bytes();require(sha(blob)==item['sha256'],'payload hash differs: '+item['file']);require('bytes' not in item or len(blob)==item['bytes'],'payload length differs');return blob

def load_manifest(root,record,xml=None):
 field=record.get(FIELD);require(isinstance(field,dict) and field.get('version')==1,'missing versioned complete source bundle');blob=checked(root,field);manifest=json.loads(blob);require(manifest['version']==VERSION and manifest['id']==record['id']==record['source_pair_sha256'],'bundle/source pair differs');require((manifest['source_code_sha256'],manifest['source_image_sha256'])==(record['source_code_sha256'],record['source_image_sha256']),'bundle original source hashes differ');require(record['source_format']=='tikz' and record.get('format')=='drawio','authoritative source format was relabelled')
 if xml is not None:require(sha(xml.encode())==record['code_sha256'] and E.fromstring(xml).get(ROOT_ATTRIBUTE)==field['sha256'],'candidate XML not bound to complete source manifest')
 for key,item in manifest['files'].items():checked(root,item)
 for field_name,key,digest in [('original_source_code','original_source','source_code_sha256'),('original_reference','original_reference','source_image_sha256'),('source_render_pdf','baseline_pdf','source_render_pdf_sha256'),('source_render_svg','projected_svg','source_render_svg_sha256')]:
  require(record[field_name]==manifest['files'][key]['file'] and record[digest]==manifest['files'][key]['sha256'],'record/source bundle payload differs: '+field_name)
 checked(root,{'file':record['code_file'],'sha256':record['code_sha256']});checked(root,{'file':record['image_file'],'sha256':record['image_sha256']})
 return manifest

def immutable_files(root,publish_files):
 root=Path(root).resolve();written=[]
 for locator,entry in publish_files.items():
  path=root/locator;require(path.resolve().is_relative_to(root/'clean'),'publication target outside clean');raw=Path(entry['source']).read_bytes();require(sha(raw)==entry['sha256'] and len(raw)==entry['bytes'],'staged candidate file changed');path.parent.mkdir(parents=True,exist_ok=True)
  for p in [path.parent,*path.parent.parents]:
   if p==root:break
   require(not p.is_symlink(),'symlink candidate parent')
  if path.exists():require(path.is_file() and not path.is_symlink() and path.read_bytes()==raw,'immutable clean target conflict')
  else:
   with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
   os.chmod(path,0o444);written.append(locator)
 return {'written':written,'verified':len(publish_files),'canonical_database_mutations':0}

def prepare(db,identifier,projection_report,work,root=ROOT,stage_clean=False):
 """Proposal material only. All original-source and QA work is repeated by adapter."""
 import tikz_closed_paint_projection_v1 as projection
 import tikz_closed_paint_bridge_v1 as bridge
 import tikz_source_only_failure_v1 as source
 root=Path(root).resolve();work=Path(work).resolve();require(work.is_relative_to(root/'conversion/prototype/tikz_closed_paint_candidate_v1'),'unowned private candidate work');work.mkdir(parents=True,exist_ok=False);require(not db.in_transaction,'candidate preparation requires RO autocommit');require(sha(Path(__file__).read_bytes())==LOADED_SHA256,'candidate module changed after import');r=json.loads(Path(projection_report).read_text());require(r.get('read_only_new_profile_full_QA_passed') is True and r['id']==identifier,'not a successful proposal material source');require(sha(projection.canonical({k:v for k,v in r.items() if k!='report_sha256'}))==r['report_sha256'],'projection material report damaged')
 for p,h in {**r['files'],**r['external_files']}.items():require(sha(Path(p).read_bytes())==h,'immutable proposal material changed')
 cols=[x[1] for x in db.execute('pragma table_info(jobs)')];row=db.execute('select * from jobs where id=?',(identifier,)).fetchone();require(row,'missing original job');job=dict(zip(cols,row));original=json.loads(job['input_record']);inputs=json.loads(job['input_manifest']);outcome=db.execute('select category,format,source_code_hash,source_image_hash,status from processing_outcomes_v2 where id=?',(identifier,)).fetchone();require(job['format']=='tikz' and job['category'] in ('scientific_diagram','poster') and outcome==(job['category'],'tikz',original['code_sha256'],original['image_sha256'],'pending'),'not authoritative pending requested source scope');require((r['source_identity']['source_code_sha256'],r['source_identity']['source_image_sha256'])==(original['code_sha256'],original['image_sha256'])==(inputs['code_sha256'],inputs['image_sha256']),'old proposal belongs to another source revision')
 code=(root/inputs['source_code']).read_bytes();reference=(root/inputs['reference_image']).read_bytes();require((sha(code),sha(reference))==(original['code_sha256'],original['image_sha256']),'actual source/reference changed');old_private=Path(r['source_record']['private_resource_check_root']);base_xml=(old_private/r['source_record']['code_file']).read_bytes();native_png=(old_private/r['source_record']['image_file']).read_bytes();base=json.loads(Path(r['bridge_evidence']).read_text());src=json.loads(Path(base['source_only_evidence']).read_text());execution=Path(src['evidence_directory'])/'execution';sidecar=json.loads((execution/'execution_graph.json').read_text());environment=json.loads((execution.parent/'environment.json').read_text());config=source.configuration(root)
 import tikz_closed_paint_quality_adapter_v1 as adapter
 adapter_config=adapter.configuration(root);seed={'id':identifier,'source_code_sha256':sha(code),'source_image_sha256':sha(reference),'base_xml_sha256':sha(base_xml),'png_sha256':sha(native_png),'projection':r['projection'],'program_policy':adapter_config['policy']};revision=sha(canonical(seed));target=Path('clean/drawio_unified')/identifier[:2]/identifier/'closed_paint_projection_v1'/revision;payload=work/'payload';payload.mkdir();files={};publish={}
 def add(label,raw,ext):
  name=label+'.'+sha(raw)+'.'+ext;private=payload/name;private.write_bytes(raw);locator=str(target/name);entry={'file':locator,'sha256':sha(raw),'bytes':len(raw)};files[label]=entry;publish[locator]={'source':str(private),'sha256':entry['sha256'],'bytes':len(raw)};return entry
 add('original_source',code,'tex');add('original_reference',reference,'png');add('baseline_pdf',(execution/'baseline/source.pdf').read_bytes(),'pdf');add('instrumented_pdf',(execution/'instrumented/source.pdf').read_bytes(),'pdf');add('source_trace',(execution/'instrumented/source.iic').read_bytes(),'iic');add('baseline_wrapper',(execution/'baseline/source.tex').read_bytes(),'tex');add('instrumented_wrapper',(execution/'instrumented/source.tex').read_bytes(),'tex');add('instrumented_hook',(execution/'instrumented/tikz_execution_graph_hooks.tex').read_bytes(),'tex');add('original_PDF_derived_svg',(old_private/'clean/original_PDF_derived.svg').read_bytes(),'svg');add('projected_svg',(old_private/r['source_record']['source_render_svg']).read_bytes(),'svg');add('projection_contract',canonical(r['projection']),'json');add('source_environment',canonical(environment['files']),'json')
 normalized={'version':'original_cached_PGF_source_compile_receipt_v1','source_sha256':sha(code),'source_bytes_unchanged':sidecar.get('source_bytes_unchanged'),'graph':sidecar['graph'],'hook_sha256':sidecar['hook_sha256'],'runs':{mode:{k:run.get(k) for k in ('returncode','wrapper_sha256','engine_sha256','cache_only')} for mode,run in sidecar['runs'].items()},'instrumentation_pdf_pixel_equivalence':sidecar['instrumentation_pdf_pixel_equivalence'],'upstream_raw_receipt_sha256':sha((execution/'execution_graph.json').read_bytes()),'core_implementation':{str(root/'conversion/scripts'/name):src['pins'][str(root/'conversion/scripts'/name)] for name in CORE_NAMES},'no_model_calls':True};add('source_execution_receipt',canonical(normalized),'json');roster=[]
 for number,f in enumerate(r['source_record']['native_embedded_fonts']):
  entry=add('font_'+str(number),(old_private/f['file']).read_bytes(),'otf');roster.append({'family':f['family'],'file':entry['file'],'sha256':entry['sha256'],'source_font_sha256':f['original_PDF_font_sha256']})
 add('source_font_roster',canonical(roster),'json');manifest={'version':VERSION,'id':identifier,'source_code_sha256':sha(code),'source_image_sha256':sha(reference),'source_format':'tikz','source_record':original,'projection':r['projection'],'files':dict(files),'runtime_policy':adapter_config['policy'],'source_scope':'only complete explicit PGF-closed basic paint and source Unicode text; no named graph or free arrows','no_image_fit':True,'no_crop':True};manifest_raw=canonical(manifest);manifest_entry=add('source_manifest',manifest_raw,'json');tree=E.fromstring(base_xml.decode());tree.set(ROOT_ATTRIBUTE,manifest_entry['sha256']);xml=E.tostring(tree,encoding='unicode').encode();xml_entry=add('diagram',xml,'drawio');png_entry=add('image',native_png,'png');record={'id':identifier,'source_pair_sha256':identifier,'source':job['source'],'category':job['category'],'source_format':'tikz','format':'drawio','source_record':original,'source_code_sha256':sha(code),'source_image_sha256':sha(reference),'code_file':xml_entry['file'],'code_sha256':xml_entry['sha256'],'image_file':png_entry['file'],'image_sha256':png_entry['sha256'],'original_source_code':files['original_source']['file'],'original_reference':files['original_reference']['file'],'source_render_pdf':files['baseline_pdf']['file'],'source_render_pdf_sha256':files['baseline_pdf']['sha256'],'source_render_svg':files['projected_svg']['file'],'source_render_svg_sha256':files['projected_svg']['sha256'],'native_embedded_fonts':roster,'conversion_method':VERSION,'quality_state':'pending_tikz_closed_paint_projection_independent_source_and_native_quality_v1','candidate_quality_adapter':{'file':str(Path(adapter.__file__).resolve()),'sha256':sha(Path(adapter.__file__).read_bytes()),'policy':adapter_config['policy']},FIELD:{'version':1,**manifest_entry},'declared_source_projection':r['projection'],'model_calls':0,'accepted':False};record_raw=canonical(record);record_entry=add('candidate_record',record_raw,'json');result={'id':identifier,'record':record,'record_file':record_entry,'publish_files':publish,'revision':revision,'source_proposal_report_sha256':sha(Path(projection_report).read_bytes()),'module_sha256':LOADED_SHA256,'adapter_policy':adapter_config['policy'],'accepted':False,'published':False,'model_calls':0,'staging_only':True}
 if stage_clean:result['clean_staging']=immutable_files(root,publish);load_manifest(root,record,xml.decode())
 result['result_sha256']=sha(canonical(result));(work/'result.json').write_bytes(canonical(result));return result
