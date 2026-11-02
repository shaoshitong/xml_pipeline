import base64,hashlib,importlib.util,json,sqlite3,tempfile,unittest,urllib.parse,zlib
from pathlib import Path
spec=importlib.util.spec_from_file_location('sampler',Path(__file__).with_name('round2_heldout_select_v1.py'));s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
def xml(a='a',b='b',label='Hello',x=1,target=None):
 return f'<mxGraphModel pageWidth="100" pageHeight="100"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="{a}" parent="1" vertex="1" value="{label}" style="shape=rect;"><mxGeometry x="{x}" y="2" width="30" height="20"/></mxCell><mxCell id="{b}" parent="1" vertex="1" value="World"/><mxCell id="edge" parent="1" edge="1" source="{a}" target="{target or b}"/></root></mxGraphModel>'
class Fingerprints(unittest.TestCase):
 def fp(self,c,f):return s.fingerprint(c,f)['template_family']
 def test_xml_normalizes_ids_text_numbers(self):self.assertEqual(self.fp(xml(),'drawio'),self.fp(xml('X','Y','Changed',99),'drawio'))
 def test_xml_preserves_edge_topology(self):self.assertNotEqual(self.fp(xml(),'drawio'),self.fp(xml(target='a'),'drawio'))
 def test_xml_preserves_shapes(self):self.assertNotEqual(self.fp(xml(),'drawio'),self.fp(xml().replace('shape=rect','shape=ellipse'),'drawio'))
 def test_compressed_drawio_same_as_uncompressed_page(self):
  source=xml();c=zlib.compressobj(wbits=-15);payload=c.compress(urllib.parse.quote(source).encode())+c.flush();encoded=base64.b64encode(payload).decode()
  self.assertEqual(self.fp('<mxfile><diagram id="p">'+encoded+'</diagram></mxfile>','drawio'),self.fp('<mxfile><diagram id="x">'+source+'</diagram></mxfile>','drawio'))
 def test_svg_numbers_text_changed_not_family(self):
  a='<svg><path d="M1,2L3,4"/><text x="3">Alice</text></svg>';b='<svg><path d="M8,9L4,7"/><text x="9">Bob</text></svg>'
  self.assertEqual(self.fp(a,'svg'),self.fp(b,'svg'));self.assertNotEqual(self.fp(a,'svg'),self.fp(a.replace('L3,4','C3,4,5,6,7,8'),'svg'))
 def test_html_labels_dimensions_ids(self):
  a='<html><style>#first{width:20px}.wide{padding:10px}</style><div id="first" class="wide">Hello</div></html>'
  b='<html><style>#second{width:50px}.narrow{padding:30px}</style><div id="second" class="narrow">Bye</div></html>'
  self.assertEqual(self.fp(a,'html'),self.fp(b,'html'))
 def test_python_constants_local_names(self):self.assertEqual(self.fp('x=[1,2]\nprint(x)','python'),self.fp('different=[4,7]\nprint(different)','python'))
 def test_python_graphviz_ids_preserve_topology(self):
  a="from graphviz import Digraph\ng=Digraph()\ng.node('a',label='Alpha')\ng.node('b',label='Beta')\ng.edge('a','b')"
  b=a.replace("'a'","'X'").replace("'b'","'Y'").replace('Alpha','Other')
  self.assertEqual(self.fp(a,'python'),self.fp(b,'python'));self.assertNotEqual(self.fp(a,'python'),self.fp(a.replace("g.edge('a','b')","g.edge('a','a')"),'python'))
 def test_python_shape_keyword_preserved(self):self.assertNotEqual(self.fp("g.node('a',shape='box')",'python'),self.fp("g.node('a',shape='ellipse')",'python'))
 def test_embedded_dot_topology(self):
  a="dot='digraph G { a -> b; b -> c; }'";b="dot='digraph H { X -> Y; Y -> Z; }'";c="dot='digraph G { a -> b; a -> c; }'"
  self.assertEqual(self.fp(a,'python'),self.fp(b,'python'));self.assertNotEqual(self.fp(a,'python'),self.fp(c,'python'))
 def test_dynamic_graph_unknown(self):self.assertIsNone(self.fp("dot=f'digraph G {{ {node} -> b; }}'",'python'))
 def test_invalid_sources_unknown(self):
  self.assertIsNone(self.fp('<not-closed','svg'));self.assertIsNone(self.fp('not valid Python !','python'));self.assertIsNone(self.fp('random plain text','mermaid'))
 def test_reservoir_order_invariant(self):
  rows=[{'id':str(i),'stratum':'svg|source'} for i in range(100)]
  self.assertEqual(s.reservoir(rows,10),s.reservoir(list(reversed(rows)),10));self.assertEqual(len(s.reservoir(rows,10)['svg|source']),10)
 def test_provider_balance_and_one_per_family(self):
  rows=[{'id':str(i),'stratum':'x','provider':'A' if i<6 else 'B','template_family':'f'+str(i//2)} for i in range(10)]
  chosen=s.balanced_groups(rows,4);self.assertEqual(len({r['template_family'] for r in chosen}),len(chosen));self.assertEqual({r['provider'] for r in chosen},{'A','B'})
 def test_unknown_source_file_does_not_get_identity_from_hash(self):
  with tempfile.TemporaryDirectory() as t:self.assertIsNone(s.source_fingerprint(t,'a'*64,'b'*64,'svg')['template_family'])
 def test_authoritative_source_locator_fallback(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);p=root/'clean/original.html';p.parent.mkdir();p.write_text('<html><body><div>Hello</div></body></html>');identifier='a'*64;h=s.sha(p.read_bytes());d=sqlite3.connect(':memory:');d.execute('create table jobs(id text,input_manifest text)');d.execute('insert into jobs values(?,?)',(identifier,json.dumps({'id':identifier,'code_sha256':h,'source_code':'clean/original.html'})))
   r=s.source_fingerprint(root,identifier,h,'html',d);self.assertIsNotNone(r['template_family']);self.assertEqual(r['source_locator_resolution'],'authoritative_input_manifest_verified');self.assertNotIn('template_reason',r);d.close()
 def test_wrong_authoritative_hash_is_unknown(self):
  with tempfile.TemporaryDirectory() as t:
   d=sqlite3.connect(':memory:');d.execute('create table jobs(id text,input_manifest text)');d.execute('insert into jobs values(?,?)',('a'*64,json.dumps({'id':'a'*64,'code_sha256':'wrong','source_code':'clean/original.html'})))
   r=s.source_fingerprint(t,'a'*64,'expected','html',d);self.assertIsNone(r['template_family']);self.assertIn('identity_mismatch',r['template_reason']);d.close()

class EndToEnd(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=tempfile.TemporaryDirectory();cls.order=Path(cls.data.name)/'order.jsonl'
  with cls.order.open('w') as f:
   for i in range(1,131905):f.write(json.dumps({'id':f'{i:064x}','seq':i,'format':'drawio','category':'scientific_diagram','source_code_sha256':'placeholder','source_image_sha256':s.sha(str(i).encode())})+'\n')
 @classmethod
 def tearDownClass(cls):cls.data.cleanup()
 def setup_fixture(self,root):
  work=root/'conversion';work.mkdir();first=root/'release/fixed_batch_v1/initial_screen_20261031_1717';first.mkdir(parents=True);second=root/'release/round2_fixed_v1/test';second.mkdir(parents=True)
  order=[json.loads(x) for x in self.order.read_text().splitlines()];codes={1:xml(),2:xml('X','Y','Other',20),3:xml().replace('shape=rect','shape=ellipse'),4:xml().replace('shape=rect','shape=triangle')}
  jobs=sqlite3.connect(work/'jobs.sqlite');jobs.execute('create table jobs(id text primary key,source text,input_record text)')
  d=sqlite3.connect(second/'status.sqlite');d.execute('create table samples(seq integer primary key,id text,source text,first_result text,initial_actions text,attempts integer,status text)')
  for i,code in codes.items():
   identifier=f'{i:064x}';source={'id':identifier,'format':'drawio','category':'scientific_diagram','code_sha256':s.sha(code.encode()),'image_sha256':s.sha(str(i).encode())};order[i-1]['source_code_sha256']=source['code_sha256'];p=work/'inputs'/identifier[:2]/identifier;p.mkdir(parents=True);(p/'source.txt').write_text(code)
   canonical={'pair_sha256':identifier,'source':'provider'+str(i%2),'format':'drawio','category':'scientific_diagram','code_sha256':source['code_sha256'],'image_sha256':source['image_sha256']}
   jobs.execute('insert into jobs values(?,?,?)',(identifier,canonical['source'],json.dumps(canonical)))
   d.execute('insert into samples values(?,?,?,?,?,?,?)',(i,identifier,json.dumps(source),json.dumps({'id':identifier,'status':'abandoned','seq':i}),json.dumps(['font']),1 if i==1 else 0,'abandoned' if i==1 else 'queued'))
  jobs.commit();jobs.close();d.commit();d.close();(second/'control.json').write_text('{"stop_dispatch":true}');(second/'launch_receipt.json').write_text('{"pins":{}}')
  with (first/'input_order.jsonl').open('w') as f:
   for r in order:f.write(json.dumps(r)+'\n')
  return second
 def test_freezes_exclusions_and_filters_development_family(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);second=self.setup_fixture(root);before=(root/'conversion/jobs.sqlite').read_bytes();out=root/'release/round2_heldout_v1/test'
   result=s.select(root,second,out,2,3);rows=[json.loads(x) for x in (out/'manifest.jsonl').read_text().splitlines()]
   self.assertEqual({r['id'] for r in rows},{f'{3:064x}',f'{4:064x}'});self.assertEqual(before,(root/'conversion/jobs.sqlite').read_bytes());self.assertTrue(result['sampling_only_no_results_viewed']);self.assertEqual(result['strata']['drawio|font']['development_family_overlap'],1)
   for r in rows:self.assertIn('first_result',r);self.assertIn('provider',r);self.assertIn('template_family',r)
   with self.assertRaises(ValueError):s.select(root,second,out,2,3)
 def test_unrecorded_smoke_directory_excluded(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);second=self.setup_fixture(root);p=root/'conversion/round2_custom_smoke/run'/f'{4:064x}';p.mkdir(parents=True)
   out=root/'release/round2_heldout_v1/test';r=s.select(root,second,out,30,150);rows=[json.loads(x) for x in (out/'manifest.jsonl').read_text().splitlines()]
   self.assertEqual([x['id'] for x in rows],[f'{3:064x}']);self.assertTrue(r['strata']['drawio|font']['low_evidence'])
 def test_inflight_and_not_stopped_refused(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);second=self.setup_fixture(root);(second/'control.json').write_text('{"stop_dispatch":false}')
   with self.assertRaises(ValueError):s.select(root,second,root/'release/round2_heldout_v1/a')
   (second/'control.json').write_text('{"stop_dispatch":true}');d=sqlite3.connect(second/'status.sqlite');d.execute('update samples set status="running" where seq=1');d.commit();d.close()
   with self.assertRaises(ValueError):s.select(root,second,root/'release/round2_heldout_v1/b')
 def test_metadata_correction_preserves_committed_non_html_ids(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);second=self.setup_fixture(root);old=root/'release/round2_heldout_v1/v1';s.select(root,second,old,2,3);old_sha=s.sha((old/'manifest.jsonl').read_bytes());actual=second.parent/'repair_pass_20261101_0627';actual.mkdir();(actual/'status.sqlite').write_bytes((second/'status.sqlite').read_bytes())
   new=root/'release/round2_heldout_v1/v2';r=s.correct_frozen_locators(root,old,new);self.assertEqual(old_sha,s.sha((old/'manifest.jsonl').read_bytes()));self.assertEqual({json.loads(x)['id'] for x in (old/'manifest.jsonl').read_text().splitlines()},{json.loads(x)['id'] for x in (new/'manifest.jsonl').read_text().splitlines()});self.assertFalse(r['automatic_rollout_permitted']);self.assertTrue(r['requires_provenance_or_cluster_audit_before_rollout'])
if __name__=='__main__':unittest.main()
