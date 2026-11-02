"""Bounded nonpublication: one prior real target and first two inventory IDs."""
import copy,hashlib,json,shutil,sqlite3,subprocess,time,unittest,xml.etree.ElementTree as E
from pathlib import Path
import tikz_execution_candidate_batch_v1 as batch
from test_tikz_execution_candidate_batch_v1 import StateTests,PublicationTests

W=batch.W;R=batch.R
ids=['0002d1280db280c2d9227e7d2188cd20f0cbc446310f112772df3d9b62cca423','0013e1b601b2cfc7a858cdcde0dcebb1472be27b77c738919c81511763a1acc8','6a09ccf14db3f3ac3d016e3eff21daed7c468f7e9a7ea1a5fef3a853f6fe36a6']
suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (StateTests,PublicationTests)]);result=unittest.TextTestRunner(verbosity=1).run(suite);assert result.wasSuccessful();tests={'at':batch.now(),'ok':True,'test_count':result.testsRun,'isolated_sqlite_and_filesystem_only':True};batch.atomic(W/'tikz_execution_candidate_v1_state_tests.json',(json.dumps(tests,indent=2)+'\n').encode())
db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)
before={id:list(batch.snapshot(db,id)) for id in ids};old_blobs={id:{key:hashlib.sha256((R/json.loads(before[id][1])[key]).read_bytes()).hexdigest() for key in ('code_file','image_file','original_source_code','original_reference')} for id in ids};queues={t:db.execute('select * from '+t+' where id in (?,?,?)',ids).fetchall() for t in batch.MODEL_TABLES if batch.exists(db,t)};db.close();batch.atomic(W/'tikz_execution_candidate_v1_smoke_before.json',(json.dumps({'jobs':before,'payload_hashes':old_blobs,'model_queues':queues},indent=2)+'\n').encode())
command=['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/tikz_execution_candidate_batch_v1.py'),'--workers','1','--limit','3']
for id in ids:command.extend(['--id',id])
run=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=1200);batch.atomic(W/'tikz_execution_candidate_v1_smoke.stdout',run.stdout.encode());batch.atomic(W/'tikz_execution_candidate_v1_smoke.stderr',run.stderr.encode());print(run.stdout,flush=True);assert run.returncode==0,run.stderr[-2500:]
db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True);after={id:list(batch.snapshot(db,id)) for id in ids};queues_after={t:db.execute('select * from '+t+' where id in (?,?,?)',ids).fetchall() for t in queues};after_blobs={id:{key:hashlib.sha256((R/json.loads(before[id][1])[key]).read_bytes()).hexdigest() for key in ('code_file','image_file','original_source_code','original_reference')} for id in ids};db.close();assert before==after,'Nonpublishing smoke changed a selected job snapshot';assert queues==queues_after,'Nonpublishing smoke changed a model queue';assert old_blobs==after_blobs,'Nonpublishing smoke changed an original source/native pair'
summary=json.loads((W/'tikz_execution_candidate_v1_summary.json').read_text())
# Revalidate actual generated metadata after moving only its immutable proof
# bundle, then reject fresh metadata corruption without editing source payloads.
import tikz_execution_source_profile_v3 as profile
db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True);raw=db.execute('select record from '+batch.TABLE+' where id=? and policy=? and state="validated_dry_run"',(ids[-1],summary['policy'])).fetchone()[0];db.close();entry=json.loads(raw);work=R/entry['work'];record=json.loads((work/'candidate_record.json').read_text());xml=(work/'candidate.drawio').read_text();png=(work/'candidate.png').read_bytes();relocated=work/'relocation_check/proof';relocated.mkdir(parents=True)
for name,item in record[profile.FIELD]['files'].items():dest=relocated/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/item['file'],dest)
record[profile.FIELD]=profile.relocate(record[profile.FIELD],relocated);positive=profile.check_execution_marker_render(record,xml,png);assert positive['ok'],positive
negatives=[]
for name in ('source_identity','baseline_xml_hash','script_pin','current_native_relation','native_png_hash'):
 bad=copy.deepcopy(record);text=xml
 if name=='source_identity':bad['source_code_sha256']='0'*64
 if name=='baseline_xml_hash':bad[profile.FIELD]['files']['baseline.drawio']['sha256']='0'*64
 if name=='script_pin':bad[profile.FIELD]['scripts']['tikz_execution_binding.py']['sha256']='0'*64
 if name=='native_png_hash':bad['image_sha256']='0'*64
 if name=='current_native_relation':
  root=E.fromstring(xml);edge=next(c for c in root.iter('mxCell') if c.get('edge')=='1');edge.set('target',edge.get('source'));text=E.tostring(root,encoding='unicode');bad['code_sha256']=batch.sha(text.encode());bad[profile.FIELD]['candidate_code_sha256']=bad['code_sha256']
 result=profile.check_execution_marker_render(bad,text,png) if name=='native_png_hash' else profile.check_execution_profile(bad,text);assert not result['ok'],name;negatives.append({'case':name,'rejected':True,'failures':result['failures']})
api={'relocated_actual_proof_bundle_passed':True,'marker_gate_passed':positive['ok'],'negative_fixtures':negatives};batch.atomic(work/'source_profile_v3_api_tests.json',(json.dumps(api,indent=2)+'\n').encode());out={'at':batch.now(),'ok':True,'published':False,'accepted':0,'ids':ids,'summary':summary,'all_selected_job_snapshots_exactly_restored':True,'all_model_queue_rows_unchanged':True,'all_source_and_native_pair_hashes_unchanged':True,'state_and_rollback_tests':tests,'source_profile_v3_api_tests':api};batch.atomic(W/'tikz_execution_candidate_v1_smoke.json',(json.dumps(out,indent=2)+'\n').encode());print(json.dumps(out),flush=True)
