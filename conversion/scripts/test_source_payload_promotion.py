import json,sqlite3,copy,uuid,hashlib
from native_worker import R,W,now
from promote_source_payloads import plan,materialize_sources
from harness_source_provenance import freeze,validate_frozen
ID='4de2105b6f4dc4c18cb5ab5c9f06df4f2f73ae8732e805ac58fef9d1bedf71f1';D=sqlite3.connect(W/'jobs.sqlite',timeout=60)
raw=D.execute('select output_record from jobs where id=?',(ID,)).fetchone()[0];r=json.loads(raw);report=json.loads(D.execute('select record from source_payload_promotions where id=? and state="promoted"',(ID,)).fetchone()[0])
assert r['code_sha256']==report['code_sha256'] and r['image_sha256']==report['image_sha256']
assert plan(r)=={}
for key,c in report['changes'].items():
 a,b=R/c['from'],R/c['to'];assert a.stat().st_ino==b.stat().st_ino and a.stat().st_dev==b.stat().st_dev
 assert hashlib.sha256(b.read_bytes()).hexdigest()==c['sha256']
old=copy.deepcopy(r)
for key,c in report['changes'].items():old[key]=c['from']
assert set(plan(old))=={'original_reference','original_source_code'}
published=materialize_sources(old)
assert published['code_sha256']==old['code_sha256'] and published['image_sha256']==old['image_sha256']
assert all(published[k]==r[k] for k in report['changes']) and plan(published)=={}
negatives=[]
for name,edit in [('wrong_source_hash',lambda r:r.update(source_image_sha256='0'*64)),('outside_staging',lambda r:r.update(original_reference='/etc/passwd')),('path_traversal_id',lambda r:r.update(id='../../bad'))]:
 x=copy.deepcopy(old);edit(x)
 try:plan(x)
 except AssertionError:negatives.append(name)
 else:raise AssertionError('Negative accepted: '+name)
work=W/'harness_sessions'/('source_payload_promotion_test_'+uuid.uuid4().hex);work.mkdir(parents=True)
proof=freeze(r,work);assert validate_frozen(proof)==r
result={'at':now(),'id':ID,'source_payload_hashes_unchanged':True,'native_xml_png_hashes_unchanged':True,'hardlink_inode_verified':True,'new_source_provenance_freeze_valid':True,'negative_guards_rejected':negatives,'report':str(work.relative_to(R)),'ok':True}
(W/'source_payload_promotion_tests.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
