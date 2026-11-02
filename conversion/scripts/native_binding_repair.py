import argparse,hashlib,io,json,sqlite3,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,normalize,now

def main(limit):
 db=sqlite3.connect(W/'jobs.sqlite',timeout=60);items=[]
 for id,raw,prep in db.execute('select id,output_record,input_manifest from jobs where route="native" and state="rendered"').fetchall():
  out=json.loads(raw)
  if out.get('metrics',{}).get('exact_reference_pixels') and out['bound_edges']!=out['edges']:items.append((id,out,json.loads(prep)))
 if limit:items=items[:limit]
 results=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=browser.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'))
  for id,out,inp in items:
   record={'id':id,'time':now()};directory=W/'native_binding_repair'/id;directory.mkdir(parents=True,exist_ok=True)
   try:
    xml=(R/out['code_file']).read_text();proposal=page.evaluate((W/'scripts/bind_native.js').read_text(),xml);record.update(changes=proposal['changes'],unresolved=proposal['unresolved']);candidate,pages,model=normalize(proposal['xml']);original_model=E.fromstring(xml).find('.//mxGraphModel')
    # mxCodec omits graph/page attributes; retain all original canvas settings.
    model.attrib.update(original_model.attrib);root=E.Element('mxfile',{'host':'app.diagrams.net','type':'device'});page_node=E.SubElement(root,'diagram',{'id':'page-1','name':'Page-1'});page_node.append(model);candidate=E.tostring(root,encoding='unicode');(directory/'candidate.drawio').write_text(candidate)
    if not proposal['changes']:record['state']='no_unambiguous_binding';results.append(record);continue
    render=native.native_job(candidate,inp['width'],inp['height'],90,native.renderer_path(R),8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');record['render_ok']=render['ok']
    if render['ok']:
     png=render.pop('png');(directory/'candidate.png').write_bytes(png);ref=Image.open(R/inp['reference_image']).convert('RGBA');bg=Image.new('RGBA',ref.size,'white');bg.alpha_composite(ref);ref=bg.convert('RGB');pred=Image.open(io.BytesIO(png)).convert('RGB');record['exact_reference_pixels']=ref.size==pred.size and bool(np.array_equal(ref,pred))
     if record['exact_reference_pixels']:
      parents={c:p for p in model.iter() for c in p};cid=lambda c:c.get('id') or parents.get(c,E.Element('none')).get('id');cells=list(model.iter('mxCell'));vertices={cid(c) for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];bound=sum(e.get('source') in vertices and e.get('target') in vertices for e in edges);record['bound_edges']=bound;record['edges']=len(edges)
      # Preserve original before replacing a pending candidate, and never touch accepted jobs.
      assert db.execute('select state from jobs where id=?',(id,)).fetchone()[0]=='rendered'
      (directory/'before.drawio').write_text(xml);(directory/'before_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));out.update(conversion_method='native_xml_normalization_and_unique_boundary_binding',binding_repair=record,code_sha256=hashlib.sha256(candidate.encode()).hexdigest(),image_sha256=hashlib.sha256(png).hexdigest(),bound_edges=bound,render=render['native_render']);(R/out['code_file']).write_text(candidate);(R/out['image_file']).write_bytes(png);(R/out['code_file']).parent.joinpath('conversion.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');db.execute('update jobs set output_record=?,updated_at=? where id=? and state="rendered"',(json.dumps(out,ensure_ascii=False),now(),id));db.commit();record['state']='pixel_exact_binding_improved'
     else:record['state']='rejected_pixel_change'
    else:record['state']='render_failed'
   except Exception as exc:record.update(state='error',error=str(exc)[:2000])
   (directory/'audit.json').write_text(json.dumps(record,indent=2)+'\n');results.append(record);print(json.dumps(record),flush=True)
  browser.close()
 (W/('native_binding_pilot.json' if limit else 'native_binding_summary.json')).write_text(json.dumps({'finished_at_utc':now(),'selected':len(items),'results':results},indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=0);main(p.parse_args().limit)
