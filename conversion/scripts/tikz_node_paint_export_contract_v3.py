"""Read unchanged physical export evidence under the new source-proof key."""
from pathlib import Path
from tikz_native_export_frame_v1 import R,require,checked,POLICY,RENDERER,sha,set_view,geometry_identity
import json,copy
from PIL import Image

def registration(record,reference,xml,data_root):
 root=Path(data_root).resolve();require(root==R,'export_registration_requires_actual_HKUST_root')
 p=record['compiler_tikz_node_paint_viewport_v2'];files=p['files'];e=json.loads(checked(root,files['native_padding_proof']));require(e['policy']==POLICY and e['renderer_sha256']==sha(RENDERER.read_bytes()),'export_policy_or_renderer_changed')
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
