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


def capture(page,legacy=False):
    describe=(D/'svg_source_endpoint_descriptors_v1.js').read_text()
    rows=page.evaluate('()=>('+describe+')(document.querySelector("svg")).map(({index,descriptor})=>({index,descriptor}))')
    facts=[dict(index=row['index'],descriptor=row['descriptor'],direction=directions(_path(row['descriptor']),row['descriptor']['matrix']))for row in rows]
    path=D/('svg_dom_v8.js'if legacy else'svg_dom_source_scene_v3.js')
    script=path.read_text()
    if script.count('__SOURCE_ENDPOINT_DESCRIPTORS_V1__')!=1:raise ValueError('source_endpoint_bridge_template_changed')
    script=script.replace('__SOURCE_ENDPOINT_DESCRIPTORS_V1__',describe)
    instances={}
    for passes in range(10):
        result=page.evaluate(script,dict(owners=facts,instances=list(instances.values())))
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
        facts_sha256=hashlib.sha256(json.dumps(dict(owners=facts,instances=list(instances.values())),sort_keys=True).encode()).hexdigest(),
        composed_extractor_sha256=hashlib.sha256(script.encode()).hexdigest(),
        actual_owner_descriptors_rechecked=True,actual_instance_descriptors_rechecked=True,
        source_DOM_attributes_changed=False,candidate_or_reference_pixels_used=False)
    return result
