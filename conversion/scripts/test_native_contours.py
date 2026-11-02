import json,xml.etree.ElementTree as E,math
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now

def fixture(shape,point,rotation=0,duplicate=False):
 r=E.Element('mxGraphModel');root=E.SubElement(r,'root');E.SubElement(root,'mxCell',id='0');E.SubElement(root,'mxCell',id='1',parent='0')
 for id in ['n','n2'] if duplicate else ['n']:
  c=E.SubElement(root,'mxCell',id=id,vertex='1',parent='1',style=f'shape={shape};rotation={rotation};strokeColor=#000000;fillColor=#ffffff;');E.SubElement(c,'mxGeometry',x='100',y='100',width='100',height='80',**{'as':'geometry'})
 c=E.SubElement(root,'mxCell',id='e',edge='1',parent='1',style='edgeStyle=none;endArrow=none;');g=E.SubElement(c,'mxGeometry',relative='1',**{'as':'geometry'});E.SubElement(g,'mxPoint',x=str(point[0]),y=str(point[1]),**{'as':'sourcePoint'});E.SubElement(g,'mxPoint',x='400',y='400',**{'as':'targetPoint'});return E.tostring(r,encoding='unicode')
cases=[('ellipse','ellipse',(200,140),0,False,True),('diamond','rhombus',(150,100),0,False,True),('rotated_ellipse','ellipse',(150+50/math.sqrt(2),140+50/math.sqrt(2)),45,False,True),('diamond_bbox_corner_negative','rhombus',(100,100),0,False,False),('ambiguous_negative','ellipse',(200,140),0,True,False),('far_negative','ellipse',(205,140),0,False,False)]
results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);pg=b.new_page();pg.route('**/*',lambda r:r.abort());pg.set_content('<html></html>');pg.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');pg.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'));js=(W/'scripts/bind_native_contours_v2.js').read_text()
 for name,shape,pt,rot,dup,expected in cases:
  out=pg.evaluate(js,fixture(shape,pt,rot,dup));ok=bool(out['changes'])==expected and all(abs(m['dx']-17)<.05 and abs(m['dy']-11)<.05 for m in out['moves']);results.append({'name':name,'ok':ok,'changes':out['changes'],'moves':out['moves']})
 b.close()
(W/'native_contours_fixture.json').write_text(json.dumps({'at':now(),'results':results},indent=2));print(json.dumps(results,indent=2));assert all(x['ok'] for x in results)
