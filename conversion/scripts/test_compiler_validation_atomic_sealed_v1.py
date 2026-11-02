"""Metadata-only controls, including real concurrent SQLite transactions."""
import hashlib,json,multiprocessing,sqlite3,tempfile,unittest
from pathlib import Path
import compiler_validation_identity_alias_v1 as A
import compiler_validation_reservation_v2 as R
import compiler_validation_sealed_cohort_v1 as S

def h(x):return hashlib.sha256(str(x).encode()).hexdigest()
def row(i):return dict(id=h('id'+str(i)),source=dict(code_sha256=h('code'+str(i)),image_sha256=h('image'+str(i))),audit_cluster='family:'+str(i),cluster_keys=['family:'+str(i)])
def bind(selected,selection):return dict(selected_manifest_sha256=h(json.dumps(selected,sort_keys=True)),protocol_sha256=h(json.dumps(selection,sort_keys=True)))
def reserve(db,selector,prefix,callback=bind):return R.reserve_fresh(db,selector,bind_selected=callback,audit='.',run_prefix=prefix,implementation_identity_sha256=h('i'),phase_runs={'B':prefix+'B','C':prefix+'C'},controls_proof_sha256=h('c'))
def static(db,rows,prefix):return reserve(db,lambda *_:dict(selected=rows),prefix)
def legacy(db,kind,value):
    con=R._open(db);con.execute('insert into reservations values(?,?,?,?,?)',('old',h('old'),'old','reserved','{}'));con.execute('insert into reservation_keys values(?,?,?)',(kind,value,'old'));con.close()
def components():
    requests=[row(i)for i in range(4)]
    records=[dict(request=requests[0],keys=['a'],known=True),dict(request=requests[1],keys=['a','b'],known=True),dict(request=requests[2],keys=['b'],known=True),dict(request=requests[3],keys=['d'],known=True)]
    return records,requests

def worker(db,groups,requests,prefix,q):
    try:
        result=reserve(db,lambda keys,_:S.select(groups,requests,keys,seed='concurrent',limit=1),prefix);q.put(('ok',result['selected'][0]['id']))
    except BaseException as e:q.put(('error',str(e)))

class Aliases(unittest.TestCase):
    def test_code(self):self.assertEqual(A.normalize_pair('hard_cluster','exact_original_code:'+h('x')),('code',h('x')))
    def test_image(self):self.assertEqual(A.normalize_pair('audit_cluster','image:'+h('x')),('image',h('x')))
    def test_id(self):self.assertEqual(A.normalize_pair('hard_cluster','id:'+h('x')),('id',h('x')))
    def test_wrapped(self):self.assertEqual(A.normalize_pair('hard_cluster','audit_cluster:hard_cluster:exact_original_code:'+h('x')),('code',h('x')))
    def test_case(self):self.assertEqual(A.normalize_pair('code',h('x').upper()),('code',h('x')))
    def test_cluster(self):self.assertEqual(A.normalize_pair('audit_cluster','opaque:family'),A.normalize_pair('hard_cluster','opaque:family'))
    def test_bare_sha_opaque(self):self.assertEqual(A.normalize_pair('hard_cluster',h('x')),('cluster',h('x')))
    def test_unknown_prefix_opaque(self):self.assertEqual(A.normalize_pair('hard_cluster','novel:'+h('x')),('cluster','novel:'+h('x')))
    def test_bad_typed(self):
        with self.assertRaises(ValueError):A.normalize_pair('id','bad')
    def test_conflicting_typed(self):
        with self.assertRaises(ValueError):A.normalize_pair('image','code:'+h('x'))
    def test_legacy_aliases(self):
        r=row(1);keys=A.storage_keys([r]);self.assertIn(('hard_cluster','exact_original_code:'+r['source']['code_sha256']),keys);self.assertIn(('audit_cluster','family:1'),keys)

class Closure(unittest.TestCase):
    def test_foreign_transitive(self):
        records,requests=components();groups=S.build_components(records,{requests[i]['id']for i in [0,2,3]});self.assertEqual(sorted(len(g['component_all_ids'])for g in groups['components']),[1,3])
    def test_foreign_id_excludes(self):
        records,requests=components();groups=S.build_components(records,{r['id']for r in requests})['components'];out=S.select(groups,requests,{('id',requests[1]['id'])},seed='x');self.assertEqual([r['id']for r in out['selected']],[requests[3]['id']])
    def test_foreign_code_excludes(self):
        records,requests=components();groups=S.build_components(records,{r['id']for r in requests})['components'];self.assertEqual(len(S.select(groups,requests,{('code',requests[1]['source']['code_sha256'])},seed='x')['selected']),1)
    def test_unknown_bridge_excludes(self):
        records,requests=components();records[1]['known']=False;groups=S.build_components(records,{r['id']for r in requests})['components'];out=S.select(groups,requests,set(),seed='x');self.assertEqual(len(out['selected']),1);self.assertEqual(out['unknown_components'],1)
    def test_full_keys_remain(self):
        records,requests=components();groups=S.build_components(records,{r['id']for r in requests})['components'];out=S.select(groups,requests,set(),seed='x');r=next(r for r in out['selected']if r['id']!=requests[3]['id']);self.assertIn(('id',requests[1]['id']),A.request_keys(r))
    def test_deterministic_once_per_component(self):
        records,requests=components();groups=S.build_components(records,{r['id']for r in requests})['components'];a=S.select(groups,requests,set(),seed='x');b=S.select(groups,list(reversed(requests)),set(),seed='x');self.assertEqual(a,b);self.assertEqual(len(a['selected']),2);self.assertTrue(a['all_remaining_observed_families_selected'])
    def test_missing_target(self):
        with self.assertRaises(ValueError):S.build_components([],{'missing'})
    def test_duplicate(self):
        records,_=components()
        with self.assertRaises(ValueError):S.build_components([records[0],records[0]],set())
    def test_missing_candidate(self):
        with self.assertRaises(ValueError):S.select([],[row(1)],set(),seed='x')

class Transactions(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'registry.sqlite'
    def tearDown(self):self.tmp.cleanup()
    def counts(self):
        con=R._open(self.db);out=tuple(con.execute('select count(*)from '+table).fetchone()[0]for table in ['reservations','reservation_keys']);con.close();return out
    def test_old_hard_blocks_typed_rollback(self):
        r=row(1);legacy(self.db,'hard_cluster','exact_original_code:'+r['source']['code_sha256']);before=self.counts()
        with self.assertRaises(R.ReservationConflict):static(self.db,[r],'new')
        self.assertEqual(self.counts(),before)
    def test_old_audit_blocks_hard(self):
        legacy(self.db,'audit_cluster','family:1')
        with self.assertRaises(R.ReservationConflict):static(self.db,[row(1)],'new')
    def test_callback_failure_rolls_back(self):
        def bad(*_):raise RuntimeError('bad binding')
        with self.assertRaises(RuntimeError):reserve(self.db,lambda *_:dict(selected=[row(1)]),'new',bad)
        self.assertEqual(self.counts(),(0,0))
    def test_duplicate_alias_rejected(self):
        a,b=row(1),row(2);b['cluster_keys']=['code:'+a['source']['code_sha256']]
        with self.assertRaises(ValueError):static(self.db,[a,b],'new')
        self.assertEqual(self.counts(),(0,0))
    def test_binding_nonhex_rejected(self):
        with self.assertRaises(ValueError):reserve(self.db,lambda *_:dict(selected=[row(1)]),'new',lambda *_:dict(selected_manifest_sha256='x'*64,protocol_sha256=h('x')))
        self.assertEqual(self.counts(),(0,0))
    def test_prefix_never_reused(self):
        static(self.db,[row(1)],'new')
        with self.assertRaises(ValueError):static(self.db,[row(2)],'new')
        self.assertEqual(self.counts()[0],1)
    def test_precommit_race_reselect(self):
        records,requests=components();groups=S.build_components(records,{r['id']for r in requests})['components'];first=S.select(groups,requests,set(),seed='x',limit=1);static(self.db,first['selected'],'other');new=reserve(self.db,lambda keys,_:S.select(groups,requests,keys,seed='x',limit=1),'new');self.assertNotEqual(new['selected'][0]['id'],first['selected'][0]['id']);self.assertEqual(new['reservation']['selection_attempts'],1)
    def test_actual_two_process_transactions(self):
        R._open(self.db).close();requests=[row(i)for i in range(3)];groups=S.build_components([dict(request=r,keys=r['cluster_keys'],known=True)for r in requests],{r['id']for r in requests})['components'];ctx=multiprocessing.get_context('spawn');queue=ctx.Queue();children=[ctx.Process(target=worker,args=(str(self.db),groups,requests,'worker'+str(i),queue))for i in range(2)]
        for p in children:p.start()
        values=[queue.get(timeout=20)for _ in children]
        for p in children:p.join(20);self.assertEqual(p.exitcode,0)
        self.assertTrue(all(v[0]=='ok'for v in values),values);self.assertEqual(len({v[1]for v in values}),2);self.assertEqual(self.counts()[0],2)

if __name__=='__main__':unittest.main(verbosity=2)
