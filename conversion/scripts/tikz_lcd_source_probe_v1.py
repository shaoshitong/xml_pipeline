"""One causal source-only LCD toggle, two seen exact-PDF cases, no fitting."""
from pathlib import Path
import hashlib,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'));sys.path.append(str(W/'runtime/python_packages'))
from PIL import Image
from playwright.sync_api import sync_playwright
import pymupdf
from compiler_language_capture_v1 import screenshot
from tikz_pdftex_execution_v1 import actual_pdf_text_positions
from auto_quality_common_v4 import image_quality
from compiler_tikz_poppler_source_v2 import CHROME
sha=lambda b:hashlib.sha256(b).hexdigest()
INPUT=W/'compiler_tikz_poppler_source_v2/development/dba35c614e45486fb77624239642ebf5/report.json'

def main():
 target=W/'compiler_tikz_poppler_source_v2/development'/('source_LCD_causal_'+uuid.uuid4().hex);target.mkdir(parents=True,exist_ok=False);records=[]
 for item in json.loads(INPUT.read_bytes())['records']:
  r=json.loads(Path(item['record_file']).read_bytes());source=R/r['source_render_svg'];pdf=R/r['source_render_pdf'];actual=R/r['source_render_png'];width,height=Image.open(actual).size;results=[]
  with pymupdf.open(pdf) as doc:text=actual_pdf_text_positions(doc[0],100/72)
  for flags in ([],['--disable-lcd-text']):
   with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu',*flags]);context=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:route.abort());page=context.new_page()
    try:
     page.set_content('<style>html,body{margin:0;padding:0;background:white;overflow:hidden}</style>'+source.read_text());page.evaluate('document.fonts.ready');png=screenshot(page)
     geometry=page.evaluate('''()=>[...document.querySelectorAll('svg text')].map(e=>{const n=e.firstChild;const rows=[];for(let i=0;i<n.textContent.length;i++){const r=document.createRange();r.setStart(n,i);r.setEnd(n,i+1);const b=r.getBoundingClientRect();rows.push([n.textContent[i],b.x,b.y,b.width,b.height]);}return rows;})''')
     result={'flags':flags,'quality_against_actual_PDF':image_quality(actual.read_bytes(),png,{},text),'source_svg_sha256':sha(source.read_bytes()),'actual_source_PDF_sha256':sha(pdf.read_bytes()),'glyph_position_sha256':sha(json.dumps(geometry,sort_keys=True).encode())}
     out=target/(item['id']+('_grayscale' if flags else '_default')+'.png');out.write_bytes(png);result['png']=str(out);results.append(result)
    finally:context.close();browser.close()
  row={'id':item['id'],'source_objects_unchanged':results[0]['source_svg_sha256']==results[1]['source_svg_sha256'],'actual_grapheme_positions_unchanged':results[0]['glyph_position_sha256']==results[1]['glyph_position_sha256'],'results':results};records.append(row)
  print(json.dumps({'id':row['id'],'actual_grapheme_positions_unchanged':row['actual_grapheme_positions_unchanged'],'qualities':[{k:x['quality_against_actual_PDF'][k] for k in ('ok','failures','ssim_1024','foreground_tile_p10_ssim')} for x in results]}),flush=True)
 report={'records':records,'source_only':True,'reference_images_used':False,'parameter_search':False,'unseen_consumed':0,'model_calls':0}
 (target/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'report':str(target/'report.json')}),flush=True)

if __name__=='__main__':main()
