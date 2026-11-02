import hashlib,io,json,sqlite3
from PIL import Image
from native_worker import R,W,now
from native_page_padding import shift
from native_padding_proof import render,verify_cells,plan_from_pixels,exact_pixel_proof
from svg_batch import metric
from strict_canvas_gate import require_declared_page
id='03299a3c21789a81926f027324ec2c78cc9134ff3fc0e46e271f1699b3202c19'
db=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);state,raw=db.execute('select state,output_record from jobs where id=?',(id,)).fetchone();r=json.loads(raw);xml=(R/r['code_file']).read_text();oldpng=(R/r['image_file']).read_bytes();reference=(R/r['original_reference']).read_bytes()
assert hashlib.sha256(xml.encode()).hexdigest()==r['code_sha256'] and hashlib.sha256(oldpng).hexdigest()==r['image_sha256'];assert hashlib.sha256(reference).hexdigest()==r['source_image_sha256']
folder=W/'native_page_padding_pilot'/id/r['code_sha256'];folder.mkdir(parents=True,exist_ok=True);(folder/'before_record.json').write_text(raw);w,h=Image.open(io.BytesIO(reference)).size
baseline,info=render(xml,w,h,folder/'baseline');assert info['selected_image']=='complete_tight_graph';audit=info['outside_page_pixel_audit'];original_padded=(folder/'baseline/render.padded.png').read_bytes();canvas=plan_from_pixels(original_padded,info);nw,nh=canvas['width'],canvas['height'];dx,dy=canvas['dx'],canvas['dy']
new,proof=shift(xml,dx,dy,nw,nh);assert verify_cells(xml,new,proof);(folder/'candidate.drawio').write_text(new)
png,newinfo=render(new,nw,nh,folder/'candidate');require_declared_page(newinfo,nw,nh)
a=Image.open(io.BytesIO(original_padded)).convert('RGB').crop(canvas['probe_crop']);b=Image.open(io.BytesIO(png)).convert('RGB')
pixel_identical=a.size==b.size and a.tobytes()==b.tobytes()
fonts_equal=info['actual_platform_font_usage']==newinfo['actual_platform_font_usage']
exact=exact_pixel_proof(folder/'baseline',folder/'candidate',info,newinfo,canvas)
out={'at':now(),'id':id,'state_at_snapshot':state,'old_code_sha256':r['code_sha256'],'new_code_sha256':hashlib.sha256(new.encode()).hexdigest(),'new_image_sha256':hashlib.sha256(png).hexdigest(),'geometry_proof':proof,'canvas_plan':canvas,'before_ref_ssim':metric(reference,oldpng),'after_ref_ssim':metric(reference,png),'padded_baseline_pixel_identical':pixel_identical,'actual_fonts_identical':fonts_equal,'old_boundary':audit,'new_boundary':newinfo['outside_page_pixel_audit'],'output_size':newinfo['output_size'],'canonical_changed':False,'quality_accepted':False}
out['exact_pixel_proof']=exact
(folder/'pilot.json').write_text(json.dumps(out,indent=2)+'\n');(W/'native_page_padding_pilot.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out));assert fonts_equal
