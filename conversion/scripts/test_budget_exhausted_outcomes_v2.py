import json,sqlite3,unittest
import budget_exhausted_outcomes_v2 as m


class ReasonedAbandonment(unittest.TestCase):
    def setUp(self):
        self.d=sqlite3.connect(':memory:');self.addCleanup(self.d.close)
        self.d.executescript('''create table jobs(id primary key,state,worker_pid,input_record,output_record,updated_at);
        create table processing_outcomes_v2(id primary key,status,source_code_hash,source_image_hash,reason,record,updated_at);
        create table auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record);''')
        self.r={'id':'one','source_pair_sha256':'one','source_code_sha256':'a'*64,'source_image_sha256':'b'*64,'code_file':'clean/a.drawio','code_sha256':'c'*64,'image_file':'clean/a.png','image_sha256':'d'*64}
        self.d.execute('insert into jobs values(?,?,?,?,?,?)',('one','needs_quality_repair',None,json.dumps({'code_sha256':'a'*64,'image_sha256':'b'*64}),json.dumps(self.r),'old'))
        self.d.execute('insert into processing_outcomes_v2 values(?,?,?,?,?,?,?)',('one','pending','a'*64,'b'*64,None,None,'old'))
        report={'id':'one','input_code_sha256':'c'*64,'input_image_sha256':'d'*64,'source_code_sha256':'a'*64,'source_image_sha256':'b'*64,'accepted':False,'failures':['raster_anomaly: local_text_failure']}
        self.d.execute('insert into auto_quality_audits_v1 values(?,?,?,?,?,?)',('one','c'*64,'d'*64,'current','repair_required',json.dumps(report)))
        self.d.commit()
        self.budget={'original_id':'one','coverage_complete_for_id':True,'confirmed_calls':6,'remaining_calls':0,'history_snapshot_id':'frozen','unknown_reservations':0}
    def plan(self):return m.prepare(self.d,'one','current',lambda _:self.budget)
    def test_records_reason_without_changing_job_or_files(self):
        before=self.d.execute('select * from jobs').fetchall();p,why=self.plan();self.assertIsNone(why)
        self.assertEqual(m.apply(self.d,p,True),'abandoned')
        status,reason,raw=self.d.execute('select status,reason,record from processing_outcomes_v2').fetchone()
        self.assertEqual(status,'abandoned');self.assertTrue(reason);self.assertEqual(json.loads(raw)['confirmed_model_calls'],6)
        self.assertEqual(self.d.execute('select * from jobs').fetchall(),before)
    def test_stale_candidate_never_abandoned(self):
        p,_=self.plan();self.d.execute("update jobs set output_record='changed'");self.d.commit()
        self.assertEqual(m.apply(self.d,p,True),'stale_revision')
        self.assertEqual(self.d.execute('select status from processing_outcomes_v2').fetchone()[0],'pending')
    def test_newly_qualified_result_never_abandoned(self):
        self.d.execute("update jobs set state='accepted'");self.d.commit();self.assertIsNone(self.plan()[0])
    def test_busy_result_never_abandoned(self):
        self.d.execute('update jobs set worker_pid=123');self.d.commit();self.assertIsNone(self.plan()[0])
    def test_unknown_reservations_not_claimed_as_confirmed_calls(self):
        self.budget.update(confirmed_calls=1,unknown_reservations=1);self.assertIsNone(self.plan()[0])
    def test_mismatched_or_missing_current_audit_remains_pending(self):
        self.d.execute("update auto_quality_audits_v1 set policy='old'");self.d.commit();self.assertIsNone(self.plan()[0])
    def test_dry_run_does_not_write_outcome(self):
        p,_=self.plan();self.assertEqual(m.apply(self.d,p,False),'validated_abandonment_plan')
        self.assertEqual(self.d.execute('select status from processing_outcomes_v2').fetchone()[0],'pending')
    def test_idempotent_decision_does_not_duplicate_or_change_reason(self):
        p,_=self.plan();m.apply(self.d,p,True);p,_=self.plan();self.assertEqual(m.apply(self.d,p,True),'already_recorded')


if __name__=='__main__':unittest.main()
