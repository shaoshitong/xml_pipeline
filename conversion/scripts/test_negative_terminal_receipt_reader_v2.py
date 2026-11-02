import copy,json,os,stat,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import negative_terminal_receipt_reader_v2 as r


class ReceiptReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.id='a'*64;self.source='b'*64;self.image='c'*64;self.pins={version:{'writer_sha256':str(version)*64,'planner_sha256':'f'*64} for version in (1,2)}
    def fixture(self,version=2,document_change=None,marker_change=None,evidence_change=None):
        spec=r.VERSIONS[version];prior={'category':'scientific_diagram','format':'tikz','source_code_hash':self.source,'source_image_hash':self.image,'status':'pending','reason':None,'record':None,'updated_at':'prior'};evidence={'id':self.id,'source_code_sha256':self.source,'source_image_sha256':self.image,'code_sha256':'d'*64,'image_sha256':'e'*64,'reason_code':'verified_program_support_limit','reason_detail':'Keep original source and candidate for later deterministic recovery.','deterministic_recovery_permitted':True,'abandonment_is_not_conversion_success':True,'new_model_calls':0};plan={'id':self.id,'evidence':copy.deepcopy(evidence),'cas':{'registry_snapshot_sha256':r.json_sha(tuple(prior[key] for key in r.REGISTRY_COLUMNS)),'active_policy':'quality-current'}};document={'version':version,'created_at':'2026-10-31T00:00:00Z','writer_policy':spec['policy'],**self.pins[version],'plan':plan,'plan_sha256':r.sha(r.canonical(plan)),'prior_outcome':prior,'historical_terminal_receipt_owners':[],'scope':'Current verified program only.','deterministic_recovery_permitted':True,'abandonment_is_not_conversion_success':True,'new_model_calls':0}
        if version==2:document.update(commit_nonce='a1'*16,preparation={'db_cas_snapshots':{'jobs':[]},'file_witnesses':{}})
        if document_change:document_change(document)
        payload=r.canonical(document);digest=r.sha(payload);relative=str(Path(spec['directory'])/self.id/('decision.'+digest+'.json'));path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():path.chmod(0o600)
        path.write_bytes(payload);path.chmod(0o444);receipt={'file':relative,'sha256':digest,'plan_sha256':document['plan_sha256'],'created_at':document['created_at']}
        marker={'policy':spec['policy'],'decision':receipt,'prior_registry_snapshot_sha256':plan['cas']['registry_snapshot_sha256'],'active_quality_policy':plan['cas']['active_policy'],'scope':'Current verified program only.'}
        if version==2:receipt['commit_nonce']=document['commit_nonce'];marker['commit_nonce']=document['commit_nonce']
        if marker_change:marker_change(marker)
        evidence[spec['marker']]=marker
        if evidence_change:evidence_change(evidence)
        row=(self.id,'scientific_diagram','tikz',self.source,self.image,'current_frozen_program:'+evidence['reason_code']+'; '+evidence['reason_detail'],json.dumps(evidence,ensure_ascii=False));return row,path,document
    def validate(self,row):return r.validate_outcome(row,self.root,self.pins)
    def test_v1_valid_receipt_and_exact_existing_export_shape(self):
        row,path,document=self.fixture(1);result=self.validate(row);self.assertEqual(result['kind'],'program_terminal_v1');self.assertTrue(result['receipt_verified']);manifest=r.manifest_row(row,self.root,self.pins);self.assertEqual(set(manifest),{'id','category','source_format','status','reason','source_code_sha256','source_image_sha256','decision'});self.assertEqual(manifest['decision'],json.loads(row[-1]));self.assertFalse(result['accepted'])
    def test_v2_valid_author_nonce_and_preparation(self):
        row,_,_=self.fixture();result=self.validate(row);self.assertEqual(result['version'],2);self.assertEqual(result['commit_nonce'],'a1'*16);self.assertTrue(result['deterministic_recovery_permitted'])
    def test_legacy_only_requires_generic_identity_and_explicit_reason(self):
        row=(self.id,'poster','html',self.source,self.image,'explicit prior decision',json.dumps({'id':self.id,'source_code_sha256':self.source,'source_image_sha256':self.image}));result=r.validate_outcome(row,self.root,pins={});self.assertEqual(result['kind'],'legacy_explicit');self.assertFalse(result['receipt_verified'])
    def test_wrong_writer_or_planner_identity_refused(self):
        for field in ['writer_sha256','planner_sha256']:
            row,_,_=self.fixture(document_change=lambda d:d.update({field:'0'*64}))
            with self.assertRaises(r.Refused):self.validate(row)
    def test_version_and_policy_impersonation_refused(self):
        for change in [lambda d:d.update(version=1),lambda d:d.update(version=True),lambda d:d.update(writer_policy=r.VERSIONS[1]['policy'])]:
            row,_,_=self.fixture(document_change=change)
            with self.assertRaises(r.Refused):self.validate(row)
    def test_marker_policy_and_active_quality_mismatch_refused(self):
        for change in [lambda m:m.update(policy='different'),lambda m:m.update(active_quality_policy='stale')]:
            row,_,_=self.fixture(marker_change=change)
            with self.assertRaises(r.Refused):self.validate(row)
    def test_v2_three_nonce_locations_must_agree(self):
        for change in [lambda m:m.update(commit_nonce='b2'*16),lambda m:m['decision'].update(commit_nonce='b2'*16),lambda m:m.pop('commit_nonce')]:
            row,_,_=self.fixture(marker_change=change)
            with self.assertRaises(r.Refused):self.validate(row)
        row,_,_=self.fixture(document_change=lambda d:d.update(commit_nonce='bad'))
        with self.assertRaises(r.Refused):self.validate(row)
    def test_v2_preparation_cannot_be_missing(self):
        for change in [lambda d:d.pop('preparation'),lambda d:d.update(preparation={}),lambda d:d['preparation'].update(db_cas_snapshots=[])]:
            row,_,_=self.fixture(document_change=change)
            with self.assertRaises(r.Refused):self.validate(row)
    def test_outcome_extra_content_or_source_rewrite_refused(self):
        for change in [lambda e:e.update(code_sha256='0'*64),lambda e:e.update(unverified_new_field=True),lambda e:e.update(source_code_sha256='0'*64)]:
            row,_,_=self.fixture(evidence_change=change)
            with self.assertRaises(r.Refused):self.validate(row)
    def test_reason_text_must_match_complete_decision(self):
        row,_,_=self.fixture();row=list(row);row[-2]='intrinsically impossible'
        with self.assertRaises(r.Refused):self.validate(row)
    def test_prior_outcome_or_registry_hash_change_refused(self):
        for change in [lambda d:d['prior_outcome'].update(updated_at='changed'),lambda d:d['prior_outcome'].update(status='qualified')]:
            row,_,_=self.fixture(document_change=change)
            with self.assertRaises(r.Refused):self.validate(row)
    def test_plan_digest_and_creation_timestamp_refused(self):
        for change in [lambda m:m['decision'].update(plan_sha256='0'*64),lambda m:m['decision'].update(created_at='changed')]:
            row,_,_=self.fixture(marker_change=change)
            with self.assertRaises(r.Refused):self.validate(row)
    def test_unknown_or_ambiguous_markers_are_not_legacy(self):
        for change in [lambda e:e.update(program_terminal_outcome_v3={}),lambda e:e.update(program_terminal_outcome_v1={})]:
            row,_,_=self.fixture(evidence_change=change)
            with self.assertRaises(r.Refused):self.validate(row)
    def test_digest_corruption_or_noncanonical_json_refused(self):
        row,path,_=self.fixture();path.chmod(0o644);path.write_bytes(b'{}\n');path.chmod(0o444)
        with self.assertRaises(r.Refused):self.validate(row)
        row,path,document=self.fixture();payload=json.dumps(document,indent=2).encode();digest=r.sha(payload);newpath=path.with_name('decision.'+digest+'.json');newpath.write_bytes(payload);newpath.chmod(0o444);e=json.loads(row[-1]);e['program_terminal_outcome_v2']['decision'].update(file=str(newpath.relative_to(self.root)),sha256=digest);row=(*row[:-1],json.dumps(e))
        with self.assertRaises(r.Refused):self.validate(row)
    def test_writeable_receipt_refused(self):
        row,path,_=self.fixture();path.chmod(0o644)
        with self.assertRaises(r.Refused):self.validate(row)
    def test_symlink_final_or_intermediate_directory_refused(self):
        row,path,_=self.fixture();data=path.read_bytes();path.chmod(0o644);path.unlink();target=self.root/'other.json';target.write_bytes(data);target.chmod(0o444);path.symlink_to(target)
        with self.assertRaises((r.Refused,OSError)):self.validate(row)
        path.unlink();path.write_bytes(data);path.chmod(0o444);moved=path.parent.with_name('alternate');path.parent.rename(moved);path.parent.symlink_to(moved,target_is_directory=True)
        with self.assertRaises((r.Refused,OSError)):self.validate(row)
    def test_default_pins_match_actual_canonical_source_and_explicit_historical_pins_work(self):
        scripts=self.root/'conversion/scripts';scripts.mkdir(parents=True);writer=b'writer v2';planner=b'frozen planner';(scripts/r.VERSIONS[2]['writer']).write_bytes(writer);(scripts/r.PLANNER).write_bytes(planner);self.pins[2]={'writer_sha256':r.sha(writer),'planner_sha256':r.sha(planner)};row,_,_=self.fixture();self.assertTrue(r.validate_outcome(row,self.root)['receipt_verified']);(scripts/r.VERSIONS[2]['writer']).write_bytes(b'later writer revision')
        with self.assertRaises(r.Refused):r.validate_outcome(row,self.root)
        self.assertTrue(self.validate(row)['receipt_verified'])
    def test_explicit_missing_pins_fail_closed(self):
        row,_,_=self.fixture()
        with self.assertRaises(r.Refused):r.validate_outcome(row,self.root,{})
    def test_validation_changes_no_files_and_accepts_mapping_projection(self):
        row,_,_=self.fixture();before={str(path):(path.stat().st_ino,path.stat().st_size,path.stat().st_mtime_ns,path.stat().st_ctime_ns,path.stat().st_mode,path.read_bytes()) for path in self.root.rglob('*') if path.is_file()};mapping=dict(zip(r.OUTCOME_COLUMNS,row));mapping['status']='abandoned';self.assertTrue(self.validate(mapping)['receipt_verified']);after={str(path):(path.stat().st_ino,path.stat().st_size,path.stat().st_mtime_ns,path.stat().st_ctime_ns,path.stat().st_mode,path.read_bytes()) for path in self.root.rglob('*') if path.is_file()};self.assertEqual(after,before);mapping['status']='qualified'
        with self.assertRaises(r.Refused):self.validate(mapping)
    def test_actual_frozen_v1_writer_fixture_is_compatible(self):
        import test_program_terminal_outcomes_v1 as fixtures
        import program_terminal_outcomes_v1 as writer
        fixture=fixtures.WriterTests('test_publish_only_changes_outcome_with_complete_immutable_replay_evidence');fixture.setUp()
        try:
            result=writer.apply(fixture.db,fixture.plan(),fixture.config,True);self.assertTrue(result['applied'],result);row=fixture.db.execute('SELECT id,category,format,source_code_hash,source_image_hash,reason,record FROM processing_outcomes_v2').fetchone();pins={1:{'writer_sha256':r.sha(Path(writer.__file__).read_bytes()),'planner_sha256':r.sha(Path(writer.planner.__file__).read_bytes())}};self.assertTrue(r.validate_outcome(row,fixture.root,pins)['receipt_verified'])
        finally:fixture.doCleanups()
    def test_actual_new_v2_writer_fixture_is_compatible(self):
        import test_bounded_program_terminal_planner_v1 as fixtures
        import program_terminal_outcomes_v2 as writer
        fixture=fixtures.Guards('test_plan_is_readonly_and_revalidates');fixture.setUp();original=writer.planner.prepare
        try:
            plan=original(fixture.db,fixture.identifier,fixture.config,terminal_verifier=fixture.stub);pins={2:{'writer_sha256':r.sha(Path(writer.__file__).read_bytes()),'planner_sha256':r.sha(Path(writer.planner.__file__).read_bytes())}}
            with patch.object(writer.planner,'prepare',side_effect=lambda db,identifier,config:original(db,identifier,config,terminal_verifier=fixture.stub)):result=writer.apply(fixture.db,plan,fixture.config,True)
            self.assertTrue(result['applied'],result);row=fixture.db.execute('SELECT id,category,format,source_code_hash,source_image_hash,reason,record FROM processing_outcomes_v2').fetchone();validated=r.validate_outcome(row,fixture.root,pins);self.assertTrue(validated['receipt_verified']);self.assertEqual(validated['commit_nonce'],result['commit_nonce']);self.assertEqual(r.manifest_row(row,fixture.root,pins)['decision'],json.loads(row[-1]));document=json.loads((fixture.root/result['decision']['file']).read_text());self.assertEqual(document['writer_policy'],writer.POLICY);self.assertEqual(document['writer_sha256'],pins[2]['writer_sha256']);self.assertIn('jobs',document['preparation']['db_cas_snapshots']['tables'])
        finally:fixture.doCleanups()


if __name__=='__main__':unittest.main()
