"""Real captured Matplotlib SVG paint -> independent editable native objects."""
from pathlib import Path
import argparse,base64,collections,hashlib,html,io,json,re,sys,traceback,urllib.parse,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_pipeline_20261102_v1'
sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from fontTools.ttLib import TTFont
from PIL import Image
import numpy as np
from skimage.metrics import structural_similarity
from playwright.sync_api import sync_playwright
from svg_convert_v2 import build
from matplotlib_plot_vector_clip_v2 import apply as clip_object
from matplotlib_plot_export_registration_v1 import registration
from matplotlib_plot_image_clip_v1 import apply as clip_image
import curate_derived as native
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
sha=lambda b:hashlib.sha256(b).hexdigest()
def metric(a,b):
    aa=Image.open(io.BytesIO(a)).convert('RGB');bb=Image.open(io.BytesIO(b)).convert('RGB');x=np.asarray(aa.resize((512,512)));y=np.asarray(bb.resize((512,512)))
    return {'size_a':list(aa.size),'size_b':list(bb.size),'ssim512':float(structural_similarity(x,y,channel_axis=2,data_range=255)),'RGB_exact':aa.size==bb.size and np.array_equal(np.asarray(aa),np.asarray(bb))}
def source_font_audit(page,faces):
    selectors=page.evaluate("""()=>{let root=document.querySelector('svg'),w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),parents=new Set();while(w.nextNode()){let n=w.currentNode;if(n.textContent.trim()&&n.parentElement.closest('text'))parents.add(n.parentElement);}return [...parents].map((e,i)=>{e.id='mpl-source-font-'+i;return '#'+e.id;});}""")
    cdp=page.context.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');root=cdp.send('DOM.getDocument',{'depth':1})['root']['nodeId'];rows=[];allowed={f['postscript'] for f in faces}
    for selector in selectors:
        node=cdp.send('DOM.querySelector',{'nodeId':root,'selector':selector})['nodeId'];fonts=cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts'];active=[f for f in fonts if f['glyphCount']]
        if not active or any(not f['isCustomFont'] or f['postScriptName'] not in allowed for f in active):raise ValueError('unproved_source_browser_physical_font')
        rows.append({'selector':selector,'actual_fonts':active})
    cdp.detach();return rows
def fonts(case,scene):
    faces=[]
    for f in scene['fonts']:
        path=case/f['file'];blob=path.read_bytes();assert sha(blob)==f['sha256'];ft=TTFont(io.BytesIO(blob));weight=ft['OS/2'].usWeightClass;italic=bool(ft['OS/2'].fsSelection&1);flags=ft['OS/2'].fsType
        if flags&0x2 or flags&0x200:raise ValueError('source_font_not_embeddable')
        faces.append({'family':ft['name'].getDebugName(1),'family_aliases':sorted(set([ft['name'].getDebugName(1),f.get('font_name',ft['name'].getDebugName(1))]+f.get('requested_families',[]))-{'serif','sans-serif','monospace','cursive','fantasy','system-ui'}),'postscript':ft['name'].getDebugName(6),'weight':weight,'bold':weight>=600,'italic':italic,'sha256':f['sha256'],'alias':'MplFace_'+f['sha256'][:20],'uri':'data:font/ttf;base64,'+base64.b64encode(blob).decode(),'cmap':set(ft.getBestCmap()),'file':str(path.relative_to(R))});ft.close()
    return faces
def embed(xml,objects,faces):
    root=ET.fromstring(xml);model=root.find('.//mxGraphModel');cells={c.get('id'):c for c in root.iter('mxCell')};used={}
    for o in objects:
        if o['type']!='text':continue
        family=o['fontFamily'].split(',')[0].strip('"\'');choices=[f for f in faces if family in f['family_aliases'] and f['bold']==bool(o['bold']) and f['italic']==bool(o['italic'])]
        if len(choices)!=1:raise ValueError('actual_source_font_face_not_captured:'+family+':'+str(o['bold'])+':'+str(o['italic']))
        f=choices[0];missing={ord(c) for c in o['text'] if not c.isspace()}-f['cmap']
        if missing:raise ValueError('source_font_missing_unicode:'+str(sorted(missing)))
        cell=cells[o['id']];style=dict(x.split('=',1) for x in cell.get('style','').split(';') if '=' in x);style['fontFamily']=f['alias'];style['fontStyle']=str(4*bool(o['underline']));rotation=float(o.get('nativeRotation',0))
        if rotation:style['rotation']=str(rotation)
        if f['alias'] not in used:style['fontSource']=urllib.parse.quote(f['uri'],safe='')
        used[f['alias']]=f;cell.set('style',';'.join(k+'='+v for k,v in style.items())+';');cell.set('matplotlib_artist_gid',o.get('artist_gid') or '')
    for o in objects:
        if o['id'] in cells:cells[o['id']].set('source_svg_object',o.get('plot_visible_paint_of',o['id']));cells[o['id']].set('matplotlib_artist_gid',o.get('artist_gid') or '')
    model.set('extFonts','|'.join(f['alias']+'^'+f['uri'] for f in used.values()))
    return ET.tostring(root,encoding='unicode'),[{k:v for k,v in f.items() if k not in {'uri','cmap'}} for f in used.values()]
def convert(case,browser):
    out=case/'native_v3';out.mkdir(exist_ok=False);audit=json.loads((case/'input_audit.json').read_text());execution=json.loads((case/'execution.json').read_text());capture=execution['captures'][0];scene=json.loads((case/capture['scene']).read_text());svg=(case/capture['svg']).read_bytes();source_png=(case/capture['png']).read_bytes();reference=(case/'original_reference.png').read_bytes();assert sha((case/'source.py').read_bytes())==audit['source_code_sha256']
    report={'software_sha256':{n:sha((R/'conversion/scripts'/n).read_bytes()) for n in ['matplotlib_plot_engine_v3.py','matplotlib_plot_image_clip_v1.py','matplotlib_plot_vector_clip_v2.py','matplotlib_plot_svg_dom_v3.js','matplotlib_plot_export_registration_v1.py']},'id':case.name,'source':audit['source'],'source_code_sha256':audit['source_code_sha256'],'source_image_sha256':audit['source_image_sha256'],'status':'development_failed','qualified':False,'model_calls':0,'all_source_data_vertices_preserved':scene['all_data_vertices_and_offsets_retained'],'source_data_vertices':scene['data_point_or_path_vertex_count'],'source_axes':scene['axes'],'source_image_array_elements':sum(int(np.prod(a['shape'])) for a in scene['artists'] if a.get('role')=='source_image'),'source_data_patch_vertices':sum(a['path_vertices']['shape'][0] for a in scene['artists'] if a.get('data_patch') and a.get('path_vertices')),'source_capture_reused_no_repeat_execution':True,'actual_source_export_settings':scene.get('actual_source_export_settings'),'complete_export_parameters_recorded':execution.get('complete_export_parameters_recorded',False),'recorded_RNG_before_sha256':sha(json.dumps(execution.get('RNG_state_before'),sort_keys=True).encode()),'recorded_RNG_after_sha256':sha(json.dumps(execution.get('RNG_state_after'),sort_keys=True).encode())}
    try:
        assert b'<script' not in svg.lower() and b'<!entity' not in svg.lower();width,height=Image.open(io.BytesIO(source_png)).size;faces=fonts(case,scene);css='\n'.join('@font-face{font-family:"'+family+'";font-weight:'+str(f['weight'])+';font-style:'+('italic' if f['italic'] else 'normal')+';src:url("'+f['uri']+'");}' for f in faces for family in f['family_aliases'])
        context=browser.new_context(viewport={'width':width,'height':height},service_workers='block');page=context.new_page();blocked=[];context.route('**/*',lambda route:(blocked.append(route.request.url.split('?',1)[0]),route.abort()))
        page.set_content('<style>html,body{margin:0;padding:0;background:white}'+css+'</style>'+svg.decode());registered=registration(scene,svg,(width,height));report['source_export_registration']=registered;page.evaluate('([w,h,vb])=>{let s=document.querySelector("svg");s.setAttribute("width",w);s.setAttribute("height",h);s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("viewBox",vb.join(" "));s.setAttribute("preserveAspectRatio","none");}',[width,height,registered['registered_viewBox']]);page.evaluate('document.fonts.ready');svg_png=page.screenshot();(out/'source_svg_browser.png').write_bytes(svg_png)
        dom=page.evaluate((R/'conversion/scripts/matplotlib_plot_svg_dom_v3.js').read_text());report['actual_source_browser_fonts']=source_font_audit(page,faces);context.close();assert not blocked,'source_SVG_external_resources';(out/'source_dom.json').write_text(json.dumps(dom,ensure_ascii=False)+'\n')
        if len(dom['objects'])>20000 or any(o['type']=='shape' and len(re.findall(r'[MmLlHhVvCcSsQqTtAaZz]',o.get('d') or ''))>10000 for o in dom['objects']):raise ValueError('complete_vector_scene_resource_bound_no_point_reduction')
        if any(i['reason'].startswith('plot_non') for i in dom['issues']):raise ValueError('unsupported_nonrect_plot_clip_family')
        report['source_canvas_contract']=dom.get('source_canvas');objects=[];clipping=[]
        for o in dom['objects']:
            if o['type']=='text' and o.get('plot_clip_rectangles'):
                b=o['bbox']
                if any(b['x']<r['x']-1e-5 or b['y']<r['y']-1e-5 or b['x']+b['w']>r['x']+r['w']+1e-5 or b['y']+b['h']>r['y']+r['h']+1e-5 for r in o['plot_clip_rectangles']):raise ValueError('unsupported_partial_'+o['type']+'_clip')
            visible,evidence=(clip_image(o) if o['type']=='image' else clip_object(o));objects.extend(visible);clipping.append(evidence)
        dom['objects']=objects;dom['issues']=[i for i in dom['issues'] if i['reason']!='clipPath'];xml,stats=build(dom,width,height)
        xml,font_evidence=embed(xml,objects,faces);tree=ET.fromstring(xml);byid={c.get('id'):c for c in tree.iter('mxCell')}
        for o in objects:
            if o['type']=='image':
                cell=byid[o['id']];st=cell.get('style','')
                if o['matrix'][0]<0:st+='flipH=1;'
                if o['matrix'][3]<0:st+='flipV=1;'
                cell.set('style',st)
        xml=ET.tostring(tree,encoding='unicode');(out/'diagram.drawio').write_text(xml);(out/'vector_clip_evidence.json').write_text(json.dumps(clipping,indent=2)+'\n');(out/'conversion_stats.json').write_text(json.dumps(stats,indent=2)+'\n')
        if stats['issues']:raise ValueError('unproved_source_paint:'+json.dumps(stats['issues'][:4]))
        result=native.native_job(xml,width,height,150,R/'conversion/rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
        if not result['ok']:raise ValueError('official_native_render_failed:'+json.dumps({k:v for k,v in result.items() if k!='png'}))
        png=result.pop('png');(out/'native.png').write_bytes(png);(out/'native_render.json').write_text(json.dumps(result['native_render'],ensure_ascii=False,indent=2)+'\n')
        root=ET.fromstring(xml);cells=[c for c in root.iter('mxCell') if c.get('vertex')=='1'];text=[c for c in cells if 'shape=text;' in c.get('style','')]
        report.update(status='editable_native_development_candidate',native_cells=len(cells),editable_text_cells=len(text),vector_objects=stats['counts']['vector_shapes'],source_raster_image_objects=stats['counts'].get('source_raster_assets',0),clip_counts=dict(collections.Counter(r['clip'] for r in clipping)),fonts=font_evidence,
          source_svg_to_native=metric(svg_png,png),fresh_Agg_to_native=metric(source_png,png),immutable_reference_to_fresh_Agg=metric(reference,source_png),immutable_reference_to_native=metric(reference,png),source_SVG_browser_to_fresh_Agg=metric(svg_png,source_png),
          source_XML_hash=sha(xml.encode()),native_PNG_sha256=sha(png),source_scene_file=str((case/capture['scene']).relative_to(R)),source_scene_sha256=sha((case/capture['scene']).read_bytes()),native_file=str((out/'diagram.drawio').relative_to(R)),native_image=str((out/'native.png').relative_to(R)),
          reference_fidelity='not_certified_development_only',text_glyph_path_substitution=False,whole_figure_image_wrapper=False,full_QA_complete=False)
    except Exception as e:report.update(error=type(e).__name__+':'+str(e)[:2500],traceback=traceback.format_exc()[-5000:])
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='traceback'},ensure_ascii=False),flush=True);return report
