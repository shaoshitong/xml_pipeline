"""Collect the contiguous source glyph prefix inside its preceding node shape.

Stop at the first nontext or first outside glyph. Never skip intervening paint,
join disjoint text, alter glyphs, or move objects. Callers still require exact
executed-label equivalence or an independently proved exact source frame.
"""
import math

def collect(shape,objects):
 index=objects.index(shape);box=shape['bbox'];assert all(math.isfinite(float(box[k]))for k in('x','y','w','h'))
 result=[];stop=None
 for item in objects[index+1:]:
  if item.get('type')!='text':stop=dict(id=item['id'],reason='next_source_nontext_paint');break
  b=item['bbox'];cx=b['x']+b['w']/2;cy=b['y']+b['h']/2
  if not(box['x']-.5<=cx<=box['x']+box['w']+.5 and box['y']-.5<=cy<=box['y']+box['h']+.5):stop=dict(id=item['id'],reason='first_source_glyph_center_outside_node');break
  result.append(item)
 return result,dict(source_shape=shape['id'],source_glyph_prefix=[t['id']for t in result],first_unowned_source_object=stop,source_glyphs_or_positions_modified=False,disjoint_or_outside_glyphs_skipped=False)
