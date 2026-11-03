"""Remote-only, bounded, low-I/O native XML prefilter. Not final acceptance.

Read PNG metadata before IDAT only; do not read/decode pixel data. Preserve raw
extracted XML and cache every result. Official decoder and strict replay still
must verify provisional candidates before any publisher may admit them.
"""
from pathlib import Path
import argparse,base64,concurrent.futures as cf,datetime,fcntl,hashlib,json,multiprocessing,os,re,signal,sqlite3,struct,time,urllib.parse,xml.etree.ElementTree as ET,zlib
from arxiv_author_native_assets_v1 import models
from arxiv_math_source_repair_v1 import native,classify,valuable
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';D=P/'embedded_XML_parallel_prefilter_v1';LIMIT=64*1024**2
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=lambda b:hashlib.sha256(b).hexdigest()
KNOWN_RAW=set()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def put(p,obj):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n');os.replace(t,p)
def bounded_inflate(b):
 for mode in (zlib.MAX_WBITS,-15):
  try:
   d=zlib.decompressobj(mode);out=d.decompress(b,LIMIT+1);require(len(out)<=LIMIT and not d.unconsumed_tail and d.eof and not d.unused_data,'unbounded_or_incomplete_text_compression');return out
  except zlib.error:
   if mode==-15:raise
 raise ValueError('text_inflate_failed')
def percent(text,count):
 for _ in range(count):
  if not text.startswith('%'):break
  require(not re.search(r'%(?![0-9a-fA-F]{2})',text),'malformed_URI_escape')
  text=urllib.parse.unquote(text,encoding='utf-8',errors='strict')
 return text

def png_xml(stream):
 require(stream.read(8)==b'\x89PNG\r\n\x1a\n','not_PNG');size=os.fstat(stream.fileno()).st_size
 for _ in range(10000):
  head=stream.read(8);require(len(head)==8,'truncated_PNG_chunk_header');n,kind=struct.unpack('>I4s',head);require(stream.tell()+n+4<=size,'truncated_PNG_chunk')
  if kind in (b'IDAT',b'IEND'):raise ValueError('no_supported_native_text_before_IDAT')
  if kind not in (b'tEXt',b'zTXt'):
   stream.seek(n+4,1);continue
  prefix=stream.read(min(n,80));keyword=prefix.split(b'\0',1)[0]
  if keyword not in (b'mxfile',b'mxGraphModel'):
   stream.seek(n-len(prefix)+4,1);continue
  require(n<=LIMIT,'native_text_chunk_above64MiB');data=prefix+stream.read(n-len(prefix));crc=stream.read(4);require(len(crc)==4 and zlib.crc32(kind+data)&0xffffffff==struct.unpack('>I',crc)[0],'native_text_CRC_mismatch')
  _,payload=data.split(b'\0',1)
  if kind==b'zTXt':
   require(payload[:1]==b'\0','unsupported_text_compression_method');text=bounded_inflate(payload[1:]).decode('utf-8').replace('+',' ')
  else:text=payload.decode('latin-1')
  text=percent(text,2);return text.encode('utf-8'),dict(container='PNG',text_chunk=kind.decode(),keyword=keyword.decode(),PNG_pixel_bytes_not_read=True,official_decoder_agreement='not_yet_tested')
 raise ValueError('PNG_chunk_count_bound')
def svg_xml(blob):
 require(len(blob)<=LIMIT,'SVG_above64MiB');text=blob.decode('utf-8-sig');require('<!ENTITY' not in text.upper(),'SVG_entity_declaration')
 declaration=re.search(r'<!DOCTYPE\s+[^>]*>',text,re.I|re.S)
 if declaration:
  require('[' not in declaration[0],'SVG_internal_DTD_subset');text=text[:declaration.start()]+text[declaration.end():]
 root=ET.fromstring(text);tag=root.tag.rsplit('}',1)[-1]
 if tag in ('mxfile','mxGraphModel'):return blob,dict(container='XML_named_SVG',official_decoder_agreement='not_yet_tested')
 require(tag=='svg','SVG_root_invalid');content=root.get('content');require(content is not None,'SVG_native_content_missing')
 if not content.startswith(('<','%')):content=base64.b64decode(content,validate=True).decode('latin-1')
 return percent(content,1).encode('utf-8'),dict(container='SVG',official_decoder_agreement='not_yet_tested')
def extract(path):
 if path.suffix.lower()=='.png':
  with path.open('rb') as stream:return png_xml(stream)
 with path.open('rb') as stream:return svg_xml(stream.read(LIMIT+1))
def graph_hash(model):
 def node(n):return [n.tag,sorted(n.attrib.items()),(n.text or '').strip(),[node(c) for c in n]]
 return sha(json.dumps([node(model.find('root'))],ensure_ascii=True).encode())
def worker(row):
 started=time.monotonic();signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('metadata_prefilter_12s_bound')));signal.alarm(12)
 out=dict(file=row['file'],status='pending_metadata_prefilter',at_utc=now(),final_QA=False,new_PDF_import_calls=0,new_source_downloads=0,new_model_calls=0)
 try:
  source=R/row['file'];require(source.resolve().is_relative_to(P/'recent_ai_source_expansion_v2/papers'),'source_outside_arxiv_tree');blob,decoder=extract(source);out.update(decoder=decoder,embedded_XML_SHA256=sha(blob),embedded_XML_bytes=len(blob));require(len(blob)<=LIMIT,'decoded_XML_above64MiB');require(b'<!DOCTYPE' not in blob.upper() and b'<!ENTITY' not in blob.upper(),'native_XML_DTD_not_supported');root=ET.fromstring(blob)
  if root.tag=='mxfile':
   count=len(root.findall('diagram'));out['native_pages']=count
   if count!=1:out['status']='multi_page_held_before_inflate';return out
  else:require(root.tag=='mxGraphModel','metadata_root_not_native')
  if sha(blob) in KNOWN_RAW:out['status']='exact_XML_already_processed';return out
  model=models(blob)[1][0];out['decoded_graph_SHA256']=graph_hash(model);f=native(ET.tostring(model,encoding='unicode'));kind,reasons=classify(f,'drawio',{});out.update(features=f,classification=kind,classification_reasons=reasons,native_pages=1)
  if kind!='complex_candidate' or not valuable(f):out['status']='below_existing_value_policy';return out
  folder=D/'extracted_XML';folder.mkdir(exist_ok=True);path=folder/(sha(blob)+'.drawio')
  if not path.exists():
   tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp');tmp.write_bytes(blob);os.replace(tmp,path)
  out.update(status='provisional_valuable_single_page_XML',embedded_XML_file=str(path.relative_to(R)),source_only_not_original_PDF_certified=True,official_decoder_and_archive_and_resource_and_font_and_edit_restore_checks_still_required=True)
 except Exception as error:out.update(reason=type(error).__name__+':'+str(error)[:1000])
 finally:signal.alarm(0);out['seconds']=time.monotonic()-started
 return out

def known_raw():
 result=set()
 for p in [R/'clean/accepted_3759_v1/pairs.jsonl',P/'goal500_progress_v1/accepted_new_pairs.jsonl']:
  for line in p.read_text().splitlines():result.add(json.loads(line)['code_sha256'])
 for name in ['new_bulk_200_v1','recent_ai_source_expansion_v2']:
  with sqlite3.connect((P/name/'once.sqlite').as_uri()+'?mode=ro',uri=True) as c:
   result.update(r[0] for r in c.execute("select json_extract(record,'$.author_xml_sha256') from pdfs where json_extract(record,'$.author_xml_sha256') is not null"))
 return result

def publish(c):
 rows=[json.loads(r[0]) for r in c.execute('select record from files where status=? order by file',('provisional_valuable_single_page_XML',))];states=dict(c.execute('select status,count(*) from files group by status'));seen={};provisional=[]
 for row in rows:
  if row['status']!='provisional_valuable_single_page_XML':continue
  graph=row['decoded_graph_SHA256']
  if graph not in seen:seen[graph]=row['file'];provisional.append(row)
 tmp=D/'provisional_unique_candidates.jsonl.tmp';tmp.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in provisional));os.replace(tmp,D/'provisional_unique_candidates.jsonl')
 summary=dict(at_utc=now(),states=states,processed=sum(v for k,v in states.items() if k!='queued'),provisional_unique_graphs=len(provisional),final_accepted_pairs=0,baseline_graph_dedup_and_official_decoder_and_full_QA_pending=True,workers=8,CPU_host='HKUST3',new_PDF_import_calls=0,new_source_downloads=0,new_model_calls=0)
 put(D/'status.json',summary);print(json.dumps(summary),flush=True)
def main(watch):
 global KNOWN_RAW
 D.mkdir(exist_ok=True);lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);put(D/'launch.json',dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],at_utc=now(),CPU_host='HKUST3'))
 c=sqlite3.connect(D/'files.sqlite',timeout=60);c.execute('pragma journal_mode=WAL');c.execute('create table if not exists files(file text primary key,status text,record text)');c.commit()
 while True:
  KNOWN_RAW=known_raw();inventory=json.loads((P/'embedded_XML_image_inventory_incremental_v3/inventory.json').read_text());by={r['file']:r for r in inventory['candidates']}
  c.executemany('insert or ignore into files values(?,?,?)',[(file,'queued',json.dumps(by[file])) for file in sorted(by)]);c.commit();publish(c)
  pending=[by[r[0]] for r in c.execute("select file from files where status='queued' order by file") if r[0] in by]
  with cf.ProcessPoolExecutor(max_workers=8,mp_context=multiprocessing.get_context('fork')) as pool:
   futures={pool.submit(worker,row):row for row in pending}
   for i,future in enumerate(cf.as_completed(futures)):
    row=future.result();c.execute('update files set status=?,record=? where file=?',(row['status'],json.dumps(row),row['file']));c.commit()
    if i%20==0:publish(c)
  publish(c)
  if not watch:break
  time.sleep(120)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');main(p.parse_args().watch)
