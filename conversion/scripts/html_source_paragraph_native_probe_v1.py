"""One consumed paragraph -> one real editable native label, fixed semantics."""
from pathlib import Path
import copy,hashlib,json,mimetypes,sqlite3,sys,urllib.parse,uuid,xml.etree.ElementTree as E
from PIL import Image
from playwright.sync_api import sync_playwright
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import html_source_whitespace_capture_v8 as cap
from html_source_clip_v8 import ink_metrics
from native_worker import native
ID='0bc37fc196e3f7ea12094ff9fe36f687bf2ff2c17308c27c7435ba5677ed4d20';B=W/'html_source_frontend_v8_development'/ID/'5c373c4cb5104374be4d4adcfa481ad1/compiler';sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 out=W/'html_source_paragraph_native_probe_v1'/uuid.uuid4().hex;out.mkdir(parents=True)
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as d:row=d.execute('select input_record,input_manifest from jobs where id=?',(ID,)).fetchone()
 source,manifest=map(json.loads,row);code=(R/manifest['source_code']).read_bytes();assert sha(code)==source['code_sha256'];assets=(R/manifest['asset_root']).resolve();size=Image.open(B/'source/source.native.png').size;blocked=[]
 with sync_playwright()as pw:
  browser=pw.chromium.launch(executable_path=cap.CHROME,args=['--disable-dev-shm-usage']);context=browser.new_context(viewport=dict(zip(('width','height'),size)),java_script_enabled=False,service_workers='block')
  def route(req):
   u=urllib.parse.urlparse(req.request.url);name=urllib.parse.unquote(u.path.lstrip('/'))
   if u.hostname!='source.invalid':blocked.append(req.request.url);req.abort();return
   if name=='index.html':req.fulfill(body=code,content_type='text/html');return
   target=(assets/name).resolve();assert target.is_relative_to(assets)and target.is_file();req.fulfill(body=target.read_bytes(),content_type=mimetypes.guess_type(str(target))[0]or'application/octet-stream')
  context.route('**/*',route);page=context.new_page();page.goto('http://source.invalid/index.html',wait_until='networkidle');page.evaluate('document.fonts.ready');png=cap.screenshot(page);assert png==(B/'source/source.native.png').read_bytes();dom=page.evaluate(cap.source_js());dom=page.evaluate(cap.SOURCE_GLYPHS,dom)['dom'];obj=next(o for o in dom['objects']if str(o['id']+1)=='98');snap=page.evaluate((W/'scripts/html_source_paragraph_snapshot_v1.js').read_text(),{'object':obj});assert cap.screenshot(page)==png
  session=context.new_cdp_session(page);session.send('DOM.enable');session.send('CSS.enable');root_node=session.send('DOM.getDocument',{'depth':-1})['root']['nodeId']
  from compiler_native_text_node_cdp_v2 import physical_fonts
  for run in snap['textNodes']:
   runtime=session.send('Runtime.evaluate',{'expression':'window.__sourceParagraphOriginalNodes['+str(run['index'])+'].parentElement','returnByValue':False})['result'];node=session.send('DOM.requestNode',{'objectId':runtime['objectId']})['nodeId'];session.send('Runtime.releaseObject',{'objectId':runtime['objectId']});run['actual_fonts']=physical_fonts(session,node,run['child_index'],run['text'])
  session.detach();page.evaluate("""()=>{const ranges=window.__sourceParagraphOriginalNodes.map(n=>{const r=document.createRange();r.selectNodeContents(n);return r;});CSS.highlights.set('paragraph-native-source',new Highlight(...ranges));const s=document.createElement('style');s.textContent='::highlight(paragraph-native-source){color:transparent;text-shadow:none;text-decoration-color:transparent;}';document.head.append(s)}""");hidden=cap.screenshot(page);context.close();browser.close()
 assert not blocked;(out/'source.png').write_bytes(png);(out/'source_hidden.png').write_bytes(hidden);(out/'source_paragraph.json').write_text(json.dumps(snap,ensure_ascii=False,indent=2));(out/'source_dom.json').write_text(json.dumps(dom,ensure_ascii=False,indent=2))
 root=E.fromstring((B/'source_compiled.drawio').read_text());cells=root.find('.//mxGraphModel/root');selected={str(o['id']+1)for o in dom['objects']if o['type']=='text'and o['qaOwner']in snap['subtreeOwners']};removed=[c for c in list(cells)if c.get('id')in selected];assert removed;index=min(list(cells).index(c)for c in removed)
 for c in removed:cells.remove(c)
 all_source_text={str(o['id']+1)for o in dom['objects']if o['type']=='text'}
 # Isolate the fixed paragraph mechanism while retaining all original native
 # backgrounds/assets. This is a development probe, never whole-source QA.
 for c in list(cells):
  if c.get('id')in all_source_text:cells.remove(c)
 index=min(index,len(cells))
 owner=snap['rootRect'];cell=E.Element('mxCell',id='source_paragraph_owner_'+str(snap['rootOwner']),vertex='1',parent='1',value=snap['markup'],style='shape=text;html=1;whiteSpace=wrap;overflow=visible;fillColor=none;strokeColor=none;align=left;verticalAlign=top;spacing=0;spacingTop=0;spacingRight=0;spacingBottom=0;spacingLeft=0;autosize=0;nl2Br=0;fontSize=26;fontFamily=Helvetica Neue,Arial,sans-serif;')
 E.SubElement(cell,'mxGeometry',{'x':str(owner['x']+32),'y':str(owner['y']+32),'width':str(owner['width']),'height':str(owner['height']),'as':'geometry'});cells.insert(index,cell);xml=E.tostring(root,encoding='unicode');native_size=[n+64 for n in size];renderer=W/'rendering_html_source_paragraph_probe_v1/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
 def render(xml,name):
  a=native.native_job(xml,*native_size,180,renderer,8192,runtime);assert a.get('ok'),a.get('error');(out/(name+'.drawio')).write_text(xml);(out/(name+'.png')).write_bytes(a['png']);(out/(name+'.json')).write_text(json.dumps(a['native_render'],ensure_ascii=False,indent=2));return a
 initial=render(xml,'initial');obs=initial['native_render']['source_paragraph_observation'];assert len(obs)==1;actual=obs[0]['rootRect'];delta={k:owner[k]+(32 if k in('x','y')else 0)-actual[k]for k in owner};assert abs(delta['width'])<.001 and abs(delta['height'])<.001,'native_source_root_box_size_changed';before_anchor=copy.deepcopy(actual)
 # Align the actual original paragraph border box, independently of glyph ink
 # or reference pixels. The official native HTML label adds its own box offset.
 # Exactly one geometry-derived correction is allowed; no raster search.
 if abs(delta['x'])>.001 or abs(delta['y'])>.001:
  before=cell.get('value');assert 'left: 0px; top: 0px;'in before;cell.set('value',before.replace('left: 0px; top: 0px;','left: '+str(delta['x'])+'px; top: '+str(delta['y'])+'px;',1));xml=E.tostring(root,encoding='unicode');initial=render(xml,'source_box_registered');obs=initial['native_render']['source_paragraph_observation'];assert len(obs)==1;actual=obs[0]['rootRect'];assert all(abs(owner[k]+(32 if k in('x','y')else 0)-actual[k])<.001 for k in owner),'native_source_root_box_registration_failed'
 actual_runs=obs[0]['runs'];assert len(actual_runs)==len(snap['textNodes']),'source_paragraph_text_node_count_changed';residuals=[]
 for a,b in zip(snap['textNodes'],actual_runs):
  assert a['text']==b['text'];assert len(a['chars'])==len(b['chars']);assert sorted((f['postScriptName'],f['glyphCount'])for f in a['actual_fonts'])==sorted((f['postScriptName'],f['glyphCount'])for f in b['actual_fonts']),'source_native_actual_Text_face_or_glyphcount_changed'
  for x,y in zip(a['chars'],b['chars']):
   assert x['text']==y['text'];residuals.extend(abs(x[k]+(32 if k in('x','y')else 0)-y[k])for k in('x','y','width','height'))
 bg=E.fromstring(xml);next(c for c in bg.iter('mxCell')if c.get('id')==cell.get('id')).set('value','');background=render(E.tostring(bg,encoding='unicode'),'hidden');ink=ink_metrics(png,hidden,initial['png'],background['png'],(32,32));result={'id':ID,'rootOwner':snap['rootOwner'],'replaced_source_objects':sorted(selected),'new_editable_native_cells':1,'source_code_sha256':source['code_sha256'],'source_image_sha256':source['image_sha256'],'original_SOURCE_root_border_box':owner,'initial_native_root_border_box':before_anchor,'final_native_root_border_box':actual,'root_geometry_registration_translation':delta,'registration_basis':'SOURCE_and_native_original_paragraph_border_boxes_only_no_ink_or_reference_pixels','complete_Unicode_and_text_node_order_preserved':True,'actual_text_node_PostScript_and_glyph_counts_preserved':True,'maximum_grapheme_Range_difference':max(residuals or[0]),'signed_SOURCE_native_paragraph_ink':ink,'source_paragraph':str(out/'source_paragraph.json'),'native_observation':str(out/'source_box_registered.json'),'actual_native_XML':str(out/'source_box_registered.drawio'),'actual_native_PNG':str(out/'source_box_registered.png'),'models':0,'new_heldout':0,'production_qualification':False,'other_source_text_omitted_for_isolated_mechanism_probe':True,'target_pixel_parameter_fitting':False};(out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({'report':str(out/'report.json'),**result}),flush=True)
if __name__=='__main__':main()
