"""Author PNG metadata -> original native source page, source-only exact binding.

Original provided code and PNG bytes remain authoritative and unchanged. The
matching author page is chosen solely by complete cells/labels/styles/geometry
and endpoints, never by dimensions, layout score or a target image transform.
"""
from pathlib import Path
import copy,hashlib,json,sqlite3,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
INDEX=W/'compiler_native_embedded_source_recovery_v1/9e24c86b8b344ead88f8a55293b70795/recovered.jsonl'
INDEX_SHA='bd3d90316e6dad30c96c4982b274b6364d0a3298e23d072a09e283da81718b06'
POLICY='full_author_PNG_metadata_unique_source_model_binding_literal_export_parameters_and_raw_XML_labels_v2'
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def checked(ref):
 p=Path(ref['file']);p=(p if p.is_absolute()else R/p).resolve(strict=True);require(p.is_relative_to((R/'clean').resolve()),'author_source_input_must_be_complete_clean_asset');b=p.read_bytes();require(sha(b)==ref['sha256'],'author_source_input_asset_changed');return p,b

def index():
 data=INDEX.read_bytes();require(sha(data)==INDEX_SHA,'author_metadata_recovery_index_changed');rows=[json.loads(line)for line in data.splitlines()if line];require(len(rows)==45,'original_author_metadata_scope_not45');return {row['id']:row for row in rows}
def load(given,database=W/'jobs.sqlite'):
 from drawio_author_native_model_semantics_v1 import compare
 from drawio_author_version_dev_v1 import extract_complete_model
 import compiler_native_embedded_source_recovery_v1 as parser
 if isinstance(given,dict):
  require({'id','category','format','source','input_record','input_manifest','output_record','worker_pid','state','updated_at'}<=set(given),'author_frontend_requires_full_canonical_job_dict');identifier=given['id']
 else:require(isinstance(given,(list,tuple))and len(given)==13,'author_frontend_requires_full_canonical_job_tuple');identifier=given[0]
 with sqlite3.connect('file:'+str(Path(database).resolve())+'?mode=ro',uri=True,timeout=30)as db:
  db.row_factory=sqlite3.Row;row=db.execute('select*from jobs where id=?',(identifier,)).fetchone();require(row is not None,'author_canonical_original_missing');job=dict(row)
 if isinstance(given,dict):require(all(given[key]==job[key]for key in ('id','category','format','source','input_record','input_manifest')),'author_frontend_given_source_snapshot_changed')
 else:require(all(given[i]==job[key]for i,key in enumerate(('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid'))if key in ('id','category','format','source','input_record','input_manifest')),'author_frontend_given_source_snapshot_changed')
 source=json.loads(job['input_record']);require((identifier,job['category'],job['format'],job['source'])==(source['pair_sha256'],source['category'],'drawio',source['source'])and source['category']in ('scientific_diagram','poster'),'author_source_original_scope_or_identity_changed')
 rows=index();require(identifier in rows,'typed_original_PNG_has_no_recovered_author_native_metadata');record=rows[identifier];require(record['original_source_record']==source,'author_recovery_original_full_source_record_changed')
 codepath,code=checked(record['assets']['original_provided_code']);imagepath,image=checked(record['assets']['original_reference']);authorpath,author=checked(record['assets']['recovered_author_native']);require(sha(code)==source['code_sha256']and sha(image)==source['image_sha256'],'author_original_code_or_PNG_identity_changed')
 payloads=[]
 for entry in parser.png_metadata(image)['texts']:
  if entry['key']=='mxfile':payloads.append(parser.decode_author(entry['text'])[0])
 require(payloads==[author],'author_clean_XML_not_exact_original_PNG_metadata_payload')
 pair=record['source_page_pairing']['paired_author_page_indices'];require(isinstance(pair,list)and len(pair)==1,'typed_author_source_page_not_uniquely_identified');page=pair[0]
 ad=parser.document(author);gd=parser.document(code);require(ad['parse_ok']and gd['parse_ok']and len(gd['pages'])==1 and ad['structurally_valid']and gd['structurally_valid'],'typed_author_or_provided_full_model_invalid')
 info=ad['pages'][page];root,model,model_bytes=extract_complete_model(author,page,info['page_id']);version=root.get('version');require(version in ('27.0.9','28.0.6'),'typed_author_app_version_not_installed')
 require(root.get('scale')is not None and root.get('border')is not None,'typed_author_scale_or_border_missing');profile={'version':version,'scale':float(root.get('scale')),'border':float(root.get('border'))}
 require(profile['scale']==1. and profile['border']==0.,'typed_author_export_scale_or_border_requires_additional_calibration')
 require(model.get('math')!='1','typed_author_source_math_pending')
 # Raw XML labels/properties remain source. Runtime-native per-text-node
 # mapping proves expansion; unsupported global/markup expansion is pending.
 gmodel=list(ET.fromstring(code).iter('mxGraphModel'));require(len(gmodel)==1,'typed_provided_source_not_one_inline_native_model')
 equivalence=compare(ET.tostring(gmodel[0]),model_bytes);require(equivalence['ok'],'author_provided_code_and_embedded_model_semantic_conflict')
 attrs=parser.attributes_diff(dict(gmodel[0].attrib),dict(model.attrib));require(set(attrs)<={'dx','dy'},'author_provided_model_paint_attribute_conflict')
 selected=copy.deepcopy(root)
 for child in list(selected):selected.remove(child)
 d=ET.SubElement(selected,'diagram',id=info['page_id']or'author_source_page',name=info['page_name']or'author_source_page');d.append(copy.deepcopy(model));xml=ET.tostring(selected,encoding='unicode')
 snapshot={'schema':POLICY,'id':identifier,'input_record_sha256':sha(job['input_record'].encode()),'input_manifest_sha256':sha((job['input_manifest']or'').encode()),'original_Gold_code_sha256':sha(code),'original_PNG_sha256':sha(image),'decoded_author_document_sha256':sha(author),'source_only_unique_author_page_index':page,'source_only_unique_author_page_id':info['page_id'],'author_model_canonical_sha256':info['canonical_model_sha256'],'normalized_selected_author_native_XML_sha256':sha(xml.encode()),'source_export_profile':profile,'Gold_author_complete_cell_semantics':equivalence,'Gold_author_only_editor_viewport_attribute_differences':attrs,'PNG_metadata_key':'mxfile','source_only_no_reference_pixels_or_dimensions_used':True}
 return {'job':job,'source':source,'original_code_bytes':code,'original_reference_bytes':image,'normalized_author_XML':xml,'source_profile':profile,'snapshot':snapshot,'original_source_code':str(codepath.relative_to(R)),'original_reference':str(imagepath.relative_to(R)),'author_document':str(authorpath.relative_to(R))}
