"""Fresh original Graphviz -> official CoSyn frame -> native glyph shape.

All transforms come from the original source, never reference fitting. This
adapter composes existing frozen source/emission/rendering primitives; it does
not install fonts or replace a native renderer/compiler implementation.
"""
import base64
import copy
import hashlib
import html
import io
import json
import math
import re
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
POLICY='official_CoSyn_complete_frame_intrinsic_text_integer_viewport_v2'
CARRIER='dataCoSynOfficialIntrinsicCompleteFrameV2'
sha=lambda value:hashlib.sha256(value).hexdigest()
raw=lambda value:(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()


def save(path,blob):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb')as stream:stream.write(blob)


def asset(path):
    path=Path(path).resolve(strict=True)
    if not path.is_relative_to((R/'clean').resolve()):raise ValueError('CoSyn_frame_asset_not_clean')
    blob=path.read_bytes();return dict(file=str(path.relative_to(R)),sha256=sha(blob),bytes=len(blob))


def source(record,work):
    """Reexecute original DOT, prove capture, apply official source-only map."""
    from compiler_graphviz_visibility_scene_v1 import _source_scene,_read,DOT
    import compiler_graphviz_visibility_domain_v1 as domain
    import compiler_cosyn_image_postprocess_v1 as official
    from compiler_capture_snapshot_v1 import check_snapshot
    from sandbox_runner import run
    from PIL import Image
    import numpy as np
    work=Path(work).resolve()
    if not work.is_relative_to(W.resolve()):raise ValueError('CoSyn_source_work_outside_owner')
    work.mkdir(parents=True,exist_ok=False)
    check_snapshot(record,record['compiler_source_capture_snapshot'])
    scene=_source_scene(record,work/'fresh_source_ir')
    runtime=W/'runtime/graphviz'
    process=run(work/'fresh_source_ir',[str(DOT),'-v','-Tpng','-o','/work/fresh.png','/work/input.dot'],timeout=45,
                extra_ro=[(runtime,runtime)],extra_env={'LD_LIBRARY_PATH':str(runtime/'lib'),'GVBINDIR':str(runtime/'lib/graphviz')})
    save(work/'fresh_PNG.stdout.log',process.stdout.encode());save(work/'fresh_PNG.stderr.log',process.stderr.encode())
    if process.returncode:
        if any(word in process.stderr for word in ('error while loading shared libraries','bwrap: ','Could not load ','not recognized. Use one of:')):
            raise RuntimeError('infrastructure_fresh_CoSyn_Graphviz_PNG_runtime_failed:'+process.stderr[-2000:])
        raise ValueError('fresh_CoSyn_Graphviz_PNG_execution_failed:'+process.stderr[-2000:])
    png=(work/'fresh_source_ir/fresh.png').read_bytes();snapshot=record['compiler_source_capture_snapshot']
    cached=_read(snapshot['returned_png'],snapshot['returned_png_sha256'],clean=False)
    a,b=[Image.open(io.BytesIO(blob)).convert('RGBA')for blob in (png,cached)]
    if a.size!=b.size or not np.array_equal(np.asarray(a),np.asarray(b)):raise ValueError('fresh_CoSyn_PNG_does_not_reproduce_original_capture')
    processed=official.postprocess(png,record)
    if not processed['ok']:raise ValueError(processed['reason'])
    reference=_read(record['original_reference'],record['source_image_sha256']);size=Image.open(io.BytesIO(reference)).size
    canvas=official.match_reference_canvas(processed,size)
    if not canvas['ok']:raise ValueError(canvas['reason'])
    original_svg=_read(record['source_render_svg'],record['source_render_svg_sha256'])
    registered,registration=official.register_svg(original_svg,processed['mapping'],record['source_render_svg_sha256'])
    destination=R/'clean/compiler_python_cosyn_intrinsic_frame_v2'/record['id'][:2]/record['id']/uuid.uuid4().hex
    destination.mkdir(parents=True,exist_ok=False)
    for name,blob in [('fresh_source.png',png),('captured_source.png',cached),('official_source.png',processed['png']),
                      ('source.original.svg',original_svg),('source.registered.svg',registered),('source_scene.json',raw(scene))]:save(destination/name,blob)
    framed={**record,'source_render_svg':str((destination/'source.registered.svg').relative_to(R)),'source_render_svg_sha256':sha(registered)}
    framed_scene=copy.deepcopy(scene);framed_scene['source']['svg_sha256']=sha(registered)
    replay=domain.replay_source(framed,framed_scene,size,size,[0,0],work/'registered_SOURCE_browser')
    engine_fonts={}
    for line in process.stderr.splitlines():
        if 'fontname:'not in line or 'resolved to:'not in line:continue
        match=re.search(r'\s(/[^\n]+\.(?:ttf|otf|ttc))\s*$',line,re.I)
        if match:
            path=Path(match[1]).resolve(strict=True);engine_fonts[str(path)]=dict(sha256=sha(path.read_bytes()),actual_Graphviz_resolution=line)
    for face in replay['faces'].values():
        if face['collection_index']!=0 or not any(row['sha256']==face['original_sha256']for row in engine_fonts.values()):
            raise ValueError('SOURCE_browser_physical_face_not_proved_by_fresh_Graphviz_font_resolution')
    for name,value in [('source_positions.json',replay['positions']),('source_dom.json',replay['dom'])]:save(destination/name,raw(value))
    from auto_quality_common import image_quality
    original_visual=image_quality(reference,processed['png'],{},domain._positions(replay['positions'],[0,0]))
    if not original_visual['ok']:raise ValueError('official_forward_source_original_reference_visual_failed:'+json.dumps(original_visual['failures']))
    proof=dict(policy=POLICY,id=record['id'],source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],
               source_capture_snapshot=record['compiler_source_capture_snapshot'],fresh_scene_sha256=sha(raw(scene)),
               original_SOURCE_SVG=asset(destination/'source.original.svg'),registered_SOURCE_SVG=asset(destination/'source.registered.svg'),
               fresh_source_PNG=asset(destination/'fresh_source.png'),official_source_PNG=asset(destination/'official_source.png'),
               official=processed['evidence'],mapping=processed['mapping'],registered_SVG=registration,
               fresh_PNG_RGBA_exact_capture=True,fresh_SVG_bytes_exact_capture=True,
               source_reference_visual=original_visual,source_browser=replay['evidence'],reference_parameters_used=False,
               actual_Graphviz_physical_fonts=engine_fonts,
               native_full_quality_still_required=True,model_calls=0)
    save(destination/'source_frame_proof.json',raw(proof))
    return dict(scene=scene,replay=replay,proof=proof,proof_asset=asset(destination/'source_frame_proof.json'),
                registered_svg=registered,processed_png=processed['png'],reference=reference,canvas=size,work=work)


def text_shape(obj):
    if obj.get('type')!='text':raise ValueError('CoSyn_glyph_shape_requires_text_object')
    a,b,c,d,_,_=map(float,obj['matrix'])
    if max(abs(b),abs(c))>1e-8 or min(a,d)<=0:raise ValueError('CoSyn_non_axis_aligned_SOURCE_text_pending')
    size=float(obj['fontSize'])
    if not math.isfinite(size)or size<=0:raise ValueError('CoSyn_invalid_intrinsic_SOURCE_font_size')
    # SVG shapes text on its effective device-size font grid. Enlarging an HTML
    # 12/14px run by the complete CTM instead magnifies HTML layout quantization.
    # Decompose the identical SOURCE affine map as effective font size plus its
    # exact residual axis ratio. Actual grapheme/pixel equality is still tested.
    return dict(fontSize=size,scale_x=1.,scale_y=d/a,source_text=obj['text'],
                source_intrinsic_font_size=size/a,source_ctm_x=a,source_ctm_y=d,
                decomposition='SOURCE_effective_font_grid_and_exact_axis_ratio_v1')


def vector_text_shape(obj,position,faces,registered_svg):
    """Keep one complete SOURCE SVG text run inside its editable native cell.

    SVG and HTML use different layout quantization. This retains SVG shaping,
    exact baseline, anchor, physical font and complete CTM without per-letter
    fitting or a whole-graph image/carrier.
    """
    shape=text_shape(obj);texts=list(ET.fromstring(registered_svg).iter('{http://www.w3.org/2000/svg}text'))
    index=position.get('source_element_index')
    if type(index)is not int or not 0<=index<len(texts):raise ValueError('CoSyn_SOURCE_text_element_binding_missing')
    element=texts[index]
    if len(element)or element.text!=obj['text']:raise ValueError('CoSyn_complex_SOURCE_SVG_text_run_pending')
    allowed={'x','y','dx','dy','text-anchor','font-family','font-size','font-weight','font-style','font-variant','fill','stroke','stroke-width','opacity','fill-opacity','stroke-opacity','text-decoration','letter-spacing','word-spacing','textLength','lengthAdjust','transform','{http://www.w3.org/XML/1998/namespace}space'}
    if set(element.attrib)-allowed:raise ValueError('CoSyn_unproved_SOURCE_SVG_text_attribute_pending')
    attrs={key:value for key,value in element.attrib.items()if key!='transform'}
    physical=physical_text_style(obj,position,faces)
    attrs.update({'font-family':physical['fontFamily'],'font-size':format(shape['source_intrinsic_font_size'],'.15g'),'font-weight':'normal','font-style':'normal','fill':obj['color'],'opacity':format(float(obj['opacity']),'.15g')})
    a,b,c,d,e,f=map(float,obj['matrix']);bbox=obj['bbox']
    shape.update(vector_svg_text=attrs,source_element_index=index,bbox=dict(bbox),
                 vector_matrix=[a,b,c,d,e-float(bbox['x']),f-float(bbox['y'])],
                 representation='individual_editable_SOURCE_SVG_text_v1')
    return shape


def shape_value(identifier,shape,offset=(0.,0.)):
    number=lambda value:format(float(value),'.12g')
    dx,dy=offset
    if not all(math.isfinite(float(v))for v in (dx,dy)):raise ValueError('CoSyn_nonfinite_SOURCE_anchor')
    if shape.get('representation')=='individual_editable_SOURCE_SVG_text_v1':
        box=shape['bbox']
        # HTML layout quantizes an inline SVG's used dimensions to 1/64 px.
        # A fractional viewport plus default aspect-ratio meet scales the full
        # source CTM by that unintended rounding. Equal integer viewport and
        # viewBox dimensions preserve its exact local-to-device map instead.
        # The original text bbox, complete Unicode run, em size and matrix stay
        # unchanged; overflow is visible, so these are no text clipping bounds.
        dimensions=[float(box[key])for key in ('w','h')]
        if any(not math.isfinite(v)or v<=0 for v in dimensions):raise ValueError('CoSyn_invalid_SOURCE_text_viewport')
        width,height=[math.ceil(v)for v in dimensions]
        svg=ET.Element('svg',xmlns='http://www.w3.org/2000/svg',width=str(width),height=str(height),viewBox='0 0 '+str(width)+' '+str(height),preserveAspectRatio='none',style='overflow:visible;display:block;',**{'data-cosyn-glyph-shape-v1':identifier})
        group=ET.SubElement(svg,'g',transform='matrix('+','.join(number(v)for v in shape['vector_matrix'])+')')
        element=ET.SubElement(group,'text',shape['vector_svg_text']);element.text=shape['source_text']
        inner=ET.tostring(svg,encoding='unicode')
    else:inner='<span data-cosyn-glyph-shape-v1="'+html.escape(identifier,quote=True)+'" style="display:inline-block;transform-origin:0 0;transform:scale('+number(shape['scale_x'])+','+number(shape['scale_y'])+');">'+html.escape(shape['source_text'])+'</span>'
    return '<span data-cosyn-source-anchor-v1="'+html.escape(identifier,quote=True)+'" style="position:relative;left:'+number(dx)+'px;top:'+number(dy)+'px;">'+inner+'</span>'


def physical_text_style(obj,position,faces):
    """Bind an actual SOURCE physical face, without synthetic double styling."""
    import compiler_graphviz_visibility_domain_v1 as domain
    signature=domain._font_signature(position['actual_fonts'],True)
    if len(signature)!=1:raise ValueError('CoSyn_mixed_SOURCE_font_run_pending')
    face=faces[signature[0][0]]
    if obj.get('bold')and not face['face']['bold']or obj.get('italic')and not face['face']['italic']:
        raise ValueError('CoSyn_unproved_synthetic_SOURCE_font_style_pending')
    return dict(fontFamily=face['family'],fontStyle=str(4*int(bool(obj.get('underline')))))


def viewport_lowering(dom,canvas):
    """Preserve SOURCE root clipping for an un-stroked background rectangle.

    The official integer PNG canvas can cut the vector background by a partial
    pixel. This is exact source viewport intersection, never content fitting.
    Named graph objects, strokes and all unsupported clips remain unchanged.
    """
    result=copy.deepcopy(dom);proof=[];width,height=map(float,canvas)
    for obj in result['objects']:
        if obj['type']!='shape'or obj.get('tag')!='polygon'or obj.get('node')or obj.get('edge')or obj.get('sourceId')or obj['style']['stroke']!='none':continue
        vals=[float(v)for v in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',obj.get('pointsAttr')or'')]
        if len(vals)!=10:continue
        local=list(zip(vals[::2],vals[1::2]));a,b,c,d,e,f=map(float,obj['matrix'])
        if abs(b)>1e-8 or abs(c)>1e-8 or a<=0 or d<=0 or local[0]!=local[-1]:continue
        xs,ys=sorted(set(x for x,y in local)),sorted(set(y for x,y in local))
        if len(xs)!=2 or len(ys)!=2 or set(local[:-1])!={(x,y)for x in xs for y in ys}:continue
        left,right=a*xs[0]+e,a*xs[1]+e;top,bottom=d*ys[0]+f,d*ys[1]+f
        if left>=0 and top>=0 and right<=width and bottom<=height:continue
        clipped=[max(0.,left),max(0.,top),min(width,right),min(height,bottom)]
        if clipped[0]>=clipped[2]or clipped[1]>=clipped[3]:raise ValueError('CoSyn_fully_clipped_background_pending')
        replacement=[]
        for x,y in local:
            px=clipped[0]if x==xs[0]else clipped[2];py=clipped[1]if y==ys[0]else clipped[3]
            replacement.append(((px-e)/a,(py-f)/d))
        proof.append(dict(source_object=obj['id'],rule='SOURCE_root_viewport_intersection_of_unstroked_background_rectangle_v1',source_points=obj['pointsAttr'],source_matrix=obj['matrix'],source_bounds=[left,top,right,bottom],viewport=[0.,0.,width,height],visible_bounds=clipped,source_semantic_id_preserved=True,absent_stroke_source_width=obj['style'].get('strokeWidth'),native_absent_stroke_width=2.,native_upstream_svg_screen_offset=0.,absent_stroke_canonicalization='upstream_mxShape_getSvgScreenOffset_even_width_for_no_stroke_v1'))
        # mxShape adds a .5px SVG transform for odd rounded widths even when
        # stroke is none. Canonical even width preserves the absent stroke and
        # the original fill coordinate system; no renderer is changed.
        obj['style']['strokeWidth']=2./math.sqrt(abs(a*d-b*c))
        obj['pointsAttr']=' '.join(format(x,'.17g')+','+format(y,'.17g')for x,y in replacement)
        obj['bbox']=dict(x=clipped[0],y=clipped[1],w=clipped[2]-clipped[0],h=clipped[3]-clipped[1]);obj['originalBoundingBox']=dict(obj['bbox'])
    return result,proof


def native(record,framed,destination):
    """Existing SVGv5 emission, explicit source-CTM text and actual source faces."""
    import compiler_graphviz_visibility_domain_v1 as domain
    from svg_convert_v5 import build
    from pdf_to_native import attach_fonts
    from compiler_graphviz_visibility_scene_v1 import encode_layout_constraints
    destination=Path(destination);width,height=framed['canvas'];dom,clips=viewport_lowering(framed['replay']['dom'],framed['canvas'])
    xml,stats=build(dom,width,height);xml=encode_layout_constraints(xml,framed['scene'])
    root=ET.fromstring(xml);cells={cell.get('id'):cell for cell in root.iter('mxCell')}
    fonts={};assets=[]
    for postscript,face in framed['replay']['faces'].items():
        embedded=(framed['work']/'registered_SOURCE_browser/fonts'/(face['embedded_sha256']+'.ttf')).read_bytes()
        original=Path(face['file']).read_bytes()
        if sha(embedded)!=face['embedded_sha256']or sha(original)!=face['original_sha256']:raise ValueError('fresh_SOURCE_physical_face_changed')
        target=destination/'fonts'/(sha(embedded)+'.ttf');origin=destination/'fonts'/(sha(original)+'.original'+Path(face['file']).suffix.lower())
        if not target.exists():save(target,embedded)
        if not origin.exists():save(origin,original)
        uri='data:font/ttf;base64,'+base64.b64encode(embedded).decode()
        fonts[face['family']]=dict(family=face['family'],uri=uri)
        assets.append(dict(family=face['family'],file=str(target.relative_to(R)),sha256=sha(embedded),original_file=str(origin.relative_to(R)),
                           original_sha256=sha(original),collection_index=face['collection_index'],physical_postscript_name=postscript))
    shapes={}
    for obj in dom['objects']:
        if obj['type']!='text':continue
        identifier=obj['id'];shape=vector_text_shape(obj,framed['replay']['positions'][identifier],framed['replay']['faces'],framed['registered_svg']);cell=cells[identifier];style=domain._style(cell)
        style['fontSize']=format(shape['fontSize'],'.12g')
        style.update(physical_text_style(obj,framed['replay']['positions'][identifier],framed['replay']['faces']))
        if style.get('fontFamily')not in fonts:raise ValueError('native_text_not_bound_to_fresh_SOURCE_physical_face')
        cell.set('style',';'.join(key+'='+value for key,value in style.items())+';');cell.set('value',shape_value(identifier,shape));shapes[identifier]=shape
    carrier=dict(policy=POLICY,source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],
                 mapping=framed['proof']['mapping'],original_source_svg_sha256=record['source_render_svg_sha256'],
                 registered_source_svg_sha256=sha(framed['registered_svg']),source_scene_sha256=sha(raw(framed['scene'])),source_viewport_clips=clips)
    cells['0'].set(CARRIER,raw(carrier).decode().strip())
    xml=attach_fonts(ET.tostring(root,encoding='unicode'),fonts)
    return xml,stats,assets,shapes,carrier


def apply_anchors(xml,shapes,offsets):
    root=ET.fromstring(xml);cells={cell.get('id'):cell for cell in root.iter('mxCell')}
    if set(shapes)!=set(offsets):raise ValueError('CoSyn_SOURCE_anchor_scope_incomplete')
    for identifier,shape in shapes.items():
        row=offsets[identifier];cells[identifier].set('value',shape_value(identifier,shape,(row['dx'],row['dy'])))
    return ET.tostring(root,encoding='unicode')


def paint_and_shape(dom,xml,carrier,source_positions,source_faces,registered_svg=None):
    """Different font-size representation has a complete explicit CTM proof."""
    import compiler_graphviz_visibility_domain_v1 as domain
    from auto_quality_source_vector_v2 import _paint_coverage
    from html.parser import HTMLParser
    root,cells,_=domain._xml_cells(xml)
    if cells['0'].get(CARRIER)!=raw(carrier).decode().strip():raise ValueError('native_complete_official_SOURCE_frame_changed')
    adjusted=copy.deepcopy(dom);textproof={}
    for obj in adjusted['objects']:
        if obj['type']!='text':continue
        identifier=obj['id'];shape=vector_text_shape(obj,source_positions[identifier],source_faces,registered_svg)if registered_svg is not None else text_shape(obj);cell=cells[identifier];style=domain._style(cell)
        expected_face=physical_text_style(obj,source_positions[identifier],source_faces)
        if any(style.get(key,'0'if key=='fontStyle'else'')!=value for key,value in expected_face.items()):raise ValueError('native_intrinsic_SOURCE_physical_font_style_changed')
        value=cell.get('value','')
        match=re.fullmatch(r'<span data-cosyn-source-anchor-v1="'+re.escape(html.escape(identifier,quote=True))+r'" style="position:relative;left:([-+0-9.eE]+)px;top:([-+0-9.eE]+)px;">([\s\S]*)</span>',value)
        if not match or any(not math.isfinite(float(v))or abs(float(v))>12 for v in match.groups()[:2]):raise ValueError('unaccounted_or_unbounded_native_SOURCE_anchor_style')
        expected=shape_value(identifier,shape,(float(match.group(1)),float(match.group(2))))
        if value!=expected:raise ValueError('native_SOURCE_glyph_shape_matrix_changed')
        if abs(float(style['fontSize'])-shape['fontSize'])>1e-8:raise ValueError('native_intrinsic_SOURCE_font_size_changed')
        # This preserves the unchanged shape/paint gate for every property.
        # The separately verified intrinsic font + exact CTM replaces only its
        # scalar-font-size representation. Fresh per-grapheme geometry and
        # pixels remain required at the original strict tolerances.
        obj['fontSize']=shape['fontSize'];textproof[identifier]=shape
    paint=_paint_coverage(adjusted,xml)
    return paint,dict(ok=True,checked_source_text_shapes=len(textproof),source_text_shapes=textproof,
                      source_intrinsic_font_shape_and_complete_axis_frame_exact=True,glyph_geometry_or_pixel_checks_waived=False)
