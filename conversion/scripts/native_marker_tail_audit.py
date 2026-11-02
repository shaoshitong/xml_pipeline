"""Bound native renderer stroke changes using actual old/new connector paths."""
import re,math
from playwright.sync_api import sync_playwright
from portable_native_fonts import ready_page
SCRIPT=r'''xml=>{document.body.innerHTML='<div id="g"></div>';const g=new Graph(document.getElementById('g')),doc=mxUtils.parseXml(xml);new mxCodec(doc).decode(doc.getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();const out={};for(const c of Object.values(g.model.cells)){if(!c.edge)continue;const st=g.getCellStyle(c),s=g.view.getState(c);out[c.id]=[...s.shape.node.querySelectorAll('path')].filter(p=>p.getAttribute('stroke')===st.strokeColor).map(p=>({d:p.getAttribute('d'),stroke:st.strokeColor,width:parseFloat(getComputedStyle(p).strokeWidth)}));}g.destroy();return out;}'''
def capture(before,after):
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(browser)
  try:return [page.evaluate(SCRIPT,x) for x in (before,after)]
  finally:browser.close()
def polyline(d):
 assert not re.search('[A-KN-Za-kn-z]',d),'Unexpected curve command in native polyline'
 n=list(map(float,re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)',d)));assert len(n)%2==0
 return list(zip(n[::2],n[1::2]))
def audit(before,after,markers):
 a,b=capture(before,after);assert set(a)==set(b);allowed={m['native_edge']:m for m in markers};rows=[]
 for id in a:
  if id not in allowed:assert a[id]==b[id],'Unrelated edge changed';continue
  m=allowed[id];assert m['side']=='end','Start marker tail audit not implemented'
  assert len(a[id])==1 and len(b[id])==2,'Unexpected connector/marker path count'
  old,new=a[id][0],b[id][0];assert old['stroke']==new['stroke'] and old['width']==new['width']
  x,y=polyline(old['d']),polyline(new['d']);i=0
  while i<min(len(x),len(y)) and x[i]==y[i]:i+=1
  assert i>=1,'Source edge prefix changed'
  xs,ys=x[i-1:],y[i-1:];length=lambda pts:sum(math.dist(p,q) for p,q in zip(pts,pts[1:]));limit=max(m['length']*4,old['width']*20)
  assert max(length(xs),length(ys))<=limit,'Connector change extends beyond source marker neighborhood'
  rows.append({'edge':id,'unchanged_prefix_points':i,'unchanged_prefix':x[:i],'stroke_color':old['stroke'],'old_tail':xs,'new_tail':ys,'stroke_width':old['width'],'tail_length_before':length(xs),'tail_length_after':length(ys),'locality_limit':limit})
 return rows
