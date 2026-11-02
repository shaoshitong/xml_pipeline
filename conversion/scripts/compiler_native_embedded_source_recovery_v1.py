"""Recover PNG-embedded author native XML, without rendering or acceptance."""
from pathlib import Path
import argparse,base64,collections,copy,decimal,hashlib,html,json,math,re,sqlite3,struct,urllib.parse,uuid,zlib
import xml.etree.ElementTree as E
from html.parser import HTMLParser
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
AUDIT=R/'release/compiler_native_source_recovery_v1/embedded_metadata_26cfec8535a849978c6dd682bb2ea757/rows.jsonl'
AUDIT_SHA='2720dc51425d1d9225db3e829b1715c6388a4c0fa282338a4a557f0a8e56791d'
LIMIT=64*1024*1024
UI_ATTRS={'dx','dy','grid','gridSize','guides','tooltips','connect','arrows','fold','page','pageScale','pageWidth','pageHeight'}
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda x:(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def put(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('xb')as f:f.write(data)
 return {'file':str(path.relative_to(R)),'sha256':sha(data),'bytes':len(data)}
def local(tag):return tag.rsplit('}',1)[-1]
def decompress(data,wbits=zlib.MAX_WBITS):
 obj=zlib.decompressobj(wbits);out=obj.decompress(data,LIMIT+1);require(len(out)<=LIMIT and not obj.unconsumed_tail,'compressed_source_resource_bound');out+=obj.flush();require(len(out)<=LIMIT and obj.eof and not obj.unused_data,'compressed_source_incomplete_or_trailing');return out

def png_metadata(blob):
 require(blob[:8]==b'\x89PNG\r\n\x1a\n','not_PNG');offset=8;chunks=[];texts=[];header=None;physical=None
 while offset<len(blob):
  require(offset+12<=len(blob),'truncated_PNG_chunk_header');n=struct.unpack('>I',blob[offset:offset+4])[0];end=offset+12+n;require(end<=len(blob),'truncated_PNG_chunk');kind=blob[offset+4:offset+8];data=blob[offset+8:offset+8+n];crc=struct.unpack('>I',blob[offset+8+n:end])[0];require((zlib.crc32(kind+data)&0xffffffff)==crc,'PNG_chunk_CRC_changed');row={'offset':offset,'length':n,'type':kind.decode('ascii'),'whole_chunk_sha256':sha(blob[offset:end]),'payload_sha256':sha(data),'CRC_valid':True};chunks.append(row)
  if kind==b'IHDR':
   w,h,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',data);header={'width':w,'height':h,'bit_depth':depth,'color_type':color,'compression':compression,'filtering':filtering,'interlace':interlace}
  if kind==b'pHYs':
   x,y,unit=struct.unpack('>IIB',data);physical={'pixels_per_unit_x':x,'pixels_per_unit_y':y,'unit':unit,'dpi_from_declared_meters':[x*.0254,y*.0254]if unit==1 else None}
  if kind in (b'tEXt',b'zTXt',b'iTXt'):
   key,rest=data.split(b'\x00',1);key=key.decode('latin-1');charset='latin-1';steps=[];language='';translated=''
   if kind==b'tEXt':payload=rest
   elif kind==b'zTXt':
    require(rest[0]==0,'unsupported_zTXt_compression');payload=decompress(rest[1:]);steps.append('zlib_text_decompression')
   else:
    compressed,method=rest[:2];rest=rest[2:];language,rest=rest.split(b'\x00',1);translated,payload=rest.split(b'\x00',1);charset='utf-8';language=language.decode('ascii');translated=translated.decode('utf-8')
    if compressed:require(method==0,'unsupported_iTXt_compression');payload=decompress(payload);steps.append('zlib_text_decompression')
   text=payload.decode(charset);texts.append({'key':key,'text':text,'text_bytes':payload,'charset':charset,'steps':steps,'language':language,'translated_keyword':translated,'chunk':row,'chunk_bytes':blob[offset:end]})
  offset=end
  if kind==b'IEND':break
 require(header is not None and chunks[-1]['type']=='IEND'and offset==len(blob),'PNG_structure_incomplete_or_trailing')
 return {'header':header,'physical':physical,'chunks':chunks,'texts':texts,'pixels_decoded':False}
def decode_author(text):
 text_bytes=text.encode('utf-8');steps=[{'operation':'PNG_text_charset_to_UTF8','output_sha256':sha(text_bytes),'output_bytes':len(text_bytes)}];value=text
 if value.lstrip().startswith('%3C')or value.lstrip().startswith('%3c'):
  b=urllib.parse.unquote_to_bytes(value);value=b.decode('utf-8');steps.append({'operation':'percent_decode_UTF8_preserve_literal_plus','input_sha256':sha(text_bytes),'output_sha256':sha(b),'output_bytes':len(b)})
 else:b=text_bytes
 require(value.lstrip('\ufeff \r\n\t').startswith('<'),'metadata_not_native_XML');require('<!DOCTYPE'not in value.upper()and'<!ENTITY'not in value.upper(),'unsupported_XML_entity_declaration');root=E.fromstring(value);require(local(root.tag)in ('mxfile','mxGraphModel'),'metadata_root_not_native');return b,steps

def tree(e,alpha_ids=None,geometry=False):
 tag=local(e.tag);geometry=geometry or tag in ('mxGeometry','mxPoint','mxRectangle');attrs={}
 for k,v in e.attrib.items():
  if alpha_ids is not None:
   if local(k)in ('id','parent','source','target')and v in alpha_ids:v=alpha_ids[v]
   if local(k)=='style':
    v=';'.join((a+'='+alpha_ids.get(b,b))if sep and a in ('sourcePort','targetPort')else item for item in v.split(';')for a,sep,b in [item.partition('=')])
  if geometry and local(k)in ('x','y','width','height','relative'):
   try:
    number=decimal.Decimal(v)
    if number.is_finite():v='0'if number==0 else format(number.normalize(),'f')
   except decimal.InvalidOperation:pass
  attrs[k]=v
 text=e.text if(e.text or'').strip()else None;tail=e.tail if(e.tail or'').strip()else None
 return {'tag':e.tag,'attrs':attrs,'text':text,'tail':tail,'children':[tree(x,alpha_ids,geometry)for x in e]}
class Plain(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag=='br'or(tag in ('div','p','li')and self.parts and not self.parts[-1].endswith('\n')):self.parts.append('\n')
 def handle_endtag(self,tag):
  if tag in ('div','p','li')and self.parts and not self.parts[-1].endswith('\n'):self.parts.append('\n')
 def handle_data(self,data):self.parts.append(data)
def plain(value):
 parser=Plain();parser.feed(value or'');parser.close();return '\n'.join(x.rstrip()for x in ''.join(parser.parts).splitlines()).strip()
def partial_inventory(text):
 parser=E.XMLPullParser(events=('start',));cells=[];error=None
 try:
  # Prefix-only evidence, never a repaired or completed model.
  for index in range(0,len(text),128):
   parser.feed(text[index:index+128])
   for event,e in parser.read_events():
    if local(e.tag)=='mxCell':cells.append({'attrs':dict(e.attrib),'plain_text':plain(e.get('value',''))})
  parser.close()
 except E.ParseError as e:error=str(e)
 return {'prefix_only':True,'not_a_valid_complete_model':True,'cells_seen_before_parse_failure':len(cells),'cells':cells,'error':error}
def document(blob):
 out={'parse_ok':False,'structurally_valid':False,'raw_sha256':sha(blob),'raw_bytes':len(blob),'decode_steps':[],'pages':[]}
 try:
  text=blob.decode('utf-8-sig');stripped=text.strip()
  if stripped.startswith('```'):
   m=re.fullmatch(r'```(?:xml|drawio)?\s*\n(.*)\n```',stripped,re.S|re.I);require(m is not None,'unrecognized_source_fence');text=m[1];out['decode_steps'].append('exact_outer_markdown_fence_removed')
  require('<!DOCTYPE'not in text.upper()and'<!ENTITY'not in text.upper(),'unsupported_XML_entity_declaration');root=E.fromstring(text);out['root']=local(root.tag);out['document_attributes']=dict(root.attrib)
  if local(root.tag)=='mxGraphModel':pages=[(None,None,root)]
  elif local(root.tag)=='mxfile':
   pages=[]
   for i,d in enumerate(root):
    if local(d.tag)!='diagram':continue
    children=[e for e in d if local(e.tag)=='mxGraphModel']
    if children:require(len(children)==1,'multiple_inline_models_one_page');model=children[0]
    else:
     payload=(d.text or'').strip();require(payload,'empty_diagram_page');packed=base64.b64decode(payload,validate=True);inflated=decompress(packed,-15);decoded=urllib.parse.unquote_to_bytes(inflated.decode('utf-8'));model=E.fromstring(decoded);require(local(model.tag)=='mxGraphModel','compressed_page_not_mxGraphModel');out['decode_steps'].append({'page':i,'operation':'base64_raw_deflate_percent_UTF8','compressed_sha256':sha(packed),'inflated_sha256':sha(inflated),'decoded_model_sha256':sha(decoded)})
    pages.append((d.get('id'),d.get('name'),model))
   require(pages,'mxfile_has_no_diagrams')
  else:raise ValueError('source_root_not_native_model_or_document')
  for i,(pid,name,model)in enumerate(pages):out['pages'].append(page(model,i,pid,name))
  out['parse_ok']=True;out['structurally_valid']=all(p['structurally_valid']for p in out['pages']);out['canonical_models_sha256']=sha(raw([p['canonical_model']for p in out['pages']]));out['expanded_document_model_sha256']=sha(raw([p['canonical_model_sha256']for p in out['pages']]))
 except Exception as error:
  out['error_type']=type(error).__name__;out['error']=str(error);out['partial_prefix_inventory']=partial_inventory(blob.decode('utf-8',errors='replace'))
 return out

def page(model,index,pid,name):
 roots=[r for r in model if local(r.tag)=='root'];require(len(roots)==1,'native_model_root_missing_or_ambiguous');root=roots[0];entries=[];errors=[];warnings=[];ids={}
 for ordinal,entry in enumerate(root):
  if local(entry.tag)=='mxCell':cell=entry;wrapper=None
  else:
   inner=[e for e in entry if local(e.tag)=='mxCell'];require(len(inner)==1,'unhandled_native_root_object');cell=inner[0];wrapper=entry
  ident=(wrapper.get('id')if wrapper is not None else None)or cell.get('id');require(ident is not None,'native_cell_missing_ID')
  if ident in ids:errors.append({'reason':'duplicate_cell_ID','id':ident})
  value=wrapper.get('label',cell.get('value',''))if wrapper is not None else cell.get('value','');geometry=[e for e in cell if local(e.tag)=='mxGeometry'];kind='edge'if cell.get('edge')in ('1','true')else'vertex'if cell.get('vertex')in ('1','true')else'layer_or_root';row={'id':ident,'ordinal':ordinal,'kind':kind,'attrs':dict(cell.attrib),'wrapper_attrs':dict(wrapper.attrib)if wrapper is not None else None,'value':value,'plain_text':plain(value),'parent':cell.get('parent'),'source':cell.get('source'),'target':cell.get('target'),'style':cell.get('style',''),'geometry':[tree(e)for e in geometry],'canonical_entry':tree(entry)};entries.append(row);ids[ident]=row
 for c in entries:
  for role in ('parent','source','target'):
   ref=c[role]
   if ref is not None and ref not in ids:errors.append({'reason':'dangling_'+role,'id':c['id'],'reference':ref})
  if c['kind']=='vertex'and not c['geometry']:warnings.append({'reason':'vertex_has_no_explicit_geometry','id':c['id']})
  if c['kind']=='edge':
   free=[]
   for role in ('source','target'):
    if c[role]is None:free.append(role)
   if free:warnings.append({'reason':'native_unbound_or_coordinate_edge_not_automatically_corruption','id':c['id'],'sides':free})
  seen=set();cur=c['id']
  while cur in ids:
   if cur in seen:errors.append({'reason':'parent_cycle','id':c['id']});break
   seen.add(cur);cur=ids[cur]['parent']
 alpha={c['id']:'cell_'+str(c['ordinal'])for c in entries};full=tree(model);content={'model_attributes_except_editor_and_export':{k:v for k,v in model.attrib.items()if local(k)not in UI_ATTRS},'ordered_entries':[tree(e)for e in root]};alpha_content={'model_attributes_except_editor_and_export':content['model_attributes_except_editor_and_export'],'ordered_entries':[tree(e,alpha)for e in root]}
 return {'index':index,'page_id':pid,'page_name':name,'model_attributes':dict(model.attrib),'canonical_model':full,'canonical_model_sha256':sha(raw(full)),'ordered_content_sha256':sha(raw(content)),'ordered_alpha_content_sha256':sha(raw(alpha_content)),'structurally_valid':not errors,'errors':errors,'warnings':warnings,'cells':entries,'cell_count':len(entries),'vertices':sum(c['kind']=='vertex'for c in entries),'edges':sum(c['kind']=='edge'for c in entries),'labels':sum(bool(c['plain_text'])for c in entries)}
def attributes_diff(a,b):return {k:{'provided':a.get(k),'author':b.get(k)}for k in sorted(set(a)|set(b))if a.get(k)!=b.get(k)}
def page_diff(a,b):
 alpha=a['ordered_alpha_content_sha256']==b['ordered_alpha_content_sha256'];mapping={x['id']:y['id']for x,y in zip(a['cells'],b['cells'])}if alpha else{};by_a={c['id']:c for c in a['cells']};by_b={c['id']:c for c in b['cells']};pairs=[(x,by_b[mapping.get(x,x)])for x in by_a if mapping.get(x,x)in by_b];changes={'text':[],'raw_label_markup':[],'edge_endpoints':[],'parent':[],'geometry':[],'style':[],'other_cell_attributes':[]}
 for ident,y in pairs:
  x=by_a[ident];key={'provided_cell':ident,'author_cell':y['id']}
  for role,field in (('text','plain_text'),('raw_label_markup','value'),('geometry','geometry'),('style','style')):
   if x[field]!=y[field]:changes[role].append(key|{'provided':x[field],'author':y[field]})
  for role in ('source','target','parent'):
   if mapping.get(x[role],x[role])!=y[role]:changes['parent'if role=='parent'else'edge_endpoints'].append(key|{'role':role,'provided':x[role],'author':y[role]})
  drop={'id','parent','source','target','value','style'};extra=attributes_diff({k:v for k,v in x['attrs'].items()if k not in drop},{k:v for k,v in y['attrs'].items()if k not in drop})
  if extra:changes['other_cell_attributes'].append(key|{'differences':extra})
 return {'provided_page':a['index'],'author_page':b['index'],'provided_page_id':a['page_id'],'author_page_id':b['page_id'],'canonical_model_exact':a['canonical_model_sha256']==b['canonical_model_sha256'],'ordered_content_exact_except_editor_export':a['ordered_content_sha256']==b['ordered_content_sha256'],'ordered_alpha_content_exact_except_editor_export':alpha,'ID_alignment':'order_preserving_exact_content_alpha_renaming'if alpha else'common_explicit_ID_only_no_guess','ID_mapping':mapping,'provided_only_cell_IDs':sorted(set(by_a)-set(mapping or by_b)),'author_only_cell_IDs':sorted(set(by_b)-set(mapping.values()if mapping else by_a)),'model_attribute_differences':attributes_diff(a['model_attributes'],b['model_attributes']),'counts':{k:len(v)for k,v in changes.items()},'changes':changes}
def compare(provided,author,provided_bytes,author_bytes):
 result={'provided_parse_ok':provided['parse_ok'],'author_parse_ok':author['parse_ok'],'provided_structurally_valid':provided['structurally_valid'],'author_structurally_valid':author['structurally_valid'],'provided_pages':len(provided['pages']),'author_pages':len(author['pages']),'page_matrix':[],'reference_pixels_used':False,'qualification_claim':False}
 for a in provided['pages']:
  for b in author['pages']:result['page_matrix'].append(page_diff(a,b))
 if not author['parse_ok']or not author['structurally_valid']:result.update(classification='author_metadata_incomplete_or_invalid_pending',reason='Exact author payload recovered, but complete native structural proof failed.');return result
 if not provided['parse_ok']or not provided['structurally_valid']:result.update(classification='provided_source_corrupt_author_original_recoverable',reason='Provided source has actual XML/native structural errors; PNG embedded author document parses completely.',paired_author_page_indices=None,page_pairing_requires_separate_source_contract=True);return result
 if provided_bytes==author_bytes:result.update(classification='completely_identical',paired_author_page_indices=list(range(len(author['pages']))),reason='Original provided bytes equal decoded PNG author XML.');return result
 matches={p['index']:[m['author_page']for m in result['page_matrix']if m['provided_page']==p['index']and m['ordered_alpha_content_exact_except_editor_export']]for p in provided['pages']};unique=all(len(v)==1 for v in matches.values())and len({v[0]for v in matches.values()})==len(matches)
 if unique:result.update(classification='wrapper_or_editor_export_metadata_difference',reason='Every provided page maps uniquely to an author page with identical ordered native content, geometry, labels, attributes and references under only ID alpha-renaming; editor/export parameters remain explicit evidence.',paired_author_page_indices=[matches[p['index']][0]for p in provided['pages']],author_extra_pages=len(author['pages'])>len(provided['pages']),page_pairing_basis='source_native_content_only_no_target_pixels')
 else:result.update(classification='valid_native_models_semantic_or_paint_conflict',reason='Both native documents parse, but source-only ordered native content equivalence is not proven; no author page is selected by reference pixels.',paired_author_page_indices=None,source_content_page_matches=matches)
 return result

def run():
 audit=AUDIT.read_bytes();require(sha(audit)==AUDIT_SHA,'metadata_audit_changed');rows=[json.loads(x)for x in audit.splitlines()if x];selected=[r for r in rows if r['disposition']=='embedded_native_source_available'];require(len(selected)==45,'expected_45_embedded_originals');batch=uuid.uuid4().hex;work=W/'compiler_native_embedded_source_recovery_v1'/batch;work.mkdir(parents=True,exist_ok=False);destroot=R/'clean/compiler_native_embedded_source_recovery_v1'/batch;destroot.mkdir(parents=True,exist_ok=False);db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True);db.execute('pragma query_only=ON');db.execute('begin');columns=[x[1]for x in db.execute('pragma table_info(jobs)')];outputs=[];errors=[];protocol={'schema':'native_author_source_metadata_recovery_protocol_v1','input_audit':str(AUDIT),'input_audit_sha256':AUDIT_SHA,'all_45_selected_before_results':True,'IDs':[r['id']for r in selected],'script':{'file':str(Path(__file__).resolve()),'sha256':sha(Path(__file__).read_bytes())},'images_and_code_HKUST_only':True,'image_pixels_decoded':False,'reference_pixels_scored':False,'no_source_or_manifest_overwrite':True,'no_qualification_or_release':True,'model_calls':0};put(work/'protocol.json',raw(protocol));print(json.dumps({'work':str(work),'clean_root':str(destroot),'count':45}),flush=True)
 for row in selected:
  ident=row['id'];directory=destroot/ident[:2]/ident
  try:
   job=dict(zip(columns,db.execute('select * from jobs where id=?',(ident,)).fetchone()));source=json.loads(job['input_record']);manifest=json.loads(job['input_manifest']);require(source['pair_sha256']==ident and source['format']=='drawio','canonical_original_identity_changed');png=(R/manifest['reference_image']).read_bytes();gold=(R/manifest['source_code']).read_bytes();require(sha(png)==source['image_sha256']==row['reference_sha256']and sha(gold)==source['code_sha256'],'original_input_hash_changed');metadata=png_metadata(png);payloads=[]
   for expected in row['embedded_native_XML']:
    matches=[x for x in metadata['texts']if x['key']==expected['metadata_key']];require(len(matches)==1,'native_metadata_key_not_unique');entry=matches[0];decoded,steps=decode_author(entry['text']);require(sha(decoded)==expected['sha256'],'decoded_author_differs_from_frozen_metadata_audit');payloads.append((expected,entry,decoded,steps))
   require(len(payloads)==1,'multiple_author_payloads_require_explicit_conflict_handling');expected,entry,decoded,steps=payloads[0];provided=document(gold);author=document(decoded);comparison=compare(provided,author,gold,decoded);assets={'original_reference':put(directory/'original_reference.png',png),'original_provided_code':put(directory/'original_provided_code.drawio',gold),'recovered_author_native':put(directory/'recovered_author.drawio',decoded),'exact_metadata_chunk':put(directory/'metadata_chunk.bin',entry['chunk_bytes']),'metadata_text_UTF8':put(directory/'metadata_text_UTF8.txt',entry['text'].encode('utf-8')),'provided_analysis':put(directory/'provided_model_analysis.json',raw(provided)),'author_analysis':put(directory/'author_model_analysis.json',raw(author)),'comparison':put(directory/'source_diff.json',raw(comparison))};evidence={'metadata_key':entry['key'],'PNG_text_chunk':entry['chunk'],'declared_text_charset':entry['charset'],'text_decode_steps':entry['steps'],'author_decode_steps':steps,'decoded_author_sha256':sha(decoded),'matches_frozen_metadata_audit':True,'source_audit_entry':expected,'PNG_header_and_physical_parameters':{'header':metadata['header'],'physical':metadata['physical']},'author_root_attributes':author.get('document_attributes'),'author_page_viewport_export_attributes':[p['model_attributes']for p in author['pages']],'parameters_used_only_as_source_evidence_not_for_pixel_fitting':True};assets['source_evidence']=put(directory/'source_evidence.json',raw(evidence));out={'schema':'unqualified_recovered_PNG_author_native_source_v1','id':ident,'source':source['source'],'original_source_record':source,'original_code_sha256':source['code_sha256'],'original_image_sha256':source['image_sha256'],'recovered_author_sha256':sha(decoded),'assets':assets,'classification':comparison['classification'],'provided_parse_ok':provided['parse_ok'],'provided_structurally_valid':provided['structurally_valid'],'author_parse_ok':author['parse_ok'],'author_structurally_valid':author['structurally_valid'],'provided_pages':len(provided['pages']),'author_pages':len(author['pages']),'source_page_pairing':{k:comparison.get(k)for k in ('paired_author_page_indices','page_pairing_basis','page_pairing_requires_separate_source_contract')},'accepted':False,'qualified':False,'quality_state':'author_source_recovered_not_rendered_not_qualified','canonical_source_replaced':False,'model_calls':0};assets['record']=put(directory/'record.json',raw(out));outputs.append(out);print(json.dumps({'id':ident,'classification':out['classification'],'provided_pages':out['provided_pages'],'author_pages':out['author_pages'],'author_valid':author['structurally_valid']}),flush=True)
  except Exception as error:errors.append({'id':ident,'type':type(error).__name__,'error':str(error)});print(json.dumps(errors[-1]),flush=True)
  put(work/('progress_'+str(len(outputs)+len(errors))+'.json'),raw({'processed':len(outputs)+len(errors),'recovered':len(outputs),'errors':errors}))
 db.close();put(work/'recovered.jsonl',b''.join(raw(x)for x in outputs));summary={'schema':'all_45_embedded_author_native_source_recovery_summary_v1','input_audit_sha256':AUDIT_SHA,'expected':45,'recovered':len(outputs),'errors':errors,'counts':dict(collections.Counter(x['classification']for x in outputs)),'by_provider':{provider:dict(collections.Counter(x['classification']for x in outputs if x['source']==provider))for provider in sorted({x['source']for x in outputs})},'author_documents_parse_ok':sum(x['author_parse_ok']for x in outputs),'author_documents_structurally_valid':sum(x['author_structurally_valid']for x in outputs),'originals_complete_and_hash_verified':len(outputs),'author_multi_page_documents':sum(x['author_pages']>1 for x in outputs),'records':{'file':str((work/'recovered.jsonl').relative_to(R)),'sha256':sha((work/'recovered.jsonl').read_bytes())},'clean_root':str(destroot),'report':str(work/'summary.json'),'all_original_source_code_and_PNG_bytes_preserved':True,'canonical_jobs_written':False,'source_manifest_modified':False,'image_pixels_decoded':False,'reference_pixels_scored':False,'native_rendering':False,'qualified_or_accepted':0,'model_calls':0,'script_sha256':sha(Path(__file__).read_bytes())};put(work/'summary.json',raw(summary));print(json.dumps(summary),flush=True)
if __name__=='__main__':run()
