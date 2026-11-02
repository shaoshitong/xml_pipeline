import json,sys,uuid,hashlib,io,copy,datetime,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
from playwright.sync_api import sync_playwright
from compiler_language_capture_v1 import screenshot
from PIL import Image
ident='0593a28ecc6e324f9bd19cdd673619ddf61a96328c03b396f26ec8dfc3f5e693';dev=W/'tikz_node_paint_source_development_v2/6239bd2f19ec4143896665a3736ab666';source=list((W/'compiler_tikz_source_viewport_v1/program_runs/tikz_fixed_inspection_unseen100_20261101_v1_C').glob('*_'+ident))[0]/'source';original=(source/'source.svg').read_bytes();dom=json.loads((source/'source_dom.json').read_bytes());proof=json.loads((dev/ident/'source_vector_ownership_contour_match_v6.json').read_bytes());assert proof['matched_labels']==proof['labels']==6;byid={o['id']:o for o in dom['objects']};ids=[byid[p['source_object']]['sourceId']for r in proof['rows']for p in r['vector_agreement']];ns='http://www.w3.org/2000/svg';E.register_namespace('',ns);base=E.fromstring(original);grouped=copy.deepcopy(base);members=[]
for id in ids:
 nodes={n.get('id'):n for n in grouped.iter()if n.get('id')};node=nodes[id];parents={c:p for p in grouped.iter()for c in p};parent=parents[node];children=list(parent);index=children.index(node);owned=[node]
 for child in children[index+1:]:
  if child.tag!='{'+ns+'}text':break
  owned.append(child)
 assert len(owned)>1;g=E.Element('{'+ns+'}g',{'data-source-owned-label-probe':id});parent.insert(index,g)
 for child in owned:parent.remove(child);g.append(child)
 members.append([child.get('id')for child in owned])
order=lambda tree:[n.get('id')for n in tree.iter()if n.get('id')];assert order(base)==order(grouped);assert all(E.canonicalize(E.tostring(next(n for n in base.iter()if n.get('id')==id),encoding='unicode'))==E.canonicalize(E.tostring(next(n for n in grouped.iter()if n.get('id')==id),encoding='unicode'))for id in order(base));negative=copy.deepcopy(grouped);next(n for n in negative.iter()if n.get('id')==ids[0]).set('transform','translate(.25,0)');variants=[('pristine',base),('source_owned_groups',grouped),('pristine_replay',base),('true_shift_negative',negative)];run=W/'tikz_source_owned_grouping_control_v4'/uuid.uuid4().hex;run.mkdir(parents=True,exist_ok=False);images={}
with sync_playwright()as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu','--disable-lcd-text'])
 try:
  for name,tree in variants:
   page=browser.new_page(viewport=dict(width=2303,height=345),java_script_enabled=True,service_workers='block');page.route('**/*',lambda r:r.abort());page.set_content('<style>html,body{margin:0;padding:0;background:white;overflow:hidden}</style>'+E.tostring(tree,encoding='unicode'));page.evaluate('async()=>{document.body.getBoundingClientRect();for(const f of document.fonts)await f.load();await document.fonts.ready;await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame)}');data=screenshot(page);images[name]=Image.open(io.BytesIO(data)).convert('RGB');(run/(name+'.png')).write_bytes(data);page.close()
 finally:browser.close()
a=images['pristine'];diffs={name:sum(x!=y for x,y in zip(a.getdata(),im.getdata()))for name,im in images.items()};result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),work=str(run),source_svg_sha256=hashlib.sha256(original).hexdigest(),source_label_blocks=members,primitive_attributes_and_D_unchanged=True,primitive_order_unchanged=True,changed_pixels=diffs,source_grouping_RGB_exact=diffs['source_owned_groups']==0,source_replay_RGB_exact=diffs['pristine_replay']==0,true_shift_negative_changed=diffs['true_shift_negative']>0,original_source_file_unchanged=(source/'source.svg').read_bytes()==original,target_pixels_read=False,normal_conversions=0,model_calls=0,goal_complete=False);(run/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
