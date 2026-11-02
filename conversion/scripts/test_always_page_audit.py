import json,base64,zlib,urllib.parse,xml.etree.ElementTree as E
from native_worker import R,W,native,now
from strict_canvas_gate import require_declared_page
B=W/'always_page_audit_tests';B.mkdir(exist_ok=True);results=[]
for spill in [False,True]:
 shape=f'<shape name="boundary_probe" w="100" h="100" aspect="variable" strokewidth="inherit"><foreground><rect x="{-20 if spill else 0}" y="0" w="{120 if spill else 100}" h="100"/><fill/></foreground></shape>';z=zlib.compressobj(wbits=-15);v=urllib.parse.quote(shape,safe="~()*!.'-").encode();payload=base64.b64encode(z.compress(v)+z.flush()).decode();root=E.Element('mxfile');m=E.SubElement(E.SubElement(root,'diagram'),'mxGraphModel',page='1',pageWidth='120',pageHeight='80');cr=E.SubElement(m,'root');E.SubElement(cr,'mxCell',id='0');E.SubElement(cr,'mxCell',id='1',parent='0');c=E.SubElement(cr,'mxCell',id='probe',parent='1',vertex='1',style='shape=stencil('+payload+');fillColor=#fefefe;strokeColor=none;');E.SubElement(c,'mxGeometry',x='5',y='20',width='40',height='20',**{'as':'geometry'});xml=E.tostring(root,encoding='unicode');r=native.native_job(xml,120,80,90,W/'rendering_fullpage_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert r['ok'];info=r['native_render'];assert not info['native_graph_bounds_outside_declared_canvas'];gate=True
 try:require_declared_page(info,120,80)
 except AssertionError:gate=False
 assert gate==(not spill)
 assert (info['outside_page_pixel_audit']['nonwhite_outside_pixels']>0)==spill;name='stencil_spill' if spill else 'inside_stencil';(B/(name+'.drawio')).write_text(xml);(B/(name+'.png')).write_bytes(r['png']);(B/(name+'_render.json')).write_text(json.dumps(info,indent=2));results.append({'fixture':name,'graph_bounds_inside_page':True,'painted_outside_pixels':info['outside_page_pixel_audit']['nonwhite_outside_pixels'],'gate_accepted':gate})
out={'at':now(),'ok':True,'results':results};(W/'always_page_audit_tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
