import hashlib,json,os,signal,subprocess,sys
from pathlib import Path
from native_worker import R,W,native

def plan_from_pixels(padded,info):
    import io
    from PIL import Image,ImageChops
    im=Image.open(io.BytesIO(padded)).convert('RGB');box=ImageChops.difference(im,Image.new('RGB',im.size,'white')).getbbox();assert box,'Empty render'
    assert box[0]>0 and box[1]>0 and box[2]<im.width and box[3]<im.height,'Probe ink reaches probe boundary'
    left,top=info['outside_page_pixel_audit']['offset'];w,h=info['canvas'];assert im.size==tuple(info['outside_page_pixel_audit']['padded_native_render_size'])
    # The 32px audit guard is diagnostic whitespace, not a required canvas margin.
    # Union actual painted pixels (+1px AA guard) with the ENTIRE original page.
    x=min(left,box[0]-1);y=min(top,box[1]-1);right=max(left+w,box[2]+1);bottom=max(top+h,box[3]+1)
    return {'dx':left-x,'dy':top-y,'width':right-x,'height':bottom-y,'probe_crop':[x,y,right,bottom],'painted_pixel_bbox':list(box),'original_page_in_probe':[left,top,left+w,top+h]}

def exact_pixel_proof(before,after,oldinfo,newinfo,canvas):
    from PIL import Image,ImageChops
    # Compare complete native paints with the same browser audit view, aligned
    # using only the renderer's recorded integer translation (never fitted).
    a=Image.open(before/'render.padded.png').convert('RGB');b=Image.open(after/'render.padded.png').convert('RGB')
    la,ta=oldinfo['outside_page_pixel_audit']['offset'];lb,tb=newinfo['outside_page_pixel_audit']['offset']
    dx,dy=canvas['dx'],canvas['dy'];sx=dx+lb-la;sy=dy+tb-ta
    x0=min(0,sx);y0=min(0,sy);x1=max(a.width+sx,b.width);y1=max(a.height+sy,b.height)
    assert (x1-x0)*(y1-y0)<=64000000
    aligned_a=Image.new('RGB',(x1-x0,y1-y0),'white');aligned_b=aligned_a.copy()
    aligned_a.paste(a,(sx-x0,sy-y0));aligned_b.paste(b,(-x0,-y0))
    assert ImageChops.difference(aligned_a,aligned_b).getbbox() is None,'Complete native paint changed'
    oldpage=Image.open(before/'render.stable_page.png').convert('RGB');newpage=Image.open(after/'render.png').convert('RGB')
    region=newpage.crop((dx,dy,dx+oldpage.width,dy+oldpage.height))
    assert oldpage.size==region.size and oldpage.tobytes()==region.tobytes(),'Original page pixels changed'
    assert oldinfo['actual_platform_font_usage']==newinfo['actual_platform_font_usage'],'Actual physical fonts changed'
    return {'complete_same_view_native_paint_pixel_identical':True,'original_page_actual_browser_export_pixel_identical':True,'actual_platform_fonts_identical':True,'registered_audit_offset':[sx,sy],'pixel_difference_tolerance':0,'capture_policy':newinfo.get('page_capture_policy')}

def render(xml,width,height,directory):
    directory.mkdir(parents=True,exist_ok=True)
    cmd=[sys.executable,str(Path(native.__file__).resolve()),'--render-native-only','--drawio-renderer',str(W/'rendering_canvas_padding_proof/remote_render.py'),'--render-directory',str(directory),'--width',str(width),'--height',str(height),'--max-side','8192','--runtime-cache',str(R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')]
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),start_new_session=True)
    try:out,err=p.communicate(xml.encode(),timeout=150)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL);p.communicate();raise
    (directory/'stderr.log').write_bytes(err);assert p.returncode==0,err.decode(errors='replace')[-1800:]
    return (directory/'render.png').read_bytes(),json.loads((directory/'native_render.json').read_text())

def verify_cells(before,after,proof):
    import xml.etree.ElementTree as E
    from decimal import Decimal
    a=E.fromstring(before);b=E.fromstring(after);ac=list(a.iter('mxCell'));bc=list(b.iter('mxCell'));assert len(ac)==len(bc)
    dx,dy=proof['translation'];changed=set(proof['translated_top_level_cells'])
    # Inverse only the documented global geometry movement, then compare full XML trees.
    for ca,cb in zip(ac,bc):
        assert ca.attrib==cb.attrib,'Text/style/binding/id/parent mutation'
        if cb.get('id') in changed:
            ga=ca.find('mxGeometry');gb=cb.find('mxGeometry')
            if cb.get('vertex')=='1':pairs=[(ga,gb)]+list(zip(ga.findall('mxRectangle'),gb.findall('mxRectangle')))
            else:pairs=[(x,y) for x,y in zip(ga.iter('mxPoint'),gb.iter('mxPoint')) if y.get('as')!='offset']
            for x,y in pairs:
                for key,delta in [('x',dx),('y',dy)]:
                    if not delta:continue
                    assert Decimal(y.get(key,'0'))-delta==Decimal(x.get(key,'0'))
                    if key in x.attrib:y.set(key,x.get(key))
                    else:y.attrib.pop(key,None)
        assert E.tostring(ca)==E.tostring(cb),'Cell descendants changed'
    am=a.find('.//mxGraphModel') if a.tag!='mxGraphModel' else a;bm=b.find('.//mxGraphModel') if b.tag!='mxGraphModel' else b
    for key in ('pageWidth','pageHeight'):bm.set(key,am.get(key))
    assert E.tostring(a)==E.tostring(b),'Non-page XML metadata changed'
    return True
