"""Read-only, revision-bound execution-source QA for reconstructed TikZ graphs.

API: check_execution_profile(record, xml) -> supported/ok/profile/failures/evidence.
Use provenance_from_pilot(report_path) to prepare the immutable provenance field.
The caller still runs native rendering/font/editing/original-reference fidelity
gates; a source-coverage pass alone never publishes or accepts a job.
"""
from __future__ import annotations
import collections
import hashlib
import io
import json
import os
import sys
import xml.etree.ElementTree as E
from functools import lru_cache
from pathlib import Path

ROOT=Path(os.environ.get('IMG2CODE_ROOT','/backup/shaoshitong/img2code_20261029')).resolve()
PROFILE='actual_pgf_execution_source_coverage_v1'
FIELD='execution_binding_provenance'
SCRIPTS=('tikz_execution_binding.py','tikz_execution_graph.py','tikz_execution_graph_hooks.tex','svg_dom_pdf_v2.js')
WRAPPERS={'baseline':b'\\input{original_source.tex}\n','instrumented':b'\\AtBeginDocument{\\input{tikz_execution_graph_hooks.tex}}\n\\input{original_source.tex}\n'}
sha=lambda data:hashlib.sha256(data).hexdigest()


def _owned(path,area):
 path=(ROOT/path).resolve()
 if not path.is_relative_to(ROOT/area):raise ValueError('Owned source path escapes '+area)
 return path


def _checked(path,digest,area):
 p=_owned(path,area);data=p.read_bytes()
 if not digest or sha(data)!=digest:raise ValueError('Source/provenance hash mismatch: '+str(path))
 return data


@lru_cache(maxsize=32)
def _runtime_hash(path,size,mtime,inode):
 return sha(Path(path).read_bytes())


def _check_runtime(path,digest):
 p=_owned(path,'conversion/runtime');stat=p.stat()
 if _runtime_hash(str(p),stat.st_size,stat.st_mtime_ns,stat.st_ino)!=digest:raise ValueError('Execution runtime changed: '+str(path))


def provenance_from_pilot(report_path):
 """Build a hash manifest, without modifying a candidate or its published paths."""
 report_file=_owned(report_path,'conversion/tikz_execution_binding_pilot');report=json.loads(report_file.read_bytes())
 if not report.get('ok'):raise ValueError('Pilot did not produce a verified current native draft')
 folder=report_file.parent;locator=json.loads((folder/'sidecar_locator.json').read_bytes());sidecar=_owned(locator['proof'],'conversion/tikz_execution_graph_prototype')
 files={}
 for key,path in [('sidecar',sidecar),('baseline_record',folder/'baseline_record.json'),('baseline_xml',folder/'baseline.drawio')]:
  files[key]={'file':str(path.relative_to(ROOT)),'sha256':sha(path.read_bytes())}
 scripts={}
 for name in SCRIPTS:
  path=ROOT/'conversion/scripts'/name;scripts[name]={'file':str(path.relative_to(ROOT)),'sha256':sha(path.read_bytes())}
 return {'version':1,'source_code_sha256':report['source_sha256'],'candidate_code_sha256':report['output_code_sha256'],'files':files,'scripts':scripts,'prototype_report':str(report_file.relative_to(ROOT)),'scope':'Current source graph/paint coverage only; native resource/editing/fidelity gates remain mandatory.'}


def _verify_files(record,xml,proof):
 if proof.get('version')!=1:raise ValueError('Unsupported execution provenance version')
 if sha(xml.encode())!=record.get('code_sha256') or proof.get('candidate_code_sha256')!=record.get('code_sha256'):raise ValueError('Current XML revision differs from provenance')
 if proof.get('source_code_sha256')!=record.get('source_code_sha256'):raise ValueError('Current source identity differs from provenance')
 if set(proof['scripts'])!=set(SCRIPTS):raise ValueError('Execution source profile requires every pinned parser/binder/hook/DOM script')
 for name,value in proof['scripts'].items():
  if value['file']!='conversion/scripts/'+name:raise ValueError('Execution source profile script locator changed')
  _checked(value['file'],value['sha256'],'conversion/scripts')
 files=proof['files'];sidecar=json.loads(_checked(files['sidecar']['file'],files['sidecar']['sha256'],'conversion/tikz_execution_graph_prototype'))
 baseline_record=json.loads(_checked(files['baseline_record']['file'],files['baseline_record']['sha256'],'conversion/tikz_execution_binding_pilot'))
 baseline_xml=_checked(files['baseline_xml']['file'],files['baseline_xml']['sha256'],'conversion/tikz_execution_binding_pilot').decode()
 if sha(baseline_xml.encode())!=baseline_record['code_sha256']:raise ValueError('Frozen baseline native hash differs from baseline record')
 for key in ('id','source_code_sha256','source_image_sha256'):
  if not record.get(key) or record[key]!=baseline_record.get(key):raise ValueError('Frozen baseline belongs to another source: '+key)
 if not sidecar.get('ok') or sidecar.get('source_sha256')!=record['source_code_sha256']:raise ValueError('Execution sidecar belongs to another source or failed validation')
 if set(sidecar['runs'])!=set(WRAPPERS) or any(run.get('returncode')!=0 for run in sidecar['runs'].values()):raise ValueError('Both baseline and instrumented execution compilations must have succeeded')
 if not sidecar.get('source_bytes_unchanged'):raise ValueError('Execution source bytes were not recorded as unchanged')
 if set(sidecar['pgf_core_files'])!={'tikz.code.tex','pgfmoduleshapes.code.tex','pgfcorearrows.code.tex'}:raise ValueError('Required PGF core identities missing')
 if sidecar['hook_sha256']!=proof['scripts']['tikz_execution_graph_hooks.tex']['sha256']:raise ValueError('Execution hook differs from pinned current hook')
 # All source payloads needed by this profile remain under clean.
 payloads={}
 for key,digest in [('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('source_render_svg','source_render_svg_sha256'),('source_render_pdf','source_render_pdf_sha256')]:
  payloads[key]=_checked(record[key],record[digest],'clean')
  if baseline_record.get(digest)!=record[digest]:raise ValueError('Original source artifact changed since source binding: '+key)
 _check_runtime(sidecar['engine_file'],sidecar['engine_sha256'])
 for value in sidecar['pgf_core_files'].values():_check_runtime(value['file'],value['sha256'])
 folder=_owned(files['sidecar']['file'],'conversion/tikz_execution_graph_prototype').parent
 for mode,run in sidecar['runs'].items():
  work=folder/mode
  wrapper=_checked(str((work/'source.tex').relative_to(ROOT)),run['wrapper_sha256'],'conversion/tikz_execution_graph_prototype')
  if wrapper!=WRAPPERS[mode]:raise ValueError('Execution wrapper bytes differ from the supported unchanged-source protocol')
  _checked(str((work/'original_source.tex').relative_to(ROOT)),sidecar['source_sha256'],'conversion/tikz_execution_graph_prototype')
  _checked(str((work/'source.pdf').relative_to(ROOT)),run['pdf_sha256'],'conversion/tikz_execution_graph_prototype')
 _checked(str((folder/'instrumented/tikz_execution_graph_hooks.tex').relative_to(ROOT)),sidecar['hook_sha256'],'conversion/tikz_execution_graph_prototype')
 trace=_checked(str((folder/'instrumented/source.iic').relative_to(ROOT)),sidecar['execution_trace_sha256'],'conversion/tikz_execution_graph_prototype')
 from tikz_execution_graph import parse_events,graph_from_events
 events=parse_events(trace.decode())
 if graph_from_events(events)!=sidecar['graph']:raise ValueError('Saved source graph does not match the actual execution trace')
 return sidecar,baseline_record,baseline_xml,payloads,events,folder


def _pdf_pixels(current,folder,sidecar):
 sys.path.append(str(ROOT/'conversion/runtime/python_packages'))
 import pymupdf
 blobs=[current,(folder/'baseline/source.pdf').read_bytes(),(folder/'instrumented/source.pdf').read_bytes()];snapshots=[]
 for data in blobs:
  with pymupdf.open(stream=data,filetype='pdf') as doc:
   pages=[]
   for page in doc:
    pix=page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False);pages.append({'rect':list(page.rect),'size':[pix.width,pix.height],'pixel_sha256':sha(pix.samples)})
   snapshots.append(pages)
 if not snapshots[0] or snapshots[0]!=snapshots[1] or snapshots[1]!=snapshots[2]:raise ValueError('Current/original/instrumented PDF pages do not have identical actual pixels')
 if len(snapshots[0])!=1:raise ValueError('This source profile requires exactly one source PDF page')
 if len(sidecar['instrumentation_pdf_pixel_equivalence'])!=len(snapshots[0]):raise ValueError('Saved PDF pixel evidence page count changed')
 for page,prior in zip(snapshots[0],sidecar['instrumentation_pdf_pixel_equivalence']):
  if prior.get('pixel_identical') is not True:raise ValueError('Saved instrumentation PDF identity failed')
  if page['pixel_sha256']!=prior['baseline_pixel_sha256'] or page['pixel_sha256']!=prior['instrumented_pixel_sha256']:raise ValueError('Saved PDF pixel evidence changed')
 return {'fresh_current_baseline_instrumented_pdf_pixels_identical':True,'pages':snapshots[0],'comparison_scale':1.5}


def _capture(svg,reference):
 from PIL import Image
 from playwright.sync_api import sync_playwright
 width,height=Image.open(io.BytesIO(reference)).size;blocked=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.environ.get('IMG2CODE_CHROMIUM','/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'),args=['--disable-dev-shm-usage'])
  try:
   context=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');context.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page=context.new_page()
   page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg.decode())
   page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h)}',[width,height]);page.evaluate('document.fonts.ready')
   script=(ROOT/'conversion/scripts/svg_dom_pdf_v2.js').read_bytes();dom=page.evaluate(script.decode());matrix=page.evaluate('()=>{const m=document.querySelector("svg").getScreenCTM();return [m.a,m.b,m.c,m.d,m.e,m.f]}')
  finally:browser.close()
 if blocked:raise ValueError('Fresh source SVG attempted external resource requests')
 return dom,matrix


def _canonical(xml):
 root=E.fromstring(xml);models=[root] if root.tag=='mxGraphModel' else list(root.iter('mxGraphModel'))
 if len(models)!=1 or root.tag=='mxfile' and len(root.findall('diagram'))!=1:raise ValueError('Exactly one native source page required')
 return E.canonicalize(E.tostring(models[0],encoding='unicode'))


def _coverage(baseline,current,dom,sidecar,binding):
 old={c.get('id'):c for c in E.fromstring(baseline).iter('mxCell')};new={c.get('id'):c for c in E.fromstring(current).iter('mxCell')}
 removed=set(old)-set(new);markers=binding['binding']['native_arrowheads'];wanted={m['source_object'] for m in markers}
 if removed!=wanted:raise ValueError('Source objects other than the matched attached arrowheads were removed')
 text_counter=lambda cells:collections.Counter(c.get('value','') for c in cells.values() if c.get('value'))
 if text_counter(old)!=text_counter(new):raise ValueError('Original source/native text fragments changed')
 edges=[c for c in new.values() if c.get('edge')=='1'];vertices={cid for cid,c in new.items() if c.get('vertex')=='1'}
 if len(edges)!=len(sidecar['graph']['edges']) or any(c.get('source') not in vertices or c.get('target') not in vertices for c in edges):raise ValueError('Source native connector coverage is incomplete')
 source_text=[o['id'] for o in dom['objects'] if o['type']=='text' and o.get('text','').strip()]
 if not set(source_text)<=set(new):raise ValueError('Source text object inventory is incomplete')
 info=[i for i in binding['issues'] if i.get('reason')=='executed_annotation_position_not_on_its_anchor_pair_path']
 material=[i for i in binding['issues'] if i not in info]
 if material:raise ValueError('Unresolved source binding feature: '+json.dumps(material))
 return {'original_source_objects':len(dom['objects']),'all_source_text_fragments_preserved':True,'required_source_text_cells':source_text,'named_source_nodes':len(sidecar['graph']['nodes']),'native_bound_edges':len(edges),'attached_native_markers':len(markers),'only_replaced_source_objects':sorted(removed),'source_edge_owned_label_groups':len(binding['binding']['edge_child_labels']),'free_annotation_count':len(binding['retained_free_annotation_serials']),'free_annotation_informational':info,'does_not_claim_all_free_annotations_are_edge_labels':True}


def check_execution_profile(record,xml):
 result={'supported':False,'ok':False,'profile':PROFILE,'failures':[],'evidence':{}}
 if record.get('source_format')!='tikz' or not record.get(FIELD):
  result['failures']=[{'reason':'execution_binding_provenance_not_available'}];return result
 result['supported']=True
 try:
  sidecar,baseline_record,baseline,payloads,events,folder=_verify_files(record,xml,record[FIELD])
  pdf=_pdf_pixels(payloads['source_render_pdf'],folder,sidecar)
  dom,matrix=_capture(payloads['source_render_svg'],payloads['original_reference'])
  from tikz_execution_binding import bind_execution
  reconstructed,binding=bind_execution(baseline,dom,sidecar,events,matrix)
  if not binding['complete']:raise ValueError('Fresh execution-source reconstruction failed: '+json.dumps(binding['issues']))
  if _canonical(reconstructed)!=_canonical(xml):raise ValueError('Current XML differs from freshly reconstructed execution-source graph')
  coverage=_coverage(baseline,xml,dom,sidecar,binding)
  result['evidence']={'code_sha256':sha(xml.encode()),'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'source_pdf_sha256':record['source_render_pdf_sha256'],'source_svg_sha256':record['source_render_svg_sha256'],'fresh_dom_sha256':sha(json.dumps(dom,sort_keys=True).encode()),'engine_sha256':sidecar['engine_sha256'],'hook_sha256':sidecar['hook_sha256'],'trace_sha256':sidecar['execution_trace_sha256'],'pdf_identity':pdf,'coordinate_mapping':binding['coordinate_mapping'],'source_coverage':coverage,'required_source_text_cells':coverage['required_source_text_cells'],'source_scope':'Full current source paint/text and executed named graph coverage. Free annotations remain explicit source objects. Native render/font/editing/local fidelity gates are separate.','native_marker_contour_gate_required':bool(binding['binding']['native_arrowheads'])}
  result['ok']=True
 except Exception as exc:result['failures'].append({'reason':'execution_source_profile_validation_error','type':type(exc).__name__,'error':str(exc)[:3500]})
 return result
