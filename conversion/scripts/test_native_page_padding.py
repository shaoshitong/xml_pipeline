import io,json,xml.etree.ElementTree as E
from PIL import Image
from native_worker import W,now
from native_page_padding import shift
from native_padding_proof import render,verify_cells,plan_from_pixels,exact_pixel_proof
from strict_canvas_gate import require_declared_page
root=E.Element('mxfile');m=E.SubElement(E.SubElement(root,'diagram'),'mxGraphModel',page='1',pageWidth='200',pageHeight='100');cr=E.SubElement(m,'root');E.SubElement(cr,'mxCell',id='0');E.SubElement(cr,'mxCell',id='1',parent='0')
def vertex(id,parent,x,y,w,h,text,style):
 c=E.SubElement(cr,'mxCell',id=id,parent=parent,vertex='1',value=text,style=style);E.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),**{'as':'geometry'});return c
vertex('a','1',-3,30,50,25,'A','shape=rectangle;fillColor=#ccddff;container=1;fontSize=12;')
vertex('child','a',7,7,15,10,'x','text;strokeColor=none;fillColor=none;fontSize=8;')
vertex('b','1',120,30,40,25,'B','shape=rectangle;fillColor=#aaffaa;fontSize=12;')
c=E.SubElement(cr,'mxCell',id='edge',parent='1',edge='1',source='a',target='b',style='edgeStyle=none;endArrow=block;strokeWidth=1;');g=E.SubElement(c,'mxGeometry',relative='1',**{'as':'geometry'});ar=E.SubElement(g,'Array',**{'as':'points'});E.SubElement(ar,'mxPoint',x='80',y='45')
c=vertex('label','edge',0,0,35,14,'edge','text;strokeColor=none;fillColor=#ffffff;fontSize=10;');c.find('mxGeometry').set('relative','1');E.SubElement(c.find('mxGeometry'),'mxPoint',x='-17',y='-20',**{'as':'offset'})
xml=E.tostring(root,encoding='unicode');folder=W/'native_page_padding_tests';folder.mkdir(exist_ok=True)
png,info=render(xml,200,100,folder/'baseline');boundary=info['outside_page_pixel_audit'];canvas=plan_from_pixels((folder/'baseline/render.padded.png').read_bytes(),info);dx,dy=canvas['dx'],canvas['dy'];nw,nh=canvas['width'],canvas['height'];new,proof=shift(xml,dx,dy,nw,nh);assert verify_cells(xml,new,proof)
result,newinfo=render(new,nw,nh,folder/'candidate');require_declared_page(newinfo,nw,nh)
a=Image.open(folder/'baseline/render.padded.png').convert('RGB').crop(canvas['probe_crop']);b=Image.open(io.BytesIO(result)).convert('RGB');assert a.size==b.size and a.tobytes()==b.tobytes(),'Actual graph/edge/child labels changed'
assert info['actual_platform_font_usage']==newinfo['actual_platform_font_usage']
exact=exact_pixel_proof(folder/'baseline',folder/'candidate',info,newinfo,canvas)
checks=[]
for kind in ('text','style','terminal','child_geometry'):
 mutated=E.fromstring(new);cells={c.get('id'):c for c in mutated.iter('mxCell')}
 if kind=='text':cells['a'].set('value','changed')
 if kind=='style':cells['a'].set('style',cells['a'].get('style')+'fillColor=#ff0000;')
 if kind=='terminal':cells['edge'].set('target','a')
 if kind=='child_geometry':cells['child'].find('mxGeometry').set('x','100')
 try:verify_cells(xml,E.tostring(mutated,encoding='unicode'),proof)
 except AssertionError:checks.append(kind)
 else:raise AssertionError('Mutation passed: '+kind)
try:shift(xml,0,0,400,100)
except AssertionError:checks.append('excessive_canvas_growth')
else:raise AssertionError('Unbounded growth passed')
bad=E.fromstring(xml);next(c for c in bad.iter('mxCell') if c.get('id')=='a').find('mxGeometry').set('relative','1')
try:shift(E.tostring(bad,encoding='unicode'),dx,dy,nw,nh)
except AssertionError:checks.append('relative_top_level_vertex')
else:raise AssertionError('Relative top-level passed')
out={'at':now(),'ok':True,'geometry_proof':proof,'bound_edge_and_nested_label_actual_pixels_identical':True,'actual_fonts_identical':True,'negative_guards_rejected':checks,'exact_pixel_proof':exact,'new_boundary':newinfo['outside_page_pixel_audit']};(W/'native_page_padding_tests.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
