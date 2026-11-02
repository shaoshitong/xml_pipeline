"""Pure synthetic SVG visibility/font/range controls in a pidfd-owned child."""
from pathlib import Path
import hashlib,io,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sha=lambda b:hashlib.sha256(b).hexdigest()
NAMES=('svg_source_endpoint_descriptors_v1.js','svg_dom_v7.js','svg_dom_source_scene_v2.js','compiler_svg_scene_frontend_v7.py')

def child(work):
 from PIL import Image
 import numpy as np
 from playwright.sync_api import sync_playwright
 import compiler_svg_scene_frontend_v7 as frontend
 from svg_source_endpoint_bridge_v1 import capture,_path
 from svg_source_endpoint_direction_v1 import directions
 work=Path(work);work.mkdir(parents=True,exist_ok=False);pins={n:sha((W/'scripts'/n).read_bytes())for n in NAMES}
 base='<text id="baseline" x="5" y="140" font-family="Arial" font-size="15">BASE VISIBLE</text>'
 marker='<defs><marker id="m" refX="10" refY="5" markerWidth="10" markerHeight="10" orient="auto"><path d="M0 0 L10 5 L0 10Z"/></marker></defs>'
 line='<path id="visible_child" d="M10 30 L80 30" fill="none" stroke="black" marker-end="url(#m)"/>'
 cases=[('display_none_M_ignored','<g display="none"><path id="hidden" d="M0 0" marker-end="url(#m)"/></g>',[],[],False),('visibility_hidden_M_ignored','<path visibility="hidden" id="hidden" d="M0 0" marker-end="url(#m)"/>',[],[],False),('hidden_g_visible_path_marker','<g visibility="hidden">'+line.replace('id="visible_child"','id="visible_child" visibility="visible"')+'</g>',['visible_child'],[],False),('collapse_g_visible_path_marker','<g visibility="collapse">'+line.replace('id="visible_child"','id="visible_child" visibility="visible"')+'</g>',['visible_child'],[],False),('hidden_text_visible_tspan','<text visibility="hidden" x="5" y="70" font-family="Arial" font-size="19">HIDDEN<tspan visibility="visible">VISIBLE</tspan>HIDDEN</text>',[],['VISIBLE'],False),('collapse_text_visible_tspan','<text visibility="collapse" x="5" y="70" font-family="Arial" font-size="19"><tspan visibility="visible">VISIBLE</tspan></text>',[],['VISIBLE'],False),('opacity_zero_child_cannot_revive','<g opacity="0"><path opacity="1" visibility="visible" d="M0 0" marker-end="url(#m)"/><text opacity="1" visibility="visible" x="5" y="60">NO PAINT</text></g>',[],[],False),('display_none_child_cannot_revive','<g display="none"><path display="inline" visibility="visible" d="M0 0" marker-end="url(#m)"/><text display="inline" visibility="visible" x="5" y="60">NO PAINT</text></g>',[],[],False),('visible_text_hidden_different_font_descendant','<text x="5" y="70" font-family="Arial" font-size="19">VISIBLE<tspan visibility="hidden" font-family="Times New Roman">HIDDEN GLYPHS</tspan></text>',[],['VISIBLE'],False),('opacity_zero_tspan_visible_child_cannot_revive','<text x="5" y="70" font-family="Arial" font-size="19">VISIBLE<tspan opacity="0"><tspan opacity="1" visibility="visible">NO PAINT</tspan></tspan></text>',[],['VISIBLE'],False),('hidden_use_instance_explicit_pending','<defs><g id="source_use"><path visibility="visible" d="M10 30 L80 30" fill="none" stroke="black"/></g></defs><use visibility="hidden" href="#source_use"/>',[],[],True),('marker_definition_visibility_explicit_pending','<defs><marker id="ambiguous" visibility="hidden" refX="10" refY="5" markerWidth="10" markerHeight="10" orient="auto"><path visibility="visible" d="M0 0 L10 5 L0 10Z"/></marker></defs><path id="visible_child" d="M10 30 L80 30" fill="none" stroke="black" marker-end="url(#ambiguous)"/>',['visible_child'],[],True)]
 cases.extend([('zero_opacity_use_definition_explicit_pending','<defs><g id="source_use" opacity="0"><path opacity="1" visibility="visible" d="M10 30 L80 30" fill="none" stroke="black"/></g></defs><use href="#source_use"/>',[],[],True),('zero_opacity_marker_definition_explicit_pending','<defs><marker id="transparent_marker" opacity="0" refX="10" refY="5" markerWidth="10" markerHeight="10" orient="auto"><path opacity="1" visibility="visible" d="M0 0 L10 5 L0 10Z"/></marker></defs><path id="visible_child" d="M10 30 L80 30" fill="none" stroke="black" marker-end="url(#transparent_marker)"/>',['visible_child'],[],True)])
 rows=[]
 def pixels(png):return Image.open(io.BytesIO(png)).convert('RGBA').tobytes()
 with sync_playwright()as pw:
  browser=pw.chromium.launch(executable_path=frontend.CHROME,args=['--disable-dev-shm-usage']);context=browser.new_context(viewport=dict(width=256,height=256));page=context.new_page()
  try:
   for name,fragment,expected_shapes,expected_text,pending in cases:
    page.set_content('<style>body{margin:0;background:white}</style><svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">'+marker+base+fragment+'</svg>');before=page.content();png=frontend._screenshot(page);domains=[]
    for legacy in (True,False):
     dom=capture(page,legacy=legacy);texts=[o['text']for o in dom['objects']if o['type']=='text'];shapes=[o.get('sourceId')for o in dom['objects']if o['type']=='shape'and not o.get('markerOwner')];assert texts==['BASE VISIBLE']+expected_text,(name,texts);assert shapes==expected_shapes,(name,shapes)
     if pending:
      assert any('visibility_context_requires_instance_proof'in json.dumps(issue)for issue in dom['issues']),(name,dom['issues'])
      try:frontend._capture_issue_gate(dom)
      except ValueError:pass
      else:raise AssertionError('ambiguous_instance_visibility_silently_accepted:'+name)
     else:assert not[issue for issue in dom['issues']if issue['reason']!='scene_marker_viewport_clip_unproven'],(name,dom['issues'])
     assert page.content()==before and pixels(frontend._screenshot(page))==pixels(png),'extractor_changed_SOURCE_DOM_or_pixels:'+name;domains.append(dom)
    identity=lambda d:[(o['id'],o['type'],o.get('sourceId'),o.get('text'))for o in d['objects']];assert identity(domains[0])==identity(domains[1]),name
    # Store exact original node objects/attrs, then restore observation wrappers.
    page.evaluate("""()=>{const elements=[...document.querySelectorAll('*')],walker=document.createTreeWalker(document,NodeFilter.SHOW_TEXT),texts=[];while(walker.nextNode())texts.push({node:walker.currentNode,parent:walker.currentNode.parentNode,next:walker.currentNode.nextSibling});window.__visibilityRestore={elements:new Set(elements),attrs:elements.map(e=>({node:e,attrs:[...e.attributes].map(a=>({name:a.name,namespace:a.namespaceURI,value:a.value}))})),texts};}""")
    frontend._wrap_source_runs(page);run_rows=page.evaluate(frontend._RUN_ROWS_JS);assert[r['text']for r in run_rows]==['BASE VISIBLE']+expected_text,(name,run_rows)
    positions,observed=frontend._observe_runs(page,context,None);assert[v['text']for v in positions.values()]==['BASE VISIBLE']+expected_text;assert all(v.get('physical_font_scope')=='one_verified_original_Text_node_only'for v in positions.values());assert pixels(frontend._screenshot(page))==pixels(png),name
    page.evaluate("""()=>{const saved=__visibilityRestore;for(const row of [...saved.texts].reverse())row.parent.insertBefore(row.node,row.next?.parentNode===row.parent?row.next:null);for(const node of [...document.querySelectorAll('*')].reverse())if(!saved.elements.has(node))node.remove();for(const row of saved.attrs){for(const a of [...row.node.attributes])row.node.removeAttributeNS(a.namespaceURI,a.localName);for(const a of row.attrs)row.node.setAttributeNS(a.namespace,a.name,a.value);}delete window.__visibilityRestore;}""")
    assert page.content()==before and pixels(frontend._screenshot(page))==pixels(png),'observation_wrappers_not_exactly_restored:'+name
    colors=np.asarray(Image.open(io.BytesIO(png)).convert('RGB'));row=dict(name=name,expected_original_shapes=expected_shapes,painted_original_texts=['BASE VISIBLE']+expected_text,actual_marker_owners=domains[1]['sourceEndpointDirection']['owners'],source_nonwhite_pixels=int(np.any(colors<245,axis=2).sum()),both_extractor_identities_exact=True,source_DOM_and_RGBA_exactly_restored=True,actual_visible_Text_physical_fonts_only=True,explicit_instance_pending=pending,original_PNG_sha256=sha(png));rows.append(row)
   # Real stale source descriptor: original direction facts must fail after a
   # source d change; reverting it restores the complete original DOM/pixels.
   page.set_content('<style>body{margin:0;background:white}</style><svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">'+marker+base+line+'</svg>');before=page.content();png=frontend._screenshot(page);describe=(W/'scripts/svg_source_endpoint_descriptors_v1.js').read_text();descriptors=page.evaluate('()=>('+describe+')(document.querySelector("svg")).map(({index,descriptor})=>({index,descriptor}))');facts=[dict(index=r['index'],descriptor=r['descriptor'],direction=directions(_path(r['descriptor']),r['descriptor']['matrix']))for r in descriptors];page.locator('#visible_child').evaluate("e=>e.setAttribute('d','M10 30 L90 30')");stale=[]
   for filename in('svg_dom_v7.js','svg_dom_source_scene_v2.js'):
    code=(W/'scripts'/filename).read_text().replace('__SOURCE_ENDPOINT_DESCRIPTORS_V1__',describe)
    try:page.evaluate(code,facts)
    except Exception as error:assert'source_endpoint_owner_descriptor_changed'in str(error);stale.append(filename)
    else:raise AssertionError('stale_source_descriptor_accepted:'+filename)
   page.locator('#visible_child').evaluate("e=>e.setAttribute('d','M10 30 L80 30')");assert page.content()==before and pixels(frontend._screenshot(page))==pixels(png);assert len(stale)==2
  finally:context.close();browser.close()
 assert pins=={n:sha((W/'scripts'/n).read_bytes())for n in NAMES}
 report=dict(schema='actual_Chromium_source_visibility_scope_controls_v1',ok=True,cases=rows,stale_source_descriptor_negatives_rejected=stale,all_source_DOM_and_RGBA_exactly_restored=True,source_metadata_font_range_scope_consistent=True,normal_dataset_conversion_calls=0,new_heldout=0,model_calls=0,pins=pins);p=work/'proof.json';p.write_text(json.dumps(report,indent=2));print(json.dumps(dict(file=str(p),sha256=sha(p.read_bytes()),actual_synthetic_cases=len(rows),stale_negatives=len(stale),normal_calls=0)),flush=True)

def run():
 import initial_conversion_process_v1 as bounded
 work=W/'svg_visibility_source_controls_v1'/uuid.uuid4().hex;result=bounded.run([sys.executable,'-B',str(Path(__file__).resolve()),'--child',str(work/'fixtures')],work/'owned_child',120);receipt=dict(schema='pidfd_owned_source_visibility_scope_controls_v1',process=result,work=str(work),normal_dataset_calls=0,model_calls=0);work.mkdir(parents=True,exist_ok=True);p=work/'receipt.json';p.write_text(json.dumps(receipt,indent=2));print(json.dumps(dict(receipt=str(p),process_ok=result['ok'],returncode=result['returncode'],cleanup_complete=result['cleanup_complete'],stdout=result['stdout_file'],stderr=result['stderr_file'])),flush=True)
if __name__=='__main__':child(sys.argv[2])if'--child'in sys.argv else run()
