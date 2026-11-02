"""Independent closed/source-role SVG paint coverage, never a graph waiver.

Only a conservative closed subset is admitted: basic boxes/ellipses, path-encoded
symmetric convex basic geometry, or explicit glyph/collection roles. Every
source object must remain a native editable object with exact stencil/asset,
geometry/style/text inventory and overlapping paint order. Source relations,
marker owners and untyped open paths explicitly require another profile.
"""
import collections
import copy
import hashlib
from html.parser import HTMLParser
import io
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as E

R=Path('/backup/shaoshitong/img2code_20261029');POLICY='closed_and_source_role_native_svg_scene_v1';sha=lambda blob:hashlib.sha256(blob).hexdigest()


def capture_closed_scene(record):
    """Reuse the independent extractor, adding actual viewport CSS paint facts."""
    import svg_source_scene_dom_v1 as scene
    from PIL import Image
    code=scene._checked_clean(record['original_source_code'],record['source_code_sha256']);reference=scene._checked_clean(record['original_reference'],record['source_image_sha256']);size=Image.open(io.BytesIO(reference)).size;script=scene.EXTRACTOR.read_bytes();blocked=[];browser=scene._browser();context=browser.new_context(viewport={'width':size[0],'height':size[1]},java_script_enabled=False,service_workers='block')
    try:
        def reject(route):blocked.append(route.request.url);route.abort()
        context.route('**/*',reject);page=context.new_page();page.set_default_timeout(45000);page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+code.decode(),wait_until='load');page.evaluate("([w,h])=>{const s=document.querySelector('svg');if(!s)throw Error('missing SVG');if(!s.viewBox.baseVal.width)s.setAttribute('viewBox',`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h)}",list(size));page.evaluate('document.fonts.ready')
        wrapper="""() => {const run=(%s),dom=run(),root=document.querySelector('svg');const keys=['backgroundColor','backgroundImage','borderTopWidth','borderRightWidth','borderBottomWidth','borderLeftWidth','borderTopStyle','borderRightStyle','borderBottomStyle','borderLeftStyle','paddingTop','paddingRight','paddingBottom','paddingLeft','overflow','overflowX','overflowY','mixBlendMode','isolation','opacity','filter','clipPath','maskImage'];const css=el=>Object.fromEntries(keys.map(k=>[k,getComputedStyle(el)[k]]));const b=root.getBoundingClientRect();dom.sceneViewport={rootCss:css(root),bodyCss:css(document.body),htmlCss:css(document.documentElement),bbox:{x:b.x,y:b.y,w:b.width,h:b.height},nonAffineCssElements:[root,...root.querySelectorAll('*')].filter(e=>{const c=getComputedStyle(e);return c.transform.startsWith('matrix3d(')||c.perspective!=='none'}).map(e=>({tag:e.localName,id:e.id||''}))};return dom;}"""%script.decode()
        dom=page.evaluate(wrapper)
    finally:context.close()
    assert sha(scene.EXTRACTOR.read_bytes())==sha(script),'SVG extractor changed during capture';scene._checked_clean(record['original_source_code'],record['source_code_sha256']);scene._checked_clean(record['original_reference'],record['source_image_sha256']);scene.enrich_scene(dom)
    if blocked:dom.setdefault('issues',[]).append({'reason':'closed_scene_external_resources_blocked','urls':sorted(set(blocked))})
    dom['sceneCapture']={'policy':POLICY,'version':1,'recordId':record['id'],'recordCodeSha256':record['code_sha256'],'sourceCodeSha256':record['source_code_sha256'],'sourceImageSha256':record['source_image_sha256'],'referenceSize':list(size),'extractorSha256':sha(script),'moduleSha256':sha(Path(__file__).read_bytes()),'sourcePayloadHashesRecheckedAfterCapture':True,'completeOfflineSource':not blocked,'blockedResources':blocked,'objectIdsV6Compatible':True,'acceptanceNotImplied':True}
    return dom


def _ops(obj):return obj.get('sceneGeometry',{}).get('topology',{}).get('subpaths',[])
def _distance(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
def _cross(a,b,c):return (b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])


def _contour(part,steps=24):
    points=[];current=None;start=None
    for entry in part['operations']:
        op=entry['operation'];p=entry['points']
        if op=='moveTo':current=tuple(p[0]);start=current;points.append(current)
        elif op=='lineTo':current=tuple(p[0]);points.append(current)
        elif op in ('curveTo','qCurveTo'):
            assert current is not None
            for i in range(1,steps+1):
                t=i/steps;u=1-t
                if op=='curveTo':point=tuple(u**3*current[j]+3*u*u*t*p[0][j]+3*u*t*t*p[1][j]+t**3*p[2][j] for j in (0,1))
                else:point=tuple(u*u*current[j]+2*u*t*p[0][j]+t*t*p[1][j] for j in (0,1))
                points.append(point)
            current=tuple(p[-1])
        elif op=='closePath':
            if current is not None and start is not None and _distance(current,start)>1e-9:points.append(start)
            current=start
        elif op!='endPath':raise AssertionError('Unknown source path operation')
    if len(points)>1 and _distance(points[0],points[-1])<1e-8:points.pop()
    return points


def _basic_closed_geometry(obj):
    topology=obj.get('sceneGeometry',{}).get('topology',{});parts=_ops(obj)
    if not topology.get('all_subpaths_explicitly_closed') or not parts:return None
    if obj['tag'] in ('rect','circle','ellipse'):return {'role':'basic_closed_primitive','basis':obj['tag']}
    parallelograms=True
    for part in parts:
        if any(entry['operation'] not in ('moveTo','lineTo','closePath') for entry in part['operations']):parallelograms=False;break
        points=_contour(part)
        while len(points)>4:
            removed=False
            for i in range(len(points)):
                if abs(_cross(points[i-1],points[i],points[(i+1)%len(points)]))<1e-8:points.pop(i);removed=True;break
            if not removed:break
        if len(points)!=4 or abs(_cross(*points[:3]))<1e-8 or max(abs(points[0][j]+points[2][j]-points[1][j]-points[3][j]) for j in (0,1))>1e-5:parallelograms=False;break
    if parallelograms:return {'role':'path_encoded_basic_frame','basis':'every closed contour is a nondegenerate parallelogram'}
    if len(parts)!=1:return None
    points=_contour(parts[0]);turns=[_cross(points[i-1],points[i],points[(i+1)%len(points)]) for i in range(len(points))];nonzero=[v for v in turns if abs(v)>1e-8]
    if not nonzero or min(nonzero)*max(nonzero)<0:return None
    # Exact source controls must have both axis symmetries; a directional head
    # or teardrop cannot pass merely because a sampled contour looks convex.
    controls=[tuple(p) for entry in parts[0]['operations'] for p in entry['points']];xs=[p[0] for p in controls];ys=[p[1] for p in controls]
    if not controls:return None
    cx=(min(xs)+max(xs))/2;cy=(min(ys)+max(ys))/2;scale=max(1,max(xs)-min(xs),max(ys)-min(ys));eps=scale*1e-6
    if all(any(_distance((2*cx-x,y),other)<=eps for other in controls) and any(_distance((x,2*cy-y),other)<=eps for other in controls) for x,y in controls):return {'role':'path_encoded_symmetric_convex_basic_shape','basis':'one convex closed contour, exact control-set x/y symmetry'}
    return None


def _roles(obj,dom):
    roles={row['role'] for row in obj.get('sceneGroupRoles',[])};uses=[dom.get('sceneMetadata',{}).get('useContexts',{}).get(key,{}) for key in obj.get('sceneUseContexts',[])];glyph=bool(uses and ('font_glyph_definition_hint' in roles or 'mathjax_group_hint' in roles) and ('matplotlib_text_hint' in roles or 'mathjax_group_hint' in roles or any(re.search(r'(?:glyph\d*[-_]|(?:DejaVu|Liberation|STIX|CM|Arial|Helvetica|TimesNewRoman)[\w-]*[-_][0-9a-f]+$|MJX[-_])',ctx.get('sourceDefinitionId',''),re.I) for ctx in uses)))
    return {'declared_roles':sorted(roles),'glyph_use':glyph,'collection':bool('matplotlib_collection_hint' in roles),'basic':_basic_closed_geometry(obj)}


def _color_alpha(value):
    value=(value or '').strip().lower()
    if value=='none':return None
    if value=='transparent':return 0.
    if re.fullmatch(r'#[0-9a-f]{3}(?:[0-9a-f]{3})?',value):return 1.
    match=re.fullmatch(r'rgba?\(([^)]+)\)',value)
    if match:
        pieces=[p.strip() for p in re.split('[,/]',match[1])]
        if len(pieces)==3:return 1.
        if len(pieces)==4:return float(pieces[3].strip('%'))/(100 if pieces[3].endswith('%') else 1)
    if value.startswith('url('):return 1.
    raise AssertionError('unmodeled source color syntax: '+value)


def _miter_ratios(obj):
    ratios=[]
    for part in _ops(obj):
        segments=[];current=None;start=None
        for entry in part['operations']:
            op=entry['operation'];points=[tuple(p) for p in entry['points']]
            if op=='moveTo':current=points[0];start=current;continue
            if op in ('lineTo','curveTo','qCurveTo'):
                end=points[-1];forward=[p for p in points if _distance(p,current)>1e-9];backward=[p for p in [current]+points[:-1] if _distance(p,end)>1e-9]
                if forward and backward:segments.append(((forward[0][0]-current[0],forward[0][1]-current[1]),(end[0]-backward[-1][0],end[1]-backward[-1][1])))
                current=end
            elif op=='closePath' and current is not None and start is not None and _distance(current,start)>1e-9:
                v=(start[0]-current[0],start[1]-current[1]);segments.append((v,v));current=start
        for index,segment in enumerate(segments):
            if index==0 and not part['closed']:continue
            a=segments[index-1][1];b=segment[0];n=math.hypot(*a)*math.hypot(*b)
            if not n:continue
            cosine=max(-1,min(1,(a[0]*b[0]+a[1]*b[1])/n));ratios.append(float('inf') if cosine<=-1+1e-12 else 1/math.sqrt((1+cosine)/2))
    return ratios


def _source_admission(dom,xml):
    from auto_quality_source_vector_v2 import _style
    from svg_convert_v2 import style as converted_style
    cells={cell.get('id'):cell for cell in E.fromstring(xml).iter('mxCell')};unsupported=[];roles={};resolved=[];relations={'declared_nodes':len(dom.get('nodes',{})),'edge_object_ids':[],'marker_owner_ids':[],'explicit_relation_role_ids':[]};metadata=dom.get('sceneMetadata',{});ancestors=metadata.get('ancestors',{})
    viewport=dom.get('sceneViewport')
    if not viewport:unsupported.append({'reason':'source_viewport_css_paint_not_captured'})
    else:
        if viewport.get('nonAffineCssElements'):unsupported.append({'reason':'nonaffine_source_css_transform_unproven','elements':viewport['nonAffineCssElements'][:10]})
        for owner in ('rootCss','bodyCss','htmlCss'):
            css=viewport.get(owner,{})
            try:
                bg=css.get('backgroundColor','rgba(0, 0, 0, 0)');alpha=_color_alpha(bg)
                if alpha not in (None,0) and bg.replace(' ','') not in ('rgb(255,255,255)','rgba(255,255,255,1)'):unsupported.append({'reason':'unmapped_source_viewport_background','owner':owner,'value':bg})
                if css.get('backgroundImage','none')!='none':unsupported.append({'reason':'unmapped_source_viewport_background_image','owner':owner})
                if any(float(re.findall(r'[-\d.]+',css.get('border'+side+'Width','0'))[0])>0 and css.get('border'+side+'Style','none')!='none' for side in ('Top','Right','Bottom','Left')):unsupported.append({'reason':'unmapped_source_viewport_css_border','owner':owner})
            except Exception as error:unsupported.append({'reason':'source_viewport_style_unmodeled','error':str(error)})
    for obj in dom.get('objects',[]):
        key=obj['id'];s=obj.get('style',{});css=obj.get('sceneComputedCss',{});role=_roles(obj,dom) if obj.get('type')=='shape' else {};roles[key]=role
        if obj.get('edge'):relations['edge_object_ids'].append(key)
        if obj.get('markerOwner') or obj.get('sceneMarkerContexts') or any(obj.get(name,'none') not in ('none','',None) for name in ('markerStart','markerEnd')):relations['marker_owner_ids'].append(key)
        if any(row.get('role') in ('graphviz_node','graphviz_edge','graphviz_graph','graphviz_cluster','relation_name_hint') or row.get('basis') in ('data-node','data-edge','data-source','data-target','data-from','data-to') for row in obj.get('sceneGroupRoles',[])):relations['explicit_relation_role_ids'].append(key)
        if not css:unsupported.append({'reason':'source_computed_style_metadata_missing','id':key});continue
        if viewport:
            vb=viewport['bbox'];box=obj['bbox']
            if box['x']<vb['x']-.03 or box['y']<vb['y']-.03 or box['x']+box['w']>vb['x']+vb['w']+.03 or box['y']+box['h']>vb['y']+vb['h']+.03:unsupported.append({'reason':'material_source_viewport_clipping_needs_an_explicit_mapping','id':key})
        own=obj.get('sceneAncestry',[])[-1:] or [None]
        for ancestor in obj.get('sceneAncestorOpacity',[]):
            if ancestor['ref'] not in own and abs(ancestor['opacity']-1)>1e-8:unsupported.append({'reason':'group_opacity_compositing_not_proven','id':key,'ancestor':ancestor});break
        for ref in obj.get('sceneAncestry',[]):
            ancestor=ancestors.get(ref,{})
            if ancestor.get('mixBlendMode','normal')!='normal' or ancestor.get('isolation','auto') not in ('auto',None):unsupported.append({'reason':'ancestor_blend_compositing_not_proven','id':key,'ref':ref})
        for use_id in obj.get('sceneUseContexts',[]):
            context=metadata.get('useContexts',{}).get(use_id)
            if not context or context.get('risks') or not context.get('bboxMatches') or context.get('paintRelevantUnforwardedCss') or context.get('selectorRisks'):unsupported.append({'reason':'source_use_instance_mapping_not_proven','id':key,'context':use_id})
        try:
            for channel in ('fill','stroke'):
                alpha=_color_alpha(s.get(channel,'none'))
                if alpha is not None and abs(alpha-1)>1e-8:unsupported.append({'reason':'rgba_alpha_not_in_base_native_paint_mapping','id':key,'channel':channel,'alpha':alpha})
            if obj.get('type')=='shape':
                topology=obj.get('sceneGeometry',{}).get('topology',{})
                if not topology.get('all_subpaths_explicitly_closed'):unsupported.append({'reason':'open_source_path_requires_plot_or_relation_profile','id':key})
                elif not (role['basic'] or role['glyph_use'] or role['collection']):unsupported.append({'reason':'closed_path_requires_an_explicit_role_or_basic_geometry_proof','id':key})
                b=obj['bbox'];thin=max(b['w'],b['h'])>12*max(.01,min(b['w'],b['h'])) and min(b['w'],b['h'])<4
                if thin and not(role['glyph_use'] or role['collection']):unsupported.append({'reason':'thin_closed_paint_may_encode_an_untyped_connector','id':key})
                if obj['tag']=='path' and re.search('[Aa]',obj.get('d') or ''):unsupported.append({'reason':'generic_svg_arc_requires_actual_contour_error_bound','id':key})
                if obj['tag'] in ('circle','ellipse'):
                    a=obj['attrs'];radius=max(a.get('r',0),a.get('rx',0),a.get('ry',0));m=obj['matrix'];scale=max(math.hypot(m[0],m[1]),math.hypot(m[2],m[3]));bound=.000273*radius*scale
                    if bound>.25:unsupported.append({'reason':'cubic_ellipse_contour_error_bound_exceeds_quarter_pixel','id':key,'bound_px':bound})
                if s.get('stroke')!='none' and float(s.get('strokeWidth',0))>0:
                    a,b,c,d,_,_=obj['matrix'];sx,sy=math.hypot(a,b),math.hypot(c,d)
                    if abs(sx-sy)>max(1,sx,sy)*1e-6 or abs(a*c+b*d)>max(1,sx*sy)*1e-6:unsupported.append({'reason':'nonuniform_or_shear_stroke_not_in_base_mapping','id':key})
                    if css.get('vectorEffect','none')!='none' and abs(sx-1)>1e-6:unsupported.append({'reason':'non_scaling_stroke_not_in_base_mapping','id':key})
                    if abs(float(str(css.get('strokeDashoffset','0')).removesuffix('px')))>1e-8:unsupported.append({'reason':'nonzero_dash_offset_not_in_base_mapping','id':key})
                    if s.get('linejoin')=='miter':
                        source=float(css.get('strokeMiterlimit',4));native=float(_style(cells[key]).get('miterlimit',10)) if key in cells else 10;ratios=_miter_ratios(obj)
                        if abs(source-native)>1e-8 and any(min(source,native)-1e-4<ratio<=max(source,native)+1e-4 for ratio in ratios):unsupported.append({'reason':'material_source_native_miter_limit_difference','id':key,'source_limit':source,'native_limit':native})
                if css.get('paintOrder','normal') not in ('normal','fill stroke markers') and s.get('fill')!='none' and s.get('stroke')!='none':unsupported.append({'reason':'nondefault_source_internal_paint_order_not_in_mapping','id':key})
                for stop in obj.get('gradient',{}).get('stops',[]):
                    if _color_alpha(stop['color']) not in (None,1):unsupported.append({'reason':'gradient_stop_rgba_alpha_not_in_base_mapping','id':key})
                converted_style(obj)
            elif obj.get('type')=='text':
                actual=obj.get('sceneText',{}).get('computedCss',css)
                if actual.get('stroke','none')!='none' and float(str(actual.get('strokeWidth','0')).removesuffix('px'))>0:unsupported.append({'reason':'source_text_stroke_not_in_native_text_mapping','id':key})
                if actual.get('fill','none')=='none' or abs(float(actual.get('fillOpacity',1))-1)>1e-8:unsupported.append({'reason':'source_text_fill_alpha_not_in_native_text_mapping','id':key})
                if actual.get('letterSpacing','normal') not in ('normal','0px','0') or actual.get('wordSpacing','0px') not in ('normal','0px','0'):unsupported.append({'reason':'source_text_advance_css_requires_separate_profile','id':key})
            elif obj.get('type')=='image':
                image=obj.get('sceneImage',{});m=obj['matrix']
                if image.get('kind')!='original_raster_asset' or image.get('frames')!=1 or abs(m[1])>1e-8 or abs(m[2])>1e-8 or m[0]<=0 or m[3]<=0 or (image.get('preserveAspectRatio','xMidYMid meet')!='none' and not image.get('intrinsic_ratio_matches_viewport')):unsupported.append({'reason':'original_image_transform_aspect_or_type_unproven','id':key})
            else:unsupported.append({'reason':'unmodeled_source_object_type','id':key})
        except Exception as error:unsupported.append({'reason':'source_style_or_geometry_admission_error','id':key,'error':repr(error)[:300]})
    if relations['declared_nodes'] or any(relations[key] for key in ('edge_object_ids','marker_owner_ids','explicit_relation_role_ids')):unsupported.append({'reason':'source_relations_require_bound_graph_and_native_marker_profile','evidence':relations})
    for issue in dom.get('issues',[]):
        reason=issue.get('reason');targets=[obj for obj in dom.get('objects',[]) if obj.get('sourceId')==issue.get('id')]
        if reason=='fill_paint_server':targets=[obj for obj in targets if obj.get('style',{}).get('fill')==issue.get('value')]
        if reason=='evenodd_requires_review':targets=[obj for obj in targets if obj.get('style',{}).get('fillRule')=='evenodd']
        if reason=='fill_paint_server' and targets and all(obj.get('gradientHandled') for obj in targets):resolved.append({'reason':reason,'resolution':'exact supported two-stop linear gradient mapping'});continue
        if reason=='evenodd_requires_review' and targets and all(_basic_closed_geometry(obj) and len(_ops(obj))==1 for obj in targets):resolved.append({'reason':reason,'resolution':'one convex simple basic contour has identical nonzero/evenodd paint'});continue
        if reason=='use_symbol_aspect_requires_review' and dom.get('sceneMetadata',{}).get('useContexts') and all(not context.get('risks') and context.get('bboxMatches') for context in dom['sceneMetadata']['useContexts'].values()):resolved.append({'reason':reason,'resolution':'actual source instance and exact expansion bbox/style mapping checked'});continue
        if issue.get('severity')=='informational':continue
        unsupported.append({'reason':'unresolved_source_feature','issue':issue})
    return {'ok':not unsupported,'unsupported':unsupported,'roles':roles,'relation_evidence':relations,'resolved_features':resolved}


class _TextMarkup(HTMLParser):
    def __init__(self,size):super().__init__(convert_charrefs=True);self.errors=[];self.size=size
    def handle_starttag(self,tag,attrs):
        if tag not in ('span','font','b','i','br'):self.errors.append('non-source text tag '+tag)
        for name,value in attrs:
            if name.startswith('data-'):continue
            if name in ('face',):continue
            if name=='style':
                for declaration in (value or '').split(';'):
                    if not declaration.strip():continue
                    property,_,setting=declaration.partition(':');property=property.strip().lower();setting=setting.strip().lower()
                    if property not in ('font-family','font-size','font-weight','font-style','text-decoration','line-height','font-synthesis'):self.errors.append('unproved text CSS '+property)
                    elif property=='font-size' and setting not in ('inherit','1em','100%'):
                        try:assert setting.endswith('px') and abs(float(setting[:-2])-self.size)<=.03
                        except Exception:self.errors.append('font-size override differs from source')
            else:self.errors.append('unproved text attribute '+name)


def _native_integrity(dom,xml):
    from auto_quality_source_vector_v2 import _style
    from svg_convert_v2 import style as source_style
    tree=E.fromstring(xml);native_cells=list(tree.iter('mxCell'));cells={cell.get('id'):cell for cell in native_cells};expected={obj['id'] for obj in dom['objects']};errors=[];extras=set(cells)-expected-{'0','1'}
    if len(cells)!=len(native_cells):errors.append({'reason':'duplicate_native_source_object_ids'})
    container=tree.find('.//mxGraphModel/root')
    if container is None or any(cell not in list(container) for cell in native_cells):errors.append({'reason':'native_source_objects_not_in_flat_model_container'})
    for key in ('0','1'):
        layer=cells.get(key)
        if layer is None or layer.get('vertex')=='1' or layer.get('edge')=='1' or layer.get('value') or layer.get('style'):errors.append({'reason':'native_layer_has_unproved_paint_or_structure','id':key})
    if extras:errors.append({'reason':'extra_native_objects_or_unproved_groups','ids':sorted(extras)[:30]})
    for obj in dom['objects']:
        key=obj['id'];cell=cells.get(key)
        if cell is None:continue
        style=_style(cell)
        if any(token.strip() and '=' not in token for token in cell.get('style','').split(';')):errors.append({'reason':'native_named_style_not_in_explicit_source_mapping','id':key})
        geometry=cell.find('mxGeometry')
        if geometry is None or geometry.get('relative','0')!='0' or list(geometry):errors.append({'reason':'native_geometry_has_unproved_relative_or_offset_layout','id':key})
        neutral={'editable','movable','rotatable','resizable','connectable','selectable','deletable','cloneable','autosize','perimeter','outlineConnect'}
        if obj['type']=='shape':allowed=set(source_style(obj))|neutral|{'shape','miterlimit'}
        elif obj['type']=='image':allowed=neutral|{'shape','image','imageAspect','opacity'}
        else:allowed=neutral|{'shape','html','align','verticalAlign','spacing','spacingTop','spacingBottom','spacingLeft','spacingRight','labelPosition','verticalLabelPosition','whiteSpace','overflow','strokeColor','fillColor','fontFamily','fontSize','fontColor','fontStyle','fontSource','opacity','rotation','textOpacity','noLabel','fontBackgroundColor','fontBorderColor','shadow'}
        unmodeled=set(style)-allowed
        if unmodeled:errors.append({'reason':'native_paint_style_has_unproved_extra_effects','id':key,'properties':sorted(unmodeled)})
        if style.get('shadow','0')!='0':errors.append({'reason':'native_shadow_not_in_closed_source_mapping','id':key})
        if obj['type']!='text' and cell.get('value','').strip():errors.append({'reason':'extra_native_label_on_source_nontext_paint','id':key})
        if cell.get('vertex')!='1' or cell.get('edge')=='1':errors.append({'reason':'source_paint_not_a_native_editable_vertex','id':key})
        parent=cell.get('parent');seen=set()
        while parent in cells and parent not in seen:
            seen.add(parent);ancestor=cells[parent]
            if ancestor.get('visible')=='0' or ancestor.get('collapsed')=='1':errors.append({'reason':'source_object_hidden_by_native_ancestor','id':key,'ancestor':parent})
            parent=ancestor.get('parent')
        if cell.get('visible')=='0' or cell.get('collapsed')=='1':errors.append({'reason':'source_native_object_hidden','id':key})
        if obj['type'] in ('shape','image') and (abs(float(style.get('rotation',0)))>1e-8 or any(style.get(name,'0') not in ('0','false','') for name in ('flipH','flipV'))):errors.append({'reason':'additional_native_transform_on_baked_source_geometry','id':key})
        if cell.get('parent')!='1':errors.append({'reason':'native_parent_geometry_not_in_flat_source_contract','id':key})
        if obj['type']!='image' and style.get('image'):errors.append({'reason':'raster_asset_or_wrapper_hidden_in_nonimage_object','id':key})
        if any(style.get(name)=='0' for name in ('editable','movable')):errors.append({'reason':'native_source_object_locked_against_editing','id':key})
        if obj['type']=='text':
            if style.get('noLabel','0')=='1' or abs(float(style.get('textOpacity',100))-100)>1e-8 or style.get('fontBackgroundColor','none')!='none' or style.get('fontBorderColor','none')!='none' or style.get('fillColor','none')!='none' or style.get('strokeColor','none')!='none':errors.append({'reason':'native_text_hidden_or_extra_background_paint','id':key})
            if bool(int(style.get('fontStyle',0))&4)!=bool(obj.get('underline')):errors.append({'reason':'native_source_text_underline_changed','id':key})
            for name,allowed in [('align',('left',)),('verticalAlign',('middle',)),('whiteSpace',('nowrap',)),('overflow',('visible',))]:
                if name in style and style[name] not in allowed:errors.append({'reason':'native_text_layout_not_in_source_mapping','id':key,'property':name})
            for name in ('spacing','spacingTop','spacingBottom','spacingLeft','spacingRight','labelPosition','verticalLabelPosition'):
                if name in style and style[name] not in ('0','center','middle'):errors.append({'reason':'native_text_layout_not_in_source_mapping','id':key,'property':name})
            markup=_TextMarkup(float(obj['fontSize']));markup.feed(cell.get('value',''))
            if markup.errors:errors.append({'reason':'native_text_markup_has_unproved_paint_or_layout','id':key,'issues':markup.errors})
    order=[cell.get('id') for cell in E.fromstring(xml).iter('mxCell') if cell.get('id') in expected];rank={key:index for index,key in enumerate(order)};inversions=[]
    def bounds(obj):
        box=obj['bbox'];stroke=float(obj.get('style',{}).get('strokeWidth',0)) if obj.get('style',{}).get('stroke')!='none' else 0;matrix=obj.get('matrix',[1,0,0,1,0,0]);pad=stroke*max(math.hypot(matrix[0],matrix[1]),math.hypot(matrix[2],matrix[3]))*5;return box['x']-pad,box['y']-pad,box['x']+box['w']+pad,box['y']+box['h']+pad
    boxes=[bounds(obj) for obj in dom['objects']]
    for i,a in enumerate(dom['objects']):
        for j in range(i+1,len(dom['objects'])):
            b=dom['objects'][j];ba,bb=boxes[i],boxes[j]
            if min(ba[2],bb[2])>max(ba[0],bb[0]) and min(ba[3],bb[3])>max(ba[1],bb[1]) and rank.get(a['id'],-1)>rank.get(b['id'],-1):inversions.append([a['id'],b['id']])
    if inversions:errors.append({'reason':'overlapping_source_native_paint_order_changed','pairs':inversions[:30]})
    return {'ok':not errors,'errors':errors,'native_source_object_ids':len(expected),'overlapping_order_inversions':len(inversions)}


def check_scene_coverage(dom,xml,expected_translation=(0,0)):
    """Pure checker for tests and hashed fresh-source capture callers."""
    import auto_quality_source_vector_v2 as prior
    result={'supported':False,'ok':False,'profile':POLICY,'failures':[],'evidence':{}}
    try:
        admission=_source_admission(dom,xml);result['evidence']['source_admission']=admission
        if not admission['ok']:result['failures']=admission['unsupported'];return result
        result['supported']=True
        if not any(obj['type'] in ('shape','text') for obj in dom.get('objects',[])):result['failures'].append({'reason':'no_meaningful_editable_source_paint_raster_only_or_empty'})
        inventory=prior._graphviz_coverage(dom,xml,{})
        paint=prior._paint_coverage(dom,xml)
        actual_translation=[paint['source_layout_translation'][axis] for axis in ('dx','dy')]
        if any(abs(a-b)>.03 for a,b in zip(actual_translation,expected_translation)):paint['errors'].append({'reason':'source_translation_lacks_verified_reference_canvas_anchor','expected':list(expected_translation),'actual':actual_translation});paint['ok']=False
        integrity=_native_integrity(dom,xml)
        result['failures']+=inventory['errors']+paint['errors']+integrity['errors'];result['ok']=not result['failures'];result['evidence'].update(source_object_inventory=inventory,complete_native_source_paint=paint,native_visibility_transform_and_paint_order=integrity,source_relations_not_silently_reclassified=True,actual_native_font_source_and_original_image_gates_required=True)
    except Exception as error:result['failures'].append({'reason':'closed_source_scene_validation_error','error':repr(error)[:1200]})
    return result


def check_svg_profile(record,xml):
    import auto_quality_source_vector_v2 as prior
    result={'supported':False,'ok':False,'profile':POLICY,'failures':[],'evidence':{}}
    try:
        assert record.get('source_format')=='svg','Direct SVG source required';prior._identity(record,xml);dom=capture_closed_scene(record);capture=dom['sceneCapture'];assert capture['completeOfflineSource'] and capture['sourceCodeSha256']==record['source_code_sha256'] and capture['sourceImageSha256']==record['source_image_sha256']
        reference=prior._read_clean(record['original_reference'],record['source_image_sha256'])
        try:from auto_quality_common_v4 import registration_record
        except ImportError:from auto_quality_common_v3 import registration_record
        verified,contract=registration_record(record,reference,xml);offset=contract['original_page_offset'] if contract else [0,0]
        result=check_scene_coverage(dom,xml,offset)
        if result['supported']:
            from auto_quality_common import resource_checks
            reference=prior._read_clean(record['original_reference'],record['source_image_sha256']);result['evidence']['original_asset_resources']=resource_checks(R,record,xml,reference)
        result['evidence'].update(current_code_sha256=sha(xml.encode()),source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],fresh_source_capture=capture,fresh_source_dom_sha256=sha(json.dumps(dom,sort_keys=True,ensure_ascii=False).encode()),scope='Closed/source-role native paint coverage only. Does not waive graph/marker relationships, font-source equivalence, strict native rendering or any original-image fidelity gate.')
    except Exception as error:
        result['ok']=False
        result['failures'].append({'reason':'closed_source_scene_capture_or_identity_error','error':repr(error)[:1200]})
    return result
