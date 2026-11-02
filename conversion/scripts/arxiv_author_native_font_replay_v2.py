"""Fresh source-only official XML replay plus exact Text-backend font audit.

No PDF import, geometry conversion, model call or old-output modification.
"""
from pathlib import Path
import argparse,collections,concurrent.futures,datetime,hashlib,io,json,os,shutil,sqlite3,subprocess,sys,time,xml.etree.ElementTree as ET,zipfile
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';D=P/'author_native_source_replay_v1';sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from arxiv_author_native_assets_v1 import dependencies,sha
from arxiv_sourceonly_bulk_200_v1_1 import facts
from arxiv_bulk_official_xml_png_v1 import OfficialXmlPng,WAR
from compiler_native_text_node_cdp_v2 import physical_fonts
from PIL import Image
from fontTools.ttLib import TTFont
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
LOAD=r'''async model=>{const ui=window.__bulkUi,g=ui.editor.graph;ui.editor.setGraphXml(mxUtils.parseXml(model).documentElement);g.clearSelection();g.refresh();g.view.validate();await document.fonts.ready;return {cells:Object.keys(g.model.cells).length,vertices:Object.values(g.model.cells).filter(c=>c.vertex).length,edges:Object.values(g.model.cells).filter(c=>c.edge).length};}'''
EXPORT=r'''options=>{const g=window.__bulkUi.editor.graph;return mxUtils.getXml(g.getSvg(options.background,options.scale,8));}'''
OBSERVE=r'''()=>{const root=document.querySelector('svg'),w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),runs=[],parents=new Map;let n;while(n=w.nextNode()){if(!n.textContent.trim()||!n.parentElement.closest('text,foreignObject'))continue;const p=n.parentElement;if(!parents.has(p)){const id='arxiv-native-font-'+parents.size;p.setAttribute('data-arxiv-native-font',id);parents.set(p,id)}const s=getComputedStyle(p),r=document.createRange();r.selectNodeContents(n);const b=r.getBoundingClientRect();if(!(b.width>0&&b.height>0)||s.visibility==='hidden'||s.display==='none')continue;runs.push({selector:'[data-arxiv-native-font="'+parents.get(p)+'"]',child_index:Array.from(p.childNodes).indexOf(n),text:n.textContent,fontFamily:s.fontFamily,fontWeight:s.fontWeight,fontStyle:s.fontStyle,fontSize:s.fontSize,fontVariationSettings:s.fontVariationSettings,rect:{x:b.x,y:b.y,width:b.width,height:b.height}})}return runs;}'''
CATALOG=None
def catalog():
 global CATALOG
 if CATALOG is None:
  CATALOG=collections.defaultdict(list)
  for line in subprocess.check_output(['fc-list','--format=%{postscriptname}\t%{file}\t%{index}\n'],text=True).splitlines():
   p=line.split('\t')
   if len(p)!=3:continue
   for ps in p[0].split(','):CATALOG[ps].append((p[1],int(p[2] or 0)))
 return CATALOG
def pixels(data):
 im=Image.open(io.BytesIO(data)).convert('RGBA');return im.size,im.tobytes()
def physical_asset(font):
 found={}
 for name,index in catalog().get(font['postScriptName'],[]):
  p=Path(name);blob=p.read_bytes();found[(sha(blob),index)]=(p,blob,index)
 out={k:font.get(k) for k in ['postScriptName','familyName','isCustomFont']}
 if font.get('isCustomFont'):return dict(out,status='custom_face_requires_inline_original_font_asset_binding')
 if len(found)!=1:return dict(out,status='pending_missing_or_ambiguous_physical_font_file',matches=len(found))
 (digest,index),(path,blob,index)=next(iter(found.items()));ft=TTFont(io.BytesIO(blob),fontNumber=index);flags=ft['OS/2'].fsType if 'OS/2' in ft else 0;destination=D/'font_dependencies'/(digest+path.suffix.lower());destination.parent.mkdir(exist_ok=True)
 if not destination.exists():
  tmp=destination.with_name(destination.name+'.'+str(os.getpid())+'.tmp');tmp.write_bytes(blob);os.replace(tmp,destination)
 assert sha(destination.read_bytes())==digest
 out.update(status='current_runtime_physical_font_bytes_pinned',file=str(destination.relative_to(R)),sha256=digest,original_runtime_path=str(path),face_index=index,physical_family=ft['name'].getDebugName(1),physical_postscript=ft['name'].getDebugName(6),font_embedding_fsType=flags,restricted_embedding=bool(flags&0x2 or flags&0x200),variable_font='fvar' in ft,currently_system_dependent_not_in_author_XML=True);ft.close();return out
def screenshot(renderer,svg,folder,name):
 page=renderer.render_page;page.set_content('<html><head><base href="'+renderer.origin+'/"></head><body style="margin:0;background:white">'+svg+'</body></html>');page.evaluate('document.fonts.ready')
 closure=page.evaluate('''async()=>{let refs=[...document.querySelectorAll('svg image,svg img')].map(n=>n.getAttribute('href')||n.getAttribute('xlink:href')||n.getAttribute('src')),failed=[];for(const ref of refs){if(!ref)continue;try{await new Promise((yes,no)=>{let image=new Image;image.onload=()=>image.naturalWidth?yes():no();image.onerror=no;image.src=ref})}catch(e){failed.push(ref.split(',',1)[0].slice(0,100))}}return {image_objects:refs.length,all_images_decode_completed:true,failed,fonts_status:document.fonts.status}}''')
 if closure['failed']:raise ValueError('fresh_official_SVG_has_unresolved_image')
 e=page.locator('svg').first;box=e.bounding_box()
 if not box or box['width']>8190 or box['height']>8190 or min(box['width'],box['height'])<2:raise ValueError('invalid_fresh_official_export_bounds')
 page.set_viewport_size({'width':int(box['width'])+2,'height':int(box['height'])+2});png=e.screenshot(type='png',animations='disabled',timeout=30000);(folder/(name+'.svg')).write_text(svg);(folder/(name+'.png')).write_bytes(png);return png,closure
def worker(row):
 case=D/'cases'/row['id'];out=case/'font_replay_audit_v2.json'
 if out.exists():return json.loads(out.read_text())
 started=time.monotonic();result={'id':row['id'],'paper':row['paper'],'status':'pending','new_PDF_import_calls':0,'new_normal_calls':0,'new_model_calls':0,'profile':'author_native_source_replay','stage_seconds':{}};renderer=None
 try:
  author=R/row['author_xml_file'];original_xml=author.read_bytes();source_png=(R/row['image_file']).read_bytes();assert sha(original_xml)==row['author_xml_sha256'] and sha(source_png)==row['image_sha256'];proof_file=R/row['render_edit_evidence'];proof=json.loads(proof_file.read_text());assert proof['edit_probe']['mutation_actual_PNG_changed'] and proof['edit_probe']['restored_actual_PNG_exact'];rootcase=proof_file.parent;assert (rootcase/'restored.png').read_bytes()==source_png;assert pixels((rootcase/'mutated.png').read_bytes())!=pixels(source_png);assert pixels((rootcase/'restored.png').read_bytes())==pixels(source_png)
  structure=facts(original_xml.decode());assert structure['complexity_match'] and not structure['all_single_image_wrapper'] and structure['pages']==1
  t=time.monotonic()
  with zipfile.ZipFile(WAR) as archive:a=dependencies(original_xml.decode(),author,R/row['pdf_file'],archive)
  result['stage_seconds']['decoded_assets_and_existing_edit_RGBA_proof']=time.monotonic()-t
  if a['issues']:raise ValueError('source_asset_portability_pending:'+','.join(sorted({x['status'] for x in a['issues']})))
  t=time.monotonic();renderer=OfficialXmlPng();renderer.assets=a['asset_map'];renderer.blocked.clear();renderer.missing.clear();model=ET.tostring(a['models'][0],encoding='unicode');graph=renderer.page.evaluate(LOAD,model);assert graph['vertices']==structure['vertices'] and graph['edges']==structure['edges'];svg=renderer.page.evaluate(EXPORT,{'background':proof['background'],'scale':proof['scale']});png,closure=screenshot(renderer,svg,case,'fresh_v2_official');result['stage_seconds']['independent_full_editor_load_and_official_PNG']=time.monotonic()-t;equal=pixels(png)==pixels(source_png)
  t=time.monotonic();runs=renderer.render_page.evaluate(OBSERVE);session=renderer.render_page.context.new_cdp_session(renderer.render_page);session.send('DOM.enable');session.send('CSS.enable');document=session.send('DOM.getDocument',{'depth':1})['root']['nodeId'];actual={}
  for run in runs:
   node=session.send('DOM.querySelector',{'nodeId':document,'selector':run['selector']})['nodeId'];run['actual_fonts']=physical_fonts(session,node,run['child_index'],run['text'])
   if run['text'].strip() and not any(f['glyphCount'] for f in run['actual_fonts']):raise ValueError('visible_Text_backend_font_not_observed')
   for f in run['actual_fonts']:
    if f['glyphCount']:actual[(f['postScriptName'],f['isCustomFont'])]=f
  session.detach();font_assets=[physical_asset(f) for f in actual.values()];(case/'current_physical_font_observations_v2.json').write_text(json.dumps({'runs':runs,'font_assets':font_assets,'observed_on_actual_fresh_official_PNG_source_SVG':True},ensure_ascii=False,indent=2)+'\n');result['stage_seconds']['actual_Text_backend_fonts_and_font_bytes']=time.monotonic()-t;result['unpainted_SVG_switch_fallback_Text_nodes_excluded_by_zero_actual_Rect']=True
  existing_edit_reused=equal;fresh_edit=None
  if not equal:
   t=time.monotonic();mutated=renderer.page.evaluate('''()=>{let ui=__bulkUi,g=ui.editor.graph,m=g.model,c=Object.values(m.cells).find(c=>c.vertex&&c.geometry&&!/(?:^|;)shape=image(?:;|$)/.test(c.style||''))||Object.values(m.cells).find(c=>c.vertex&&c.geometry),source=mxUtils.getXml(ui.editor.getGraphXml()),geo=c.geometry.clone();geo.x+=13;m.setGeometry(c,geo);m.setValue(c,String(c.value||'')+' replay-probe');return {cell:c.id,source};}''');msvg=renderer.page.evaluate(EXPORT,{'background':proof['background'],'scale':proof['scale']});mp,_=screenshot(renderer,msvg,case,'fresh_v2_mutated');renderer.page.evaluate(LOAD,model);rsvg=renderer.page.evaluate(EXPORT,{'background':proof['background'],'scale':proof['scale']});rp,_=screenshot(renderer,rsvg,case,'fresh_v2_restored');fresh_edit={'cell':mutated['cell'],'mutation_actual_RGBA_changed':pixels(mp)!=pixels(png),'restored_actual_RGBA_exact':pixels(rp)==pixels(png),'restored_actual_PNG_bytes_exact':rp==png};assert all(fresh_edit[k] for k in ['mutation_actual_RGBA_changed','restored_actual_RGBA_exact','restored_actual_PNG_bytes_exact']);result['stage_seconds']['fresh_native_edit_restore_for_changed_runtime_replay']=time.monotonic()-t
  if renderer.blocked or renderer.missing:raise ValueError('independent_open_has_unclosed_runtime_resource:'+str(renderer.blocked[:3])+str(renderer.missing[:3]))
  assert sha(author.read_bytes())==row['author_xml_sha256'];assert sha((R/row['image_file']).read_bytes())==row['image_sha256'];result.update(status='audited_author_native_source_replay_pair',raw_author_XML_unmodified=True,original_PDF_fidelity='review_not_certified',legacy_full8_qualified=False,independent_full_official_Editor_load=graph,standalone_image_assets_complete=True,raw_native_code_can_open_in_declared_official_runtime=True,standalone_font_portability_certified=False,font_portability_state='current_runtime_physical_font_dependencies_pinned_but_author_XML_not_rewritten',historical_author_OS_fonts_exact=False,observed_export_Text_nodes=len(runs),observed_Unicode_characters=sum(sum(ord(c)>127 for c in r['text']) for r in runs),font_assets=font_assets,declared_font_families=a['declared_font_families'],fresh_resource_closure=closure,fresh_official_png_file=str((case/'fresh_v2_official.png').relative_to(R)),fresh_official_png_sha256=sha(png),fresh_official_svg_file=str((case/'fresh_v2_official.svg').relative_to(R)),fresh_official_svg_sha256=sha(svg.encode()),fresh_replay_RGBA_equals_existing_official_PNG=equal,existing_verified_actual_native_edit_restore_reused=existing_edit_reused,existing_native_edit_evidence_sha256=sha(proof_file.read_bytes()),fresh_native_edit_restore=fresh_edit,decoded_models_sha256=a['decoded_model_SHA256'],current_runtime_fonts_physical_bytes_complete=all(f['status']=='current_runtime_physical_font_bytes_pinned' for f in font_assets),structure=structure,official_runtime_WAR_sha256=sha(WAR.read_bytes()))
 except Exception as e:result.update(status='typed_pending_author_native_portability_audit',reason=type(e).__name__+':'+str(e)[:1600])
 finally:
  if renderer:renderer.close()
  result['seconds']=time.monotonic()-started;result['finished_utc']=now();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 return result
def main(workers):
 rows=[json.loads(l) for l in (D/'input_snapshot.jsonl').read_text().splitlines()];begin=time.monotonic();results=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
  for result in pool.map(worker,rows):
   results.append(result);summary={'at_utc':now(),'input_rows':len(rows),'finished_rows':len(results),'states':dict(collections.Counter(r['status'] for r in results)),'elapsed_seconds':time.monotonic()-begin,'cases_per_minute':len(results)/max(1,time.monotonic()-begin)*60,'new_PDF_import_calls':0,'new_normal_calls':0,'new_model_calls':0};(D/'font_replay_progress_v2.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'id':result['id'],'status':result['status'],'reason':result.get('reason'),'seconds':result['seconds'],'fonts':len(result.get('font_assets',[]))}),flush=True)
 (D/'font_replay_summary_v2.json').write_text(json.dumps({'summary':summary,'results':results},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=2);a=p.parse_args();main(a.workers)
