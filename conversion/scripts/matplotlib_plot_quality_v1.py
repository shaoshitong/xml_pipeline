"""Independent source coverage, unchanged raster gates and actual edit/restore."""
from pathlib import Path
import ast,collections,copy,hashlib,html,io,json,sys,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from auto_quality_common import image_quality,require_rendered_text,structure_checks,rgb
import curate_derived as native
from PIL import Image
from skimage.metrics import structural_similarity
import numpy as np
sha=lambda b:hashlib.sha256(b).hexdigest()
def array_audit(value):
    count=0;errors=[]
    def walk(v):
        nonlocal count
        if isinstance(v,dict):
            if v.get('all_values_retained') and 'shape' in v and 'values' in v:
                count+=1
                if list(np.asarray(v['values'],dtype=object).shape)!=v['shape']:errors.append('array_shape_or_value_count_changed')
                if 'original_mask' in v and list(np.asarray(v['original_mask']).shape)!=v['shape']:errors.append('array_mask_shape_changed')
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(value);return {'ok':not errors,'arrays_checked':count,'errors':errors}
def unseeded_rng(case,execution):
    aliases={};tree=ast.parse((case/'source.py').read_bytes());seeds=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):
            for a in n.names:aliases[a.asname or a.name.split('.')[0]]=a.name
        elif isinstance(n,ast.ImportFrom):
            for a in n.names:aliases[a.asname or a.name]=(n.module or '')+'.'+a.name
    for n in ast.walk(tree):
        if isinstance(n,ast.Call) and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value is not None:
            name=ast.unparse(n.func);first=name.split('.')[0];name=aliases.get(first,first)+name[len(first):]
            if name in {'numpy.random.seed','random.seed'}:seeds.add(name)
    before=execution.get('RNG_state_before',{});after=execution.get('RNG_state_after',{})
    if not before or not after:return True
    if before['numpy_legacy']!=after['numpy_legacy'] and 'numpy.random.seed' not in seeds:return True
    if before['python_random']!=after['python_random'] and 'random.seed' not in seeds:return True
    return any(r['seed_argument'] is None or r['seed_argument']=='<nonprimitive>' for r in after.get('independent_default_rng_generators',[]))
def render(xml,w,h):
    result=native.native_job(xml,w,h,150,R/'conversion/rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not result['ok']:raise ValueError('official_render:'+str({k:v for k,v in result.items() if k!='png'}))
    return result['png'],result['native_render']
def coverage(xml,dom,clipping):
    cells=[c for c in ET.fromstring(xml).iter('mxCell') if c.get('vertex')=='1'];mapping=collections.defaultdict(list)
    for c in cells:mapping[c.get('source_svg_object')].append(c)
    evidence={r['id']:r for r in clipping};errors=[]
    for o in dom['objects']:
        expected=evidence[o['id']].get('output_objects',0 if evidence[o['id']]['clip']=='fully_outside' else 1);actual=mapping[o['id']]
        if len(actual)!=expected:errors.append({'id':o['id'],'reason':'source_paint_object_omitted_or_duplicated'})
        if o['type']=='text':
            if actual and html.unescape(actual[0].get('value',''))!=o['text']:errors.append({'id':o['id'],'reason':'source_text_changed'})
            for c in actual:
                st=dict(x.split('=',1) for x in c.get('style','').split(';') if '=' in x)
                if c.get('visible')=='0' or float(st.get('opacity',100))<=0:errors.append({'id':o['id'],'reason':'source_text_hidden'})
    return {'ok':not errors,'errors':errors,'source_DOM_objects':len(dom['objects']),'native_objects':len(cells)}
def validate(case):
    case=Path(case);p=case/'native_v1';q=p/'quality';q.mkdir(exist_ok=False);report=json.loads((p/'report.json').read_text());xml=(p/'diagram.drawio').read_text();png=(p/'native.png').read_bytes();meta=json.loads((p/'native_render.json').read_text());execution=json.loads((case/'execution.json').read_text());capture=execution['captures'][0];scene=json.loads((case/capture['scene']).read_text());dom=json.loads((p/'source_dom.json').read_text());clipping=json.loads((p/'vector_clip_evidence.json').read_text())
    cov=coverage(xml,dom,clipping);structure=structure_checks(xml);text=require_rendered_text(xml,meta);root=ET.fromstring(xml);cells=[c for c in root.iter('mxCell') if c.get('vertex')=='1'];expected_ps={f['alias']:f['postscript'] for f in report['fonts']};styles={c.get('id'):dict(x.split('=',1) for x in c.get('style','').split(';') if '=' in x) for c in cells};font_errors=[]
    for row in meta.get('actual_platform_font_usage',[]):
        expected=expected_ps.get(styles[row['cell']].get('fontFamily'));active=[f for f in row['fonts'] if f['glyphCount']]
        if expected and (not active or any(not f['isCustomFont'] or f['postScriptName']!=expected for f in active)):font_errors.append(row['cell'])
    font_ok=not font_errors and all(f['status']=='loaded' for f in meta.get('loaded_fonts',[]))
    def gate(reference,target=png):
        try:
            a=rgb(reference);b=rgb(target)
            if a.size==b.size:
                scale=min(1,1024/max(a.size));size=tuple(max(8,round(v*scale)) for v in a.size);aa=np.array(a.resize(size,Image.Resampling.LANCZOS));bb=np.array(b.resize(size,Image.Resampling.LANCZOS));global_score=float(structural_similarity(aa,bb,channel_axis=2,data_range=255))
                if global_score<.90:return {'ok':False,'failures':['global_fidelity_below_0.90'],'ssim_1024':global_score,'fixed_gate_short_circuit':'Same unchanged global gate already fails; expensive local scans are unnecessary for this rejected profile.'}
            return image_quality(reference,target,{},meta.get('actual_text_positions'))
        except Exception as e:return {'ok':False,'failures':[str(e)]}
    svg_png=(p/'source_svg_browser.png').read_bytes();agg_png=(case/capture['png']).read_bytes();original=(case/'original_reference.png').read_bytes();original_gate=gate(original);agg_gate=gate(agg_png);svg_gate=gate(svg_png);source_export_gate=gate(svg_png,agg_png)
    image_objects=[o for o in dom['objects'] if o['type']=='image'];scene_images=[a for a in scene['artists'] if a.get('role')=='source_image'];image_gids={a['gid'] for a in scene_images};assets_ok=all(o.get('artist_gid') in image_gids for o in image_objects)
    # Independent image assets must originate in captured Matplotlib image Artists.
    assets=[]
    if image_objects and assets_ok:
        dest=q/'source_image_assets';dest.mkdir()
        for o in image_objects:
            head,payload=o['href'].split(',',1);data=__import__('base64').b64decode(payload) if ';base64' in head else __import__('urllib.parse',fromlist=['unquote_to_bytes']).unquote_to_bytes(payload);digest=sha(data);file=dest/(digest+'.png');file.write_bytes(data)
            with Image.open(io.BytesIO(data)) as a,Image.open(io.BytesIO(agg_png)) as b:
                if a.size==b.size and a.convert('RGBA').tobytes()==b.convert('RGBA').tobytes():assets_ok=False
            assets.append({'source_svg_object':o['id'],'file':str(file.relative_to(R)),'sha256':digest,'source_AxesImage_arrays':[{k:a[k] for k in ['gid','array_file','array_sha256','shape']} for a in scene_images]})
    arrays=array_audit(scene)
    for artist in scene['artists']:
        if artist.get('role')=='source_image':
            path=case/artist['array_file']
            if sha(path.read_bytes())!=artist['array_sha256'] or list(np.load(path,allow_pickle=False).shape)!=artist['shape']:arrays['ok']=False;arrays['errors'].append('source_image_array_changed')
            mask=case/artist['mask_file']
            if sha(mask.read_bytes())!=artist['mask_sha256'] or list(np.load(mask,allow_pickle=False).shape)!=artist['shape']:arrays['ok']=False;arrays['errors'].append('source_image_mask_changed')
    complete=bool(execution.get('complete_export_parameters_recorded') and execution.get('RNG_state_before') and execution.get('RNG_state_after') and scene.get('actual_source_export_settings') and scene['all_data_vertices_and_offsets_retained'] and arrays['ok'] and not execution.get('source_text_glyph_path_events'))
    unseeded=unseeded_rng(case,execution);potential=cov['ok'] and structure['ok'] and font_ok and assets_ok and complete and svg_gate['ok'] and ((original_gate['ok'] and not unseeded) or (agg_gate['ok'] and source_export_gate['ok']))
    if potential:
        gids={a['gid'] for a in scene['artists'] if a.get('role') in {'data_line','collection','source_image'} or a.get('role')=='patch' and a.get('data_patch')}
        candidates=[c for c in cells if c.get('matplotlib_artist_gid') in gids and ('stencil(' in c.get('style','') or 'shape=image;' in c.get('style',''))]
        if not candidates:raise ValueError('no_independent_data_paint_for_edit_probe')
        target=next((c for c in candidates if c.get('matplotlib_artist_gid') in {a['gid'] for a in scene['artists'] if a.get('role')=='data_line'}),candidates[0]);mutant=copy.deepcopy(root);m=next(c for c in mutant.iter('mxCell') if c.get('id')==target.get('id'));g=m.find('mxGeometry');g.set('x',str(float(g.get('x','0'))+17));mx=ET.tostring(mutant,encoding='unicode');(q/'mutated.drawio').write_text(mx);w,h=Image.open(io.BytesIO(png)).size;mp,_=render(mx,w,h);rp,_=render(xml,w,h);(q/'mutated.png').write_bytes(mp);(q/'restored.png').write_bytes(rp);a=np.asarray(Image.open(io.BytesIO(png)).convert('RGBA'));b=np.asarray(Image.open(io.BytesIO(mp)).convert('RGBA'));r=np.asarray(Image.open(io.BytesIO(rp)).convert('RGBA'));changed=int(np.any(a!=b,axis=2).sum());restored=bool(np.array_equal(a,r));edit_ok=changed>0 and restored
    else:target=None;changed=0;restored=False;edit_ok=False;rp=None
    common_ok=cov['ok'] and structure['ok'] and font_ok and assets_ok and edit_ok and complete and svg_gate['ok'];replay_ok=common_ok and agg_gate['ok'] and source_export_gate['ok']
    original_ok=common_ok and original_gate['ok'] and not unseeded
    out={'ok':original_ok or replay_ok,'independent_source_coverage':cov,'source_array_shape_and_count_audit':arrays,'structure':structure,'actual_rendered_text':text,'source_font_custom_faces_match':font_ok,'source_font_errors':font_errors,'source_image_assets_complete':assets_ok,'source_image_assets':assets,'complete_recorded_source_export_and_RNG_contract':complete,'all_raw_Artist_arrays_sha256':sha((case/capture['scene']).read_bytes()),'input_data_point_or_path_vertices':scene['data_point_or_path_vertex_count'],
      'source_SVG_native_gate':svg_gate,'fresh_Agg_native_gate':agg_gate,'fresh_SVG_Agg_gate':source_export_gate,'provider_original_reference_gate':original_gate,'unseeded_source_RNG_prevents_original_reference_certification':unseeded,
      'profiles':{'provider_original_reference_aligned':original_ok,'source_replay_aligned':replay_ok},'actual_edit_probe':{'performed':target is not None,'skipped_reason':None if target is not None else 'Both declared profiles already fail fixed closed gates; no publication is possible.','cell':target.get('id') if target is not None else None,'source_artist_gid':target.get('matplotlib_artist_gid') if target is not None else None,'changed_RGBA_pixels':changed,'restore_RGBA_exact':restored,'restore_PNG_bytes_exact':rp==png,'published_source_XML_unchanged':sha((p/'diagram.drawio').read_bytes())==sha(xml.encode())},'model_calls':0}
    (q/'report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');return out
