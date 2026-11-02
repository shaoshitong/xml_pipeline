"""Synthetic gate metadata only: no dataset, renderer, reservation, or models."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import compiler_evaluate_validation_v2 as gate


class DecisionTests(unittest.TestCase):
    def pairs(self,n=30,passed=6):
        return [dict(id=str(i),cluster='cluster'+str(i),B='abandoned',
                     C='qualified' if i<passed else 'abandoned',infrastructure_failure=False)
                for i in range(n)]

    def test_twenty_percent_boundary_and_gain_unchanged(self):
        result=gate.decision(self.pairs())
        self.assertTrue(result['passed']);self.assertEqual(result['new_qualified_clusters'],6)

    def test_five_of_thirty_still_insufficient(self):
        self.assertFalse(gate.decision(self.pairs(passed=5))['passed'])

    def test_baseline_overlap_does_not_count_as_gain(self):
        pairs=self.pairs();pairs[0]['B']=pairs[1]['B']='qualified'
        result=gate.decision(pairs)
        self.assertEqual(result['new_qualified_clusters'],4);self.assertFalse(result['passed'])

    def test_any_positive_regression_blocks(self):
        pairs=self.pairs(passed=12);pairs[-1]['B']='qualified'
        self.assertFalse(gate.decision(pairs)['passed'])

    def test_duplicate_cluster_cannot_replace_sample_size(self):
        pairs=self.pairs()
        for row in pairs:row['cluster']='same'
        self.assertFalse(gate.decision(pairs)['passed'])

    def test_infrastructure_and_controls_block(self):
        pairs=self.pairs();pairs[-1]['infrastructure_failure']=True
        self.assertFalse(gate.decision(pairs)['passed'])
        self.assertFalse(gate.decision(self.pairs(),False)['passed'])

    def test_twenty_nine_successes_not_thirty_clusters(self):
        self.assertFalse(gate.decision(self.pairs(n=29,passed=29))['passed'])

    def test_empty_pairs_fail_without_dividing_by_zero(self):
        self.assertFalse(gate.decision([])['passed'])


class CandidateTextProofTests(unittest.TestCase):
    def test_complete_candidate_proof_passes(self):
        gate.require_candidate_text_render('C',dict(compiler_text_render=dict(supported=True,ok=True,failures=[])))

    def test_candidate_proof_rejects_missing_or_incomplete(self):
        bad=[None,{},dict(supported=False,ok=True,failures=[]),dict(supported=True,ok=False,failures=[]),
             dict(supported=True,ok=True,failures=['text differs']),dict(supported=True,ok=True),
             dict(supported=1,ok=True,failures=[]),dict(supported=True,ok=1,failures=[])]
        for proof in bad:
            with self.subTest(proof=proof):
                with self.assertRaisesRegex(ValueError,'compiler_text_render_not_passed'):
                    gate.require_candidate_text_render('C',dict(compiler_text_render=proof))

    def test_baseline_does_not_need_converter_text_proof(self):
        gate.require_candidate_text_render('B',{})
        gate.require_candidate_text_render('B',dict(compiler_text_render=dict(ok=False)))


class RenderDomainProofTests(unittest.TestCase):
    def test_complete_common_proof_passes_without_converter_proof(self):
        gate.require_render_domain(dict(compiler_render_domain=dict(supported=True,ok=True,failures=[])))

    def test_common_proof_rejects_missing_failed_or_incomplete_even_with_C_proof(self):
        bad=[None,{},[],dict(supported=False,ok=True,failures=[]),dict(supported=True,ok=False,failures=[]),
             dict(supported=True,ok=True,failures=['paint differs']),dict(supported=True,ok=True),
             dict(supported=1,ok=True,failures=[]),dict(supported=True,ok=1,failures=[])]
        for proof in bad:
            with self.subTest(proof=proof):
                checks=dict(compiler_render_domain=proof,compiler_text_render=dict(supported=True,ok=True,failures=[]))
                with self.assertRaisesRegex(ValueError,'compiler_render_domain_not_passed'):
                    gate.require_render_domain(checks)


class LedgerRowsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='compiler-v2-gate-test-')
        self.root=Path(self.temp.name).resolve();self.work=self.root/'conversion'
        self.rootpatch=patch.multiple(gate,R=self.root,W=self.work);self.rootpatch.start()
        self.addCleanup(self.rootpatch.stop);self.addCleanup(self.temp.cleanup)
        self.bindings={'synthetic':'compiler-v2 bindings'}
        self.freeze=dict(qa_policy_sha256=gate.base.sha(gate.base.raw(self.bindings)))
        self.policy='compiler_source_ir_and_full_native_quality_v2:'+self.freeze['qa_policy_sha256'][:20]

    def write(self,path,blob):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(blob if isinstance(blob,bytes) else gate.base.raw(blob));return path

    def fixture(self,phase,textproof=True,domainproof=True,suffix=''):
        run=self.root/'release/compiler_v2'/('fixture_'+phase+suffix);run.mkdir(parents=True)
        identifier='1'*64;clean=self.root/'clean/fixtures'/phase
        blobs={name:self.write(clean/name,(phase+':'+name).encode())
               for name in ['source.py','reference.png','diagram.drawio','image.png','metadata.json']}
        source=dict(code_sha256=gate.base.sha(blobs['source.py'].read_bytes()),
                    image_sha256=gate.base.sha(blobs['reference.png'].read_bytes()))
        task=dict(seq=1,id=identifier,evaluation_phase='baseline' if phase=='B' else 'candidate',
                  source=source,cluster='synthetic_cluster',compiler_unit=gate.UNIT)
        manifest=dict(id=identifier)
        for name,field,digest in [('source.py','original_source_code','source_code_sha256'),
                                  ('reference.png','original_reference','source_image_sha256'),
                                  ('diagram.drawio','code_file','code_sha256'),
                                  ('image.png','image_file','image_sha256'),
                                  ('metadata.json','metadata_file','metadata_sha256')]:
            manifest[field]=str(blobs[name].relative_to(self.root));manifest[digest]=gate.base.sha(blobs[name].read_bytes())
        checks=dict(structure={},resources={},source=dict(ok=True),render={},text_paint={},
                    fonts=dict(all_rendered_fonts_embedded=True),visual=dict(ok=True),native_editing=dict(ok=True))
        if textproof:checks['compiler_text_render']=dict(supported=True,ok=True,failures=[])
        if domainproof:checks['compiler_render_domain']=dict(supported=True,ok=True,failures=[])
        quality=dict(id=identifier,policy=self.policy,compiler_quality_bindings=self.bindings,state='qualified',failures=[],
                     checks=checks,input_code_sha256=manifest['code_sha256'],new_png_sha256=manifest['image_sha256'])
        qualityfile=self.write(self.work/'compiler_v2'/run.name/'quality.json',quality)
        record=dict(id=identifier,compiler_unit=gate.UNIT,seq=1,source_code_sha256=source['code_sha256'],
                    source_image_sha256=source['image_sha256'],cluster=task['cluster'],case_cleanup_complete=True,
                    model_calls=0,status='qualified',quality_report=str(qualityfile.relative_to(self.root)),
                    quality_policy=self.policy,manifest=manifest,source_reproduction_evidence=dict(synthetic=True))
        self.write(self.work/'compiler_v2'/run.name/('000001_'+identifier)/'result.json',record)
        target=self.write(run/'targets.jsonl',gate.base.raw(task));freeze=dict(self.freeze,input_sha256=gate.base.sha(target.read_bytes()))
        db=sqlite3.connect(run/'status.sqlite')
        db.execute('create table samples(seq integer,id text,source text,status text,attempts integer,result text)')
        db.execute('insert into samples values(?,?,?,?,?,?)',(1,identifier,json.dumps(task),'qualified',1,json.dumps(record)))
        db.commit();db.close()
        return run,freeze,qualityfile,quality,manifest

    def read(self,run,phase,freeze):
        snapshot=dict(metadata=dict(finished=True),counts=dict(qualified=1),infrastructure_stop=False)
        with patch.object(gate.controller,'snapshot',return_value=snapshot):return gate.rows(run,phase,freeze)

    def test_v2_candidate_full_qualified_row_passes(self):
        run,freeze,*_=self.fixture('C')
        result=self.read(run,'C',freeze)
        self.assertEqual(result['1'*64]['result']['status'],'qualified')
        self.assertIn('/compiler_v2/',result['1'*64]['result_file']['file'])

    def test_candidate_missing_textproof_rejects_even_full_other_checks(self):
        run,freeze,*_=self.fixture('C',False)
        with self.assertRaisesRegex(ValueError,'compiler_text_render_not_passed'):self.read(run,'C',freeze)

    def test_baseline_missing_textproof_keeps_v1_gate_behavior(self):
        run,freeze,*_=self.fixture('B',False)
        self.assertEqual(self.read(run,'B',freeze)['1'*64]['result']['status'],'qualified')

    def test_both_phases_require_common_render_domain_evidence(self):
        for phase in ('B','C'):
            with self.subTest(phase=phase):
                run,freeze,*_=self.fixture(phase,domainproof=False)
                with self.assertRaisesRegex(ValueError,'compiler_render_domain_not_passed'):
                    self.read(run,phase,freeze)

    def test_both_phases_reject_failed_common_check_despite_other_proofs(self):
        for phase in ('B','C'):
            with self.subTest(phase=phase):
                run,freeze,file,quality,_=self.fixture(phase)
                quality['checks']['compiler_render_domain']=dict(supported=True,ok=False,failures=['wrong glyph'])
                self.write(file,quality)
                with self.assertRaisesRegex(ValueError,'compiler_render_domain_not_passed'):
                    self.read(run,phase,freeze)

    def test_both_phases_pass_the_same_common_render_domain_rule(self):
        for phase in ('B','C'):
            with self.subTest(phase=phase):
                run,freeze,*_=self.fixture(phase,textproof=phase=='C')
                self.assertEqual(self.read(run,phase,freeze)['1'*64]['result']['status'],'qualified')

    def test_v1_policy_cannot_be_relabelled_as_v2(self):
        run,freeze,file,quality,_=self.fixture('C')
        quality['policy']=quality['policy'].replace('_v2:','_v1:');self.write(file,quality)
        with self.assertRaisesRegex(ValueError,'quality_policy_mismatch'):self.read(run,'C',freeze)

    def test_existing_visual_source_and_font_checks_still_required(self):
        for key in ['visual','source','native_editing','fonts']:
            with self.subTest(check=key):
                # One fixture per test iteration under a fresh private directory.
                run,freeze,file,quality,_=self.fixture('C'+key)
                # fixture's phase must match C for its synthetic task.
                db=sqlite3.connect(run/'status.sqlite');task=json.loads(db.execute('select source from samples').fetchone()[0]);task['evaluation_phase']='candidate'
                payload=gate.base.raw(task);(run/'targets.jsonl').write_bytes(payload);freeze['input_sha256']=gate.base.sha(payload)
                db.execute('update samples set source=?',(json.dumps(task),));db.commit();db.close()
                quality['checks'][key]={};self.write(file,quality)
                with self.assertRaises(ValueError):self.read(run,'C',freeze)

    def test_actual_qualified_png_hash_is_still_checked(self):
        run,freeze,_,_,manifest=self.fixture('C')
        self.write(self.root/manifest['image_file'],b'changed bytes')
        with self.assertRaisesRegex(ValueError,'payload_missing_or_changed:image_file'):self.read(run,'C',freeze)


if __name__=='__main__':unittest.main()
