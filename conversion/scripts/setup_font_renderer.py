from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');dest=W/'rendering_fonts';dest.mkdir(exist_ok=True)
if not (dest/'assets').exists():(dest/'assets').symlink_to(W/'rendering/assets',target_is_directory=True)
s=(W/'rendering/remote_render.py').read_text();needle="        page.evaluate('document.fonts.ready')\n        page.locator('#graph').screenshot";replacement="        page.evaluate('document.fonts.ready')\n        info['loaded_fonts']=page.evaluate('Array.from(document.fonts).map(f=>({family:f.family,status:f.status}))')\n        page.evaluate('window.evalViewer.graph.refresh();window.evalViewer.graph.view.validate()')\n        info.update(page.evaluate('() => { const g=window.evalViewer.graph,b=g.getGraphBounds(); return {graphBounds:{x:b.x,y:b.y,width:b.width,height:b.height}}; }'))\n        page.locator('#graph').screenshot";assert needle in s;s=s.replace(needle,replacement);(dest/'remote_render.py').write_text(s);print('font renderer created')
# mxConnector's bounding box can include marker padding along the whole shaft.
# Keep the declared page only after a padded *actual native render* proves zero ink outside.
needle="        info['content_outside_declared_canvas']=outside\n"
replacement='''        info['native_graph_bounds_outside_declared_canvas']=outside
        if outside:
            from PIL import Image
            import numpy as np
            left=max(0,math.ceil(-b['x'])+4);top=max(0,math.ceil(-b['y'])+4)
            probe_w=max(canvas_w+left,math.ceil(b['x']+b['width'])+left+4)
            probe_h=max(canvas_h+top,math.ceil(b['y']+b['height'])+top+4)
            if max(probe_w,probe_h)<=8192 and probe_w*probe_h<=64000000:
                page.evaluate("a=>{const g=window.evalViewer.graph,d=document.getElementById('graph');g.view.scaleAndTranslate(1,a[0],a[1]);g.view.validate();d.style.width=a[2]+'px';d.style.height=a[3]+'px';d.scrollLeft=0;d.scrollTop=0;}",[left,top,probe_w,probe_h])
                page.set_viewport_size({'width':max(probe_w,640),'height':max(probe_h,480)})
                probe=page.locator('#graph').screenshot(animations='disabled')
                pixels=np.asarray(Image.open(io.BytesIO(probe)).convert('RGB'))
                ink=np.min(pixels,axis=2)<250
                ink[top:top+canvas_h,left:left+canvas_w]=False
                actual_outside_pixels=int(ink.sum())
                info['outside_page_pixel_audit']={'padded_native_render_size':[probe_w,probe_h],'offset':[left,top],'nonwhite_outside_pixels':actual_outside_pixels,'white_threshold':250}
                if actual_outside_pixels==0:outside=False
                page.evaluate("a=>{const g=window.evalViewer.graph,d=document.getElementById('graph');g.view.scaleAndTranslate(1,0,0);g.view.validate();d.style.width=a[0]+'px';d.style.height=a[1]+'px';d.scrollLeft=0;d.scrollTop=0;}",[canvas_w,canvas_h])
                page.set_viewport_size({'width':max(canvas_w,640),'height':max(canvas_h,480)})
        info['content_outside_declared_canvas']=outside
'''
assert needle in s;s=s.replace(needle,replacement);(dest/'remote_render.py').write_text(s);print('native pixel overflow audit installed')
