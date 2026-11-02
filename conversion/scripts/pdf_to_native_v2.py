"""PDF vector geometry + Unicode text with embedded reconstructed fonts, not a raster wrapper."""
import html,json,math,re,urllib.parse,xml.etree.ElementTree as E
from pdf_fonts import build_fonts
from svg_convert_v2 import build
N='http://www.w3.org/2000/svg'
def rgb(c):
 if c is None:return 'none'
 if len(c)==1:c=c*3
 if len(c)!=3:raise ValueError('unsupported PDF color space')
 return '#'+''.join(f'{max(0,min(255,round(x*255))):02x}' for x in c)
def pathdata(d):
 parts=[];last=None
 for item in d['items']:
  kind=item[0]
  if kind in ['l','c']:
   start=tuple(item[1])
   if last!=start:parts.append(f'M{start[0]},{start[1]}')
   if kind=='l':end=tuple(item[2]);parts.append(f'L{end[0]},{end[1]}')
   else:
    end=tuple(item[4]);parts.append('C'+' '.join(f'{p.x},{p.y}' for p in item[2:]))
   last=end
  elif kind=='re':
   r=item[1];points=[(r.x0,r.y0),(r.x1,r.y0),(r.x1,r.y1),(r.x0,r.y1)]
   if item[2]<0:points=points[::-1]
   parts.append('M'+' L'.join(f'{x},{y}' for x,y in points)+' Z');last=None
  elif kind=='qu':
   q=item[1];parts.append('M'+' L'.join(f'{p.x},{p.y}' for p in [q.ul,q.ur,q.lr,q.ll])+' Z');last=None
  else:raise ValueError('unsupported PDF drawing item '+kind)
 if d.get('closePath') and last is not None:parts.append('Z')
 return ' '.join(parts)

def source_svg(doc,page,directory):
 fonts,traces=build_fonts(doc,page,directory/'fonts');issues=[];root=E.Element('svg',{'xmlns':N,'width':str(page.rect.width),'height':str(page.rect.height),'viewBox':f'0 0 {page.rect.width} {page.rect.height}'});style=E.SubElement(root,'style');style.text='\n'.join('@font-face{font-family:"'+f['family']+'";src:url("'+f['uri']+'");}' for f in fonts.values());items=[];drawings=page.get_drawings(extended=True)
 for n,d in enumerate(drawings):
  if d['type'] in ['clip','group']:
   if d['type']=='clip' or d.get('blendmode','Normal')!='Normal' or d.get('opacity',1)!=1:issues.append({'reason':'pdf_'+d['type']+'_semantics_require_reconstruction','details':{k:v for k,v in d.items() if k!='items'}})
   continue
  attrs={'id':'pdfpath'+str(n),'d':pathdata(d),'fill':rgb(d.get('fill')),'stroke':rgb(d.get('color')),'stroke-width':str(d.get('width') or 0),'fill-opacity':str(d.get('fill_opacity') if d.get('fill_opacity') is not None else 1),'stroke-opacity':str(d.get('stroke_opacity') if d.get('stroke_opacity') is not None else 1),'stroke-linecap':['butt','round','square'][max(d.get('lineCap') or (0,))],'stroke-linejoin':['miter','round','bevel'][round(d.get('lineJoin') or 0)]}
  if d.get('even_odd'):attrs['fill-rule']='evenodd'
  dash=re.match(r'\[([^\]]*)\]\s*([\d.-]+)',d.get('dashes') or '')
  if dash and dash[1].strip():attrs.update({'stroke-dasharray':dash[1].strip(),'stroke-dashoffset':dash[2]})
  items.append((d['seqno'],n,E.Element('path',attrs)))
 run_count=0
 for n,t in enumerate(traces):
  if t['type']==3:continue
  f=fonts[t['font']];runs=[]
  for c in t['clusters']:
   x,y=c['origin'];advance=f['glyph_advances'][c['gid']]*t['size'];previous=runs[-1] if runs else None
   if previous and abs(previous['end_x']-x)<.03 and abs(previous['end_y']-y)<.03:previous['text']+=c['text'];previous['end_x']=x+advance*t['dir'][0];previous['end_y']=y+advance*t['dir'][1]
   else:runs.append({'x':x,'y':y,'text':c['text'],'end_x':x+advance*t['dir'][0],'end_y':y+advance*t['dir'][1]})
  angle=math.degrees(math.atan2(t['dir'][1],t['dir'][0]));assert abs(math.hypot(*t['dir'])-1)<.001,'nonuniform PDF text direction'
  if t['type']!=0:issues.append({'reason':'nonfill_pdf_text_requires_review','seqno':t['seqno'],'type':t['type']})
  for k,r in enumerate(runs):
   attrs={'id':f'pdftext{n}_{k}','x':str(r['x']),'y':str(r['y']),'font-family':f['family'],'font-size':str(t['size']),'fill':rgb(t['color']),'opacity':str(t['opacity']),'style':'font-kerning:none;white-space:pre'};
   if abs(angle)>.001:attrs['transform']=f'rotate({angle},{r["x"]},{r["y"]})'
   node=E.Element('text',attrs);node.text=r['text'];items.append((t['seqno'],100000+n*1000+k,node));run_count+=1
 for _,_,node in sorted(items,key=lambda x:(x[0],x[1])):root.append(node)
 if page.get_images():issues.append({'reason':'pdf_raster_assets_need_explicit_extraction','count':len(page.get_images())})
 return E.tostring(root,encoding='unicode'),fonts,{'issues':issues,'pdf_drawing_paths':sum(d['type'] not in ['clip','group'] for d in drawings),'pdf_text_traces':len(traces),'native_text_runs':run_count,'unicode_text':'\n'.join(''.join(c['source_text'] for c in t['clusters']) for t in traces if t['type']!=3)}

def attach_fonts(xml,fonts):
 root=E.fromstring(xml);by={f['family']:f for f in fonts.values()};seen=set();model=root.find('.//mxGraphModel');model.set('extFonts','|'.join(f['family']+'^'+f['uri'] for f in fonts.values()))
 for c in root.iter('mxCell'):
  styles=dict(x.split('=',1) for x in c.get('style','').split(';') if '=' in x);family=styles.get('fontFamily')
  if family in by and family not in seen:styles['fontSource']=urllib.parse.quote(by[family]['uri'],safe='');seen.add(family);c.set('style',';'.join(k+'='+v for k,v in styles.items())+';')
 return E.tostring(root,encoding='unicode')
