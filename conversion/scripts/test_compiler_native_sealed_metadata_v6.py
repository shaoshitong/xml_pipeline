"""Contract controls for complete canonical source/baseline and bounded SQL."""
import copy,json,sqlite3,types,unittest
from unittest.mock import patch
import compiler_native_materialized_text_node_iteration_pool_v6 as P
from test_compiler_validation_atomic_sealed_v1 import h

class SourceContract(unittest.TestCase):
    def fixture(self):
        source=dict(pair_sha256=h('id'),code_sha256=h('code'),image_sha256=h('image'),format='drawio',category='scientific_diagram',source='provider',annotation={'original_id':'real complete canonical object'},license='example')
        capture=dict(schema='native_original_payload_and_normalized_XML_snapshot_v1',id=source['pair_sha256'],source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],normalized_source_sha256=h('normalized'),input_source_code='clean/source.txt',input_reference_image='clean/reference.png',source_declared_page=[100,200])
        old=dict(code_sha256=h('baselinecode'),image_sha256=h('baselineimage'));job=[source['pair_sha256'],source['category'],source['format'],source['source'],json.dumps(source),'failed','',0,'time',json.dumps(old),'error',json.dumps({'source_code':'clean/source.txt'}),None]
        capture.update(input_record_sha256=P.sha(job[4].encode()),input_manifest_sha256=P.sha(job[11].encode()))
        guard={k:v for k,v in capture.items()if k in ('id','source_code_sha256','input_record_sha256','input_manifest_sha256')};guard.update(supported=True,policy=P.label_guard.POLICY,runtime_bundle_sha256=P.label_guard.RUNTIME_BUNDLE_SHA256,normal_source_conversion_called=False)
        request=dict(id=job[0],source=source,compiler_unit='unit',source_capture_snapshot=capture,source_dynamic_label_guard=guard,source_record_sha256=P.sha(job[9].encode()),baseline_code_sha256=old['code_sha256'],baseline_image_sha256=old['image_sha256'])
        return request,tuple(job)
    def verify(self,request,job):
        with patch.object(P.importlib,'import_module',return_value=types.SimpleNamespace(UNIT='unit')):return P.verify_request(request,job,{'pins':{}})
    def test_full_canonical_positive(self):
        r,j=self.fixture();self.assertTrue(self.verify(r,j))
    def test_scope_five_field_summary_rejected(self):
        r,j=self.fixture();r['source']={k:v for k,v in r['source'].items()if k in ('category','format','source','code_sha256','image_sha256')}
        with self.assertRaisesRegex(ValueError,'complete_canonical'):self.verify(r,j)
    def test_annotations_removed_rejected(self):
        r,j=self.fixture();r['source']=dict(r['source']);r['source'].pop('annotation')
        with self.assertRaises(ValueError):self.verify(r,j)
    def test_capture_full_source_hash_rejected(self):
        r,j=self.fixture();r['source_capture_snapshot']['input_record_sha256']=h('wrong')
        with self.assertRaisesRegex(ValueError,'snapshot_changed'):self.verify(r,j)
    def test_manifest_hash_rejected(self):
        r,j=self.fixture();r['source_capture_snapshot']['input_manifest_sha256']=h('wrong')
        with self.assertRaises(ValueError):self.verify(r,j)
    def test_baseline_changed_rejected(self):
        r,j=self.fixture();r['source_record_sha256']=h('wrong')
        with self.assertRaisesRegex(ValueError,'baseline'):self.verify(r,j)
    def test_baseline_asset_changed_rejected(self):
        r,j=self.fixture();r['baseline_image_sha256']=h('wrong')
        with self.assertRaises(ValueError):self.verify(r,j)
    def test_dynamic_guard_changed_rejected(self):
        r,j=self.fixture();r['source_dynamic_label_guard']['supported']=False
        with self.assertRaisesRegex(ValueError,'guard_changed'):self.verify(r,j)
    def test_partial_canonical_tuple_rejected(self):
        r,j=self.fixture()
        with self.assertRaises(ValueError):self.verify(r,j[:12])
    def test_stale_worker_metadata_does_not_change_source(self):
        r,j=self.fixture();j=list(j);j[12]=837387;self.assertTrue(self.verify(r,tuple(j)))
    def test_scope_query_is_only_bounded_in(self):
        class DB:
            def __init__(self):self.calls=[]
            def execute(self,sql,params):self.calls.append((sql,params));return [(x,)for x in params]
        db=DB();values=list(P.bounded_jobs(db,['ID'+str(i)for i in range(1101)]));self.assertEqual(len(values),1101);self.assertEqual(len(db.calls),3);self.assertTrue(all('where id in ('in sql and len(params)<=400 for sql,params in db.calls))

if __name__=='__main__':unittest.main(verbosity=2)
