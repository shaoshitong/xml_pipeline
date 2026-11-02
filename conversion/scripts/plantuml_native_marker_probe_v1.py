"""Actual mxMarker paint/endpoint/orientation editing probe, no publication."""
import hashlib,math,re,xml.etree.ElementTree as E
from pathlib import Path
from tikz_execution_binding_v2 import VIEWER_SHA256,native_marker_polygon

SCRIPT=r'''async a=>{
document.body.innerHTML='<div id="g" style="width:8192px;height:8192px;position:relative"></div>';
const calls=[],factory=mxMarker.createMarker;
mxMarker.createMarker=function(canvas,shape,type,pe,ux,uy,size,source,sw,filled){
 const point={x:pe.x,y:pe.y},unit={x:ux,y:uy},state={dx:canvas.state.dx,dy:canvas.state.dy,scale:canvas.state.scale},edge=shape.state.cell.id;
 const draw=factory.apply(this,arguments);if(!draw)return draw;
 return function(){const before=new Set([...canvas.root.childNodes]);draw();const nodes=[...canvas.root.childNodes].filter(n=>!before.has(n));calls.push({edge,type,side:source?'start':'end',point,unit,size,stroke:sw,filled,canvas:state,paint:nodes.flatMap(n=>[...(n.matches?.('path')?[n]:[]),...n.querySelectorAll?.('path')||[]]).map(n=>({d:n.getAttribute('d'),fill:n.getAttribute('fill'),stroke:n.getAttribute('stroke'),transform:n.getAttribute('transform'),computed:{fill:getComputedStyle(n).fill,stroke:getComputedStyle(n).stroke,strokeWidth:getComputedStyle(n).strokeWidth,strokeLinejoin:getComputedStyle(n).strokeLinejoin,strokeMiterlimit:getComputedStyle(n).strokeMiterlimit,strokeLinecap:getComputedStyle(n).strokeLinecap,opacity:getComputedStyle(n).opacity,fillOpacity:getComputedStyle(n).fillOpacity,strokeOpacity:getComputedStyle(n).strokeOpacity}}))});};
};
const g=new Graph(document.getElementById('g')),doc=mxUtils.parseXml(a.xml);new mxCodec(doc).decode(doc.getElementsByTagName('mxGraphModel')[0],g.model);
function render(){calls.length=0;g.refresh();g.view.validate();return a.markers.map(m=>{let call=calls.filter(c=>c.edge===m.edge&&c.side===m.side).at(-1);if(!call)throw Error('Missing actual native marker paint '+m.edge+' '+m.side);const es=g.view.getState(g.model.cells[m.edge]);return {...call,absolutePoints:es.absolutePoints.map(p=>({x:p.x,y:p.y}))};});}
g.view.validate();await document.fonts.ready;const initial=render(),probes=[];
for(let i=0;i<a.markers.length;i++){
 const m=a.markers[i],edge=g.model.cells[m.edge],source=m.side==='start',terminal=g.model.getTerminal(edge,source),owner=terminal||edge,original=owner.geometry.clone(),moved=original.clone();if(terminal){moved.x+=17;moved.y+=11;}else{const point=original.getTerminalPoint(source);if(!point)throw Error('Missing explicit source coordinate endpoint');moved.setTerminalPoint(new mxPoint(point.x+17,point.y+11),source);}
 g.model.beginUpdate();g.model.setGeometry(owner,moved);g.model.endUpdate();const translated=render()[i];
 g.model.beginUpdate();g.model.setGeometry(owner,original);g.model.endUpdate();const restored=render()[i];
 const old=edge.geometry.clone(),turned=old.clone(),points=(turned.points||[]).map(p=>p.clone()),es=g.view.getState(edge),end=es.absolutePoints[source?0:es.absolutePoints.length-1];
 if(points.length){const j=source?0:points.length-1;points[j]=new mxPoint(end.x+(source?19:-19),end.y+23);turned.points=points;}
 else{turned.points=[new mxPoint(end.x+(source?19:-19),end.y+23)];}
 g.model.beginUpdate();g.model.setGeometry(edge,turned);g.model.endUpdate();const oriented=render()[i];
 g.model.beginUpdate();g.model.setGeometry(edge,old);g.model.endUpdate();const final=render()[i];probes.push({edge:m.edge,side:m.side,terminal:terminal?.id||null,initial:initial[i],translated,restored,oriented,final});
}
g.destroy();mxMarker.createMarker=factory;return {probes,nativeFactoryActuallyExecuted:true};}'''

def validate_paint(call):
    if call['type'] not in ('classic','classicThin','block','blockThin'):raise ValueError('Unsupported actual native marker factory')
    expected,_=native_marker_polygon(call['type'],call['size'],call['stroke'],(call['point']['x'],call['point']['y']),(call['unit']['x'],call['unit']['y']));state=call['canvas'];expected=[((x+state['dx'])*state['scale'],(y+state['dy'])*state['scale']) for x,y in expected];paths=[p for p in call['paint'] if p['fill'] not in ('none',None)]
    if len(paths)!=1:raise ValueError('Actual native filled marker path missing or compound')
    path=paths[0]
    if path['transform']:raise ValueError('Unproven extra native marker paint transform')
    if re.search(r'[^MLZmlz\d.,\s+eE-]',path['d']):raise ValueError('Actual native marker is not a line-only polygon')
    numbers=list(map(float,re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',path['d'])));actual=list(zip(numbers[::2],numbers[1::2]));distance=max(max(min(math.dist(p,q) for q in actual) for p in expected),max(min(math.dist(p,q) for q in expected) for p in actual))
    if distance>.03:raise ValueError('Actual native marker paint differs from pinned factory geometry: '+str(distance))
    return {'actual_native_paint_matches_pinned_factory':True,'maximum_vertex_error_px':distance,'fill':path['fill'],'stroke':path['stroke']}

def audit(xml,markers,runtime=None,reference_offset=(0,0)):
    if runtime is None:
        from native_worker import R,native
        runtime=native.renderer_path(R).parent/'assets/viewer-static.min.js'
    runtime=Path(runtime)
    if hashlib.sha256(runtime.read_bytes()).hexdigest()!=VIEWER_SHA256:raise ValueError('Native marker editing viewer SHA mismatch')
    from svg_source_scene_dom_v1 import _browser
    browser=_browser();page=browser.new_page()
    try:
        page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(runtime));raw=page.evaluate(SCRIPT,{'xml':xml,'markers':markers})
    finally:page.close()
    checked=[];cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')}
    from svg_convert_v3 import unpack
    for probe,marker in zip(raw['probes'],markers):
        paints={key:validate_paint(probe[key]) for key in ('initial','translated','restored','oriented','final')};before=probe['initial'];after=probe['translated'];restored=probe['restored'];oriented=probe['oriented'];final=probe['final'];delta=[after['point'][axis]-before['point'][axis] for axis in ('x','y')]
        expected_axis=marker['source_geometry']['axis'];actual_axis=[before['unit'][axis] for axis in ('x','y')]
        if sum(a*b for a,b in zip(expected_axis,actual_axis))<.97:raise ValueError('Initial actual native marker points away from its source marker tangent')
        actual_tip=[before['point'][axis]-before['unit'][axis]*before['stroke']*1.118 for axis in ('x','y')];expected_tip=[marker['source_geometry']['tip'][i]+reference_offset[i] for i in (0,1)]
        # Four-point source fitting permits a bounded source-geometric tip shift.
        # Whole actual closed paint is independently certified by the caller.
        if math.dist(actual_tip,expected_tip)>1+1e-8:raise ValueError('Initial actual native marker tip displacement exceeds one source pixel')
        source_style=unpack(cells[marker['edge']].get('style'));expected_fill=source_style.get(marker['side']+'FillColor',source_style.get('strokeColor'))
        if paints['initial']['fill']!=expected_fill:raise ValueError('Initial actual native marker fill differs from the source-bound XML')
        if abs(delta[0]-17)>.03 or abs(delta[1]-11)>.03:raise ValueError('Native marker endpoint did not follow its actual source terminal')
        for key in ('point','unit','paint'):
            if before[key]!=restored[key] or before[key]!=final[key]:raise ValueError('Native marker editing failed exact restoration')
        if math.hypot(oriented['unit']['x']-before['unit']['x'],oriented['unit']['y']-before['unit']['y'])<.001:raise ValueError('Native marker did not reorient with its edited shaft')
        if before['paint']==oriented['paint']:raise ValueError('Native marker paint stayed floating after shaft direction edit')
        checked.append({'edge':probe['edge'],'side':probe['side'],'terminal':probe['terminal'],'endpoint_translation':delta,'actual_paints':paints,'initial_actual_source_tangent_tip_and_fill_verified':True,'terminal_move_and_shaft_rotation_followed':True,'full_restoration_exact':True})
    if not checked:raise ValueError('No native marker editing probes')
    return {'ok':True,'policy':'actual_native_classic_factory_bound_endpoint_and_rotation_editing_v1','viewer_sha256':VIEWER_SHA256,'markers':checked,'raw':raw,'accepted':False}
