"""Source-owned arbitrary SVG path clipping; complete Artist arrays stay intact."""
import copy,hashlib
from matplotlib_plot_vector_clip_v2 import path,svg,transform,stroke,skia,apply as rectangles
from svg_convert_v2 import path_for
def apply(o):
    paths=o.get('plot_clip_paths') or []
    if not paths:return rectangles(o)
    if o['type']!='shape':raise ValueError('unsupported_nonrect_clip_paint_type')
    clips=[]
    for r in o.get('plot_clip_rectangles') or []:
        p=skia.Path();p.addRect(skia.Rect.MakeXYWH(r['x'],r['y'],r['w'],r['h']));clips.append(p)
    for r in paths:
        p=path(r['d']);rule=r.get('fillRule','nonzero')
        if rule not in {'nonzero','evenodd'}:raise ValueError('unsupported_SVG_clip_fill_rule')
        p.setFillType(skia.PathFillType.kEvenOdd if rule=='evenodd' else skia.PathFillType.kWinding);clips.append(transform(p,r['matrix']))
    clip=clips[0]
    for c in clips[1:]:clip=skia.Op(clip,c,skia.PathOp.kIntersect_PathOp)
    p=path(path_for(o));s=o['style'];paint=[]
    if s['fill']!='none':paint.append(('fill',transform(p,o['matrix']),s['fill'],s.get('fillOpacity',1)))
    if s['stroke']!='none' and s['strokeWidth']>0:paint.append(('stroke',transform(stroke(p,o),o['matrix']),s['stroke'],s.get('strokeOpacity',1)))
    proof={'id':o['id'],'clip':'source_nonrect_path_visible_paint_intersection','source_clip_paths':[{'id':r['id'],'path_sha256':hashlib.sha256(r['d'].encode()).hexdigest(),'matrix':r['matrix'],'fillRule':r['fillRule']} for r in paths],'complete_Artist_arrays_retained':True,'source_clip_geometry_only_no_pixel_fit':True,'Skia_version':skia.__version__}
    if all(skia.Op(q,clip,skia.PathOp.kDifference_PathOp).isEmpty() for _,q,_,_ in paint):return [o],{**proof,'clip':'source_nonrect_path_proved_paint_noop','all_original_path_commands_preserved':True}
    out=[];conics=0
    for kind,q,color,opacity in paint:
        visible=skia.AsWinding(skia.Op(q,clip,skia.PathOp.kIntersect_PathOp))
        if visible.isEmpty():continue
        d,n=svg(visible);conics+=n;b=visible.computeTightBounds();v=copy.deepcopy(o);v.update(id=o['id']+'_'+kind+'_visible',tag='path',d=d,attrs={},matrix=[1,0,0,1,0,0],bbox={'x':float(b.left()),'y':float(b.top()),'w':float(b.width()),'h':float(b.height())},plot_visible_paint_of=o['id'],plot_paint_role=kind)
        v['style'].update(fill=color,fillOpacity=opacity,stroke='none',strokeWidth=0,strokeOpacity=1,dash='none');out.append(v)
    return out,{**proof,'output_objects':len(out),'conic_sections_approximated_by32quadratics':conics}
