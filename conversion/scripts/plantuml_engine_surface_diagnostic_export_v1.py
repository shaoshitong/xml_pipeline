"""Actual native full-paint inspection and original recorded SVG surface export."""
from pathlib import Path
import copy,hashlib,json,os,signal,subprocess,sys,uuid,xml.etree.ElementTree as E
from compiler_typed_runtime_failure_v1 import is_infrastructure
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';RENDERER=W/'rendering_plantuml_surface_diagnostic_v1/remote_render.py'
ATTRS={k:'plantumlSourceInspection'+k.title()+'V1'for k in ('x','y','width','height')}
MODE='diagnostic_PlantUML_surface_actual_native_effect_paint_never_qualified_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(x,r):
 if not x:raise ValueError(r)
def declare(xml,plan):
 t=E.fromstring(xml);m=t if t.tag=='mxGraphModel'else t.find('.//mxGraphModel');require(m is not None,'source_native_model_missing')
 for k,a in ATTRS.items():
  require(k in plan and isinstance(plan[k],int)and not isinstance(plan[k],bool),'source_inspection_plan_invalid');m.set(a,str(plan[k]))
 return E.tostring(t,encoding='unicode')
def verify_declaration(xml,plan):
 t=E.fromstring(xml);m=t if t.tag=='mxGraphModel'else t.find('.//mxGraphModel');require(m is not None and all(m.get(a)==str(plan[k])for k,a in ATTRS.items()),'native_source_inspection_not_fresh_SOURCE_plan');return True
def geometry_identity(before,after):
 a,b=map(E.fromstring,[before,after]);m=b if b.tag=='mxGraphModel'else b.find('.//mxGraphModel')
 for k in ATTRS.values():m.attrib.pop(k,None)
 require(E.canonicalize(E.tostring(a,encoding='unicode'))==E.canonicalize(E.tostring(b,encoding='unicode')),'source_viewport_changed_native_geometry_style_topology_or_text');return dict(only_source_inspection_attrs_added=True,all_native_geometry_style_topology_text_identical=True)
def render(xml,size,work=None):
 from native_worker import native
 from PIL import Image
 work=Path(work or W/'plantuml_surface_diagnostic_export_v1'/uuid.uuid4().hex).resolve();require(work.is_relative_to(W),'source_native_render_work_outside_owner');work.mkdir(parents=True,exist_ok=False)
 argv=[sys.executable,str(Path(native.__file__).resolve()),'--render-native-only','--drawio-renderer',str(RENDERER),'--render-directory',str(work),'--width',str(size[0]),'--height',str(size[1]),'--max-side','8192','--runtime-cache',str(R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')]
 p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
 try:stdout,stderr=p.communicate(xml.encode(),timeout=180)
 except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.communicate();raise
 (work/'stderr.log').write_bytes(stderr)
 if p.returncode!=0 and is_infrastructure({'failures':[{'error':stderr.decode(errors='replace')}] }):raise RuntimeError('infrastructure_source_viewport_native_runtime:'+stderr.decode(errors='replace')[-1800:])
 require(p.returncode==0,'source_viewport_native_render_failed:'+stderr.decode(errors='replace')[-1800:]);info=json.loads((work/'native_render.json').read_bytes());png=(work/'render.png').read_bytes();inspection=(work/'render.inspection.png').read_bytes();svg=(work/'render.svg').read_bytes()
 require(info.get('export_mode')==MODE and info.get('strict_outside_inspection_pixels')==0,'native_full_source_inspection_unproved')
 rootclip=info.get('native_outer_svg_inspection_clip_policy',{});require(rootclip.get('inspection_computed_overflow')=='visible' and rootclip.get('only_actual_graph_outer_SVG_and_container_clips_disabled')is True and rootclip.get('inspection_container_computed_overflow')=='visible' and rootclip.get('model_unchanged')is True,'native_outer_svg_full_paint_hidden')
 for k in ['actual_native_dom_bounds_contained_in_source_inspection','native_inspection_to_export_pixels_exact','complete_native_model_paint_inspected','model_geometry_preserved','graph_view_unchanged']:require(info.get(k)is True,'native_source_viewport_proof_missing:'+k)
 require(info['full_native_inspection_png_sha256']==sha(inspection)and info['native_svg_export_sha256']==sha(svg),'native_source_viewport_artifact_hash_changed');require(list(Image.open(__import__('io').BytesIO(png)).size)==list(size),'native_source_viewport_canvas_changed')
 return dict(ok=True,png=png,native_render=info,inspection_png=inspection,svg=svg,work=str(work))

def require_native_render(info,width,height):
 require(info.get('export_mode')==MODE and info.get('export_viewport')==[width,height],'native_official_PlantUML_surface_export_not_proved')
 require(info.get('strict_outside_inspection_pixels')==0 and all(info.get(k)is True for k in ('complete_native_model_paint_inspected','native_inspection_to_export_pixels_exact','model_geometry_preserved','graph_view_unchanged')),'native_complete_source_paint_not_inspected')
 return True
