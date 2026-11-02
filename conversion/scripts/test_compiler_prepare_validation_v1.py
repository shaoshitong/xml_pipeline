"""Temporary synthetic metadata only: no source execution, renderer, or model."""
import copy
import json
import multiprocessing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import compiler_prepare_validation_v1 as p
import compiler_capture_snapshot_v1 as capture
import compiler_validation_reservation_v1 as registry


def reserve_child(path,rows,prefix,queue):
    try:
        registry.reserve(path,rows,audit=Path(path).parent,run_prefix=prefix,
                         implementation_identity_sha256='a'*64,phase_runs={'B':prefix+'_B','C':prefix+'_C'},
                         selected_manifest_sha256='b'*64,protocol_sha256='c'*64,controls_proof_sha256='d'*64)
        queue.put('reserved')
    except (ValueError,sqlite3.Error):queue.put('rejected')


class PreparerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='compiler-preparer-test-');self.root=Path(self.temp.name).resolve()
        self.work=self.root/'conversion';self.work.mkdir();self.counter=0
        self.patches=[patch.multiple(p,R=self.root,W=self.work),patch.object(capture,'R',self.root),
                      patch.object(p.controller,'FLOOR',self.root/'release/compiler_v1')]
        for x in self.patches:x.start()
        self.addCleanup(self.temp.cleanup)
        for x in reversed(self.patches):self.addCleanup(x.stop)
        self.bindings={'synthetic':'quality_bindings'};self.qa=p.base.sha(p.base.raw(self.bindings))
        self.freeze=dict(pins={str(self.root/'synthetic_module.py'):'a'*64},qa_policy_sha256=self.qa,
                         predicate_hashes={p.UNIT:'b'*64})
        self.freeze['implementation_identity']=p.controller.implementation_identity(self.freeze)
        self.freeze['implementation_identity_sha256']=p.controller.implementation_digest(self.freeze)

    def write(self,path,value):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(value if isinstance(value,bytes) else p.base.raw(value));return path

    def asset(self,path,role=None):
        item=dict(file=str(path),sha256=p.base.sha(Path(path).read_bytes()))
        if role:item['role']=role
        return item

    def source(self,index):
        ident=p.base.sha(('pair:'+str(index)).encode());folder=self.root/'clean/inputs'/str(index)
        code=self.write(folder/'source.py',('source:'+str(index)).encode());image=self.write(folder/'reference.bin',('image:'+str(index)).encode())
        dot=self.write(folder/'source.dot',('graph:'+str(index)).encode());svg=self.write(folder/'source.svg',('svg:'+str(index)).encode())
        target=self.write(folder/'candidate.drawio',('xml:'+str(index)).encode());png=self.write(folder/'candidate.png',('png:'+str(index)).encode())
        auditfolder=self.work/'captures'/str(index);self.write(auditfolder/'returned_image.png',('cache:'+str(index)).encode())
        audit=self.write(auditfolder/'audit.json',dict(id=ident,source_code_sha256=p.base.sha(code.read_bytes()),directory=str(auditfolder.relative_to(self.root))))
        source=dict(pair_sha256=ident,category='scientific_diagram',format='python',source='synthetic',
                    code_sha256=p.base.sha(code.read_bytes()),image_sha256=p.base.sha(image.read_bytes()))
        record=dict(id=ident,source_pair_sha256=ident,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],
                    source_format='python',original_source_code=str(code.relative_to(self.root)),original_reference=str(image.relative_to(self.root)),
                    code_file=str(target.relative_to(self.root)),code_sha256=p.base.sha(target.read_bytes()),
                    image_file=str(png.relative_to(self.root)),image_sha256=p.base.sha(png.read_bytes()),
                    source_render_dot=str(dot.relative_to(self.root)),source_render_svg=str(svg.relative_to(self.root)),
                    source_render_svg_sha256=p.base.sha(svg.read_bytes()),execution_audit=str(audit.relative_to(self.root)))
        evidence=dict(source_dot_sha256=p.base.sha(dot.read_bytes()),source_svg_sha256=p.base.sha(svg.read_bytes()),execution_audit_sha256=p.base.sha(audit.read_bytes()))
        item=dict(id=ident,source=source,audit_cluster='cluster:'+str(index),cluster_keys=['skeleton:'+str(index)],
                  support_unit=p.UNIT,source_hash_verified=True,development_overlap=False,static_support_evidence=evidence,
                  source_record_sha256=p.base.sha(p.base.raw(record)))
        return source,record,item

    def controls(self):
        self.counter+=1;folder=self.root/'controls'/str(self.counter);manifest=[];expected=[];outcomes=[];info={}
        policy=p.quality.POLICY+':'+self.qa[:20]
        for kind,index in [('positive',101),('negative',102)]:
            source,record,item=self.source(index+self.counter*1000);identifier=kind;work=folder/kind
            source_record=self.write(work/'source_record.json',record)
            request=dict(id=record['id'],seq=1 if kind=='positive' else 2,source=source,compiler_unit=p.UNIT,
                         source_record_sha256=p.base.sha(source_record.read_bytes()),pins=self.freeze['pins'],
                         source_capture_snapshot=capture.seal_snapshot(record))
            request_path=self.write(work/'request.json',request)
            audit_path=work/'audit.json';checks=dict(structure={},resources={},source=dict(supported=True,ok=kind=='positive',failures=[] if kind=='positive' else ['missing edge']),
                 render={},text_paint={},fonts=dict(all_rendered_fonts_embedded=True),visual=dict(ok=True),native_editing=dict(ok=True))
            audit=dict(id=record['id'],policy=policy,compiler_quality_bindings=self.bindings,checks=checks,
                       state='qualified' if kind=='positive' else 'repair_required',failures=[] if kind=='positive' else ['source_coverage_failure'],
                       input_code_sha256=record['code_sha256'],new_png_sha256=record['image_sha256'])
            self.write(audit_path,audit)
            result=dict(id=record['id'],seq=request['seq'],compiler_unit=p.UNIT,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],
                        status='qualified' if kind=='positive' else 'abandoned',quality_report=str(audit_path.relative_to(self.root)),quality_policy=policy)
            if kind=='positive':
                evidencefolder=self.root/'clean/proofs'/str(self.counter);assets={}
                for name in ('source_dot','source_svg','cached_execution_audit','cached_returned_png','source_scene','fresh_source_engine_png','fresh_source_reference_canvas_png','source_text_line_boxes'):
                    assets[name]=self.asset(self.write(evidencefolder/(name+'.bin'),name.encode()))
                stage=self.write(evidencefolder/'source_stage.json',dict(id=record['id'],ok=True,graphviz_reexecuted=True,
                     fresh_vs_cache=dict(exact_rgba_pixels_equal=True),source_reference_visual=dict(ok=True),
                     assets=assets,reference=dict(file=record['original_reference'],sha256=source['image_sha256'])))
                result['source_reproduction_evidence']=self.asset(stage)
                metadata=dict(record,automatic_quality_policy=policy,automatic_quality_audit=str(audit_path.relative_to(self.root)),
                              compiler_source_reproduction=self.asset(stage))
                metadatafile=self.write(evidencefolder/'metadata.json',metadata)
                result['manifest']=dict(record,metadata_file=str(metadatafile.relative_to(self.root)),metadata_sha256=p.base.sha(metadatafile.read_bytes()))
            result_path=self.write(work/'result.json',result)
            isolation=self.write(work/'isolation.json',dict(ok=True,cleanup_complete=True,returncode=0,deadline_exceeded=False))
            manifest.append(dict(control_id=identifier,kind=kind,compiler_unit=p.UNIT,input_assets=[self.asset(request_path,'request'),self.asset(source_record,'source_record')]))
            expected.append(dict(control_id=identifier,kind=kind,expected_status=result['status'],expected_failure_stage=None if kind=='positive' else 'source'))
            outcomes.append(dict(control_id=identifier,result=self.asset(result_path),quality_audit=self.asset(audit_path),isolation=self.asset(isolation)))
            info[kind]=dict(result=result_path,audit=audit_path,request=request_path,isolation=isolation,record=source_record)
        refs={}
        for key,rows in [('controls_manifest',manifest),('expectations',expected),('outcomes',outcomes)]:
            refs[key]=self.asset(self.write(folder/(key+'.jsonl'),b''.join(p.base.raw(x) for x in rows)))
        proof=self.write(folder/'proof.json',dict(schema='compiler_controls_proof_v1',implementation_identity=self.freeze['implementation_identity'],
                    implementation_identity_sha256=self.freeze['implementation_identity_sha256'],**refs));return proof,info

    def rehash(self,proof,kind,filekey):
        body=json.loads(proof.read_bytes());ref=body['outcomes'];rows=[json.loads(x) for x in Path(ref['file']).read_bytes().splitlines()]
        for row in rows:
            if row['control_id']==kind:row[filekey]=self.asset(Path(row[filekey]['file']))
        self.write(ref['file'],b''.join(p.base.raw(x) for x in rows));body['outcomes']=self.asset(Path(ref['file']));self.write(proof,body)

    def audit_cohort(self):
        audit=self.root/'release/compiler_validation_v1/audit';audit.mkdir(parents=True);selected=[]
        db=sqlite3.connect(self.work/'jobs.sqlite');db.execute('create table jobs(id text,input_record text,output_record text)')
        for index in range(1,31):
            source,record,item=self.source(index);selected.append(item)
            db.execute('insert into jobs values(?,?,?)',(item['id'],p.base.raw(source).decode(),p.base.raw(record).decode()))
        db.commit();db.close()
        scene=self.write(self.work/'scripts/compiler_scene_v1.py',b'# synthetic predicate')
        protocol=dict(audit_budget_exceeded_blocks_all_groups=False,predicate_pins={'scene':dict(path=str(scene),sha256=p.base.sha(scene.read_bytes()),static_support_ast_sha256='b'*64)},release_gate={})
        manifest=self.write(audit/'compiler_validation_selected_manifest.jsonl',b''.join(p.base.raw(x) for x in selected));proto=self.write(audit/'compiler_validation_protocol.json',protocol)
        self.write(audit/'compiler_validation_summary.json',dict(files=[dict(file=x.name,sha256=p.base.sha(x.read_bytes())) for x in (manifest,proto)],
            validation_executions=0,outcomes_viewed=False,statistics={p.UNIT:dict(minimum_30_met=True,selected_validation_clusters=30,matching_queued_population=100)}))
        return audit,selected

    def prepare(self,prefix):
        config=dict(policy='synthetic',policy_sha256=self.qa,bindings=self.bindings)
        with patch.object(p.quality,'configuration',return_value=config),patch.object(p,'implementation_pins',return_value=self.freeze['pins']),\
                patch.object(p,'check_controls_proof',return_value=dict(sha256='e'*64,counts=dict(positive=1,negative=1))),\
                patch.object(p.controller,'create',return_value=dict(counts={'queued':30})):
            return p.prepare('audit',prefix,self.root/'synthetic-proof.json')

    def test_controls_complete_positive_and_actual_negative_pass(self):
        proof,info=self.controls();result=p.check_controls_proof(proof,self.freeze)
        self.assertEqual(result['counts'],{'positive':1,'negative':1});self.assertEqual(result['infrastructure_errors'],0)

    def test_controls_identity_or_actual_policy_mismatch_rejected(self):
        proof,info=self.controls();other=copy.deepcopy(self.freeze);other['qa_policy_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'implementation_mismatch'):p.check_controls_proof(proof,other)
        audit=json.loads(info['positive']['audit'].read_bytes());audit['compiler_quality_bindings']={'different':'policy'};self.write(info['positive']['audit'],audit);self.rehash(proof,'positive','quality_audit')
        with self.assertRaisesRegex(ValueError,'actual_quality_policy_mismatch'):p.check_controls_proof(proof,self.freeze)

    def test_claimed_boolean_pass_without_actual_full_quality_or_rejection_fails(self):
        for kind in ('positive','negative'):
            with self.subTest(kind=kind):
                proof,info=self.controls();audit=json.loads(info[kind]['audit'].read_bytes())
                if kind=='positive':audit['checks'].pop('native_editing')
                else:audit['checks']['source']['ok']=True
                self.write(info[kind]['audit'],audit);self.rehash(proof,kind,'quality_audit')
                with self.assertRaisesRegex(ValueError,'missing_full_quality|not_rejected'):p.check_controls_proof(proof,self.freeze)

    def test_current_payload_result_and_isolation_bytes_are_checked(self):
        proof,info=self.controls();info['negative']['result'].write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash_changed'):p.check_controls_proof(proof,self.freeze)
        proof,info=self.controls();isolation=json.loads(info['positive']['isolation'].read_bytes());isolation['cleanup_complete']=False
        self.write(info['positive']['isolation'],isolation);self.rehash(proof,'positive','isolation')
        with self.assertRaisesRegex(ValueError,'isolation_or_cleanup'):p.check_controls_proof(proof,self.freeze)

    def test_reserved_cohort_or_any_identity_or_hard_cluster_cannot_be_reused(self):
        _,_,item=self.source(1);path=self.root/'registry.sqlite'
        kwargs=dict(audit=self.root,implementation_identity_sha256='a'*64,selected_manifest_sha256='b'*64,protocol_sha256='c'*64,controls_proof_sha256='d'*64)
        record=registry.reserve(path,[item],run_prefix='first',phase_runs={'B':'first_B','C':'first_C'},**kwargs)
        self.assertEqual(record['state'],'reserved');self.assertFalse(record['consumed'])
        for mode in ('cohort','id','code','image','hard_cluster'):
            with self.subTest(mode=mode):
                _,_,other=self.source(2)
                if mode=='cohort':other=copy.deepcopy(item)
                elif mode=='id':other['id']=item['id']
                elif mode in ('code','image'):other['source'][mode+'_sha256']=item['source'][mode+'_sha256']
                else:other['cluster_keys']=item['cluster_keys']
                with self.assertRaisesRegex(ValueError,'already_reserved'):
                    registry.reserve(path,[other],run_prefix='new_'+mode,phase_runs={'B':'new_'+mode+'_B','C':'new_'+mode+'_C'},**kwargs)
        db=sqlite3.connect(path);self.assertEqual(db.execute('select count(*) from reservations').fetchone()[0],1);db.close()

    def test_registry_concurrent_reservation_is_atomic(self):
        _,_,row=self.source(1);ctx=multiprocessing.get_context('spawn');queue=ctx.Queue();path=self.root/'concurrent.sqlite'
        workers=[ctx.Process(target=reserve_child,args=(str(path),[row],name,queue)) for name in ('one','two')]
        for worker in workers:worker.start()
        try:self.assertEqual(sorted(queue.get(timeout=10) for _ in workers),['rejected','reserved'])
        finally:
            for worker in workers:
                worker.join(10)
                if worker.is_alive():worker.terminate();worker.join()
        self.assertTrue(all(worker.exitcode==0 for worker in workers));queue.close()

    def test_preparer_seals_same_snapshot_to_B_C_and_reserves_only(self):
        audit,rows=self.audit_cohort();before={x.name:x.read_bytes() for x in audit.iterdir()};receipt=self.prepare('pair')
        self.assertEqual(receipt['reservation']['state'],'reserved');self.assertFalse(receipt['reservation']['consumed'])
        sealed=self.root/'release/compiler_v1/seal_pair';b=[json.loads(x) for x in (sealed/'B.jsonl').read_bytes().splitlines()];cc=[json.loads(x) for x in (sealed/'C.jsonl').read_bytes().splitlines()]
        self.assertEqual(len(b),30);self.assertEqual([x['source_capture_snapshot'] for x in b],[x['source_capture_snapshot'] for x in cc])
        self.assertEqual(before,{x.name:x.read_bytes() for x in audit.iterdir()})

    def test_new_prefix_does_not_reuse_static_unconsumed_summary(self):
        self.audit_cohort();self.prepare('first')
        with self.assertRaisesRegex(ValueError,'already_reserved'):self.prepare('second')
        self.assertFalse((self.root/'release/compiler_v1/seal_second').exists())

    def test_capture_drift_blocks_before_reservation(self):
        _,rows=self.audit_cohort();path=self.root/'clean/inputs/1/source.dot';path.write_bytes(path.read_bytes()+b'\n# changed')
        with self.assertRaisesRegex(RuntimeError,'differs_from_selected_snapshot'):self.prepare('drift')
        self.assertFalse((self.root/'release/compiler_v1/validation_registry.sqlite').exists())

    def test_failed_partial_preparation_stays_reserved_and_cannot_rename(self):
        self.audit_cohort();config=dict(policy='synthetic',policy_sha256=self.qa,bindings=self.bindings)
        with patch.object(p.quality,'configuration',return_value=config),patch.object(p,'implementation_pins',return_value=self.freeze['pins']),\
                patch.object(p,'check_controls_proof',return_value=dict(sha256='e'*64)),\
                patch.object(p.controller,'create',side_effect=RuntimeError('synthetic create failure')):
            with self.assertRaisesRegex(RuntimeError,'synthetic create failure'):p.prepare('audit','partial',self.root/'proof')
        with self.assertRaisesRegex(ValueError,'already_reserved'):self.prepare('renamed')
        db=sqlite3.connect(self.root/'release/compiler_v1/validation_registry.sqlite')
        self.assertEqual(db.execute('select state from reservations').fetchall(),[('reserved',)]);db.close()


if __name__=='__main__':unittest.main(verbosity=2)
