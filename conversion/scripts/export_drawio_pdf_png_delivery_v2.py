"""HKUST3-only, resumable accepted-pair delivery; exactly three files per pair.

PDFs are printed from the official native graph SVG, never made from the PNG.
The immutable source snapshot, provenance and QA live outside the deliverable.
"""
from pathlib import Path
import argparse,base64,concurrent.futures,datetime,hashlib,io,json,math,mimetypes,os,re,shutil,subprocess,time,traceback,urllib.parse,xml.etree.ElementTree as ET,zipfile
from PIL import Image,ImageChops,ImageOps,ImageFilter
import numpy as np
from arxiv_bulk_official_xml_png_math_v1 import OfficialXmlPng,WAR
from arxiv_author_native_assets_v1 import dependencies,inventory

R=Path('/backup/shaoshitong/img2code_20261029')
NAME='drawio_pdf_png_4316_v1'
A=R/'conversion'/NAME
D=R/'deliveries'/NAME
sha=lambda b:hashlib.sha256(b).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
RENDERER=None

def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp.'+str(os.getpid()))
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,path)

def renderer():
    global RENDERER
    if RENDERER is None: RENDERER=OfficialXmlPng()
    return RENDERER

def portable(xml,code):
    """Keep bytes unless adjacent image files must be embedded for relocation."""
    with zipfile.ZipFile(WAR) as war:
        _,models,refs,_,_=inventory(xml)
        replacements={}
        for ref in refs:
            uri=ref['uri']
            if uri.startswith(('data:','#')):continue
            parsed=urllib.parse.urlparse(uri)
            if parsed.scheme or parsed.netloc:raise ValueError('nonportable_external_asset')
            key=urllib.parse.urlparse(urllib.parse.urljoin('http://source.invalid/',uri)).path.lstrip('/')
            adjacent=(code.parent/urllib.parse.unquote(parsed.path)).resolve()
            if adjacent.is_file() and adjacent.is_relative_to(R):blob=adjacent.read_bytes()
            elif key in war.namelist():blob=war.read(key)
            else:raise ValueError('missing_portable_asset:'+key)
            mime=mimetypes.guess_type(key)[0] or 'application/octet-stream'
            replacements[uri]='data:'+mime+';base64,'+base64.b64encode(blob).decode()
        if not replacements:return xml,{},0
        for model in models:
            for node in model.iter():
                for key,value in list(node.attrib.items()):
                    for old,new in replacements.items():
                        value=value.replace(old,new).replace(urllib.parse.quote(old,safe=''),urllib.parse.quote(new,safe=''))
                    node.set(key,value)
        root=ET.Element('mxfile',host='app.diagrams.net',type='device')
        for i,model in enumerate(models):ET.SubElement(root,'diagram',id='page-'+str(i+1),name='Page-'+str(i+1)).append(model)
        result=ET.tostring(root,encoding='utf-8')
        closed=dependencies(result,D/'000001/diagram.drawio',D/'000001/diagram.drawio',war)
        if closed['issues'] or closed['asset_map']:raise ValueError('portable_embedding_incomplete')
        return result,{},len(replacements)

def cached_svg(row,xml):
    path=(R/row.get('original_image_file',row['image_file'])).with_suffix('.svg')
    proof=path.parent/'synced_replay_proof.json'
    if not path.exists():return None
    if not proof.exists():
        # The accepted baseline retains paired original locations. Replay the
        # companion SVG only after checking both original payload identities;
        # the independent screen/PDF checks below still have to pass.
        if sha((R/row.get('original_code_file',row['code_file'])).read_bytes())!=sha(xml):return None
        if sha((R/row.get('original_image_file',row['image_file'])).read_bytes())!=row['image_sha256']:return None
        return path.read_text()
    p=json.loads(proof.read_text())
    if not (p.get('ok') and p.get('source_XML_sha256')==sha(xml)
            and p.get('source_official_PNG_sha256')==row['image_sha256']
            and p.get('source_official_SVG_sha256')==sha(path.read_bytes())):return None
    return path.read_text()

def native_svg(r,xml,w,h):
    _,ms,_,_,_=inventory(xml)
    if len(ms)!=1:raise ValueError('delivery_requires_one_complete_page')
    model=ET.tostring(ms[0],encoding='unicode')
    r.page.bring_to_front()
    return r.page.evaluate(r'''async args=>{
      const ui=__bulkUi,g=ui.editor.graph;
      const root=mxUtils.parseXml(args.model).documentElement;
      const fontCSS=(root.getAttribute('extFonts')||'').split('|').filter(Boolean).map(entry=>{
        let k=entry.indexOf('^');return '@font-face{font-family:'+JSON.stringify(entry.slice(0,k))+';src:url('+JSON.stringify(entry.slice(k+1))+')}';
      }).join('\n');
      let style=document.getElementById('delivery-fonts');if(!style){style=document.createElement('style');style.id='delivery-fonts';document.head.append(style)}style.textContent=fontCSS;
      await Promise.all((root.getAttribute('extFonts')||'').split('|').filter(Boolean).map(entry=>document.fonts.load('12px '+JSON.stringify(entry.split('^')[0]))));
      g.sizeDidChange=function(){};
      ui.editor.setGraphXml(root);
      g.view.setScale(1);g.view.setTranslate(0,0);g.container.scrollLeft=0;g.container.scrollTop=0;
      g.clearSelection();g.refresh();g.view.validate();await document.fonts.ready;
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      g.view.scaleAndTranslate(1,0,0);g.view.invalidate();g.view.validate();
      // Native legacy PNGs use the declared page. Override only export bounds,
      // never cells, styles, text or geometry, to retain that exact viewport.
      const previous=g.view.getBackgroundPageBounds;
      g.view.getBackgroundPageBounds=()=>new mxRectangle(g.view.translate.x*g.view.scale,g.view.translate.y*g.view.scale,args.w*g.view.scale,args.h*g.view.scale);
      try{const svg=g.getSvg('#ffffff',1,0,false,false,true,true,null,null,false,true,null,'page');
        if(fontCSS){const style=svg.ownerDocument.createElementNS('http://www.w3.org/2000/svg','style');style.textContent=fontCSS;svg.insertBefore(style,svg.firstChild)}return mxUtils.getXml(svg);}
      finally{g.view.getBackgroundPageBounds=previous;}
    }''',dict(model=model,w=w,h=h))

def compare(a,b):
    def white(im):
        im=im.convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im);return bg.convert('RGB')
    if abs(a.width-b.width)<=3 and abs(a.height-b.height)<=3:
        w,h=min(a.width,b.width),min(a.height,b.height);a=a.crop((0,0,w,h));b=b.crop((0,0,w,h))
    a=ImageOps.contain(white(a),(1000,1000))
    b=white(b).resize(a.size,Image.Resampling.LANCZOS)
    x=np.asarray(a,dtype=np.float32);y=np.asarray(b,dtype=np.float32)
    from skimage.metrics import structural_similarity
    score=float(structural_similarity(x,y,data_range=255,channel_axis=2))
    blurred_a=np.asarray(a.filter(ImageFilter.GaussianBlur(1)),dtype=np.float32)
    blurred_b=np.asarray(b.filter(ImageFilter.GaussianBlur(1)),dtype=np.float32)
    coarse_a=np.asarray(a.filter(ImageFilter.GaussianBlur(3)),dtype=np.float32)
    coarse_b=np.asarray(b.filter(ImageFilter.GaussianBlur(3)),dtype=np.float32)
    return dict(ssim=score,blur1px_ssim=float(structural_similarity(blurred_a,blurred_b,data_range=255,channel_axis=2)),blur3px_ssim=float(structural_similarity(coarse_a,coarse_b,data_range=255,channel_axis=2)),mean_absolute_error=float(np.abs(x-y).mean()))

def one(item):
    number,row=item;start=time.monotonic();proof=A/'proofs'/f'{number:06d}.json'
    out=D/f'{number:06d}';tmp=A/'work'/f'{number:06d}';tmp.mkdir(parents=True,exist_ok=True)
    if proof.exists():
        old=json.loads(proof.read_text())
        if old.get('ok') and all((out/k).is_file() and sha((out/k).read_bytes())==v for k,v in old['output_sha256'].items()):return old
    record=dict(number=number,id=row['id'],at_utc=now(),CPU_host='HKUST3',ok=False)
    try:
        source=R/row['code_file'];xml=source.read_bytes();png=(R/row['image_file']).read_bytes()
        assert sha(xml)==row['code_sha256'] and sha(png)==row['image_sha256'],'input_checksum_mismatch'
        with Image.open(io.BytesIO(png)) as im:reference=im.convert('RGBA');w,h=im.size
        portable_xml,assets,embedded=portable(xml,R/row.get('original_code_file',row['code_file']))
        r=renderer();r.assets=assets;r.blocked.clear();r.missing.clear()
        svg=cached_svg(row,xml);kind='verified_cached_official_native_SVG'
        if svg is None:svg=native_svg(r,portable_xml,w,h);kind='fresh_official_native_page_SVG'
        page=r.render_page
        page.bring_to_front()
        page.emulate_media(media='screen',color_scheme='light')
        page.set_content('<!doctype html><html><head><base href="'+r.origin+'/"><style>html,body{margin:0;padding:0;background:white;-webkit-print-color-adjust:exact;print-color-adjust:exact}body>svg{display:block}</style></head><body>'+svg+'</body></html>',wait_until='load')
        page.evaluate('async()=>{await document.fonts.ready;const refs=[...document.querySelectorAll("svg image,svg img")].map(n=>n.getAttribute("href")||n.getAttribute("xlink:href")||n.getAttribute("src")).filter(Boolean);await Promise.all(refs.map(src=>new Promise((yes,no)=>{let i=new Image;i.onload=()=>i.naturalWidth?yes():no(Error("empty_image"));i.onerror=()=>no(Error("image_decode_failed"));i.src=src})));await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))}')
        element=page.locator('body>svg').first;box=element.bounding_box()
        assert box and min(box['width'],box['height'])>0,'empty_svg'
        sw,sh=box['width'],box['height']
        assert abs(sw-w)<=1 and abs(sh-h)<=1,('viewport_mismatch',sw,sh,w,h)
        page.set_viewport_size(dict(width=math.ceil(sw)+2,height=math.ceil(sh)+2))
        screen=element.screenshot(animations='disabled',timeout=30000)
        (tmp/'screen.png').write_bytes(screen)
        screencheck=compare(reference,Image.open(io.BytesIO(screen)))
        record['source_png_vs_native_screen']=screencheck
        if screencheck['ssim']<0.94 and screencheck['blur1px_ssim']<0.98:raise ValueError('native_screen_mismatch:'+str(screencheck))
        pdf=tmp/'diagram.pdf'
        page.add_style_tag(content=f'@page{{size:{sw}px {sh}px;margin:0}}')
        page.pdf(path=str(pdf),width=f'{sw}px',height=f'{sh}px',prefer_css_page_size=True,margin=dict(top='0',right='0',bottom='0',left='0'),print_background=True,display_header_footer=False,scale=1)
        info=subprocess.check_output(['pdfinfo',str(pdf)],text=True,timeout=20)
        assert re.search(r'Pages:\s+1\s',info),'PDF_not_single_page'
        render=tmp/'pdf'
        subprocess.run(['pdftoppm','-singlefile','-r','96','-png',str(pdf),str(render)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=45,check=True)
        with Image.open(render.with_suffix('.png')) as rendered:pdfcheck=compare(reference,rendered)
        record['source_png_vs_compiled_pdf']=pdfcheck
        pdfscreen=compare(Image.open(io.BytesIO(screen)),Image.open(render.with_suffix('.png')))
        record['native_screen_vs_compiled_pdf']=pdfscreen
        # Poppler and Chromium use different font hinting and stroke AA.
        # The coarse check is allowed only with a high raw structural score;
        # it cannot excuse missing panels, clipped views or absent resources.
        print_ok=(pdfscreen['ssim']>=0.90 or pdfscreen['blur1px_ssim']>=0.96
                  or (pdfscreen['ssim']>=0.85 and pdfscreen['blur3px_ssim']>=0.975))
        if not print_ok:raise ValueError('PDF_render_mismatch:'+str(pdfscreen))
        assert not r.blocked and not r.missing,('resource_requests_failed',r.blocked[:2],r.missing[:2])
        out.mkdir(parents=True,exist_ok=True)
        (out/'diagram.drawio').write_bytes(portable_xml);(out/'diagram.png').write_bytes(png)
        shutil.copyfile(pdf,out/'diagram.pdf')
        assert {x.name for x in out.iterdir()}=={'diagram.drawio','diagram.png','diagram.pdf'}
        record.update(ok=True,renderer=kind,PDF_compiled_from_native_SVG=True,PNG_unchanged=True,
            source_code_sha256=sha(xml),source_png_sha256=sha(png),embedded_asset_count=embedded,
            drawio_bytes_unchanged=portable_xml==xml,output_sha256={x.name:sha(x.read_bytes()) for x in out.iterdir()},
            output_bytes={x.name:x.stat().st_size for x in out.iterdir()},seconds=time.monotonic()-start)
        write_json(proof,record);shutil.rmtree(tmp)
    except Exception as e:
        record.update(error=type(e).__name__+':'+str(e)[:1500],seconds=time.monotonic()-start)
        write_json(A/'errors'/f'{number:06d}.json',record)
    return record

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=6);p.add_argument('--numbers');a=p.parse_args()
    rows=[json.loads(x) for x in (A/'input_snapshot.jsonl').read_text().splitlines()]
    items=list(enumerate(rows,1))
    if a.numbers:
        selected={int(n) for n in a.numbers.split(',')};items=[x for x in items if x[0] in selected]
    counts=dict(ok=0,failed=0);started=time.monotonic();D.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(one,x) for x in items]
        for future in concurrent.futures.as_completed(futures):
            record=future.result();counts['ok' if record['ok'] else 'failed']+=1
            status=dict(at_utc=now(),state='running',CPU_host='HKUST3',requested=len(items),**counts,elapsed_seconds=time.monotonic()-started)
            write_json(A/'status.json',status)
            if not record['ok'] or sum(counts.values())%25==0:print(json.dumps(record,ensure_ascii=False),flush=True)
    status.update(at_utc=now(),state='complete' if counts['failed']==0 else 'needs_repair',elapsed_seconds=time.monotonic()-started)
    write_json(A/'status.json',status);print(json.dumps(status),flush=True)
    if counts['failed']:raise SystemExit(1)

if __name__=='__main__':main()
