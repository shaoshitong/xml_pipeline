"""Exact single-fill leaf alpha, including native closed polygons; opaque ancestors required."""
import math
import xml.etree.ElementTree as ET

def prove(dom,xml):
    from svg_convert_v3 import unpack
    cells={c.get('id'):c for c in ET.fromstring(xml).iter('mxCell')}
    ancestors=dom.get('sceneMetadata',{}).get('ancestors',{})
    proved={};rejected={}
    for obj in dom['objects']:
        style=obj.get('style',{});alpha=float(style.get('opacity',1))
        if abs(alpha-1)<=1e-8:continue
        key=obj['id']
        try:
            assert math.isfinite(alpha) and 0<alpha<1,'invalid_leaf_alpha'
            assert obj['type']=='shape' and obj['tag'] in ('rect','circle','ellipse','polygon'),'only_single_primitive_fill_supported'
            assert style.get('fill')!='none' and style.get('stroke')=='none','fill_and_stroke_need_separate_compositing'
            assert not obj.get('sceneUseContexts') and not obj.get('sceneMarkerContexts') and not obj.get('markerOwner'),'composed_use_or_marker_requires_separate_alpha_proof'
            lineage=obj['sceneAncestry'];assert lineage and ancestors[lineage[-1]]['tag']==obj['tag'],'leaf_identity_unproved'
            assert all(abs(float(ancestors[ref]['opacity'])-1)<=1e-8 for ref in lineage[:-1]),'ancestor_group_alpha_requires_compositing'
            assert abs(float(ancestors[lineage[-1]]['opacity'])-alpha)<=1e-8,'source_leaf_alpha_differs'
            css=obj['sceneComputedCss'];assert css['mixBlendMode']=='normal' and css['isolation']=='auto' and all(css[k]=='none'for k in ('filter','clipPath','maskImage')),'effect_requires_separate_compositing'
            cell=cells[key];native=unpack(cell.get('style',''))
            assert cell.get('vertex')=='1' and native.get('shape','').startswith('stencil('),'native_leaf_not_single_stencil'
            assert native.get('strokeColor')=='none' and native.get('fillColor') not in ('none',None),'native_single_fill_mapping_missing'
            assert abs(float(native.get('opacity','100'))/100-alpha)<=1e-8,'native_leaf_alpha_changed'
            assert abs(float(native.get('fillOpacity','100'))/100-float(style['fillOpacity']))<=1e-8,'native_fill_alpha_changed'
            proved[key]=dict(source_opacity=alpha,native_opacity=float(native['opacity'])/100,source_leaf_ref=lineage[-1],opaque_ancestors=len(lineage)-1,fill_only=True,group_opacity_allowed=False,method='single_fill_primitive_uniform_alpha_exact_v2')
        except (AssertionError,KeyError,ValueError,TypeError)as error:rejected[key]=str(error)
    return dict(proved=proved,rejected=rejected)

def source_features(core,dom,size,xml):
    result=core.source_features(dom,size);proof=prove(dom,xml)
    result['failures']=[f for f in result['failures']if not(f.get('reason')=='source_element_or_ancestor_opacity_requires_compositing_frontend'and f.get('id')in proof['proved'])]
    result['ok']=not result['failures'];result['single_fill_leaf_opacity_proof']=proof
    return result
