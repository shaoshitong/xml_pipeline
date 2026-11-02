"""Represent rectangular source overflow clips on editable native HTML text."""
import html,xml.etree.ElementTree as E
from html.parser import HTMLParser
class Text(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
 def handle_data(self,s):self.parts.append(s)
def plain(s):
 p=Text();p.feed(s);return ''.join(p.parts)
def apply_clips(xml,dom,positions,width,height):
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};native={r['cell']:r for r in positions};changes=[];issues=[]
 for o in dom['objects']:
  if o['type']!='text' or not o.get('sourceClip',{}).get('partial'):continue
  cid=str(o['id']+1);c=cells[cid];value=c.get('value','');assert plain(value)==o['text'],(cid,'source/native text mismatch')
  assert not o['sourceClip'].get('unmodeled'),('Unsupported clipping context',o['sourceClip'].get('unmodeled'));chain=o['sourceClip']['chain'];assert all(all(float(v.removesuffix('px'))==0 for v in e['radius']) for e in chain),'Rounded clip needs native shape mask'
  left=max([0]+[a['left'] for a in chain if a['clipX']]);right=min([width]+[a['right'] for a in chain if a['clipX']]);top=max([0]+[a['top'] for a in chain if a['clipY']]);bottom=min([height]+[a['bottom'] for a in chain if a['clipY']]);row=native[cid];chars=[x for r in row['runs'] for x in r['chars']];assert ''.join(x['text'] for x in chars)==o['text'];x=min(a['x'] for a in chars);y=min(a['y'] for a in chars);x1=max(a['x']+a['width'] for a in chars);y1=max(a['y']+a['height'] for a in chars);insets=[top-y,x1-right,y1-bottom,left-x]
  # An inline clipping span leaves the original whole text and typography intact.
  css='clip-path:inset('+ ' '.join(format(v,'.8g')+'px' for v in insets)+');';c.set('value','<span style="'+css+'">'+value+'</span>');changes.append({'cell':cid,'source_text':o['text'],'before_value':value,'clip_bounds':[left,top,right,bottom],'native_range_bbox':[x,y,x1,y1],'insets':insets,'source_clip':o['sourceClip']})
 return E.tostring(root,encoding='unicode'),{'changes':changes,'issues':issues}

def verify_graph(before,after,details):
 a=E.fromstring(before);b=E.fromstring(after);cells={c.get('id'):c for c in b.iter('mxCell')}
 for ch in details['changes']:
  c=cells[ch['cell']];expected='<span style="clip-path:inset('+' '.join(format(v,'.8g')+'px' for v in ch['insets'])+');">'+ch['before_value']+'</span>';assert c.get('value')==expected,'Unexpected clip label markup';assert plain(c.get('value'))==ch['source_text'];c.set('value',ch['before_value'])
 assert E.canonicalize(E.tostring(a,encoding='unicode'))==E.canonicalize(E.tostring(b,encoding='unicode')),'Non-label graph change'


def verify_positions(before,after):
 new={r['cell']:r for r in after};errors=[]
 for row in before:
  a=[c for r in row['runs'] for c in r['chars']];b=[c for r in new.get(row['cell'],{}).get('runs',[]) for c in r['chars']]
  if a!=b:errors.append(row['cell'])
 assert not errors,'Native character positions changed: '+str(errors)
 return True

def pixel_clip_proof(before_png,after_png,background_png,details):
 import io,numpy as np
 from PIL import Image
 a=np.array(Image.open(io.BytesIO(before_png)).convert('RGB'));b=np.array(Image.open(io.BytesIO(after_png)).convert('RGB'));bg=np.array(Image.open(io.BytesIO(background_png)).convert('RGB'));assert a.shape==b.shape==bg.shape;h,w=a.shape[:2];mask=np.zeros((h,w),dtype=bool)
 for ch in details['changes']:
  left,top,right,bottom=ch['clip_bounds'];assert all(float(v).is_integer() for v in [left,top,right,bottom]),'Fractional clips require separate edge-coverage validation';x,y,x1,y1=ch['native_range_bbox'];left=max(left,x-4);top=max(top,y-4);right=min(right,x1+4);bottom=min(bottom,y1+4);xs=np.arange(w)+.5;ys=np.arange(h)+.5;mask|=(ys[:,None]>=top)&(ys[:,None]<bottom)&(xs[None,:]>=left)&(xs[None,:]<right)
 expected=bg.copy();expected[mask]=a[mask];mismatch=int(np.any(expected!=b,axis=2).sum());return {'expected_source_clip_pixel_mismatches':mismatch,'actual_changed_pixels':int(np.any(a!=b,axis=2).sum()),'visible_text_preserved_and_only_hidden_source_pixels_removed':mismatch==0,'ok':mismatch==0}
