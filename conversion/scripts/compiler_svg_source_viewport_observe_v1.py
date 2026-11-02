"""Independent recorded-Cairo source surface and full SVG paint inspection.

The PNG provider supplies a finite output surface. Browser embedding defaults are
measured, never presumed to be the standalone SVG root's computed overflow.
No candidate or reference pixels participate in the source-frame calculation.
"""
from pathlib import Path
import hashlib,io,json,math,copy
import numpy as np
from PIL import Image
POLICY='recorded_cairosvg_surface_root_viewport_full_source_inspection_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(x,r):
 if not x:raise ValueError(r)
def pixels(png):return np.asarray(Image.open(io.BytesIO(png)).convert('RGB'))
def _state(page):
 return page.evaluate('''()=>{const root=document.querySelector('svg');const mat=m=>[m.a,m.b,m.c,m.d,m.e,m.f];return [...root.querySelectorAll('path,rect,circle,ellipse,line,polyline,polygon,text,use')].filter(e=>!e.closest('defs,marker,symbol,clipPath,mask,pattern')).map((e,i)=>{const b=e.getBBox(),m=e.getScreenCTM(),c=getComputedStyle(e),r=e.getBoundingClientRect();return {i,tag:e.localName,id:e.id,attrs:[...e.attributes].map(a=>[a.name,a.value]),bbox:[b.x,b.y,b.width,b.height],world:[r.x,r.y,r.width,r.height],ctm:mat(m),css:{fill:c.fill,stroke:c.stroke,strokeWidth:c.strokeWidth,strokeMiterlimit:c.strokeMiterlimit,opacity:c.opacity,fillOpacity:c.fillOpacity,strokeOpacity:c.strokeOpacity,font:c.font,display:c.display,visibility:c.visibility,filter:c.filter,clipPath:c.clipPath},text:e.textContent}})}''')
def _bounds(rows,dom,size):
 boxes=[(0.,0.,float(size[0]),float(size[1]))]
 for r in rows:
  c=r['css'];require(c['filter']=='none','source_effect_requires_another_inspection_policy')
  if c['display']=='none'or c['visibility']=='hidden':continue
  m=r['ctm'];scale=max(math.hypot(m[0],m[1]),math.hypot(m[2],m[3]));stroke=0 if c['stroke']=='none'else float(c['strokeWidth'].removesuffix('px'));pad=4+stroke*scale*max(1.,float(c['strokeMiterlimit']));x,y,w,h=r['world'];boxes.append((x-pad,y-pad,x+w+pad,y+h+pad))
 # Source-scene extractor supplies actual invocation contexts for marker/use
 # descendants. These are source-derived, not a candidate content bbox.
 for o in dom['objects']:
  b=o['bbox'];stroke=float(o.get('style',{}).get('strokeWidth',0)or 0);pad=4+stroke*8;boxes.append((b['x']-pad,b['y']-pad,b['x']+b['w']+pad,b['y']+b['h']+pad))
 x=math.floor(min(b[0]for b in boxes))-32;y=math.floor(min(b[1]for b in boxes))-32;r=math.ceil(max(b[2]for b in boxes))+32;b=math.ceil(max(b[3]for b in boxes))+32
 plan=dict(x=x,y=y,width=r-x,height=b-y,source_width=int(size[0]),source_height=int(size[1]));require(max(plan['width'],plan['height'])<=8192 and plan['width']*plan['height']<=64000000,'source_full_inspection_resource_bound');return plan

def observe(page,context,size,dom,work,screenshot):
 work=Path(work);baseline=screenshot(page);before=_state(page);root=page.locator('svg').first;style=root.get_attribute('style');oldviewport=dict(page.viewport_size)
 rootinfo=root.evaluate('''s=>{const c=getComputedStyle(s),r=s.getBoundingClientRect(),m=s.getScreenCTM();return {attributes:[...s.attributes].map(a=>[a.name,a.value]),computedOverflow:c.overflow,parentTag:s.parentElement.localName,standaloneDocumentRoot:s===document.documentElement,viewport:[r.x,r.y,r.width,r.height],ctm:[m.a,m.b,m.c,m.d,m.e,m.f],preserveAspectRatio:s.getAttribute('preserveAspectRatio'),viewBox:s.getAttribute('viewBox')}}''');require(rootinfo['viewport']==[0,0,*list(size)],'source_normalized_surface_viewport_mismatch');require(not rootinfo['standaloneDocumentRoot']and rootinfo['parentTag']=='body','source_browser_embedding_contract_changed')
 plan=_bounds(before,dom,size);left,top=-plan['x'],-plan['y'];page.set_viewport_size({'width':plan['width'],'height':plan['height']});root.evaluate('(s,p)=>{s.style.position="absolute";s.style.left=p[0]+"px";s.style.top=p[1]+"px"}',[left,top]);clipped=screenshot(page);shifted=_state(page);shiftstyle=root.get_attribute('style');root.evaluate('s=>s.style.setProperty("overflow","visible","important")');full=screenshot(page);unclipped=_state(page);require(unclipped==shifted,'source_overflow_observation_changed_primitive_geometry_font_or_css');root.evaluate('(s,v)=>s.setAttribute("style",v)',shiftstyle);require(screenshot(page)==clipped,'source_root_clip_restore_changed_pixels')
 maximum=0.
 for a,b in zip(before,shifted):
  require(a['attrs']==b['attrs']and a['bbox']==b['bbox']and a['css']==b['css']and a['text']==b['text'],'source_inspection_changed_original_primitive')
  residual=max(abs(y-x-d)for x,y,d in zip(a['ctm'],b['ctm'],[0,0,0,0,left,top]));maximum=max(maximum,residual)
  require(residual<=.0001,'source_inspection_transform_not_exact_integer_translation')
 require(len(before)==len(shifted),'source_inspection_changed_primitive_count');root.evaluate('(s,v)=>{if(v===null)s.removeAttribute("style");else s.setAttribute("style",v)}',style);page.set_viewport_size(oldviewport);require(_state(page)==before and screenshot(page)==baseline,'source_inspection_did_not_restore_original_DOM_and_pixels')
 A,C=pixels(full),pixels(clipped);mask=np.any(A<255,axis=2);outside=np.ones(mask.shape,bool);outside[top:top+size[1],left:left+size[0]]=False;ring=mask.copy();ring[32:-32,32:-32]=False;require(not ring.any(),'source_paint_touches_full_inspection_guard');sourceclipoutside=np.any(C<255,axis=2)&outside
 # The original recorded provider writes exactly this finite PNG surface;
 # standalone-root overflow defaults cannot enlarge an encoded PNG canvas.
 source_full=work/'source_full_inspection.png';source_full.write_bytes(full);(work/'source_root_clipped_inspection.png').write_bytes(clipped)
 crop=C[top:top+size[1],left:left+size[0]];base=pixels(baseline)
 evidence=dict(policy=POLICY,plan=plan,provider_surface='recorded CairoSVG PNGSurface.convert output_width/output_height',browser_embedding=rootinfo,standalone_root_default_overflow_not_inferred=True,primitive_count=len(before),all_primitive_geometry_style_font_retained=True,maximum_integer_CTM_residual=maximum,original_DOM_and_pixels_restored=True,source_unclipped_pixels_outside_viewport=int(np.sum(mask&outside)),source_browser_clip_pixels_outside_viewport=int(sourceclipoutside.sum()),strict_outside_source_inspection_pixels=0,inspection_integer_translation_diagnostic_changed_inside_pixels=int(np.any(crop!=base,axis=2).sum()),source_full_inspection_sha256=sha(full),source_clipped_inspection_sha256=sha(clipped),source_original_browser_png_sha256=sha(baseline),source_primitive_state_sha256=sha(json.dumps(before,sort_keys=True).encode()),no_reference_or_candidate_pixels_used=True)
 (work/'source_viewport_proof.json').write_text(json.dumps(evidence,sort_keys=True,indent=2));return dict(evidence=evidence,png=full,file=source_full)
