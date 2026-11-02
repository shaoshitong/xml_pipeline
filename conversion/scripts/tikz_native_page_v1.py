"""Bounded integer whole-graph padding, proved by complete native pixels.

Only actual target paint determines an AA guard. The entire original source
page remains present; no reference pixels choose offsets, scales or geometry.
"""
from pathlib import Path
import copy,hashlib,io,json,os,signal,subprocess,sys
from PIL import Image,ImageChops
from native_page_padding import shift
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
STRICT=W/'rendering_tikz_pdf100_v1/remote_render.py'
PADDING=W/'rendering_tikz_pdf100_padding_v1/remote_render.py'
POLICY='whole_native_graph_integer_padding_full_pixel_and_original_page_preservation_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda x:(json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()

def require(ok,reason):
 if not ok:raise ValueError(reason)

def render(xml,width,height,directory):
 from native_worker import native
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
 argv=[sys.executable,str(Path(native.__file__).resolve()),'--render-native-only','--drawio-renderer',str(PADDING),'--render-directory',str(directory),'--width',str(width),'--height',str(height),'--max-side','8192','--runtime-cache',str(R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')]
 p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'},start_new_session=True)
 try:out,err=p.communicate(xml.encode(),timeout=180)
 except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.communicate();raise
 (directory/'stderr.log').write_bytes(err)
 require(p.returncode==0,'native_full_padding_probe_failed:'+err.decode(errors='replace')[-1500:])
 return (directory/'render.png').read_bytes(),json.loads((directory/'native_render.json').read_bytes())

def exact_pixels(before_padded,after_padded,before_page,after_page,oldinfo,newinfo,plan):
 a=Image.open(io.BytesIO(before_padded)).convert('RGB');b=Image.open(io.BytesIO(after_padded)).convert('RGB')
 la,ta=oldinfo['outside_page_pixel_audit']['offset'];lb,tb=newinfo['outside_page_pixel_audit']['offset'];dx,dy=plan['dx'],plan['dy'];sx=dx+lb-la;sy=dy+tb-ta
 x0=min(0,sx);y0=min(0,sy);x1=max(a.width+sx,b.width);y1=max(a.height+sy,b.height);require((x1-x0)*(y1-y0)<=64000000,'padding_pixel_proof_resource_bound')
 aa=Image.new('RGB',(x1-x0,y1-y0),'white');bb=aa.copy();aa.paste(a,(sx-x0,sy-y0));bb.paste(b,(-x0,-y0))
 require(ImageChops.difference(aa,bb).getbbox() is None,'complete_native_paint_changed_by_integer_padding')
 old=Image.open(io.BytesIO(before_page)).convert('RGB');new=Image.open(io.BytesIO(after_page)).convert('RGB');region=new.crop((dx,dy,dx+old.width,dy+old.height))
 require(old.size==region.size and old.tobytes()==region.tobytes(),'original_native_page_pixels_changed_by_padding')
 require(oldinfo['actual_platform_font_usage']==newinfo['actual_platform_font_usage'],'actual_physical_fonts_changed_by_padding')
 return {'complete_same_view_native_paint_pixel_identical':True,'original_native_page_pixel_identical':True,'actual_platform_fonts_identical':True,'pixel_difference_tolerance':0,'registered_audit_offset':[sx,sy]}

def produce(xml,width,height,work):
 from native_padding_proof import plan_from_pixels,verify_cells
 work=Path(work);work.mkdir(parents=True,exist_ok=False)
 before_png,old=render(xml,width,height,work/'before')
 plan=plan_from_pixels((work/'before/render.padded.png').read_bytes(),old)
 changed,geometry=shift(xml,int(plan['dx']),int(plan['dy']),int(plan['width']),int(plan['height']))
 verify_cells(xml,changed,geometry)
 after_png,new=render(changed,plan['width'],plan['height'],work/'after')
 from strict_canvas_gate import require_declared_page
 require_declared_page(new,plan['width'],plan['height'])
 before_probe=(work/'before/render.padded.png').read_bytes();after_probe=(work/'after/render.padded.png').read_bytes();before_page=(work/'before/render.stable_page.png').read_bytes()
 proof=exact_pixels(before_probe,after_probe,before_page,after_png,old,new,plan)
 evidence={'policy':POLICY,'input_code_sha256':sha(xml.encode()),'output_code_sha256':sha(changed.encode()),'source_canvas':[width,height],'target_canvas':[plan['width'],plan['height']],'geometry':geometry,'plan':plan,'actual_pixel_proof':proof,'reference_pixels_used_for_alignment':False,'complete_original_page_retained':True}
 assets={'unshifted_native_xml':(xml.encode(),'drawio'),'native_padding_before_probe':(before_probe,'png'),'native_padding_after_probe':(after_probe,'png'),'native_padding_before_page':(before_page,'png'),'native_padding_after_page':(after_png,'png'),'native_padding_before_info':(raw(old),'json'),'native_padding_after_info':(raw(new),'json'),'native_padding_proof':(raw(evidence),'json')}
 (work/'proof.json').write_bytes(raw(evidence));return changed,evidence,assets

def checked(root,ref):
 p=(root/ref['file']).resolve(strict=True);require(p.is_relative_to(root/'clean'),'padding_evidence_outside_clean');data=p.read_bytes();require(sha(data)==ref['sha256'],'padding_evidence_changed');return data

def registration(record,reference,xml,data_root):
 from native_padding_proof import verify_cells
 root=Path(data_root).resolve();require(root==R,'padding_registration_requires_actual_HKUST_root')
 p=record['compiler_tikz_poppler_source_v2'];files=p['files'];evidence=json.loads(checked(root,files['native_padding_proof']))
 require(evidence['policy']==POLICY and evidence['output_code_sha256']==record['code_sha256']==sha(xml.encode()),'padding_contract_not_bound_to_current_native_XML')
 original=checked(root,files['unshifted_native_xml']).decode();require(evidence['input_code_sha256']==sha(original.encode()),'padding_original_XML_changed')
 plan=evidence['plan'];replayed,geometry=shift(original,plan['dx'],plan['dy'],plan['width'],plan['height'])
 require(geometry==evidence['geometry'] and replayed==xml,'whole_graph_padding_transform_does_not_replay');verify_cells(original,xml,geometry)
 old=json.loads(checked(root,files['native_padding_before_info']));new=json.loads(checked(root,files['native_padding_after_info']))
 proof=exact_pixels(checked(root,files['native_padding_before_probe']),checked(root,files['native_padding_after_probe']),checked(root,files['native_padding_before_page']),checked(root,files['native_padding_after_page']),old,new,plan)
 require(proof==evidence['actual_pixel_proof'],'whole_graph_native_pixel_proof_changed')
 from strict_canvas_gate import require_declared_page
 require_declared_page(new,plan['width'],plan['height'])
 require(sha(reference)==record['source_image_sha256'] and list(Image.open(io.BytesIO(reference)).size)==evidence['source_canvas'],'padding_original_reference_identity_or_canvas_changed')
 contract={'version':1,'method':POLICY,'reference_page':evidence['source_canvas'],'output_page':evidence['target_canvas'],'original_page_offset':[plan['dx'],plan['dy']],'source_image_sha256':record['source_image_sha256'],'current_code_sha256':record['code_sha256'],'scale':1,'complete_original_page_retained':True,'reference_pixels_used_for_alignment':False,'original_native_page_actual_pixels_unchanged':True}
 return {**copy.deepcopy(record),'_verified_reference_registration':contract},contract
