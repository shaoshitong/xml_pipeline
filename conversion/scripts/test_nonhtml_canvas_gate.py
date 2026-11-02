import json,xml.etree.ElementTree as E
from native_worker import R,W,native,now
from strict_canvas_gate import require_declared_page
B=W/'nonhtml_canvas_gate_tests';B.mkdir(exist_ok=True);results=[]
for color,should_pass in [('#ffffff',True),('#fefefe',False)]:
 root=E.Element('mxfile');model=E.SubElement(E.SubElement(root,'diagram'),'mxGraphModel',page='1',pageWidth='120',pageHeight='80');cr=E.SubElement(model,'root');E.SubElement(cr,'mxCell',id='0');E.SubElement(cr,'mxCell',id='1',parent='0')
 for id,x,y,w,h,fill in [('outside',10,-2,40,1,color),('inside',20,20,40,20,'#000000')]:
  c=E.SubElement(cr,'mxCell',id=id,parent='1',vertex='1',style='shape=rectangle;fillColor='+fill+';strokeColor=none;');E.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),**{'as':'geometry'})
 xml=E.tostring(root,encoding='unicode');r=native.native_job(xml,120,80,90,W/'rendering_fontproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert r['ok'];accepted=True
 try:require_declared_page(r['native_render'],120,80)
 except AssertionError:accepted=False
 assert accepted==should_pass;name='white_bounds' if should_pass else 'faint_visible_overflow';(B/(name+'.drawio')).write_text(xml);(B/(name+'.png')).write_bytes(r['png']);(B/(name+'_render.json')).write_text(json.dumps(r['native_render'],indent=2));results.append({'fixture':name,'gate_accepted':accepted,'expected':should_pass,'boundary':r['native_render']['outside_page_pixel_audit'],'selected_image':r['native_render']['selected_image']})
out={'at':now(),'ok':True,'scope':'Actual official native-render positive and near-white outside-page negative fixtures exercise the same publication canvas gate. No dataset record changed.','results':results};(W/'nonhtml_canvas_overflow_rejection.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
