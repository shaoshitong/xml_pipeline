import json,xml.etree.ElementTree as E
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
script=r'''xml=>{document.body.innerHTML='<div id="g" style="width:8192px;height:8192px;position:relative"></div>';const g=new Graph(document.getElementById('g'));new mxCodec(mxUtils.parseXml(xml)).decode(mxUtils.parseXml(xml).getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();let results=[];for(const e of Object.values(g.model.cells).filter(c=>c.edge)){for(const source of [true,false]){const t=g.model.getTerminal(e,source);if(!t)throw Error('unbound edge');const state=g.view.getState(e),idx=source?0:state.absolutePoints.length-1,before=state.absolutePoints[idx].clone(),old=t.geometry.clone(),moved=old.clone();moved.x+=17;moved.y+=11;g.model.beginUpdate();g.model.setGeometry(t,moved);g.model.endUpdate();g.view.validate();const after=g.view.getState(e).absolutePoints[idx];results.push({edge:e.id,terminal:t.id,source,dx:after.x-before.x,dy:after.y-before.y});g.model.beginUpdate();g.model.setGeometry(t,old);g.model.endUpdate();g.view.validate();}}g.destroy();return results;}'''
base=W/'plantuml_source_probe';results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'))
 for r in json.loads((W/'text_fidelity_selection.json').read_text()):
  if r['format']!='plantuml':continue
  variant='dejavu_fonts' if r['id'].startswith('741d') else 'natural_dejavu';xml=(base/r['id']/(variant+'.drawio')).read_text();moves=page.evaluate(script,xml);ok=all(abs(m['dx']-17)<.05 and abs(m['dy']-11)<.05 for m in moves);item={'id':r['id'],'variant':variant,'ok':ok,'moves':moves};results.append(item);print(json.dumps({'id':r['id'],'moves':len(moves),'ok':ok,'failures':[m for m in moves if abs(m['dx']-17)>=.05 or abs(m['dy']-11)>=.05]}),flush=True)
 b.close()
(base/'editability_audit.json').write_text(json.dumps({'at':now(),'results':results},indent=2));assert all(x['ok'] for x in results)
