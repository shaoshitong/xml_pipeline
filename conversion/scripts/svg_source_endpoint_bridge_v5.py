"""Analytic facts for exact original and expanded use-instance descriptors.

Every instance is observed in its actual composed matrix. Python parses only
source geometry; candidate geometry, sampled tangents and reference pixels are
never used. All legacy source-scene rejection gates are retained.
"""
import hashlib
import json
from pathlib import Path
from svg_source_endpoint_bridge_v1 import _path
from svg_source_endpoint_direction_v1 import directions
D=Path(__file__).parent


def _capture(scratch,legacy,symbols):
    page=scratch
    describe=(D/'svg_source_endpoint_descriptors_v1.js').read_text()
    rows=page.evaluate('()=>('+describe+')(document.querySelector("svg")).map(({index,descriptor})=>({index,descriptor}))')
    facts=[dict(index=row['index'],descriptor=row['descriptor'],direction=directions(_path(row['descriptor']),row['descriptor']['matrix']))for row in rows]
    path=D/('svg_dom_v11.js'if legacy else'svg_dom_source_scene_v6.js')
    script=path.read_text()
    if script.count('__SOURCE_RESOLVED_GEOMETRY_V1__')!=1:raise ValueError('source_geometry_bridge_template_changed')
    script=script.replace('__SOURCE_RESOLVED_GEOMETRY_V1__',(D/'svg_resolved_geometry_v1.js').read_text())
    if script.count('__SOURCE_ENDPOINT_DESCRIPTORS_V1__')!=1:raise ValueError('source_endpoint_bridge_template_changed')
    script=script.replace('__SOURCE_ENDPOINT_DESCRIPTORS_V1__',describe)
    script=script.replace('__SOURCE_SYMBOL_VIEWPORT_BUILDER_V1__',(D/'svg_source_symbol_viewport_v1.js').read_text())
    instances={}
    for passes in range(10):
        result=page.evaluate(script,dict(owners=facts,instances=list(instances.values()),symbols=symbols))
        requests=result.pop('sourceEndpointRequests')
        if not requests:break
        before=len(instances)
        for descriptor in requests:
            key=json.dumps(descriptor,separators=(',',':'))
            if key not in instances:
                instances[key]=dict(descriptor=descriptor,direction=directions(_path(descriptor),descriptor['matrix']))
        if len(instances)==before:raise ValueError('source_instance_endpoint_observation_not_converging')
    else:raise ValueError('source_instance_endpoint_observation_depth_exceeded')
    result['sourceEndpointDirection']=dict(method='SVG2_analytic_original_and_exact_use_instance_endpoint_direction_v2',
        owners=len(facts),instances=len(instances),observation_passes=passes+1,
        facts_sha256=hashlib.sha256(json.dumps(dict(owners=facts,instances=list(instances.values()),symbols=symbols),sort_keys=True).encode()).hexdigest(),
        composed_extractor_sha256=hashlib.sha256(script.encode()).hexdigest(),
        actual_owner_descriptors_rechecked=True,actual_instance_descriptors_rechecked=True,
        source_DOM_attributes_changed=False,candidate_or_reference_pixels_used=False)
    return result


def capture(page,legacy=False):
    from svg_source_symbol_viewport_v1 import collect
    # Cache fresh facts only on this immutable original observer page.
    if not hasattr(page,'_source_symbol_facts_v1'):
        page._source_symbol_facts_v1=collect(page)
    scratch=page.context.new_page()
    try:
        scratch.set_viewport_size(page.viewport_size)
        scratch.set_content(page.content())
        scratch.evaluate('()=>document.fonts.ready')
        result=_capture(scratch,legacy,page._source_symbol_facts_v1)
        result['sourceSymbolViewportFacts']=page._source_symbol_facts_v1
        return result
    finally:scratch.close()
