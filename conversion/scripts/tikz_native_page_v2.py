"""Complete native export viewport with unchanged model geometry.

The source-only full paint inspection determines one integer viewport translation.
Only explicit export attrs are added. Original page, every actual paint pixel,
all original native geometry/styles and all physical glyphs are retained.
"""
from pathlib import Path
import copy,hashlib,io,json,uuid,xml.etree.ElementTree as ET
from PIL import Image
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
RENDERER=W/'rendering_tikz_export_view_v1/remote_render.py'
POLICY='complete_native_source_paint_external_CSS_export_viewport_v2'
ATTRS={k:'tikzExport'+k.title()+'V1' for k in ('dx','dy','width','height')}
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda x:(json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def model(xml):
 root=ET.fromstring(xml);m=root if root.tag=='mxGraphModel' else root.find('.//mxGraphModel');require(m is not None,'one_native_model_required');return root,m
def set_view(xml,plan):
 root,m=model(xml)
 for k,a in ATTRS.items():m.set(a,str(plan[k]))
 return ET.tostring(root,encoding='unicode')
def geometry_identity(before,after):
 a,_=model(before);b,m=model(after)
 for k in ATTRS.values():m.attrib.pop(k,None)
 require(ET.canonicalize(ET.tostring(a,encoding='unicode'))==ET.canonicalize(ET.tostring(b,encoding='unicode')),'export_changed_original_geometry_styles_topology_or_text')
 return {'all_model_geometry_styles_text_topology_identical':True,'only_explicit_export_viewport_attrs_added':True}
def dimensions(xml):
 _,m=model(xml);return tuple(int(m.get(ATTRS[k],m.get('page'+k.title(),'0'))) for k in ('width','height'))
def render(xml,width,height,directory=None):
 from native_worker import native
 out=native.native_job(xml,width,height,180,RENDERER,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
 require(out.get('ok'),'complete_native_export_render_failed:'+str({k:v for k,v in out.items() if k!='png'})[:2000])
 info=out['native_render'];require(info.get('export_mode')=='complete_native_paint_css_viewport_v1','wrong_export_renderer_policy')
 for k in ('complete_source_paint_retained','complete_original_page_retained','model_geometry_preserved','graph_view_unchanged','exact_complete_paint_export_pixels','actual_export_glyph_translation_verified'):require(info.get(k) is True,'missing_full_export_proof:'+k)
 require(info['strict_outside_inspection_pixels']==info['strict_outside_export_pixels']==0,'source_paint_outside_export_or_inspection')
 require(info['paint_safety_frame']=='full_paint_inspection_viewport','ambiguous_paint_safety_frame')
 require(list(Image.open(io.BytesIO(out['png'])).size)==info['export_viewport'],'export_canvas_changed')
 if directory:
  d=Path(directory);d.mkdir(parents=True,exist_ok=False);(d/'render.png').write_bytes(out['png']);(d/'native_render.json').write_bytes(raw(info))
 return out['png'],info

def produce(xml,width,height,work):
 work=Path(work);work.mkdir(parents=True,exist_ok=False)
 before,old=render(xml,width,height,work/'before');plan=old['export_plan'];changed=set_view(xml,plan);geometry=geometry_identity(xml,changed)
 after,new=render(changed,plan['width'],plan['height'],work/'after')
 require(old['export_plan']==new['export_plan'],'export_plan_changed_by_declaration')
 require(Image.open(io.BytesIO(before)).convert('RGBA').tobytes()==Image.open(io.BytesIO(after)).convert('RGBA').tobytes(),'declared_export_changed_native_pixels')
 require(old['actual_platform_font_usage']==new['actual_platform_font_usage'] and old['actual_text_positions']==new['actual_text_positions'],'declared_export_changed_actual_fonts_or_glyphs')
 evidence={'policy':POLICY,'input_code_sha256':sha(xml.encode()),'output_code_sha256':sha(changed.encode()),'source_canvas':[width,height],'target_canvas':[plan['width'],plan['height']],'geometry':geometry,'plan':plan,'source_only_complete_paint_inspection':True,'reference_pixels_used_for_alignment':False,'complete_original_page_retained':True,'exact_complete_native_paint_pixels':True,'original_declared_page_outside_pixels':new['original_declared_page_outside_pixels'],'strict_outside_export_pixels':0,'strict_outside_inspection_pixels':0,'paint_safety_frame':'full_paint_inspection_viewport','renderer_sha256':sha(RENDERER.read_bytes())}
 assets={'unshifted_native_xml':(xml.encode(),'drawio'),'native_export_before_png':(before,'png'),'native_export_after_png':(after,'png'),'native_export_before_info':(raw(old),'json'),'native_export_after_info':(raw(new),'json'),'native_padding_proof':(raw(evidence),'json')}
 (work/'proof.json').write_bytes(raw(evidence));return changed,evidence,assets

def checked(root,ref):
 p=(root/ref['file']).resolve(strict=True);require(p.is_relative_to(root/'clean'),'export_evidence_outside_clean');data=p.read_bytes();require(sha(data)==ref['sha256'],'export_evidence_changed');return data

def registration(record,reference,xml,data_root):
 root=Path(data_root).resolve();require(root==R,'export_registration_requires_actual_HKUST_root')
 p=record['compiler_tikz_poppler_source_v3'];files=p['files'];e=json.loads(checked(root,files['native_padding_proof']));require(e['policy']==POLICY and e['renderer_sha256']==sha(RENDERER.read_bytes()),'export_policy_or_renderer_changed')
 require(e['output_code_sha256']==record['code_sha256']==sha(xml.encode()),'export_contract_not_bound_to_current_native_XML')
 original=checked(root,files['unshifted_native_xml']).decode();require(e['input_code_sha256']==sha(original.encode()),'export_original_XML_changed')
 require(set_view(original,e['plan'])==xml,'declared_export_viewport_does_not_replay');require(geometry_identity(original,xml)==e['geometry'],'export_model_identity_changed')
 old=json.loads(checked(root,files['native_export_before_info']));new=json.loads(checked(root,files['native_export_after_info']))
 require(old['export_plan']==new['export_plan']==e['plan'],'export_paint_inventory_plan_changed')
 for info in (old,new):
  require(info['strict_outside_export_pixels']==info['strict_outside_inspection_pixels']==0 and info['complete_source_paint_retained'] and info['exact_complete_paint_export_pixels'],'full_export_evidence_missing')
 a=Image.open(io.BytesIO(checked(root,files['native_export_before_png']))).convert('RGBA');b=Image.open(io.BytesIO(checked(root,files['native_export_after_png']))).convert('RGBA')
 require(a.size==b.size and a.tobytes()==b.tobytes(),'export_complete_paint_pixels_changed')
 require(sha(reference)==record['source_image_sha256'] and list(Image.open(io.BytesIO(reference)).size)==e['source_canvas'],'export_original_reference_identity_or_canvas_changed')
 contract={'version':2,'method':POLICY,'reference_page':e['source_canvas'],'output_page':e['target_canvas'],'original_page_offset':[e['plan']['dx'],e['plan']['dy']],'source_image_sha256':record['source_image_sha256'],'current_code_sha256':record['code_sha256'],'scale':1,'complete_original_page_retained':True,'reference_pixels_used_for_alignment':False,'model_geometry_preserved':True,'paint_safety_frame':'full_paint_inspection_viewport'}
 return {**copy.deepcopy(record),'_verified_reference_registration':contract},contract
