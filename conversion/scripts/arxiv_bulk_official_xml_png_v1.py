"""Official draw.io XML rendering/edit probe; never a PDF geometry converter."""
from pathlib import Path
import base64, hashlib, http.server, json, mimetypes, re, threading, urllib.parse, zipfile
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops
R=Path('/backup/shaoshitong/img2code_20261029')
WAR=R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war'
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
sha=lambda b:hashlib.sha256(b).hexdigest()
class OfficialXmlPng:
    def __init__(self):
        self.archive=zipfile.ZipFile(WAR);self.lock=threading.Lock();self.assets={};self.blocked=[];self.missing=[];owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                key=urllib.parse.unquote(urllib.parse.urlparse(self.path).path).lstrip('/') or 'index.html'
                try:
                    if key in owner.assets:body=owner.assets[key].read_bytes()
                    else:
                        with owner.lock:body=owner.archive.read(key)
                    if key=='js/main.js':body=b'App.main(function(ui){window.__bulkUi=ui;});\n'+body
                    self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(key)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
                except (KeyError,FileNotFoundError):owner.missing.append(key);self.send_error(404)
            def log_message(self,*args):pass
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=self.server.serve_forever,daemon=True).start();self.origin='http://127.0.0.1:'+str(self.server.server_port)
        self.p=sync_playwright().start();self.browser=self.p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu']);self.context=self.browser.new_context(service_workers='block')
        def guard(route):
            if route.request.url.startswith(self.origin+'/'):route.continue_()
            else:self.blocked.append(route.request.url.split('?',1)[0]);route.abort()
        self.context.route('**/*',guard);self.page=self.context.new_page();self.page.goto(self.origin+'/?dev=1&offline=1&local=1&splash=0&libs=0&math=0&ui=kennedy&stealth=1',wait_until='domcontentloaded',timeout=45000)
        self.page.wait_for_function('window.__bulkUi && window.__bulkUi.editor',timeout=45000);self.render_page=self.context.new_page()
    def render(self,xml,folder,asset_map=None):
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);self.assets=asset_map or {};self.blocked.clear();self.missing.clear()
        record=self.page.evaluate(r'''xml=>{
          const ui=window.__bulkUi,g=ui.editor.graph,m=g.getModel();
          let root=mxUtils.parseXml(xml).documentElement;
          if(root.nodeName==='mxfile'){let d=root.getElementsByTagName('diagram')[0],model=d.getElementsByTagName('mxGraphModel')[0];root=model||mxUtils.parseXml(Graph.decompress(mxUtils.getTextContent(d))).documentElement;}
          ui.editor.setGraphXml(root);g.refresh();
          const original=mxUtils.getXml(ui.editor.getGraphXml()),b=g.getGraphBounds(),scale=Math.min(1,2400/Math.max(b.width,b.height)),background=root.getAttribute('background')||g.background||'#ffffff';
          const svg=mxUtils.getXml(g.getSvg(background,scale,8));
          const cells=Object.values(m.cells),target=cells.find(c=>c.vertex&&c.geometry&&!/(?:^|;)shape=image(?:;|$)/.test(c.style||''))||cells.find(c=>c.vertex&&c.geometry);
          if(!target)throw Error('no_independently_editable_vertex');
          const geo=target.geometry.clone();geo.x+=13;m.setGeometry(target,geo);m.setValue(target,String(target.value||'')+' edit-probe');
          const mutated=mxUtils.getXml(ui.editor.getGraphXml()),changed=mutated!==original,mutatedSvg=mxUtils.getXml(g.getSvg(background,scale,8));
          ui.editor.setGraphXml(mxUtils.parseXml(original).documentElement);const restored=mxUtils.getXml(ui.editor.getGraphXml());
          const restoredSvg=mxUtils.getXml(g.getSvg(background,scale,8));
          return {svg,mutatedSvg,restoredSvg,background,bounds:{x:b.x,y:b.y,width:b.width,height:b.height},scale,vertices:cells.filter(c=>c.vertex).length,edges:cells.filter(c=>c.edge).length,
            edit_probe:{cell_id:target.id,geometry_and_label_mutation_changes_xml:changed,restore_xml_exact:restored===original},official_generator:'Graph.getSvg from pinned full Editor',original_normalized_xml:original};
        }''',xml)
        if not all(record['edit_probe'][k] for k in ['geometry_and_label_mutation_changes_xml','restore_xml_exact']):raise ValueError('edit_restore_probe_failed')
        svg=record.pop('svg');mutated=record.pop('mutatedSvg');restored=record.pop('restoredSvg');normalized=record.pop('original_normalized_xml');record['normalized_xml_sha256']=sha(normalized.encode())
        pngs={}
        for name,body in [('official',svg),('mutated',mutated),('restored',restored)]:
            (folder/(name+'.svg')).write_text(body)
            self.render_page.set_content('<html><head><base href="'+self.origin+'/"></head><body style="margin:0;background:white">'+body+'</body></html>');self.render_page.evaluate('document.fonts.ready')
            image_check=self.render_page.evaluate('''async()=>{let urls=Array.from(document.querySelectorAll('svg image,svg img')).map(x=>x.getAttribute('href')||x.getAttribute('xlink:href')||x.getAttribute('src'));let failed=[];for(let url of urls){if(!url)continue;try{await new Promise((ok,bad)=>{let im=new Image();im.onload=()=>im.naturalWidth?ok():bad();im.onerror=bad;im.src=url;});}catch(e){failed.push(url.split(':',1)[0]);}}return {image_objects:urls.length,all_images_decode_completed:true,failed:failed,fonts_status:document.fonts.status,font_families:[...new Set(Array.from(document.querySelectorAll('text,foreignObject span,foreignObject div')).map(x=>getComputedStyle(x).fontFamily))]};}''')
            if image_check['failed']:raise ValueError('unresolved_official_SVG_image_assets')
            element=self.render_page.locator('svg').first;size=element.bounding_box()
            if not size or size['width']<2 or size['height']<2:raise ValueError('empty_official_svg_bounds')
            self.render_page.set_viewport_size({'width':min(8192,max(2,int(size['width'])+2)),'height':min(8192,max(2,int(size['height'])+2))})
            pngs[name]=element.screenshot(type='png',animations='disabled',timeout=20000);(folder/(name+'.png')).write_bytes(pngs[name])
            if name=='official':record['resource_font_closure']=image_check
        canonical=lambda s:re.sub(r'ge-svg-[A-Za-z0-9_-]+','ge-svg-OFFICIAL-EXPORT-ID',s)
        png=pngs['official'];record['edit_probe'].update(mutation_SVG_changed=mutated!=svg,restored_SVG_raw_exact=restored==svg,restored_SVG_export_ID_canonical_exact=canonical(restored)==canonical(svg),SVG_comparison_note='Only official random ge-svg export namespace IDs are normalized for comparison; actual exported SVG files remain unchanged.',mutation_actual_PNG_changed=pngs['mutated']!=png,restored_actual_PNG_exact=pngs['restored']==png)
        if not all(record['edit_probe'][k] for k in ['mutation_SVG_changed','restored_SVG_export_ID_canonical_exact','mutation_actual_PNG_changed','restored_actual_PNG_exact']):raise ValueError('actual_render_mutation_restore_failed')
        with Image.open(folder/'official.png') as image:
            rgb=image.convert('RGB');record['png_dimensions']=list(image.size)
            if ImageChops.difference(rgb,Image.new('RGB',rgb.size,'white')).getbbox() is None:raise ValueError('blank_official_png')
        if self.blocked or self.missing:raise ValueError('unresolved_external_or_missing_resource:'+str(len(self.blocked))+':'+str(len(self.missing)))
        record.update(png_sha256=sha(png),official_war_sha256=sha(WAR.read_bytes()),external_network_requests_blocked=0,custom_pdf_geometry_converter=False)
        (folder/'render_edit_evidence.json').write_text(json.dumps(record,indent=2)+'\n');return record
    def close(self):
        self.browser.close();self.p.stop();self.server.shutdown();self.server.server_close();self.archive.close()
