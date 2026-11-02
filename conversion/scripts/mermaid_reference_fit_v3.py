from native_label_paint_order import repair as repair_paint_order,pixel_audit
"""Conservative whole-source affine calibration; never an original-fidelity acceptance gate."""
import io,json,hashlib,collections
import numpy as np
from scipy.ndimage import label,find_objects
from scipy.optimize import linear_sum_assignment
from PIL import Image
from native_worker import R,W,native
from mermaid_geometry_batch import BUNDLE,BUNDLE_SHA
from mermaid_semantic_v4 import PARSE,check as semantic
from mermaid_geometry_coverage import check as geometry
from mermaid_native_v2 import build,check_backgrounds,MOVE_SCRIPT as BACKGROUND_MOVE_SCRIPT
from svg_source_coverage_v2 import audit as coverage
from portable_native_fonts import ready_page,capture,embed
from native_move_audit import SCRIPT as MOVE_SCRIPT
from strict_canvas_gate import require_declared_page
from svg_batch import metric

def rgb(data):
 im=Image.open(io.BytesIO(data)).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im);return np.asarray(bg.convert('RGB'))

def components(im,color,min_area=32):
 labs,n=label(np.all(im==np.array(color),axis=2));out=[]
 for k,s in enumerate(find_objects(labs),1):
  y,x=s;area=int((labs[s]==k).sum())
  if area<min_area or x.stop-x.start<4 or y.stop-y.start<4:continue
  out.append({'x0':x.start,'y0':y.start,'x1':x.stop,'y1':y.stop,'area':area})
 return out

def fit(source,reference,nodes):
 assert source.shape==reference.shape and source.ndim==3
 h,w=source.shape[:2];assert 3<=len(nodes)<=80,'At least three independently visible source nodes required'
 groups=collections.defaultdict(list)
 for n in nodes:
  c=tuple(n['color']);assert len(c)==3 and c not in [(255,255,255),(0,0,0)],'Ambiguous background/ink fill'
  groups[c].append(n)
 pairs=[]
 for color,group in groups.items():
  min_area=max(32,min((n['x1']-n['x0'])*(n['y1']-n['y0']) for n in group)*.05)
  a=components(source,color,min_area);b=components(reference,color,min_area)
  assert len(a)==len(b)==len(group),f'Missing, extra or fragmented color components: {color} {len(a)}/{len(b)}/{len(group)}'
  # Each source component must belong to exactly one DOM node, with nearly identical bounds.
  assigned=set()
  for box in a:
   matches=[]
   for n in group:
    if max(abs(box[k]-n[k]) for k in ['x0','x1','y0','y1'])<=4:matches.append(n['id'])
   assert len(matches)==1 and matches[0] not in assigned,'Ambiguous source fill-to-node mapping'
   assigned.add(matches[0]);box['node']=matches[0]
  centers=lambda boxes:np.array([[(x['x0']+x['x1'])/2/w,(x['y0']+x['y1'])/2/h] for x in boxes])
  ac,bc=centers(a),centers(b);dist=np.linalg.norm(ac[:,None,:]-bc[None,:,:],axis=2);ai,bi=linear_sum_assignment(dist)
  for i,j in zip(ai,bi):
   assert dist[i,j]<.12,'Reference geometry too far from source'
   alternatives=np.delete(dist[i],j)
   if len(alternatives):assert float(alternatives.min())>float(dist[i,j])+2/max(w,h),'Ambiguous reference component assignment'
   pairs.append({'color':list(color),'source':a[i],'reference':b[j]})
 fits={}
 for axis,size in [('x',w),('y',h)]:
  x=np.array([p['source'][axis+str(k)] for p in pairs for k in [0,1]],float);y=np.array([p['reference'][axis+str(k)] for p in pairs for k in [0,1]],float)
  assert np.ptp(x)>=size*.15,'Insufficient anchor extent'
  coeff=np.linalg.lstsq(np.column_stack([x,np.ones_like(x)]),y,rcond=None)[0];res=y-(coeff[0]*x+coeff[1])
  assert .85<=coeff[0]<=1.15 and abs(coeff[1])<=size*.05,'Large transform requires separate review'
  assert float(np.max(abs(res)))<=1.25,'Non-affine node layout difference'
  fits[axis]={'scale':float(coeff[0]),'offset':float(coeff[1]),'max_abs_residual':float(np.max(abs(res))),'residuals':res.tolist()}
 return {'pairs':pairs,'fits':fits,'node_count':len(nodes),'scope':'Only whole-source geometry calibration; text, topology and native fidelity are separate gates.'}

NODE_SCRIPT=r'''()=>[...document.querySelectorAll('g.node')].map(g=>{const shapes=[...g.children].filter(e=>['rect','polygon','ellipse','circle','path'].includes(e.localName));if(shapes.length!==1)throw Error('Unsupported multi-shape node');const s=shapes[0],c=getComputedStyle(s),m=c.fill.match(/^rgb\((\d+), (\d+), (\d+)\)$/);if(!m||+c.opacity!==1||+c.fillOpacity!==1)throw Error('Nonopaque flat fill');const b=s.getBoundingClientRect();return {id:g.getAttribute('data-id'),color:m.slice(1).map(Number),x0:b.x,y0:b.y,x1:b.right,y1:b.bottom};})'''
STYLE_SCRIPT="p=>{const s=document.querySelector('svg');s.style.maxWidth='none';s.style.width=p[0]+'px';s.style.height=p[1]+'px';s.style.position='absolute';s.style.left=p[2]+'px';s.style.top=p[3]+'px';s.setAttribute('preserveAspectRatio','none')}"

def convert_variant(browser,r,directory,font=None,allow_background_experiment=False):
 directory.mkdir(parents=True,exist_ok=True);ref=(R/r['original_reference']).read_bytes();code=(R/r['original_source_code']).read_bytes()
 assert hashlib.sha256(code).hexdigest()==r['source_code_sha256'] and hashlib.sha256(ref).hexdigest()==r['source_image_sha256']
 assert hashlib.sha256(BUNDLE.read_bytes()).hexdigest()==BUNDLE_SHA
 target=rgb(ref);h,w=target.shape[:2];assert max(w,h)<=4096 and w*h<=10000000,'Resource bound'
 ctx=browser.new_context(viewport={'width':w,'height':h},service_workers='block');page=ctx.new_page();page.set_default_timeout(45000);blocked=[];page.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()))
 try:
  page.set_content('<html></html>');page.add_script_tag(path=str(BUNDLE))
  svg=page.evaluate("async a=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,themeVariables:a.font?{fontFamily:a.font}:{},flowchart:{htmlLabels:true}});return (await mermaid.render('diagram',a.code)).svg}",{'font':font,'code':code.decode()});ast=page.evaluate(PARSE,code.decode());assert not ast.get('groups'),'Subgraph calibration not covered'
  page.set_content('<style>html,body{margin:0;background:white;overflow:hidden}</style>'+svg);page.evaluate(STYLE_SCRIPT,[w,h,0,0]);page.evaluate('document.fonts.ready');source=page.screenshot();nodes=page.evaluate(NODE_SCRIPT);anchor=fit(rgb(source),target,nodes)
  initial=[w*anchor['fits']['x']['scale'],h*anchor['fits']['y']['scale'],anchor['fits']['x']['offset'],anchor['fits']['y']['offset']];scores=[]
  def render(params):
   page.evaluate(STYLE_SCRIPT,params);page.evaluate('document.fonts.ready');png=page.screenshot();error=float(np.mean((target.astype(float)-rgb(png).astype(float))**2));scores.append({'parameters':list(params),'mse':error});return error,png,list(params)
  best=render([w,h,0,0]);baseline_mse=best[0]
  integer_grid=[[round(initial[0])+dx,round(initial[1])+dy,round(initial[2]),round(initial[3])] for dx in [-1,0,1] for dy in [-1,0,1]]
  for params in [initial,[round(initial[0]),round(initial[1]),0.,0.]]+integer_grid:
   candidate=render(params)
   if candidate[0]<best[0]:best=candidate
  for step in [1.,.25]:
   for axis in range(4):
    current=list(best[2])
    for delta in [-step,step]:
     q=current.copy();q[axis]+=delta
     if abs(q[axis]-initial[axis])>2:continue
     candidate=render(q)
     if candidate[0]<best[0]:best=candidate
  best=render(best[2]);fitted_svg=page.locator('svg').evaluate('s=>s.outerHTML');md=page.evaluate((W/'scripts/mermaid_dom_adapter_v2.js').read_text(),ast);adapted=page.screenshot();(directory/'pre_adapter.png').write_bytes(best[1]);(directory/'post_adapter.png').write_bytes(adapted);assert np.array_equal(rgb(adapted),rgb(best[1])),'Source adapter changed original source pixels';dom=page.evaluate((W/'scripts/svg_dom_mermaid_v3.js').read_text());assert np.array_equal(rgb(page.screenshot()),rgb(best[1])),'Source object extraction changed source pixels';assert not dom['issues'],dom['issues'];xml,stats,processed=build(dom,w,h,md);cov=coverage(processed,xml,stats);geo=geometry(ast,xml,md);sem=semantic(ast,xml);assert cov['ok'] and geo['ok'] and sem['status']=='node_edge_text_match';assert not blocked
  for name,obj in [('source_ast',ast),('source_dom',dom),('source_geometry',md),('source_stats',stats),('anchor_fit',anchor),('optimization',scores)]:(directory/(name+'.json')).write_text(json.dumps(obj,indent=2))
  (directory/'source_fit.svg').write_text(fitted_svg);(directory/'source_fit.png').write_bytes(best[1]);(directory/'unembedded.drawio').write_text(xml)
 finally:ctx.close()
 xml,paint_order=repair_paint_order(browser,xml,stats['native_html_label_backgrounds'])
 (directory/'paint_order.json').write_text(json.dumps(paint_order,indent=2))
 pagefont=ready_page(browser)
 try:observations=capture(pagefont,xml);new,fonts,fontproof=embed(xml,observations,directory/'fonts');assert not fontproof['issues'],fontproof
 finally:pagefont.close()
 before=native.native_job(xml,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');after=native.native_job(new,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');
 for label_name,result in [('unembedded_render',before),('embedded_render',after)]:
  (directory/(label_name+'.json')).write_text(json.dumps({k:v for k,v in result.items() if k!='png'},indent=2))
  if result.get('png'):(directory/(label_name+'.png')).write_bytes(result['png'])
 assert before['ok'] and after['ok'],'Actual native render failed; see unembedded/embedded_render.json'
 assert before['png']==after['png'],'Font embedding changed native pixels'
 require_declared_page(after['native_render'],w,h)
 usage=after['native_render']['actual_platform_font_usage'];assert len(usage)==len(fontproof['changes'])
 for row in usage:
  assert row['fonts'] and all(f['isCustomFont'] for f in row['fonts'] if f['glyphCount'])
 movepage=ready_page(browser)
 try:moves=movepage.evaluate(MOVE_SCRIPT,new)
 finally:movepage.close()
 assert len(moves['moves'])==2*geo['source_edges']
 for m in moves['moves']:
  assert abs(m['delta']['x']-17)<1e-5 and abs(m['delta']['y']-11)<1e-5
  for c in m['child_deltas']:assert abs(c['x']-17)<1e-5 and abs(c['y']-11)<1e-5
 bgproof=check_backgrounds(new,stats['native_html_label_backgrounds']);bgpage=ready_page(browser)
 try:bgmoves=bgpage.evaluate(BACKGROUND_MOVE_SCRIPT,{'xml':new,'bindings':stats['native_html_label_backgrounds']})
 finally:bgpage.close()
 for m in bgmoves:
  assert all(abs(m['background_delta'][a]-m['label_delta'][a])<1e-5 for a in ['x','y'])
 paint_pixels=pixel_audit(new,paint_order['boxes'],w,h);assert paint_pixels['ok'],paint_pixels
 bgproof['paint_order']=paint_order;bgproof['pixel_audit']=paint_pixels
 bgproof['actual_matched_background_label_moves']=len(bgmoves);(directory/'background_moves.json').write_text(json.dumps(bgmoves,indent=2))
 for name,obj in [('font_proof',fontproof),('fonts',fonts),('native_render',after['native_render']),('moves',moves)]:(directory/(name+'.json')).write_text(json.dumps(obj,indent=2))
 (directory/'candidate.drawio').write_text(new);(directory/'candidate.png').write_bytes(after['png'])
 report={'source_adapter_pixels_unchanged':True,'source_adapter_version':'data_attributes_v2','native_html_backgrounds':bgproof,'source_renderer_version':'10.9.1','bundle_sha256':BUNDLE_SHA,'font_override':font,'parameters':best[2],'anchor_fit':anchor,'mse_before':baseline_mse,'mse_after':best[0],'optimization':scores,'source_reference_ssim':metric(ref,best[1]),'native_reference_ssim':metric(ref,after['png']),'source_native_ssim':metric(best[1],after['png']),'prior_ssim':r.get('metrics',{}).get('original_reference_ssim_512'),'font_pixels_unchanged':True,'physical_fonts':[f['physical_postscript_name'] for f in fonts.values()],'semantic':sem,'source_object_coverage':cov,'geometry':geo,'actual_endpoint_moves':len(moves['moves']),'source_dom_issues':dom['issues'],'accepted':False,'requires_independent_visual_review':True}
 (directory/'report.json').write_text(json.dumps(report,indent=2));return report
