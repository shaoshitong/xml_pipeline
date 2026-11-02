"""Independent original-byte/metadata/model reconciliation; no pixel decoder."""
from pathlib import Path
import base64,copy,hashlib,json,sqlite3,struct,urllib.parse,zlib
import xml.etree.ElementTree as E
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';WORK=W/'compiler_native_embedded_source_recovery_v1/9e24c86b8b344ead88f8a55293b70795'
sha=lambda b:hashlib.sha256(b).hexdigest()
def models(data):
 root=E.fromstring(data.decode('utf-8-sig'));tag=root.tag.rsplit('}',1)[-1]
 if tag=='mxGraphModel':return root,[root]
 assert tag=='mxfile';out=[]
 for d in root:
  if d.tag.rsplit('}',1)[-1]!='diagram':continue
  inline=[n for n in d if n.tag.rsplit('}',1)[-1]=='mxGraphModel']
  if inline:assert len(inline)==1;out.append(inline[0])
  else:out.append(E.fromstring(urllib.parse.unquote_to_bytes(zlib.decompress(base64.b64decode(d.text.strip()),-15).decode())))
 return root,out
def canonical(model,drop_view=False):
 m=copy.deepcopy(model)
 if drop_view:
  for k in ('dx','dy'):m.attrib.pop(k,None)
 for n in m.iter():
  if n.text is not None and not n.text.strip():n.text=None
  if n.tail is not None and not n.tail.strip():n.tail=None
 return E.canonicalize(E.tostring(m,encoding='unicode'))
def extract(blob):
 assert blob[:8]==b'\x89PNG\r\n\x1a\n';pos=8;values=[]
 while pos<len(blob):
  n=int.from_bytes(blob[pos:pos+4],'big');kind=blob[pos+4:pos+8];payload=blob[pos+8:pos+8+n];crc=int.from_bytes(blob[pos+8+n:pos+12+n],'big');assert crc==zlib.crc32(kind+payload)&0xffffffff
  if kind in (b'tEXt',b'zTXt',b'iTXt'):
   key,value=payload.split(b'\x00',1);charset='latin1'
   if kind==b'zTXt':assert value[0]==0;value=zlib.decompress(value[1:])
   if kind==b'iTXt':
    flag,method=value[:2];language,rest=value[2:].split(b'\x00',1);translated,value=rest.split(b'\x00',1);charset='utf8'
    if flag:assert method==0;value=zlib.decompress(value)
   if key==b'mxfile':values.append(value.decode(charset))
  pos+=12+n
  if kind==b'IEND':break
 assert len(values)==1;return urllib.parse.unquote_to_bytes(values[0])
def main():
 rows=[json.loads(x)for x in(WORK/'recovered.jsonl').read_bytes().splitlines()if x];assert len(rows)==45;db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True);db.execute('pragma query_only=ON');db.execute('begin');results=[]
 for row in rows:
  source=json.loads(db.execute('select input_record from jobs where id=?',(row['id'],)).fetchone()[0]);assert source==row['original_source_record'];assets=row['assets']
  for a in assets.values():
   p=(R/a['file']).resolve();assert p.is_relative_to(R/'clean/compiler_native_embedded_source_recovery_v1');assert p.is_file()and not(R/a['file']).is_symlink();assert sha(p.read_bytes())==a['sha256']
  png=(R/assets['original_reference']['file']).read_bytes();gold=(R/assets['original_provided_code']['file']).read_bytes();author=(R/assets['recovered_author_native']['file']).read_bytes();assert sha(png)==source['image_sha256'];assert sha(gold)==source['code_sha256'];assert extract(png)==author
  g,gpages=models(gold);a,apages=models(author);assert len(gpages)==1;exact=[i for i,p in enumerate(apages)if canonical(p)==canonical(gpages[0])];content=[i for i,p in enumerate(apages)if canonical(p,True)==canonical(gpages[0],True)];assert len(content)==1;assert content==row['source_page_pairing']['paired_author_page_indices'];assert a.get('scale')=='1'and a.get('border')=='0'
  results.append({'id':row['id'],'all_clean_assets_hash_verified':True,'canonical_original_code_and_image_unchanged':True,'independent_original_PNG_text_decode_exact':True,'provided_full_native_model_exact':bool(exact),'complete_native_model_except_dx_dy_exact':True,'author_page_match':content[0],'author_pages':len(apages),'node_text_edge_binding_style_geometry_and_order_included':True,'image_pixels_decoded':False})
 db.close();report={'schema':'independent_all_45_original_byte_and_complete_native_model_reconciliation_v1','rows':results,'expected':45,'verified':len(results),'all_assets_clean_actual_files':True,'complete_models_exact':sum(x['provided_full_native_model_exact']for x in results),'only_dx_dy_differ':sum(not x['provided_full_native_model_exact']for x in results),'all_complete_native_contents_exact':True,'canonical_originals_unchanged':True,'pixels_decoded':False,'target_pixels_fitted':False,'renders':0,'qualification_claims':0,'model_calls':0,'verifier_sha256':sha(Path(__file__).read_bytes())};p=WORK/'independent_verification.json';p.open('xb').write(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2).encode());print(json.dumps({'report':str(p),'sha256':sha(p.read_bytes()),'verified':len(results),'complete_models_exact':report['complete_models_exact'],'only_dx_dy_differ':report['only_dx_dy_differ']}))
if __name__=='__main__':main()
