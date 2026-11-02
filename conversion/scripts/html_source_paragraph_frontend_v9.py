"""Fresh original paragraph flow -> editable native text, shapes and assets."""
import copy,hashlib,html,io,json,math,re,urllib.parse,uuid,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';PADDING=32
UNIT='fresh_HTML_complete_inline_formatting_paragraph_SOURCE_exact_paint_v9'
UNITS={'html':UNIT};VERSION='html_source_paragraph_frontend_v9'
sha=lambda b:hashlib.sha256(b).hexdigest()
def configuration(data_root=R):
 if Path(data_root).resolve()!=R.resolve():raise ValueError('paragraph_HTML_requires_HKUST')
 from compiler_html_source_paragraph_quality_ro_v9 import pins
 p=pins();return{'unit':UNIT,'policy':VERSION+':'+sha(json.dumps(p,sort_keys=True).encode())[:20],'pins':p}
def source_inputs(given):
 from html_source_frontend_v8 import source_inputs as original
 return original(given)
def static_support(given):
 from html_source_frontend_v8 import static_support as old
 result=old(given);result['unit']=UNIT;result['paragraph_scope']='original_block_or_inline_block_formatting_hosts_with_safe_inline_semantic_descendants_and_rectangular_ancestor_clips';result['source_only']=True;return result
def lower(dom,ir,served,record):
 from html_batch_v3 import convert
 viewport=ir['viewport'];size=[v+64 for v in viewport];shifted=copy.deepcopy(dom);paths={};assets=(R/record['original_asset_root']).resolve()if record.get('original_asset_root')else None
 for url,blob in served.items():
  target=(assets/urllib.parse.unquote(urllib.parse.urlparse(url).path.lstrip('/'))).resolve();assert target.is_relative_to(assets)and target.read_bytes()==blob;paths[url]=target
 for o in shifted['objects']:
  o['x']+=32;o['y']+=32
  if o['type']=='text':o['fontFamily']=o['actualSourceCss']['fontFamily']
 xml,asset_map=convert(shifted,paths,*size);root=E.fromstring(xml);cells=root.find('.//mxGraphModel/root');objects={str(o['id']+1):o for o in dom['objects']};order=dom['_source_paint_order'];keys={}
 for c in list(cells):
  if c.get('vertex')!='1':continue
  o=objects[c.get('id')];keys[c.get('id')]=(order[str(o['id'])],o.get('qaPaintEvent',0),o.get('qaTextStart',0))
  if o['type']=='text':cells.remove(c)
 for group in ir['groups']:
  key='source_paragraph_owner_'+str(group['rootOwner']);r=group['rootRect'];left,top,right,bottom=group['ancestorClipFrame'];insets=[top-r['y'],r['x']+r['width']-right,r['y']+r['height']-bottom,left-r['x']];value=group['markup'];assert 'position: relative; left: 0px; top: 0px;'in value
  value=value.replace('position: relative; left: 0px; top: 0px;','position: relative; left: 0px; top: 0px; clip-path: inset('+' '.join(format(v,'.12g')+'px'for v in insets)+');',1)
  sourcecss=group['cssEvidence'][0]['css'];font=float(sourcecss['font-size'].removesuffix('px'));family=sourcecss['font-family'];c=E.SubElement(cells,'mxCell',id=key,parent='1',vertex='1',value=value,style='html=1;shape=text;fillColor=none;strokeColor=none;align=left;verticalAlign=top;spacing=0;spacingTop=0;spacingRight=0;spacingBottom=0;spacingLeft=0;whiteSpace=wrap;overflow=visible;autosize=0;nl2Br=0;fontSize='+str(font)+';fontFamily='+family+';')
  E.SubElement(c,'mxGeometry',{'x':str(r['x']+32),'y':str(r['y']+32),'width':str(r['width']),'height':str(r['height']),'as':'geometry'});keys[key]=min(keys[k]for k in group['sourceObjectIDs'])
 vertices=[c for c in list(cells)if c.get('vertex')=='1']
 for c in vertices:cells.remove(c)
 for c in sorted(vertices,key=lambda c:keys[c.get('id')]):cells.append(c)
 return E.tostring(root,encoding='unicode'),asset_map
def register_source_boxes(xml,ir,info,dom):
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};rows={r['cell']:r for r in info['source_paragraph_observation']};changes=[]
 assert set(rows)=={'source_paragraph_owner_'+str(g['rootOwner'])for g in ir['groups']},'paragraph_native_host_binding_incomplete'
 for g in ir['groups']:
  key='source_paragraph_owner_'+str(g['rootOwner']);row=rows[key];assert not row.get('unbound'),'paragraph_native_host_binding_pending';source=g['rootRect'];actual=row['rootRect'];assert all(abs(source[k]-actual[k])<.001 for k in('width','height')),'paragraph_native_original_host_dimensions_changed';dx=source['x']+32-actual['x'];dy=source['y']+32-actual['y'];assert all(math.isfinite(v)for v in(dx,dy));cell=cells[key];before=cell.get('value');assert 'left: 0px; top: 0px;'in before;cell.set('value',before.replace('left: 0px; top: 0px;','left: '+format(dx,'.12g')+'px; top: '+format(dy,'.12g')+'px;',1));changes.append({'cell':key,'original_source_border_box':source,'initial_native_border_box':actual,'translation':{'dx':dx,'dy':dy},'basis':'actual_original_SOURCE_and_native_paragraph_border_boxes_no_ink_or_reference_pixels'})
 rectangles={r['cell']:r for r in info['source_rectangle_observation']};source_rects={str(o['id']+1):o for o in dom['objects']if o['type']=='rect'};assert set(rectangles)==set(source_rects),'paragraph_SOURCE_rectangle_native_primitive_scope_changed'
 for key,o in source_rects.items():
  row=rectangles[key];paint=row['native_geometric_path_box'];bw=o['bw'];wanted={'x':o['x']+32+bw/2,'y':o['y']+32+bw/2,'width':o['w']-bw,'height':o['h']-bw};assert wanted['width']>0 and wanted['height']>0,'paragraph_CSS_border_consumes_box_pending';cell=cells[key];geo=cell.find('mxGeometry');delta={k:wanted[k]-paint[k]for k in wanted}
  for k in delta:geo.set(k,format(float(geo.get(k))+delta[k],'.12g'))
  if o['radius']:
   style=cell.get('style');style=re.sub(r'arcSize=[^;]+;', 'arcSize='+format(2*max(0,o['radius']-bw/2),'.12g')+';',style);cell.set('style',style)
  changes.append({'cell':key,'type':'CSS_rectangle_fill_and_inset_solid_border','original_source_border_box':{'x':o['x'],'y':o['y'],'width':o['w'],'height':o['h']},'source_border_width':bw,'initial_native_geometric_path_box':paint,'required_native_geometric_path_box':wanted,'model_geometry_delta':delta,'official_native_screen_offset':row['actual_SVG_screen_offset'],'basis':'SOURCE_CSS_border_box_inset_border_centerline_and_actual_official_native_SVG_path_geometry_no_pixels'})
 return E.tostring(root,encoding='unicode'),changes
def source_glyph_checks(ir,info,custom=False):
 rows={r['cell']:r for r in info['source_paragraph_observation']};details=[]
 for group in ir['groups']:
  key='source_paragraph_owner_'+str(group['rootOwner']);live=rows[key];assert not live.get('unbound'),'paragraph_live_dom_unbound';want=group['rootRect'];assert all(abs(want[k]+(32 if k in('x','y')else 0)-live['rootRect'][k])<.001 for k in want),'paragraph_SOURCE_border_box_not_exact'
  assert len(group['textNodes'])==len(live['runs']),'paragraph_original_Text_node_count_changed';maximum=0
  for a,b in zip(group['textNodes'],live['runs']):
   assert a['text']==b['text'],'paragraph_raw_Unicode_or_Text_node_order_changed';assert len(a['chars'])==len(b['chars']),'paragraph_grapheme_count_changed'
   counts=lambda fonts:sorted((f['postScriptName'],f['glyphCount'])for f in fonts if f.get('glyphCount',0))
   assert counts(a['actual_fonts'])==counts(b['actual_fonts']),'paragraph_actual_original_Text_face_or_glyph_count_changed'
   if custom:assert all(f.get('isCustomFont')for f in b['actual_fonts']if f.get('glyphCount',0)),'paragraph_system_font_after_portable_binding'
   for x,y in zip(a['chars'],b['chars']):
    assert x['text']==y['text'],'paragraph_grapheme_Unicode_changed'
    empty=x.get('rectCount')==0 and y.get('rectCount')==0
    if empty:assert all(x[k]==y[k]==0 for k in('x','y','width','height')),'paragraph_empty_Range_geometry_changed'
    else:maximum=max(maximum,*[abs(x[k]+(32 if k in('x','y')else 0)-y[k])for k in('x','y','width','height')])
  assert maximum<=.03,'paragraph_SOURCE_grapheme_geometry_changed';details.append({'cell':key,'all_original_Text_nodes':len(group['textNodes']),'maximum_grapheme_Range_error':maximum,'direct_original_Text_PostScript_and_glyph_inventory_preserved':True,'original_source_border_box_exact':True})
 return details
def source_strut_checks(ir,font):
 rows={row['cell']:row for row in font['source_strut_runs']};after={row['cell']:row for row in font['current_strut_runs']};checks=[]
 for group in ir['groups']:
  key='source_paragraph_owner_'+str(group['rootOwner']);original=[s for s in rows[key]['struts']if s['kind']=='element'];portable=[s for s in after[key]['struts']if s['kind']=='element'];assert len(original)==len(portable)==len(group['cssEvidence']),'paragraph_SOURCE_native_element_strut_scope_changed'
  counts=lambda fs:sorted((f['postScriptName'],f['glyphCount'])for f in fs if f.get('glyphCount',0))
  for i,evidence in enumerate(group['cssEvidence']):
   expected=counts(evidence['source_primary_M_fonts']);assert expected==counts(original[i]['primary_metric_fonts'])==counts(portable[i]['primary_metric_fonts']),'paragraph_SOURCE_native_primary_element_strut_physical_face_changed';assert all(f.get('isCustomFont')for f in portable[i]['primary_metric_fonts']if f.get('glyphCount',0)),'paragraph_portable_element_strut_uses_system_font';checks.append({'cell':key,'source_element':i,'physical_primary_M':expected,'SOURCE_native_portable_face_and_glyph_exact':True})
 return checks
def render(xml,size,work,name):
 from html_source_paragraph_render_v9 import run as actual_native
 work=Path(work);work.mkdir(parents=True,exist_ok=True);out=actual_native(xml,size,work/(name+'.raw_native'));assert out.get('ok'),'paragraph_actual_native_render_pending';assert out['native_render'].get('selected_image')in('declared_first_page','original_HTML_source_viewport'),'paragraph_complete_SOURCE_inspection_not_available'
 for suffix,blob in [('.drawio',xml.encode()),('.png',out['png']),('.native.json',json.dumps(out['native_render'],sort_keys=True).encode())]:(work/(name+suffix)).write_bytes(blob)
 return out
def reconstruct(record,work):
 from html_source_paragraph_capture_v9 import capture_source
 from html_source_paragraph_ink_v9 import ink_metrics
 work=Path(work);dom,ir,served,source_png,hidden,capture=capture_source(record,work/'source');assert not[u for u in dom.get('unsupported',[])if u.get('reason')!='css_stacking_order'],'paragraph_SOURCE_unsupported_layout';ir['viewport']=capture['viewport'];size=[v+64 for v in capture['viewport']];xml,assets=lower(dom,ir,served,record);initial=render(xml,size,work,'seed');xml,registration=register_source_boxes(xml,ir,initial['native_render'],dom);actual=render(xml,size,work,'registered');glyphs=source_glyph_checks(ir,actual['native_render']);source_rects={str(o['id']+1):o for o in dom['objects']if o['type']=='rect'}
 for row in actual['native_render']['source_rectangle_observation']:
  o=source_rects[row['cell']];bw=o['bw'];wanted={'x':o['x']+32+bw/2,'y':o['y']+32+bw/2,'width':o['w']-bw,'height':o['h']-bw};assert all(abs(wanted[k]-row['native_geometric_path_box'][k])<.001 for k in wanted),'paragraph_final_SOURCE_CSS_rectangle_path_geometry_changed'
 bg=E.fromstring(xml)
 for cell in bg.iter('mxCell'):
  if cell.get('id','').startswith('source_paragraph_owner_'):cell.set('value','')
 background=render(E.tostring(bg,encoding='unicode'),size,work,'background');ink=ink_metrics(source_png,hidden,actual['png'],background['png'],(32,32));assert ink['exact_same_domain_source_native_ink'],'paragraph_whole_SOURCE_native_signed_ink_mismatch:'+json.dumps(ink)
 (work/'registration.json').write_text(json.dumps(registration,sort_keys=True));return{'xml':xml,'png':actual['png'],'info':actual['native_render'],'dom':dom,'ir':ir,'assets':assets,'served':served,'source_png':source_png,'source_hidden':hidden,'capture':capture,'registration':registration,'glyphs':glyphs,'ink':ink,'size':size,'background':background['png']}
def repair(record,job,work):
 try:
  from html_source_paragraph_fonts_v9 import compile as compile_fonts
  config=configuration();assert all(sha(Path(p).read_bytes())==h for p,h in config['pins'].items()),'infrastructure_paragraph_frontend_pin_changed'
  source,manifest,code,image=source_inputs(job);assert(record['id'],record['source_code_sha256'],record['source_image_sha256'])==(source['pair_sha256'],source['code_sha256'],source['image_sha256']);work=Path(work).resolve();assert work.is_relative_to(W.resolve());work.mkdir(parents=True,exist_ok=False)
  keys=('id','source_pair_sha256','source','category','source_format','original_source_code','original_reference','original_asset_root','source_code_sha256','source_image_sha256');seed={k:record[k]for k in keys};result=reconstruct(seed,work/'source_compilation');font=compile_fonts(result['xml'],result['size'],work/'portable_fonts');source_struts=source_strut_checks(result['ir'],font);assert font['png']==result['png'],'paragraph_portable_fonts_changed_SOURCE_native_pixels'
  from html_source_paragraph_export_v9 import attach,compare,pixels
  final_xml=attach(font['xml'],result['capture']['viewport']);export=render(final_xml,result['size'],work,'source_viewport_export');compare(font['png'],export['png'],result['capture']['viewport']);inspection=Path(export['inspection_png']).read_bytes();assert pixels(inspection)==pixels(font['png']),'paragraph_export_changed_full_model_inspection_pixels';dest=R/'clean/html_source_paragraph_frontend_v9'/seed['id'][:2]/seed['id']/uuid.uuid4().hex;dest.mkdir(parents=True);(dest/'diagram.drawio').write_text(final_xml);(dest/'image.png').write_bytes(export['png']);(dest/'inspection.png').write_bytes(inspection);(dest/'source_export.proof.json').write_bytes(Path(export['export_proof']).read_bytes());(dest/'native.svg').write_bytes(Path(export['svg_export']).read_bytes());assert all(sha(Path(p).read_bytes())==h for p,h in config['pins'].items()),'infrastructure_paragraph_frontend_pin_changed';meta={'unit':UNIT,'configuration':config,'source_metadata':result['capture'],'source_groups':len(result['ir']['groups']),'source_text_objects':len(result['ir']['allSourceTextObjects']),'registration':result['registration'],'source_glyphs':result['glyphs'],'source_viewport_export':export['native_render']['source_html_export'],'inspection_file':str((dest/'inspection.png').relative_to(R)),'inspection_sha256':sha(inspection),'export_proof_file':str((dest/'source_export.proof.json').relative_to(R)),'export_proof_sha256':sha((dest/'source_export.proof.json').read_bytes()),'native_svg_file':str((dest/'native.svg').relative_to(R)),'native_svg_sha256':sha((dest/'native.svg').read_bytes()),'all_SOURCE_native_text_ink':result['ink'],'font_proof':font['proof'],'fresh_SOURCE_native_portable_element_strut_checks':source_struts,'font_proof_file':font.get('proof_file'),'original_source_complete_Unicode':True,'model_calls':0}
  (dest/'source_compilation.json').write_text(json.dumps(meta,ensure_ascii=False,sort_keys=True));seed.update(format='drawio',model=None,conversion_method=VERSION,code_file=str((dest/'diagram.drawio').relative_to(R)),image_file=str((dest/'image.png').relative_to(R)),code_sha256=sha(final_xml.encode()),image_sha256=sha(export['png']),source_assets=result['assets'],native_embedded_fonts=font['assets'],render=export['native_render'],vertices=sum(1 for c in E.fromstring(font['xml']).iter('mxCell')if c.get('vertex')=='1'),text_objects=len(result['ir']['groups']),edges=0,bound_edges=0,html_source_paragraph_v9=meta);(work/'candidate_record.json').write_text(json.dumps(seed,ensure_ascii=False,sort_keys=True));return{'ok':True,'record':seed,'record_file':str(work/'candidate_record.json'),'model_calls':0}
 except Exception as error:return{'ok':False,'reason':str(error)[:6000],'error_type':type(error).__name__,'model_calls':0}
def convert(record,job,work):return repair(record,job,work)
