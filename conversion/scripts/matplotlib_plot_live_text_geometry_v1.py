"""Correct native live-text positions using source/native character geometry only."""
import math,xml.etree.ElementTree as ET
def position(xml,objects,native_metadata):
 root=ET.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};positions={r['cell']:r for r in native_metadata.get('actual_text_positions',[])};evidence=[]
 for o in objects:
  if o['type']!='text':continue
  row=positions.get(o['id']);chars=[c for run in (row or {}).get('runs',[]) for c in run.get('chars',[]) if c.get('text') and c.get('width',0)>0 and c.get('height',0)>0]
  if not chars:continue
  actual=[min(c['x'] for c in chars),min(c['y'] for c in chars),max(c['x']+c['width'] for c in chars),max(c['y']+c['height'] for c in chars)];source=o.get('originalBoundingBox',o['bbox']);sw,sh=source['w'],source['h'];nw,nh=actual[2]-actual[0],actual[3]-actual[1];dx=source['x']+sw/2-(actual[0]+actual[2])/2;dy=source['y']+sh/2-(actual[1]+actual[3])/2
  if max(abs(sw-nw),abs(sh-nh))>.2 or max(abs(dx),abs(dy))>4:
   evidence.append({'cell':o['id'],'corrected':False,'reason':'source_native_character_geometry_not_translation_only','size_delta':[sw-nw,sh-nh],'screen_translation':[dx,dy]});continue
  if max(abs(dx),abs(dy))<.025:continue
  theta=math.radians(float(o.get('nativeRotation',0)));lx=dx*math.cos(theta)+dy*math.sin(theta);ly=-dx*math.sin(theta)+dy*math.cos(theta);cell=cells[o['id']];value=cell.get('value','');cell.set('value','<span style="display:inline-block;transform:translate('+format(lx,'.8g')+'px,'+format(ly,'.8g')+'px)">'+value+'</span>');evidence.append({'cell':o['id'],'corrected':True,'source_SVG_character_bbox':source,'actual_native_character_bbox_before':actual,'screen_translation':[dx,dy],'local_live_HTML_span_translation':[lx,ly],'rotation_degrees':o.get('nativeRotation',0),'position_from_geometry_only':True,'reference_PNG_scores_used':False,'Unicode_and_font_unchanged':True})
 return ET.tostring(root,encoding='unicode'),evidence
