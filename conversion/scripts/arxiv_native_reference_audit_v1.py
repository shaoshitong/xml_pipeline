"""Independent, program-only author-XML vs original-PDF fidelity audit.

Registration uses uniquely identified source image pixels or unique opaque
vector fill colors and their actual geometry. It never optimizes image scores.
Unproved registrations remain pending; no existing qualification is overwritten.
"""
from pathlib import Path
import base64,collections,hashlib,io,json,math,os,re,sqlite3,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1'
sys.path[:0]=[str(R/'conversion/scripts'),str(R/'env'),str(R/'evaluation/assets/pdf_inventory_python_v1')]
import fitz,numpy as np
from PIL import Image
from arxiv_bulk_official_xml_png_v1 import OfficialXmlPng
from auto_quality_common import image_quality

sha=lambda b:hashlib.sha256(b).hexdigest()
def rgba_key(im):
 a=im.convert('RGBA');return str(a.size)+':'+sha(a.tobytes())
def png_bytes(im):
 out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()
def write_json(path,data):
 tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=True,indent=2)+'\n');os.replace(tmp,path)

OBSERVE=r'''()=>{
 const root=document.querySelector('svg'),shapes=[],images=[],texts=[];
 function box(el){const b=el.getBBox(),m=el.getScreenCTM();const p=[[b.x,b.y],[b.x+b.width,b.y],[b.x+b.width,b.y+b.height],[b.x,b.y+b.height]].map(([x,y])=>({x:m.a*x+m.c*y+m.e,y:m.b*x+m.d*y+m.f}));return [Math.min(...p.map(x=>x.x)),Math.min(...p.map(x=>x.y)),Math.max(...p.map(x=>x.x)),Math.max(...p.map(x=>x.y))];}
 function opacity(el){let a=1;for(let q=el;q&&q!==root.parentElement;q=q.parentElement)a*=Number(getComputedStyle(q).opacity);return a;}
 for(const el of root.querySelectorAll('path,rect,circle,ellipse,polygon,polyline')){
  if(el.closest('defs,clipPath,mask')||opacity(el)!==1)continue;
  const st=getComputedStyle(el),rgb=st.fill.match(/^rgba?\(([^)]+)\)$/);
  if(!rgb||Number(st.fillOpacity)!==1)continue;
  const v=rgb[1].split(',').map(Number);if(v.length===4&&v[3]!==1)continue;
  const color=v.slice(0,3).map(Math.round);if(color.every(x=>x>=250)||color.every(x=>x<=5))continue;
  const b=box(el);if(b[2]-b[0]<5||b[3]-b[1]<5)continue;
  shapes.push({color,box:b,tag:el.tagName});
 }
 for(const el of root.querySelectorAll('image')){
  images.push({href:el.getAttribute('href')||el.getAttribute('xlink:href')||'',
    x:el.x.baseVal.value,y:el.y.baseVal.value,w:el.width.baseVal.value,h:el.height.baseVal.value,
    matrix:[el.getScreenCTM().a,el.getScreenCTM().b,el.getScreenCTM().c,el.getScreenCTM().d,el.getScreenCTM().e,el.getScreenCTM().f],
    aspect:el.getAttribute('preserveAspectRatio')||'xMidYMid meet'});
 }
 const walk=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),seg=new Intl.Segmenter(undefined,{granularity:'grapheme'});let t;
 while(t=walk.nextNode()){
  if(!t.parentElement||t.parentElement.closest('style,script,defs,title,desc')||!t.textContent.trim())continue;
  const chars=[];
  for(const g of seg.segment(t.textContent)){
   if(!g.segment.trim())continue;
   const r=document.createRange();r.setStart(t,g.index);r.setEnd(t,g.index+g.segment.length);
   for(const b of r.getClientRects())if(b.width>0&&b.height>0)chars.push({text:g.segment,x:b.x,y:b.y,width:b.width,height:b.height});
  }
  if(chars.length)texts.push({cell:'native-svg-text-'+texts.length,runs:[{chars}]});
 }
 return {shapes,images,text_positions:texts};
}'''

def native_image_anchors(observation):
 values=collections.defaultdict(list)
 for image in observation['images']:
  href=image['href']
  if not href.startswith('data:image/') or 'svg' in href.split(',',1)[0]:continue
  try:
   header,data=href.split(',',1);raw=base64.b64decode(data) if ';base64' in header else __import__('urllib.parse',fromlist=['unquote_to_bytes']).unquote_to_bytes(data)
   with Image.open(io.BytesIO(raw)) as im:key=rgba_key(im);iw,ih=im.size
   x,y,w,h=[image[k] for k in ['x','y','w','h']]
   if image['aspect']!='none':
    # Fixed SVG preserveAspectRatio mapping, independent of PDF/raster scores.
    meet='slice' not in image['aspect'];s=min(w/iw,h/ih) if meet else max(w/iw,h/ih)
    aw,ah=iw*s,ih*s;align=image['aspect']
    x+=0 if 'xMin' in align else w-aw if 'xMax' in align else (w-aw)/2
    y+=0 if 'YMin' in align else h-ah if 'YMax' in align else (h-ah)/2
    w,h=aw,ah
   a,b,c,d,e,f=image['matrix'];pts=[(a*u+c*v+e,b*u+d*v+f) for u,v in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]]
   values[key].append([min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)])
  except Exception:continue
 return values

def source_anchors(doc,page,obs):
 anchors=[];ns=collections.defaultdict(list);ps=collections.defaultdict(list)
 for row in obs['shapes']:ns[tuple(row['color'])].append(row['box'])
 for row in page.get_drawings():
  if not row.get('fill') or abs(row.get('fill_opacity',1)-1)>1e-6:continue
  color=tuple(round(float(x)*255) for x in row['fill']);b=list(row['rect'])
  if len(color)!=3 or all(x>=250 for x in color) or all(x<=5 for x in color) or b[2]-b[0]<3 or b[3]-b[1]<3:continue
  ps[color].append(b)
 for key in sorted(set(ns)&set(ps)):
  if len(ns[key])==len(ps[key])==1:anchors.append({'kind':'unique_opaque_vector_fill','identity':list(key),'native':ns[key][0],'PDF':ps[key][0]})
 ni=native_image_anchors(obs);pi=collections.defaultdict(list)
 for item in page.get_images(full=True):
  try:
   pix=fitz.Pixmap(doc,item[0])
   if item[1]:pix=fitz.Pixmap(pix,fitz.Pixmap(doc,item[1]))
   if pix.n not in [3,4]:pix=fitz.Pixmap(fitz.csRGB,pix)
   # PNG serialization unpremultiplies alpha, unlike treating Pixmap.samples as straight RGBA.
   with Image.open(io.BytesIO(pix.tobytes('png'))) as im:key=rgba_key(im)
   pi[key].extend(list(r) for r in page.get_image_rects(item[0]))
  except Exception:continue
 for key in sorted(set(ni)&set(pi)):
  if len(ni[key])==len(pi[key])==1:anchors.insert(0,{'kind':'exact_original_image_pixels','identity':key,'native':ni[key][0],'PDF':pi[key][0]})
 return anchors

def registration(anchors):
 if len(anchors)<2:raise ValueError('fewer_than_two_independent_unique_source_geometry_anchors')
 first=anchors[0];n,p=first['native'],first['PDF'];sx=(p[2]-p[0])/(n[2]-n[0]);sy=(p[3]-p[1])/(n[3]-n[1]);scale=(sx+sy)/2
 if not .01<scale<100 or abs(sx-sy)>scale*.002:raise ValueError('primary_source_anchor_not_uniform_scale')
 tx=(p[0]+p[2])/2-scale*(n[0]+n[2])/2;ty=(p[1]+p[3])/2-scale*(n[1]+n[3])/2
 errors=[]
 for anchor in anchors:
  a=anchor['native'];expected=[scale*a[0]+tx,scale*a[1]+ty,scale*a[2]+tx,scale*a[3]+ty]
  err=max(abs(x-y) for x,y in zip(expected,anchor['PDF']));errors.append(err)
 if max(errors)>.4:raise ValueError('independent_source_geometry_anchor_disagreement:'+str(max(errors)))
 return {'PDF_points_per_native_pixel':scale,'PDF_translation':[tx,ty],'primary_anchor':first,
         'independent_holdout_anchors':anchors[1:],'maximum_anchor_error_PDF_points':max(errors),
         'registration_pixels_optimized':False,'registration_rule':'First identity-ordered unique asset/color geometry; all other anchors validate it, no image-score search.'}

class Auditor:
 def __init__(self):self.renderer=None
 def close(self):
  if self.renderer:self.renderer.close()
 def audit(self,record,folder):
  folder.mkdir(parents=True,exist_ok=True);start=time.perf_counter();xml_file=R/record['author_xml_file'];png_file=R/record['image_file'];source=(R/record['render_edit_evidence']).parent/'source.pdf'
  assert sha(xml_file.read_bytes())==record['author_xml_sha256'];assert sha(png_file.read_bytes())==record['image_sha256'];assert sha(source.read_bytes())==record['id']
  out={'id':record['id'],'paper':record['paper'],'status':'pending','source_PDF':str(source.relative_to(R)),
    'source_PDF_sha256':record['id'],'source_author_XML':record['author_xml_file'],'source_author_XML_sha256':record['author_xml_sha256'],
    'native_PNG':record['image_file'],'native_PNG_sha256':record['image_sha256'],'normal_generation_calls':0,'external_models':0}
  try:
   xml=xml_file.read_text()
   # Standalone author data is required. Relative resources need a separate packaging proof.
   refs=re.findall(r'(?:^|;)image=([^;]+(?:;base64,[^;]+)?)',xml)
   if any(not x.startswith(('data:','#')) for x in refs):raise ValueError('relative_or_external_asset_requires_standalone_packaging_proof')
   if self.renderer is None:self.renderer=OfficialXmlPng()
   tick=time.perf_counter();fresh=self.renderer.render(xml,folder/'fresh_official',{});out['fresh_official_render_and_native_edit_seconds']=time.perf_counter()-tick
   with Image.open(folder/'fresh_official/official.png') as a,Image.open(png_file) as b:
    if a.size!=b.size or a.convert('RGBA').tobytes()!=b.convert('RGBA').tobytes():raise ValueError('stored_native_PNG_not_pixel_exact_to_fresh_author_XML_render')
    native=b.convert('RGB');width,height=b.size
   out['native_PNG_pixel_exact_to_independent_author_XML_render']=True
   obs=self.renderer.render_page.evaluate(OBSERVE)
   with fitz.open(source) as doc:
    page=doc[0]
    if len(doc)!=1 or page.rotation:raise ValueError('unsupported_PDF_page_rotation_or_multipage')
    anchors=source_anchors(doc,page,obs);out['source_geometry_anchor_inventory']=anchors
    reg=registration(anchors);out['registration']=reg;s=reg['PDF_points_per_native_pixel'];tx,ty=reg['PDF_translation']
    matrix=fitz.Matrix(1/s,0,0,1/s,-tx/s,-ty/s);pix=page.get_pixmap(matrix=matrix,alpha=False)
    reference=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
   x0=min(0,pix.x);y0=min(0,pix.y);x1=max(width,pix.x+pix.width);y1=max(height,pix.y+pix.height)
   if max(x1-x0,y1-y0)>8192:raise ValueError('registered_union_canvas_above8192')
   canvas=(x1-x0,y1-y0);a=Image.new('RGB',canvas,'white');b=Image.new('RGB',canvas,'white')
   a.paste(reference,(pix.x-x0,pix.y-y0));b.paste(native,(-x0,-y0))
   positions=obs['text_positions']
   for row in positions:
    for run in row['runs']:
     for char in run['chars']:char['x']-=x0;char['y']-=y0
   pa,pb=png_bytes(a),png_bytes(b);(folder/'registered_original_PDF.png').write_bytes(pa);(folder/'registered_native.png').write_bytes(pb)
   tick=time.perf_counter();quality=image_quality(pa,pb,{},positions);out['strong_original_reference_raster_gate']=quality;out['raster_gate_seconds']=time.perf_counter()-tick
   out['registered_union_canvas']=list(canvas);out['native_text_objects_checked']=len(positions)
   out['status']='qualified_registered_original_PDF_visual_profile_v1' if quality['ok'] else 'pending_original_PDF_visual_difference'
   out['strict_provider_reference_full8_profile']=False
   out['quality_scope']='Fresh exact author-XML native rendering/edit proof, independent identity/geometry registration, unchanged global/foreground/local-text raster gates. Not a claim of the legacy full8 font/source compiler profile.'
  except Exception as e:out.update(status='pending_original_PDF_registration_or_render',reason=type(e).__name__+':'+str(e)[:1200])
  out['seconds']=time.perf_counter()-start
  assert sha(xml_file.read_bytes())==record['author_xml_sha256'] and sha(png_file.read_bytes())==record['image_sha256']
  write_json(folder/'audit.json',out);return out

def snapshot():
 rows={}
 for name in ['new_bulk_200_v1','recent_ai_source_expansion_v2']:
  with sqlite3.connect((P/name/'once.sqlite').as_uri()+'?mode=ro',uri=True) as db:
   for (raw,) in db.execute('select record from pdfs where status=?',('qualified_native_xml_png_pair',)):
    row=json.loads(raw);rows[row['id']]=row
 return rows

if __name__=='__main__':
 D=P/'original_PDF_reference_audit_v1';D.mkdir(exist_ok=True);auditor=Auditor();rows=snapshot();results=[]
 try:
  for ident,row in sorted(rows.items()):
   folder=D/'development'/ident
   if (folder/'audit.json').exists():result=json.loads((folder/'audit.json').read_text())
   else:result=auditor.audit(row,folder)
   results.append(result);print(json.dumps({'id':ident,'status':result['status'],'reason':result.get('reason'),'seconds':result['seconds'],'anchors':len(result.get('source_geometry_anchor_inventory',[]))},ensure_ascii=True),flush=True)
 finally:auditor.close()
 summary={'cases':len(results),'states':dict(collections.Counter(x['status'] for x in results)),'external_models':0,'normal_generations':0}
 write_json(D/'development_summary.json',summary);print(json.dumps(summary))
