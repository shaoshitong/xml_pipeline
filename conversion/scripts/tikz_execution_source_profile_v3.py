"""Batch execution graph/marker QA with self-contained proof bundles in clean.

check_graph_profile(record, xml) is the source-profile API for QA v3.
check_native_markers(record, xml, actual_png) adds the fixed local marker gate.
Both return supported/ok/profile/failures/evidence. They never change jobs.
"""
import hashlib,json,xml.etree.ElementTree as E
from pathlib import Path
import tikz_execution_source_profile as base
from tikz_execution_graph import parse_events,graph_from_events
from tikz_execution_binding import bind_execution
from tikz_execution_binding_v2 import VIEWER_SHA256,marker_metrics
from tikz_execution_marker_paint_fit import fit_painted_markers,check_marker_only_delta,aa_diagnostics

ROOT=base.ROOT
FIELD='tikz_execution_source_v3'
PROFILE='actual_pgf_execution_full_source_paint_graph_and_native_marker_paint_v3'
SCRIPTS=('tikz_execution_source_profile_v3.py','tikz_execution_source_profile.py','tikz_execution_graph.py','tikz_execution_graph_hooks.tex','tikz_execution_binding.py','tikz_execution_binding_v2.py','tikz_execution_marker_paint_fit.py','tikz_execution_marker_quality.py','svg_dom_pdf_v2.js','svg_convert_v2.py','svg_convert_v3.py','tikz_literal_connectivity.py','tikz_literal_graph.py')
BUNDLE_FILES=('baseline_record.json','baseline.drawio','baseline.png','execution/execution_graph.json','execution/baseline/source.tex','execution/baseline/original_source.tex','execution/baseline/source.pdf','execution/instrumented/source.tex','execution/instrumented/original_source.tex','execution/instrumented/source.pdf','execution/instrumented/source.iic','execution/instrumented/tikz_execution_graph_hooks.tex')
sha=lambda b:hashlib.sha256(b).hexdigest()


def owned(path):
 p=(ROOT/path).resolve()
 if not any(p.is_relative_to(ROOT/area) for area in ('clean','conversion/tikz_execution_candidates_v1')):raise ValueError('Execution proof/data path escapes owned clean or unpublished batch workspace')
 return p


def checked(item):
 data=owned(item['file']).read_bytes()
 if sha(data)!=item['sha256']:raise ValueError('Execution source/proof file hash mismatch: '+item['file'])
 return data


def script_pins():
 return {name:{'file':'conversion/scripts/'+name,'sha256':sha((ROOT/'conversion/scripts'/name).read_bytes())} for name in SCRIPTS}


def manifest(record,xml,bundle,rank=0):
 bundle=Path(bundle).resolve();files={}
 for name in BUNDLE_FILES:
  path=bundle/name
  if path.is_symlink():raise ValueError('Execution proof bundle may not contain symlinks')
  files[name]={'file':str(path.relative_to(ROOT)),'sha256':sha(path.read_bytes())}
 return {'version':3,'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate_code_sha256':sha(xml.encode()),'rank':rank,'files':files,'scripts':script_pins(),'viewer_sha256':VIEWER_SHA256,'accepted':False,'scope':'Complete executed source graph plus every source paint/text object; local native marker/resource/editing/fidelity QA remains mandatory.'}


def relocate(proof,bundle):
 import copy
 out=copy.deepcopy(proof);root=Path(bundle).resolve()
 for name,item in out['files'].items():item['file']=str((root/name).relative_to(ROOT))
 return out


def prepare(record,xml):
 proof=record[FIELD]
 if proof.get('version')!=3 or proof.get('accepted') is not False:raise ValueError('Unsupported or preaccepted execution provenance')
 if sha(xml.encode())!=record.get('code_sha256') or proof['candidate_code_sha256']!=record['code_sha256']:raise ValueError('Current native code revision differs from execution provenance')
 if any(proof[key]!=record.get(key) for key in ('source_code_sha256','source_image_sha256')):raise ValueError('Execution provenance source identity changed')
 if set(proof['scripts'])!=set(SCRIPTS):raise ValueError('Complete execution dependency pins required')
 for name,item in proof['scripts'].items():
  if item['file']!='conversion/scripts/'+name:raise ValueError('Execution script locator changed')
  base._checked(item['file'],item['sha256'],'conversion/scripts')
 required=set(BUNDLE_FILES)
 if required!=set(proof['files']):raise ValueError('Execution proof bundle must contain exactly the required source/pair/trace/PDF artifacts')
 payload={name:checked(item) for name,item in proof['files'].items()};baseline_record=json.loads(payload['baseline_record.json']);baseline=payload['baseline.drawio'].decode();sidecar=json.loads(payload['execution/execution_graph.json']);folder=owned(proof['files']['execution/execution_graph.json']['file']).parent
 # The bundle layout used for fresh PDF comparison is independently pinned.
 for name in required:
  expected=folder.parent/name
  if owned(proof['files'][name]['file'])!=expected:raise ValueError('Execution proof bundle layout changed')
 if sha(baseline.encode())!=baseline_record['code_sha256'] or sha(payload['baseline.png'])!=baseline_record['image_sha256']:raise ValueError('Frozen native baseline pair differs from its record')
 for key in ('id','source_code_sha256','source_image_sha256'):
  if not record.get(key) or baseline_record.get(key)!=record[key]:raise ValueError('Frozen native baseline source changed: '+key)
 if not sidecar.get('ok') or not sidecar.get('source_bytes_unchanged') or sidecar['source_sha256']!=record['source_code_sha256']:raise ValueError('Execution trace source failed or belongs to another source')
 if set(sidecar['runs'])!=set(base.WRAPPERS) or any(r.get('returncode')!=0 for r in sidecar['runs'].values()):raise ValueError('Both execution compile runs must succeed')
 if sidecar['hook_sha256']!=proof['scripts']['tikz_execution_graph_hooks.tex']['sha256']:raise ValueError('Execution hook changed')
 if set(sidecar['pgf_core_files'])!={'tikz.code.tex','pgfmoduleshapes.code.tex','pgfcorearrows.code.tex'}:raise ValueError('Required PGF core files missing')
 base._check_runtime(sidecar['engine_file'],sidecar['engine_sha256'])
 for item in sidecar['pgf_core_files'].values():base._check_runtime(item['file'],item['sha256'])
 for mode,wrapper in base.WRAPPERS.items():
  if payload['execution/'+mode+'/source.tex']!=wrapper or sha(wrapper)!=sidecar['runs'][mode]['wrapper_sha256']:raise ValueError('Unchanged-source wrapper protocol changed')
  if sha(payload['execution/'+mode+'/original_source.tex'])!=record['source_code_sha256'] or sha(payload['execution/'+mode+'/source.pdf'])!=sidecar['runs'][mode]['pdf_sha256']:raise ValueError('Execution source/PDF hash differs from trace provenance')
 if sha(payload['execution/instrumented/tikz_execution_graph_hooks.tex'])!=sidecar['hook_sha256']:raise ValueError('Executed hook bytes changed')
 trace=payload['execution/instrumented/source.iic']
 if sha(trace)!=sidecar['execution_trace_sha256']:raise ValueError('Actual execution trace changed')
 events=parse_events(trace.decode())
 if graph_from_events(events)!=sidecar['graph']:raise ValueError('Execution graph differs from re-parsed trace')
 sources={}
 for key,digest in [('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('source_render_svg','source_render_svg_sha256'),('source_render_pdf','source_render_pdf_sha256')]:
  p=owned(record[key])
  if not p.is_relative_to(ROOT/'clean'):raise ValueError('Original source artifact is outside clean')
  sources[key]=p.read_bytes()
  if sha(sources[key])!=record[digest] or baseline_record.get(digest)!=record[digest]:raise ValueError('Original source artifact changed: '+key)
 pdf=base._pdf_pixels(sources['source_render_pdf'],folder,sidecar);dom,matrix=base._capture(sources['source_render_svg'],sources['original_reference']);rebuilt,binding=bind_execution(baseline,dom,sidecar,events,matrix)
 if not binding['complete']:raise ValueError('Fresh executed source reconstruction failed: '+json.dumps(binding['issues']))
 v1=rebuilt;fitting={'markers':[],'policy':'no_source_markers'}
 if binding['binding']['native_arrowheads']:
  viewer=ROOT/'evaluation/assets/viewer-static.min.js'
  if proof['viewer_sha256']!=VIEWER_SHA256 or sha(viewer.read_bytes())!=VIEWER_SHA256:raise ValueError('Pinned native viewer identity changed')
  rank=proof['rank']
  if not isinstance(rank,int) or isinstance(rank,bool) or not 0<=rank<4:raise ValueError('Paint fit rank outside fixed bounded search protocol')
  rebuilt,binding,fitting=fit_painted_markers(rebuilt,dom,binding,viewer,rank)
 if base._canonical(rebuilt)!=base._canonical(xml):raise ValueError('Current XML differs from fresh complete execution-source and deterministic marker reconstruction')
 coverage=base._coverage(baseline,xml,dom,sidecar,binding);delta=check_marker_only_delta(v1,xml)
 evidence={'code_sha256':record['code_sha256'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'engine_sha256':sidecar['engine_sha256'],'hook_sha256':sidecar['hook_sha256'],'trace_sha256':sidecar['execution_trace_sha256'],'pdf_identity':pdf,'coordinate_mapping':binding['coordinate_mapping'],'source_coverage':coverage,'required_source_text_cells':coverage['required_source_text_cells'],'native_marker_contour_gate_required':bool(binding['binding']['native_arrowheads']),'marker_only_delta':delta,'paint_fitting':fitting,'native_marker_binding':binding['binding'],'source_scope':'Full executed source graph and complete source paint/text. Free annotations are explicitly informational; no unused anchor read is claimed as edge ownership.'}
 return evidence,dom,binding,payload['baseline.png']


def check_graph_profile(record,xml):
 out={'supported':False,'ok':False,'profile':PROFILE,'failures':[],'evidence':{}}
 if record.get('source_format')!='tikz' or not record.get(FIELD):out['failures']=[{'reason':'execution_v3_source_provenance_not_available'}];return out
 out['supported']=True
 try:out['evidence']=prepare(record,xml)[0];out['ok']=True
 except Exception as exc:out['failures'].append({'reason':'execution_v3_source_validation_failed','type':type(exc).__name__,'error':str(exc)[:4000]})
 return out


def check_native_markers(record,xml,actual_png):
 out={'supported':False,'ok':False,'profile':PROFILE+'_actual_native_markers','failures':[],'evidence':{}}
 if record.get('source_format')!='tikz' or not record.get(FIELD):out['failures']=[{'reason':'execution_v3_source_provenance_not_available'}];return out
 out['supported']=True
 try:
  if sha(actual_png)!=record.get('image_sha256'):raise ValueError('Actual native PNG differs from current image revision')
  evidence,dom,binding,before=prepare(record,xml);out['evidence']=evidence
  if binding['binding']['native_arrowheads']:
   quality=marker_metrics(before,actual_png,xml,dom,binding);evidence.update(marker_quality=quality,marker_aa_diagnostics=aa_diagnostics(before,actual_png,dom,binding,quality))
   if not quality['ok']:raise ValueError('Uniform actual native marker physical-scale/IoU/area/outside-ROI gate failed')
  else:evidence['marker_quality']={'ok':True,'source_marker_count':0,'scope':'No source marker to replace; full source/native fidelity remains separately required.'}
  out['evidence']=evidence;out['ok']=True
 except Exception as exc:out['failures'].append({'reason':'execution_v3_native_marker_validation_failed','type':type(exc).__name__,'error':str(exc)[:4000]})
 return out


# QA3 names mirror the v2 adapter. A canvas-only repair may validate the frozen
# execution record/XML/PNG here and prove its current delta with the independent
# canvas contract. Changed current hashes are never silently treated as frozen.
check_execution_profile=check_graph_profile
check_execution_marker_render=check_native_markers
