import json,xml.etree.ElementTree as E
from native_worker import R,W,native,now
root=E.Element('mxfile');model=E.SubElement(E.SubElement(root,'diagram'),'mxGraphModel',page='1',pageWidth='120',pageHeight='80');r=E.SubElement(model,'root');E.SubElement(r,'mxCell',id='0');E.SubElement(r,'mxCell',id='1',parent='0')
for id,x,y,w,h,color in [('faint',10,-2,40,1,'#fefefe'),('black',20,20,40,20,'#000000')]:
 c=E.SubElement(r,'mxCell',id=id,parent='1',vertex='1',style='shape=rectangle;fillColor='+color+';strokeColor=none;');E.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),**{'as':'geometry'})
xml=E.tostring(root,encoding='unicode');result={'at':now()}
for version in ['rendering_fontproof_v2','rendering_fontproof_strict']:
 out=native.native_job(xml,120,80,90,W/version/'remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert out['ok'];info=out['native_render'];result[version]={k:info.get(k) for k in ['outside_page_pixel_audit','content_outside_declared_canvas','selected_image','output_size']}
assert result['rendering_fontproof_v2']['outside_page_pixel_audit']['nonwhite_outside_pixels']==0
assert result['rendering_fontproof_strict']['outside_page_pixel_audit']['nonwhite_outside_pixels']>0 and result['rendering_fontproof_strict']['content_outside_declared_canvas'];result['ok']=True;(W/'strict_native_bounds_test.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
