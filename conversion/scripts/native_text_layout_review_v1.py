"""Review flags from actual paired native glyph ranges; never changes QA.

Opaque-shape hit testing alone misses stacked text labels. Compare distinct
logical text cells, allowing shared SVG text-run parents and single-symbol
formula spacing. These flags require content review, not converter rejection.
"""
import math,re
from collections import defaultdict


def inspect(info,canvas):
    width,height=canvas;glyphs=[];texts={};outside=defaultdict(list)
    for row in info.get('actual_text_positions',[]):
        cell=row['cell'];chars=[c for run in row.get('runs',[])for c in run.get('chars',[])]
        texts[cell]=''.join(c.get('text','')for c in chars)
        for c in chars:
            if not c.get('text','').strip()or min(c.get('width',0),c.get('height',0))<=0:continue
            x,y,w,h=(float(c[k])for k in ['x','y','width','height'])
            if not all(math.isfinite(v)for v in [x,y,w,h]):raise ValueError('native_layout_nonfinite_glyph')
            if x<-.03 or y<-.03 or x+w>width+.03 or y+h>height+.03:
                outside[cell].append(dict(text=c['text'],box=[x,y,x+w,y+h]))
            glyphs.append(dict(cell=cell,text=c['text'],box=(x,y,x+w,y+h),area=w*h))
    buckets=defaultdict(list);pairs=defaultdict(lambda:(set(),set()));per_cell=defaultdict(int)
    for i,g in enumerate(glyphs):
        per_cell[g['cell']]+=1;x0,y0,x1,y1=g['box'];keys=[(x,y)for x in range(math.floor(x0/16),math.floor(x1/16)+1)for y in range(math.floor(y0/16),math.floor(y1/16)+1)]
        candidates={j for key in keys for j in buckets[key]}
        for j in candidates:
            p=glyphs[j]
            if p['cell']==g['cell']or re.sub(r't\d+$','',p['cell'])==re.sub(r't\d+$','',g['cell']):continue
            a,b=p['box'],g['box'];area=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
            if area/min(p['area'],g['area'])<.4:continue
            if texts[p['cell']]==texts[g['cell']]and max(abs(a[k]-b[k])for k in range(4))<=.03:continue
            if p['cell']<g['cell']:key=(p['cell'],g['cell']);left,right=j,i
            else:key=(g['cell'],p['cell']);left,right=i,j
            pairs[key][0].add(left);pairs[key][1].add(right)
        for key in keys:buckets[key].append(i)
    overlap=[]
    for (left,right),(a,b)in pairs.items():
        if min(len(a),len(b))>=3 and min(len(a)/per_cell[left],len(b)/per_cell[right])>=.2:
            overlap.append(dict(left_cell=left,right_cell=right,left_text=texts[left],right_text=texts[right],left_overlapping_graphemes=len(a),right_overlapping_graphemes=len(b)))
    clipped=[dict(cell=cell,text=texts[cell],outside_graphemes=len(chars),examples=chars[:4])for cell,chars in outside.items()]
    return dict(actual_native_text_cells=len(texts),actual_nonblank_glyphs=len(glyphs),
                potential_text_overlap_pairs=len(overlap),potential_outside_canvas_text_cells=len(clipped),
                overlap_examples=overlap[:20],outside_canvas_examples=clipped[:20],
                needs_content_review=bool(overlap or clipped),
                source_and_candidate_unchanged=True,qualification_or_rejection_not_implied=True,
                method='actual_native_grapheme_rectangles_distinct_logical_cells_40pct_overlap_3glyphs_20pct_labels_v1')


def controls():
    def row(cell,text,x,y):return dict(cell=cell,runs=[dict(chars=[dict(text=c,x=x+i*10,y=y,width=9,height=12)for i,c in enumerate(text)])])
    examples=[('separate',[row('v1t0','ABCDE',0,0),row('v2t0','FGHIJ',0,30)],False),
              ('stacked',[row('v1t0','ABCDE',0,0),row('v2t0','FGHIJ',2,1)],True),
              ('same_logical_parent',[row('v1t0','ABC',0,0),row('v1t1','DEF',2,1)],False),
              ('clipped',[row('v1t0','ABCDE',90,0)],True)]
    result=[]
    for name,rows,expected in examples:
        answer=inspect(dict(actual_text_positions=rows),(100,100));assert answer['needs_content_review']==expected,(name,answer)
        result.append(dict(name=name,expected_flag=expected,observed_flag=answer['needs_content_review']))
    return result
