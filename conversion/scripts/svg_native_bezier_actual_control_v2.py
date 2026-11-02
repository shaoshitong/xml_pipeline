from pathlib import Path
import sys,json,uuid,hashlib,xml.etree.ElementTree as E,math
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
from svg_native_bezier_ir_v1 import compile_path
from playwright.sync_api import sync_playwright
from portable_native_fonts import ready_page
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
fixtures=['M20 80 C20 20 140 20 140 80','M20 90 Q80 20 150 100','M20 30 L40 30 Q80 30 80 70 C80 110 140 110 140 70']
script=r'''xml=>{document.body.style.margin='0';document.body.innerHTML='<div id="p" style="position:absolute;left:0;top:0;width:256px;height:256px"></div>';const graph=new Graph(document.getElementById('p'));new mxCodec(mxUtils.parseXml(xml)).decode(mxUtils.parseXml(xml).documentElement,graph.model);graph.refresh();graph.view.validate();const cell=graph.model.getCell('curve'),state=graph.view.getState(cell),paint=()=>[...graph.view.getState(cell).shape.node.querySelectorAll('path')].filter(p=>p.getAttribute('stroke')==='#123456').map(p=>p.getAttribute('d'));const initialDOM=state.shape.node.outerHTML;const before=paint(),beforeModel=mxUtils.getXml(new mxCodec().encode(graph.model));const original=cell.geometry.clone(),changed=cell.geometry.clone();changed.targetPoint.x+=13;graph.model.setGeometry(cell,changed);graph.view.validate();const moved=paint();graph.model.setGeometry(cell,original);graph.view.validate();const restored=paint(),afterModel=mxUtils.getXml(new mxCodec().encode(graph.model));const result={before,moved,restored,initialDOM,actualPointCount:state.absolutePoints.length,svgOffset:state.shape.getSvgScreenOffset(),bezier:state.style.bezier,changed:JSON.stringify(before)!==JSON.stringify(moved),restoredExact:JSON.stringify(before)===JSON.stringify(restored),modelRestoredExact:beforeModel===afterModel};graph.destroy();return result;}'''
work=W/'svg_native_bezier_actual_controls_v1'/uuid.uuid4().hex;work.mkdir(parents=True);rows=[]
with sync_playwright()as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 try:
  page=ready_page(browser)
  for index,source in enumerate(fixtures):
   ir=compile_path(source);points=ir['points'];root=E.Element('mxGraphModel');r=E.SubElement(root,'root');E.SubElement(r,'mxCell',id='0');E.SubElement(r,'mxCell',id='1',parent='0');cell=E.SubElement(r,'mxCell',id='curve',edge='1',parent='1',style='edgeStyle=none;shape=connector;bezier=1;curved=0;rounded=0;jumpStyle=none;startArrow=none;endArrow=none;strokeColor=#123456;strokeWidth=1;');g=E.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'});E.SubElement(g,'mxPoint',x=repr(points[0][0]),y=repr(points[0][1]),attrib={'as':'sourcePoint'});E.SubElement(g,'mxPoint',x=repr(points[-1][0]),y=repr(points[-1][1]),attrib={'as':'targetPoint'});b=E.SubElement(g,'Array',attrib={'as':'points'});
   for point in points[1:-1]:E.SubElement(b,'mxPoint',x=repr(point[0]),y=repr(point[1]))
   xml=E.tostring(root,encoding='unicode');actual=page.evaluate(script,xml);assert actual['changed']and actual['restoredExact']and actual['modelRestoredExact'],actual;assert actual['bezier']==1 or actual['bezier']=='1';assert actual['actualPointCount']==len(points);assert len(actual['before'])==1,actual
   pen=RecordingPen();parse_path(actual['before'][0],pen);controls=[]
   for op,values in pen.value:
    assert op in ('moveTo','curveTo','endPath'),op
    controls.extend(list(v)for v in values)
   assert len(controls)==len(points),(len(controls),len(points));error=max(math.dist(a,b)for a,b in zip(controls,points));assert error<=.03,error
   rows.append(dict(fixture=index,actual_point_count=len(points),source_curve_count=len(ir['subdivisions']),actual_cubic_segments=sum(op=='curveTo'for op,_ in pen.value),maximum_actual_control_error_px=error,actual_endpoint_edit_and_model_paint_restore=True,source_IR=ir,actual=actual));(work/('fixture_'+str(index)+'.drawio')).write_text(xml)
 finally:browser.close()
proof=dict(schema='actual_official_native_bezier_controls_v1',rows=rows,normal_dataset_conversion_calls=0,target_reference_pixels_used=False,model_calls=0,goal_complete=False);path=work/'proof.json';path.write_text(json.dumps(proof,indent=2));print(json.dumps(dict(file=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cases=[{k:r[k]for k in ('fixture','actual_point_count','source_curve_count','actual_cubic_segments','maximum_actual_control_error_px','actual_endpoint_edit_and_model_paint_restore')}for r in rows],normal_calls=0)))
