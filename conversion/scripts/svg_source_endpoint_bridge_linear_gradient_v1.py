"""Supply parser-derived source endpoint facts to read-only scene observations."""
import hashlib,json
from pathlib import Path
from fontTools.pens.recordingPen import RecordingPen
from fontTools.svgLib.path import parse_path
from svg_source_endpoint_direction_v1 import directions,_SVGArc

DIRECTORY=Path(__file__).parent


def _path(descriptor):
    from svg_convert_v2 import path_for
    path=path_for(descriptor)
    if descriptor['tag']=='path'and(descriptor.get('cssDDeclared') or descriptor.get('computedD')=='none'):
        raise ValueError('source_marker_css_path_override_requires_separate_compiler')
    return path


def capture(page,legacy=False):
    describe=(DIRECTORY/'svg_source_endpoint_descriptors_v1.js').read_text()
    rows=page.evaluate('()=>('+describe+')(document.querySelector("svg")).map(({index,descriptor})=>({index,descriptor}))')
    facts=[dict(index=row['index'],descriptor=row['descriptor'],
                direction=directions(_path(row['descriptor']),row['descriptor']['matrix']))for row in rows]
    path=DIRECTORY/('svg_dom_v7.js'if legacy else'svg_dom_linear_gradient_v1.js')
    script=path.read_text()
    if script.count('__SOURCE_ENDPOINT_DESCRIPTORS_V1__')!=1:
        raise ValueError('source_endpoint_bridge_template_changed')
    script=script.replace('__SOURCE_ENDPOINT_DESCRIPTORS_V1__',describe)
    result=page.evaluate(script,facts)
    result['sourceEndpointDirection']={
        'method':'SVG2_analytic_open_path_endpoint_direction_v1',
        'owners':len(facts),'facts_sha256':hashlib.sha256(json.dumps(facts,sort_keys=True).encode()).hexdigest(),
        'composed_extractor_sha256':hashlib.sha256(script.encode()).hexdigest(),
        'actual_owner_descriptors_rechecked':True,'source_DOM_attributes_changed':False}
    return result
