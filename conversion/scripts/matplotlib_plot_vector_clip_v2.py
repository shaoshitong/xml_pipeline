"""Source-owned SVG rectangle clipping via deterministic Skia vector operations.

Full Matplotlib Artist arrays are retained separately. No data is resampled to
match reference pixels. Visible stroke outlines remain editable vector objects.
"""
import copy,math,re,sys
from pathlib import Path
sys.path.insert(0,'/backup/shaoshitong/img2code_20261029/evaluation/assets/matplotlib_plot_python_v1')
import skia
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
from svg_convert_v2 import path_for

def path(text):
    rec=RecordingPen();parse_path(text,rec);p=skia.Path()
    for op,v in rec.value:
        if op=='moveTo':p.moveTo(*v[0])
        elif op=='lineTo':p.lineTo(*v[0])
        elif op=='curveTo':p.cubicTo(*(a for pt in v for a in pt))
        elif op=='qCurveTo':p.quadTo(*(a for pt in v for a in pt))
        elif op=='closePath':p.close()
        elif op!='endPath':raise ValueError('unsupported_svg_path_operation:'+op)
    return p
def svg(p):
    out=[];conics=0;it=skia.Path.RawIter(p)
    xy=lambda point:format(float(point.x()),'.8g')+','+format(float(point.y()),'.8g')
    while True:
        verb,pts=it.next()
        if verb==skia.Path.kDone_Verb:break
        if verb==skia.Path.kMove_Verb:out.append('M'+xy(pts[0]))
        elif verb==skia.Path.kLine_Verb:out.append('L'+xy(pts[-1]))
        elif verb==skia.Path.kQuad_Verb:out.append('Q'+xy(pts[1])+' '+xy(pts[2]))
        elif verb==skia.Path.kCubic_Verb:out.append('C'+' '.join(map(xy,pts[1:])))
        elif verb==skia.Path.kConic_Verb:
            conics+=1;q=skia.Path.ConvertConicToQuads(*pts,it.conicWeight(),5)
            for i in range(1,len(q),2):out.append('Q'+xy(q[i])+' '+xy(q[i+1]))
        elif verb==skia.Path.kClose_Verb:out.append('Z')
        else:raise ValueError('unsupported_clipped_path_verb')
    return ' '.join(out),conics
def transform(p,m):
    a,b,c,d,e,f=m;q=skia.Path(p);q.transform(skia.Matrix.MakeAll(a,c,e,b,d,f,0,0,1));return q
def stroke(p,o):
    s=o['style'];paint=skia.Paint(Style=skia.Paint.kStroke_Style,StrokeWidth=float(s['strokeWidth']))
    paint.setStrokeCap({'butt':skia.Paint.kButt_Cap,'round':skia.Paint.kRound_Cap,'square':skia.Paint.kSquare_Cap}[s['linecap']])
    paint.setStrokeJoin({'miter':skia.Paint.kMiter_Join,'round':skia.Paint.kRound_Join,'bevel':skia.Paint.kBevel_Join}[s['linejoin']]);paint.setStrokeMiter(float(o.get('strokeMiterlimit',4)))
    if s.get('dash','none')!='none':
        values=[float(x) for x in re.findall(r'[-+]?\d*\.?\d+(?:e[-+]?\d+)?',s['dash'],re.I)]
        if len(values)%2:values*=2
        paint.setPathEffect(skia.DashPathEffect.Make(values,float(o.get('dashoffset',0))))
    out=skia.Path()
    if not paint.getFillPath(p,out,resScale=8):raise ValueError('unsupported_hairline_stroke_clip')
    return out
def apply(o):
    rects=o.get('plot_clip_rectangles') or []
    if o['type']!='shape' or not rects:return [o],{'id':o['id'],'clip':'none'}
    x=max(r['x'] for r in rects);y=max(r['y'] for r in rects);right=min(r['x']+r['w'] for r in rects);bottom=min(r['y']+r['h'] for r in rects)
    if right<=x or bottom<=y:return [],{'id':o['id'],'clip':'fully_outside','original_artist_arrays_preserved':True}
    clip=skia.Path();clip.addRect(skia.Rect.MakeLTRB(x,y,right,bottom));p=path(path_for(o));s=o['style'];paint=[]
    if s['fill']!='none':paint.append(('fill',transform(p,o['matrix']),s['fill'],s.get('fillOpacity',1)))
    if s['stroke']!='none' and s['strokeWidth']>0:paint.append(('stroke',transform(stroke(p,o),o['matrix']),s['stroke'],s.get('strokeOpacity',1)))
    if all(skia.Op(q,clip,skia.PathOp.kDifference_PathOp).isEmpty() for _,q,_,_ in paint):return [o],{'id':o['id'],'clip':'proved_paint_noop','all_original_path_commands_preserved':True}
    out=[];conics=0
    for kind,q,color,opacity in paint:
        visible=skia.AsWinding(skia.Op(q,clip,skia.PathOp.kIntersect_PathOp))
        if visible.isEmpty():continue
        text,n=svg(visible);conics+=n;b=visible.computeTightBounds();v=copy.deepcopy(o);v.update(id=o['id']+'_'+kind+'_visible',tag='path',d=text,attrs={},matrix=[1,0,0,1,0,0],bbox={'x':float(b.left()),'y':float(b.top()),'w':float(b.width()),'h':float(b.height())},plot_visible_paint_of=o['id'],plot_paint_role=kind)
        v['style'].update(fill=color,fillOpacity=opacity,stroke='none',strokeWidth=0,strokeOpacity=1,dash='none');out.append(v)
    return out,{'id':o['id'],'clip':'vector_visible_paint_intersection','output_objects':len(out),'conic_sections_approximated_by32quadratics':conics,'input_artist_arrays_preserved':True,'Skia_version':skia.__version__,'pixel_fitting':False}
