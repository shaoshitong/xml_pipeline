"""Whole-source, explicit-root SVG marker composition verification, read-only.

Marker-subset success never resolves untyped open source paths. Fresh exact
inventory, unknown-feature admission and independent source mutation replay are
mandatory before this profile can report complete_source_coverage.
"""
from pathlib import Path
import collections,copy,hashlib,html,io,json,math,sys,xml.etree.ElementTree as E
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path[:0]=[str(W/'prototype'),str(W/'scripts'),str(W/'prototype/svg_marker_font_composition_v1')]
import svg_native_triangle_marker_v1 as marker
import svg_native_marker_edit_probe_v1 as marker_edit
import auto_quality_svg_closed_scene_v1 as closed
import svg_source_scene_dom_v1 as scene
import svg_source_coverage_v2 as inventory
import auto_quality_source_vector_v2 as prior
import svg_marker_font_composition_v1 as composition
POLICY='whole_source_svg_marker_portable_font_dependency_paint_composition_v2'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def require(ok,reason):
    if not ok:raise ValueError(reason)
def canonical(value):return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
def read_owned(root,relative,digest,area='clean'):
    root=Path(root).resolve();logical=Path(relative);require(not logical.is_absolute() and '..' not in logical.parts,'relative_owned_asset_required');require(not any((root/Path(*logical.parts[:i])).is_symlink() for i in range(1,len(logical.parts)+1)),'owned_asset_symlink_forbidden');path=(root/logical).resolve(strict=True);require(path.is_relative_to((root/area).resolve()) and path.is_file(),'asset_outside_closed_data_root:'+str(relative));before=path.stat();raw=path.read_bytes();after=path.stat();require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'asset_changed_while_reading');require(sha(raw)==digest,'asset_sha256_mismatch:'+str(relative));return raw
def asset(root,proof,key):
    entry=proof['assets'][key];return read_owned(root,entry['file'],entry['sha256'])
def configuration(root=R):
    paths=[Path(__file__).resolve(),Path(marker.__file__),Path(marker_edit.__file__),Path(closed.__file__),Path(scene.__file__),Path(prior.__file__),Path(inventory.__file__),Path(composition.__file__),scene.EXTRACTOR,W/'scripts/native_source_editing_v4.py',W/'scripts/native_source_editing_v4.js',W/'scripts/native_font_embedding_batch.py',W/'scripts/auto_quality_font_repair.py',W/'scripts/portable_native_fonts.py',W/'rendering_paintbounds_strict/remote_render.py',W/'rendering_paintbounds_strict/assets/viewer-static.min.js',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'];pins={str(path.resolve()):sha(path.read_bytes()) for path in paths};return {'policy':POLICY+':'+sha(canonical(pins))[:20],'pins':pins,'root':str(Path(root).resolve()),'source_requires_native_info':True}
def close_worker_runtime():scene.close_worker_runtime()

def source_platform_fonts(page,context,dom):
    """Exact source TextNode->one actual parent, never aggregate unrelated runs."""
    mapping=page.evaluate(r"""objects=>{const candidates=[],root=document.querySelector('svg');for(const el of root.querySelectorAll('text')){if(el.closest('defs,marker,symbol,clipPath,mask'))continue;const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){if(!n.textContent.trim())continue;const r=document.createRange();r.selectNodeContents(n);const b=r.getBoundingClientRect();if(b.width&&b.height)candidates.push({node:n,parent:n.parentElement,text:n.textContent,bbox:{x:b.x,y:b.y,w:b.width,h:b.height}})}}const parents=[],rows=[],failures=[];for(const o of objects.filter(o=>o.type==='text')){const matches=candidates.filter(c=>c.text===o.text&&['x','y','w','h'].every(k=>Math.abs(c.bbox[k]-o.originalBoundingBox[k])<1e-7));if(matches.length!==1){failures.push({id:o.id,reason:'source_text_physical_font_instance_not_unique',matches:matches.length});continue}const c=matches[0],walker=document.createTreeWalker(c.parent,NodeFilter.SHOW_TEXT);let n,nonempty=0;while(n=walker.nextNode())if(n.textContent.trim())nonempty++;if(nonempty!==1||parents.includes(c.parent)){failures.push({id:o.id,reason:'source_text_parent_font_usage_not_individually_attributable',nonempty});continue}parents.push(c.parent);rows.push({cell:o.id,index:parents.length-1,text:o.text,bbox:c.bbox})}window.__markerSourceFontParents=parents;return {rows,failures}}""",dom['objects'])
    client=context.new_cdp_session(page);client.send('DOM.enable');client.send('DOM.getDocument',{'depth':-1,'pierce':True});client.send('CSS.enable');usage=[]
    try:
        for row in mapping['rows']:
            remote=client.send('Runtime.evaluate',{'expression':'window.__markerSourceFontParents[%d]'%row['index']})['result'];node=client.send('DOM.requestNode',{'objectId':remote['objectId']})['nodeId'];fonts=client.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
            if not fonts or any(not f.get('postScriptName') or not isinstance(f.get('glyphCount'),int) or f['glyphCount']<0 for f in fonts) or not any(f.get('glyphCount') for f in fonts):mapping['failures'].append({'id':row['cell'],'reason':'source_text_physical_font_usage_missing'})
            usage.append({'cell':row['cell'],'fonts':fonts,'source_text_node_bbox':row['bbox'],'source_text':row['text']})
    finally:
        page.evaluate('delete window.__markerSourceFontParents');client.detach()
    return {'actual_platform_font_usage':usage,'failures':mapping['failures'],'complete':not mapping['failures'] and len(usage)==sum(o['type']=='text' for o in dom['objects']),'basis':'Fresh CDP CSS.getPlatformFontsForNode; exact source TextNode text+bbox mapping; unique one-text-node parent; no CSS family inference.'}

def capture(record,baseline,root):
    from PIL import Image
    from playwright.sync_api import sync_playwright
    code=read_owned(root,record['original_source_code'],record['source_code_sha256']);reference=read_owned(root,record['original_reference'],record['source_image_sha256']);size=Image.open(io.BytesIO(reference)).size;script=scene.EXTRACTOR.read_bytes();blocked=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=prior.CHROME,args=['--disable-dev-shm-usage'])
        try:
            context=browser.new_context(viewport={'width':size[0],'height':size[1]},java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page=context.new_page();page.set_default_timeout(45000);page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+code.decode(),wait_until='load');page.evaluate("([w,h])=>{const s=document.querySelector('svg');if(!s)throw Error('missing SVG');if(!s.viewBox.baseVal.width)s.setAttribute('viewBox',`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h)}",list(size));page.evaluate('document.fonts.ready');wrapper="""() => {const run=(%s),dom=run(),root=document.querySelector('svg');const keys=['backgroundColor','backgroundImage','borderTopWidth','borderRightWidth','borderBottomWidth','borderLeftWidth','borderTopStyle','borderRightStyle','borderBottomStyle','borderLeftStyle','paddingTop','paddingRight','paddingBottom','paddingLeft','overflow','overflowX','overflowY','mixBlendMode','isolation','opacity','filter','clipPath','maskImage'];const css=el=>Object.fromEntries(keys.map(k=>[k,getComputedStyle(el)[k]]));const b=root.getBoundingClientRect();dom.sceneViewport={rootCss:css(root),bodyCss:css(document.body),htmlCss:css(document.documentElement),bbox:{x:b.x,y:b.y,w:b.width,h:b.height},nonAffineCssElements:[root,...root.querySelectorAll('*')].filter(e=>{const c=getComputedStyle(e);return c.transform.startsWith('matrix3d(')||c.perspective!=='none'}).map(e=>({tag:e.localName,id:e.id||''}))};return dom;}"""%script.decode();dom=page.evaluate(wrapper);dom['sourcePhysicalFonts']=source_platform_fonts(page,context,dom);context.close()
        finally:browser.close()
    require(sha(scene.EXTRACTOR.read_bytes())==sha(script),'extractor_changed_during_capture');require(read_owned(root,record['original_source_code'],record['source_code_sha256'])==code and read_owned(root,record['original_reference'],record['source_image_sha256'])==reference,'source_changed_during_capture');scene.enrich_scene(dom)
    if blocked:dom.setdefault('issues',[]).append({'reason':'source_external_resources_blocked','urls':sorted(set(blocked))})
    dom['sceneCapture']={'recordId':record['id'],'recordCodeSha256':sha(baseline.encode()),'sourceCodeSha256':record['source_code_sha256'],'sourceImageSha256':record['source_image_sha256'],'referenceSize':list(size),'extractorSha256':sha(script),'moduleSha256':sha(Path(__file__).read_bytes()),'completeOfflineSource':not blocked,'sourcePayloadHashesRecheckedAfterCapture':True};return dom

def source_inventory(dom,xml,heads=()):
    tree=E.fromstring(xml)
    for cell in tree.iter('mxCell'):
        if cell.get('value'):cell.set('value',html.escape(prior._plain(cell.get('value'))))
    return inventory.audit(dom,E.tostring(tree,encoding='unicode'),{'native_graphviz_arrowheads':[{'source_arrow_object':key} for key in heads]})

def analyse_source(record,baseline,root=R):
    require(record.get('source_format')=='svg','direct_svg_source_required');dom=capture(record,baseline,root);page=list(dom['sceneCapture']['referenceSize']);model=E.fromstring(baseline).find('.//mxGraphModel');require(model is not None and [float(model.get(key,0)) for key in ['pageWidth','pageHeight']]==page,'unregistered_canvas_not_in_marker_composition_v2');proposal=marker.propose_from_scene(dom,baseline,(0,0),page);owners={ctx['owner'] for ctx in dom.get('sceneMetadata',{}).get('markerContexts',{}).values()};head_ids={obj['id'] for obj in dom['objects'] if obj.get('sceneMarkerContexts')};drop=owners|head_ids;filtered=copy.deepcopy(dom);filtered['objects']=[obj for obj in dom['objects'] if obj['id'] not in drop];resolved={item['context'] for item in proposal.get('markers',[]) if item.get('viewport_full_filled_triangle_containment_proven')};filtered['issues']=[issue for issue in dom.get('issues',[]) if not(issue.get('reason')=='scene_marker_viewport_clip_unproven' and issue.get('markerContext') in resolved)];tree=E.fromstring(baseline);container=tree.find('.//mxGraphModel/root')
    for cell in list(container):
        if cell.get('id') in drop:container.remove(cell)
    nonmarker=E.tostring(tree,encoding='unicode');admission=closed._source_admission(filtered,nonmarker);integrity=closed._native_integrity(filtered,nonmarker);count=source_inventory(dom,baseline);paint=prior._paint_coverage(dom,baseline);unknown=list(admission['unsupported']);failures=[]
    unknown += dom['sourcePhysicalFonts']['failures']
    if dom.get('nodes'):unknown.append({'reason':'declared_source_graph_groups_require_dedicated_membership_profile'})
    if not proposal.get('ok') or not proposal.get('complete_source_marker_coverage'):unknown += [{'reason':'source_marker_rule_incomplete','details':proposal.get('failures',[])}]
    if not dom['sceneCapture']['completeOfflineSource']:unknown.append({'reason':'source_not_complete_offline'})
    failures += count['errors']+paint['errors']+integrity['errors'];text_ids=sorted(obj['id'] for obj in dom['objects'] if obj['type']=='text');require(len(text_ids)==len(set(text_ids)),'duplicate_source_text_ids');return {'supported':not unknown,'ok':not unknown and not failures,'unknown_source_features':unknown,'failures':failures,'required_text_cell_ids':text_ids,'source_object_inventory':count,'source_paint_geometry':paint,'source_physical_fonts':dom['sourcePhysicalFonts'],'nonmarker_source_admission':admission,'nonmarker_native_integrity':integrity,'complete_marker_subset':bool(proposal.get('ok') and proposal.get('complete_source_marker_coverage')),'semantic_edge_ids':sorted(owners),'source_objects':[{'id':obj['id'],'type':obj['type'],'marker_head':obj['id'] in head_ids,'marker_owner':obj['id'] in owners,'covered_by_native_object':obj['id'] in {cell.get('id') for cell in E.fromstring(baseline).iter('mxCell')}} for obj in dom['objects']],'dom':dom,'proposal':proposal}

def _proof(record,root):
    marker_record=record.get('svg_marker_composition_v2');require(isinstance(marker_record,dict),'missing_marker_composition_v2_provenance');raw=read_owned(root,marker_record['file'],marker_record['sha256'],'conversion/svg_marker_composition_v2');proof=json.loads(raw);require(proof['policy']==POLICY and proof['id']==record['id'],'composition_proof_identity_mismatch');return proof
def _render(xml,width,height):
    from native_worker import native
    from strict_canvas_gate import require_declared_page
    result=native.native_job(xml,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');require(result['ok'],'source_font_native_render_failed');require_declared_page(result['native_render'],width,height);return result
def font_signature(info):
    counts=collections.Counter()
    for row in info.get('actual_platform_font_usage',[]):
        for font in row.get('fonts',[]):
            if font.get('glyphCount'):counts[(row['cell'],font['postScriptName'])]+=font['glyphCount']
    return counts

def check_source(record,xml,source,root=R,native_info=None):
    result={'supported':False,'ok':False,'profile':POLICY,'failures':[],'evidence':{'complete_source_coverage':False,'required_text_cell_ids':[]}}
    try:
        root=Path(root).resolve();require(record.get('source_format')=='svg' and sha(xml.encode())==record['code_sha256'],'candidate_or_source_format_identity_mismatch');require(read_owned(root,record['code_file'],record['code_sha256']).decode()==xml,'candidate_file_differs_from_supplied_xml');original=read_owned(root,record['original_source_code'],record['source_code_sha256']);require((source.encode() if isinstance(source,str) else source)==original,'supplied_source_differs_from_original');proof=_proof(record,root);baseline=asset(root,proof,'baseline_xml').decode();baseline_record=json.loads(asset(root,proof,'baseline_record'));require(baseline_record['id']==record['id'] and all(baseline_record[key]==record[key] for key in ['source_pair_sha256','source_format','source','category','source_code_sha256','source_image_sha256']),'baseline_source_identity_mismatch');require(sha(baseline.encode())==baseline_record['code_sha256'] and sha(asset(root,proof,'baseline_png'))==baseline_record['image_sha256'],'baseline_payload_identity_mismatch');analysis=analyse_source(record,baseline,root);evidence={key:value for key,value in analysis.items() if key not in ['dom','proposal']};evidence.update(complete_source_coverage=False,current_code_sha256=record['code_sha256'],source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],fresh_source_capture=analysis['dom']['sceneCapture']);result['evidence']=evidence;result['supported']=analysis['supported'];result['failures']=analysis['unknown_source_features']+analysis['failures']
        if not analysis['ok']:return result
        from native_font_embedding_batch import canonical as font_canonical
        base_proposal=analysis['proposal'];require(asset(root,proof,'marker_xml').decode()==base_proposal['candidate_xml'],'source_marker_baseline_not_independently_reconstructed');fontbase=asset(root,proof,'font_baseline_xml').decode();details=json.loads(asset(root,proof,'font_details'));changed={item['cell'] for item in details['changes']};require(changed<=set(analysis['required_text_cell_ids']),'font_mutation_contains_non_source_text_cell');require(font_canonical(baseline,changed)==font_canonical(fontbase,changed),'font_mutation_changed_graph_content');composed=marker.propose_from_scene(analysis['dom'],fontbase,(0,0),analysis['dom']['sceneCapture']['referenceSize']);require(composed['ok'] and composed['complete_source_marker_coverage'],'composed_marker_rule_incomplete');mutation,binding=composition.verified_mutation(analysis['dom'],fontbase,xml,composed);require(font_canonical(base_proposal['candidate_xml'],changed)==font_canonical(xml,changed),'current_candidate_has_nonfont_or_nonsource_mutation');width,height=analysis['dom']['sceneCapture']['referenceSize'];old=_render(baseline,width,height);embedded=_render(fontbase,width,height);require(composition.pixels(old['png'])==composition.pixels(embedded['png'])==composition.pixels(asset(root,proof,'baseline_png')),'font_only_baseline_pixels_changed');current=_render(xml,width,height)['native_render'];require(native_info is None or font_signature(native_info)==font_signature(current),'supplied_native_font_evidence_differs_from_fresh_current');require(font_signature(analysis['dom']['sourcePhysicalFonts'])==font_signature(old['native_render']),'original_source_physical_faces_or_glyph_counts_differ_from_native');require(font_signature(old['native_render'])==font_signature(embedded['native_render'])==font_signature(current),'physical_font_faces_or_glyph_counts_changed');require(all(font.get('isCustomFont') for row in current.get('actual_platform_font_usage',[]) for font in row.get('fonts',[]) if font.get('glyphCount')),'noncustom_current_font');require(source_inventory(analysis['dom'],xml,composed['consumed_source_head_ids'])['ok'],'current_source_text_or_object_inventory_mismatch');edge_ids=sorted(cell.get('id') for cell in E.fromstring(xml).iter('mxCell') if cell.get('edge')=='1');require(edge_ids==analysis['semantic_edge_ids'],'current_semantic_edges_do_not_exactly_match_source_owners');evidence.update(complete_source_coverage=True,required_text_cell_ids=analysis['required_text_cell_ids'],source_marker_independent_replay=binding,mutation_set=mutation,font_only_source_physical_faces_glyphs_and_pixels_verified=True,all_current_semantic_edge_ids=edge_ids);result['ok']=True;return result
    except Exception as error:result['failures'].append({'reason':'whole_source_composition_verification_failed','error':str(error)[:2000]});return result
    finally:close_worker_runtime()

def registration_record(record,reference,xml,root=R):
    from PIL import Image
    model=E.fromstring(xml).find('.//mxGraphModel');require(model is not None and [float(model.get(key,0)) for key in ['pageWidth','pageHeight']]==list(Image.open(io.BytesIO(reference)).size),'marker_composition_requires_unchanged_original_page');return record,None

def _load_fonts(page,xml):
    model=E.fromstring(xml).find('.//mxGraphModel');fonts=[]
    for entry in (model.get('extFonts') or '').split('|'):
        if not entry:continue
        family,uri=entry.split('^',1);require(uri.startswith('data:font/'),'editing_font_requires_inline_verified_font');fonts.append({'family':family,'uri':uri})
    page.evaluate('''async fonts=>{for(const f of fonts){const face=new FontFace(f.family,`url(${JSON.stringify(f.uri)})`);await face.load();document.fonts.add(face);}await document.fonts.ready;}''',fonts)

def audit_editing(record,xml,source_profile,root=R):
    require(source_profile.get('supported') is True and source_profile.get('ok') is True and source_profile.get('evidence',{}).get('complete_source_coverage') is True,'editing_requires_verified_whole_source_not_marker_subset');return research_editing(record,xml,root,require_complete=True)

def research_editing(record,xml,root=R,require_complete=False):
    """RO diagnostics for current XML; partial source evidence stays explicit."""
    from playwright.sync_api import sync_playwright
    from native_source_editing_v4 import validate_report
    proof=_proof(record,root);baseline=asset(root,proof,'baseline_xml').decode();analysis=analyse_source(record,baseline,root);require(analysis['complete_marker_subset'],'editing_requires_complete_source_marker_subset');require(not require_complete or analysis['ok'],'editing_source_unknown_features_remain');fontbase=asset(root,proof,'font_baseline_xml').decode();proposal=marker.propose_from_scene(analysis['dom'],fontbase,(0,0),analysis['dom']['sceneCapture']['referenceSize']);composition.verified_mutation(analysis['dom'],fontbase,xml,proposal);edge_ids=sorted(cell.get('id') for cell in E.fromstring(xml).iter('mxCell') if cell.get('edge')=='1');require(edge_ids==analysis['semantic_edge_ids'],'editing_semantic_edge_inventory_changed');width,height=analysis['dom']['sceneCapture']['referenceSize'];fresh=_render(xml,width,height);work=Path(root)/'conversion/svg_marker_composition_v2'/record['id']/'editing';work.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=prior.CHROME,args=['--disable-dev-shm-usage'])
        try:
            page=browser.new_page();page.route('**/*',lambda route:route.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(W/'rendering_paintbounds_strict/assets/viewer-static.min.js'));_load_fonts(page,xml);moves=page.evaluate((W/'scripts/native_source_editing_v4.js').read_text(),xml);page.close();validate_report(moves);require(moves['edge_count']==len(edge_ids),'editing_not_all_semantic_edges');descriptors=[{'edge':edge,'side':side} for edge in edge_ids for side in ['start','end']];padded=composition.padded_edit_probe(browser,xml,descriptors,width,height,fresh['png'],work)
        finally:browser.close()
    try:factory=marker_edit.audit(xml,proposal['markers'])
    finally:close_worker_runtime()
    return {'ok':bool(moves['ok'] and padded['ok'] and factory['ok']),'profile':'all_current_source_owned_semantic_edges_and_native_marker_intervention_v2','moves':moves['moves'],'edge_count':len(edge_ids),'model_and_all_live_states_restored':moves['model_and_all_live_states_restored'],'full_restore':bool(padded['ok'] and all(row['full_model_and_native_pixels_restored'] for row in padded['probes'])),'fixed_viewport_pixels':padded,'all_marker_factory_endpoint_rotation_and_restore':factory,'complete_source_coverage':bool(analysis['ok']),'unknown_source_features':analysis['unknown_source_features'],'scope':'All current XML semantic edges and all marker factories; partial source remains research-only and never whole qualification.','accepted':False}
