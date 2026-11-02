"""Finite probe on two already seen originals; no selection or qualification.

The original PNG pHYs records 100dpi. This probes that declared density against
the previously compiled original PDF using Poppler, without reference-pixel
fitting, code rewrites, runtime mutation or changes to any registered job.
"""
from pathlib import Path
import hashlib,json,os,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
from sandbox_runner import run
from auto_quality_common_v4 import image_quality
from PIL import Image
import numpy as np

sha=lambda b:hashlib.sha256(b).hexdigest()
SEEN={'0002d1280db280c2d9227e7d2188cd20f0cbc446310f112772df3d9b62cca423','0036b5425c60a565c4de754bd9940630f0cacb14f7813e9c83eda930de1d1a7e'}
INPUT=W/'compiler_tikz_free_paths_v1/development/46015474892e4c8c84668e50a86ae648/report.json'

def foreground(path):
 a=np.asarray(Image.open(path).convert('RGB'));ys,xs=np.where(a.min(2)<230)
 return {'canvas':[a.shape[1],a.shape[0]],'box':[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if len(xs) else None,'pixels':int(len(xs))}

def main():
 folder=W/'compiler_tikz_poppler_source_v2/development'/('poppler100_existing_pdf_'+uuid.uuid4().hex);folder.mkdir(parents=True,exist_ok=False)
 report={'schema':'tikz_poppler100_development_probe_v1','unseen_consumed':0,'model_calls':0,'qualification_claimed':False,'pdftoppm_sha256':sha(Path('/usr/bin/pdftoppm').read_bytes()),'records':[]}
 for row in json.loads(INPUT.read_bytes())['results']:
  if row['id'] not in SEEN:continue
  record_path=Path(row['record_file']);record_bytes=record_path.read_bytes();r=json.loads(record_bytes)
  assert r['source_record']['source']=='Y36521478Y--omnidiagram_train_sft'
  pdf=R/r['source_render_pdf'];reference=R/r['original_reference'];source_code=R/r['original_source_code']
  pdf_bytes=pdf.read_bytes();ref_bytes=reference.read_bytes();code_bytes=source_code.read_bytes()
  assert sha(pdf_bytes)==r['source_render_pdf_sha256'] and sha(ref_bytes)==r['source_image_sha256'] and sha(code_bytes)==r['source_code_sha256']
  dpi=Image.open(reference).info.get('dpi');assert dpi and all(abs(float(x)-100)<.001 for x in dpi)
  target=folder/r['id'];target.mkdir();(target/'source.pdf').write_bytes(pdf_bytes)
  argv=['/usr/bin/pdftoppm','-png','-r','100','-singlefile','/work/source.pdf','/work/poppler100']
  proc=run(target,argv,timeout=120);(target/'stdout.log').write_text(proc.stdout);(target/'stderr.log').write_text(proc.stderr)
  assert proc.returncode==0,proc.stderr
  png=target/'poppler100.png';canvas_equal=Image.open(png).size==Image.open(reference).size
  quality=image_quality(ref_bytes,png.read_bytes(),{}) if canvas_equal else {'ok':False,'reason':'exact_density_source_canvas_differs','no_registration_or_resizing':True}
  item={'id':r['id'],'original_code_sha256':r['source_code_sha256'],'original_image_sha256':r['source_image_sha256'],'original_pdf_sha256':sha(pdf_bytes),'original_png_dpi':dpi,'source_renderer':'Poppler pdftoppm default rasterizer at PNG-declared100dpi','argv':argv,'reference':foreground(reference),'poppler100':foreground(png),'previous_svg_chromium':foreground(R/r['source_render_png']),'canvas_equal':canvas_equal,'quality':quality,'poppler_png':str(png),'poppler_png_sha256':sha(png.read_bytes())}
  report['records'].append(item)
  assert record_path.read_bytes()==record_bytes and pdf.read_bytes()==pdf_bytes and reference.read_bytes()==ref_bytes and source_code.read_bytes()==code_bytes
 assert {r['id'] for r in report['records']}==SEEN
 (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'report':str(folder/'report.json'),'results':[{k:x[k] for k in ('id','original_png_dpi','reference','poppler100','previous_svg_chromium','canvas_equal','quality')} for x in report['records']]}),flush=True)

if __name__=='__main__':main()
