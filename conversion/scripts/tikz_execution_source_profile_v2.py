"""Fresh execution-source reconstruction plus deterministic paint-aware marker fit.

Two-stage batch API: check_execution_profile(record, xml) verifies source/code;
check_execution_marker_render(record, xml, actual_native_png) additionally runs
the unchanged physical-scale marker gate and AA diagnostics. Neither publishes.
Native resource/font/whole-object paint/editing/original-fidelity gates remain
the responsibility of the caller. There is no per-item visual approval step.
"""
import hashlib,json
from pathlib import Path
import tikz_execution_source_profile as base
from tikz_execution_binding_v2 import marker_metrics,VIEWER_SHA256
from tikz_execution_marker_paint_fit import fit_painted_markers,check_marker_only_delta,aa_diagnostics

ROOT=base.ROOT
FIELD='execution_painted_marker_provenance'
PROFILE='actual_pgf_execution_source_and_painted_native_markers_v2'
SCRIPTS=('tikz_execution_binding_v2.py','tikz_execution_marker_quality.py','tikz_execution_marker_paint_fit.py','tikz_execution_source_profile.py','tikz_execution_source_profile_v2.py')
sha=lambda b:hashlib.sha256(b).hexdigest()


def provenance_from_paint_pilot(report_path,v1_report_path=None):
 report_file=base._owned(report_path,'conversion/tikz_execution_marker_paint_pilot');report=json.loads(report_file.read_bytes())
 if not report.get('ok'):raise ValueError('Paint-aware marker pilot did not pass its fixed gates')
 if v1_report_path is None:
  pointer=json.loads((ROOT/'conversion/tikz_execution_binding_pilot.json').read_bytes());v1_report_path=ROOT/pointer['work']/'report.json'
 original_file=base._owned(v1_report_path,'conversion/tikz_execution_binding_pilot');original=json.loads(original_file.read_bytes())
 if report['id']!=original['id']:raise ValueError('Paint-aware pilot and source binding belong to different sources')
 chosen=next(c for c in report['candidates'] if c['rank']==report['chosen_rank']);candidate=(report_file.parent/'candidate.drawio').read_bytes()
 if sha(candidate)!=chosen['code_sha256']:raise ValueError('Paint-aware pilot XML changed')
 files={}
 for name,path in [('v1_xml',original_file.parent/'candidate.drawio'),('baseline_png',original_file.parent/'baseline.png')]:files[name]={'file':str(path.relative_to(ROOT)),'sha256':sha(path.read_bytes())}
 scripts={}
 for name in SCRIPTS:
  path=ROOT/'conversion/scripts'/name;scripts[name]={'file':str(path.relative_to(ROOT)),'sha256':sha(path.read_bytes())}
 return {'version':2,'candidate_code_sha256':chosen['code_sha256'],'rank':chosen['rank'],'v1':base.provenance_from_pilot(original_file),'files':files,'scripts':scripts,'viewer_sha256':VIEWER_SHA256,'prototype_report':str(report_file.relative_to(ROOT)),'scope':'Fresh executed source graph/object reconstruction and deterministic marker fit. Actual native marker pixels plus other native/fidelity gates remain mandatory.'}


def _prepare(record,xml):
 proof=record[FIELD]
 if proof.get('version')!=2:raise ValueError('Unsupported painted marker provenance version')
 if sha(xml.encode())!=record.get('code_sha256') or record['code_sha256']!=proof.get('candidate_code_sha256'):raise ValueError('Current XML differs from painted marker provenance')
 if set(proof['scripts'])!=set(SCRIPTS):raise ValueError('All painted-marker script pins are required')
 for name,value in proof['scripts'].items():
  if value['file']!='conversion/scripts/'+name:raise ValueError('Painted-marker script locator changed')
  base._checked(value['file'],value['sha256'],'conversion/scripts')
 files=proof['files']
 if set(files)!={'v1_xml','baseline_png'}:raise ValueError('Painted-marker baseline file inventory changed')
 v1_xml=base._checked(files['v1_xml']['file'],files['v1_xml']['sha256'],'conversion/tikz_execution_binding_pilot').decode()
 original={**record,'code_sha256':sha(v1_xml.encode()),base.FIELD:proof['v1']}
 sidecar,baseline_record,baseline,payloads,events,folder=base._verify_files(original,v1_xml,proof['v1']);pdf=base._pdf_pixels(payloads['source_render_pdf'],folder,sidecar);dom,matrix=base._capture(payloads['source_render_svg'],payloads['original_reference'])
 from tikz_execution_binding import bind_execution
 rebuilt,binding=bind_execution(baseline,dom,sidecar,events,matrix)
 if not binding['complete']:raise ValueError('Fresh source reconstruction failed: '+json.dumps(binding['issues']))
 if base._canonical(rebuilt)!=base._canonical(v1_xml):raise ValueError('Frozen v1 XML differs from freshly reconstructed executed source graph')
 coverage=base._coverage(baseline,v1_xml,dom,sidecar,binding)
 viewer=ROOT/'evaluation/assets/viewer-static.min.js'
 if proof['viewer_sha256']!=VIEWER_SHA256 or sha(viewer.read_bytes())!=VIEWER_SHA256:raise ValueError('Actual native viewer identity changed')
 if not isinstance(proof['rank'],int) or isinstance(proof['rank'],bool) or not 0<=proof['rank']<4:raise ValueError('Paint-aware marker fit rank outside fixed search protocol')
 current,new_binding,fitting=fit_painted_markers(v1_xml,dom,binding,viewer,proof['rank'])
 if base._canonical(current)!=base._canonical(xml):raise ValueError('Current XML differs from fresh deterministic source/native painted marker reconstruction')
 delta=check_marker_only_delta(v1_xml,xml)
 before=base._checked(files['baseline_png']['file'],files['baseline_png']['sha256'],'conversion/tikz_execution_binding_pilot')
 if sha(before)!=baseline_record['image_sha256']:raise ValueError('Native comparison PNG does not match the frozen baseline record')
 evidence={'code_sha256':record['code_sha256'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'source_pdf_sha256':record['source_render_pdf_sha256'],'source_svg_sha256':record['source_render_svg_sha256'],'engine_sha256':sidecar['engine_sha256'],'hook_sha256':sidecar['hook_sha256'],'trace_sha256':sidecar['execution_trace_sha256'],'pdf_identity':pdf,'coordinate_mapping':binding['coordinate_mapping'],'source_coverage':coverage,'required_source_text_cells':coverage['required_source_text_cells'],'fresh_painted_marker_fitting':fitting,'marker_only_delta':delta,'native_marker_contour_gate_required':True,'native_marker_binding':new_binding['binding'],'native_marker_baseline_png_sha256':sha(before),'source_scope':'Full current source paint/text and actual executed named graph coverage. Free annotations remain explicit. The supplied native PNG is not yet assessed by this source-only API.'}
 return evidence,dom,new_binding,before


def check_execution_profile(record,xml):
 result={'supported':False,'ok':False,'profile':PROFILE,'failures':[],'evidence':{}}
 if record.get('source_format')!='tikz' or not record.get(FIELD):result['failures']=[{'reason':'execution_painted_marker_provenance_not_available'}];return result
 result['supported']=True
 try:result['evidence']=_prepare(record,xml)[0];result['ok']=True
 except Exception as exc:result['failures'].append({'reason':'execution_painted_marker_source_validation_error','type':type(exc).__name__,'error':str(exc)[:3500]})
 return result


def check_execution_marker_render(record,xml,native_png):
 result={'supported':False,'ok':False,'profile':PROFILE+'_native_marker_render','failures':[],'evidence':{}}
 if record.get('source_format')!='tikz' or not record.get(FIELD):result['failures']=[{'reason':'execution_painted_marker_provenance_not_available'}];return result
 result['supported']=True
 try:
  if sha(native_png)!=record.get('image_sha256'):raise ValueError('Supplied actual native PNG differs from current image revision')
  evidence,dom,binding,before=_prepare(record,xml);quality=marker_metrics(before,native_png,xml,dom,binding);evidence.update(actual_native_png_sha256=sha(native_png),marker_quality=quality,marker_aa_diagnostics=aa_diagnostics(before,native_png,dom,binding,quality));result['evidence']=evidence
  if not quality['ok']:raise ValueError('Actual native marker paint failed the uniform physical-scale/IoU/area/outside-ROI gate')
  result['ok']=True
 except Exception as exc:result['failures'].append({'reason':'execution_painted_marker_native_validation_error','type':type(exc).__name__,'error':str(exc)[:3500]})
 return result
