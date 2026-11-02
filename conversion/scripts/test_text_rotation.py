import io,json
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_convert_v6 import build
from svg_convert_v2 import build as baseline_build
from svg_batch import metric
from svg_source_coverage_v2 import audit
work=W/'text_rotation_tests';work.mkdir(exist_ok=True);results=[];sheet=Image.new('RGB',(1200,1000),'white');draw=ImageDraw.Draw(sheet)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page(viewport={'width':800,'height':500});page.route('**/*',lambda r:r.abort())
 for i,angle in enumerate([-90,30,-25,180]):
  svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500"><rect width="800" height="500" fill="white"/><g transform="translate(400,250) rotate({angle}) scale(1.2)"><text x="0" y="0" text-anchor="middle" font-family="Arial" font-size="26" fill="black">Editable Rotation {angle} degrees</text></g></svg>'
  page.set_content('<style>html,body{margin:0}</style>'+svg);page.evaluate('document.fonts.ready');page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');source=page.screenshot();old_dom=page.evaluate((W/'scripts/svg_dom.js').read_text());dom=page.evaluate((W/'scripts/svg_dom_v6.js').read_text());assert not dom['issues'],dom['issues'];xml,stats=build(dom,800,500);coverage=audit(dom,xml,stats);assert coverage['ok'];assert len(stats['native_rotated_text'])==1
  rendered=native.native_job(xml,800,500,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert rendered['ok'];oldxml,_=baseline_build(old_dom,800,500);old=native.native_job(oldxml,800,500,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert old['ok'];before=metric(source,old['png']);after=metric(source,rendered['png']);assert after>before+.01,(angle,before,after);assert after>.97,(angle,after)
  folder=work/str(angle);folder.mkdir(exist_ok=True);(folder/'source.svg').write_text(svg);(folder/'source.png').write_bytes(source);(folder/'diagram.drawio').write_text(xml);(folder/'image.png').write_bytes(rendered['png']);results.append({'angle':angle,'before_ssim':before,'after_ssim':after,'source_coverage':coverage,'rotation':stats['native_rotated_text']})
  for j,blob in enumerate([source,rendered['png']]):
   im=ImageOps.contain(Image.open(io.BytesIO(blob)).convert('RGB'),(590,225));sheet.paste(im,(j*600,i*250+25));draw.text((j*600+4,i*250+4),str(angle)+' '+['SVG source','Native drawio'][j],fill='black')
 # Nonuniform/sheared text must retain unresolved warning, never be misclassified as rotation.
 page.set_content('<svg width="800" height="500"><text x="50" y="100" transform="skewX(20)">Sheared text</text></svg>');bad=page.evaluate((W/'scripts/svg_dom_v6.js').read_text());assert any(x['reason']=='text_transform' for x in bad['issues']);b.close()
report={'time':now(),'ok':True,'cases':results,'negative_shear_stays_unresolved':True};(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');sheet.save(work/'comparison.jpg',quality=90);print(json.dumps({'ok':True,'cases':[{'angle':r['angle'],'before':r['before_ssim'],'after':r['after_ssim']} for r in results],'negative_shear_stays_unresolved':True}))
