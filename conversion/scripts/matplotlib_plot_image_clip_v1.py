"""Clip each original source AxesImage independently with a local vector viewport."""
import base64,copy,hashlib,xml.etree.ElementTree as ET
def apply(o):
 rects=o.get('plot_clip_rectangles') or [];b=o['bbox'];e={'id':o['id'],'clip':'none'}
 if not rects:return [o],e
 left=max([b['x']]+[r['x'] for r in rects]);top=max([b['y']]+[r['y'] for r in rects]);right=min([b['x']+b['w']]+[r['x']+r['w'] for r in rects]);bottom=min([b['y']+b['h']]+[r['y']+r['h'] for r in rects])
 if right<=left or bottom<=top:return [],{'id':o['id'],'clip':'fully_outside','original_AxesImage_array_preserved':True}
 if max(abs(left-b['x']),abs(top-b['y']),abs(right-b['x']-b['w']),abs(bottom-b['y']-b['h']))<1e-6:return [o],{'id':o['id'],'clip':'proved_image_clip_noop'}
 if abs(o['matrix'][1])>1e-7 or abs(o['matrix'][2])>1e-7:raise ValueError('non_axis_aligned_source_image_clip_requires_another_family')
 svg=ET.Element('svg',{'xmlns':'http://www.w3.org/2000/svg','width':str(right-left),'height':str(bottom-top),'viewBox':' '.join(map(str,[left,top,right-left,bottom-top])),'preserveAspectRatio':'none'})
 image=ET.SubElement(svg,'image',{'x':str(b['x']),'y':str(b['y']),'width':str(b['w']),'height':str(b['h']),'href':o['href'],'preserveAspectRatio':'none'})
 transforms=[]
 if o['matrix'][0]<0:transforms.append('translate('+str(2*b['x']+b['w'])+' 0) scale(-1 1)')
 if o['matrix'][3]<0:transforms.append('translate(0 '+str(2*b['y']+b['h'])+') scale(1 -1)')
 if transforms:image.set('transform',' '.join(transforms))
 blob=ET.tostring(svg);v=copy.deepcopy(o);v.update(href='data:image/svg+xml;base64,'+base64.b64encode(blob).decode(),bbox={'x':left,'y':top,'w':right-left,'h':bottom-top},matrix=[1,0,0,1,0,0])
 return [v],{'id':o['id'],'clip':'source_AxesImage_vector_viewport_clip','output_objects':1,'source_image_href_sha256':hashlib.sha256(o['href'].encode()).hexdigest(),'source_axesimage_gid':o.get('artist_gid'),'source_image_bbox':b,'visible_bbox':v['bbox'],'original_image_matrix':o['matrix'],'native_image_SVG_sha256':hashlib.sha256(blob).hexdigest(),'only_original_source_image_in_local_SVG':True,'original_AxesImage_array_preserved':True,'pixel_resampling_or_fitting':False}
