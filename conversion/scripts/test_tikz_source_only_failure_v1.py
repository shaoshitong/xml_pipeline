import ast,copy,json,tempfile,types,unittest,sys
from pathlib import Path
from unittest.mock import patch
import tikz_source_only_failure_v1 as m

class PureTests(unittest.TestCase):
 def setUp(self):
  self.literal={'supported':False,'pure_source_parse_rejection':True}
  self.sidecar={'runs':{'baseline':{'returncode':0},'instrumented':{'returncode':0}},'instrumentation_pdf_pixel_equivalence':[{'pixel_identical':True}],'graph':{'ok':False,'failures':[{'reason':'numeric_or_unbound_path_terminal','picture':'1','path':'2'}]},'_events':[]}
 def result(self,**kw):return m.classify(kw.get('literal',self.literal),kw.get('sidecar',self.sidecar),kw.get('context',{'ok':True}),kw.get('history',{'possible_success':False}),kw.get('stable',True),kw.get('candidate',False),kw.get('assets',False))
 def test_complete_current_static_environment_semantic_failure_proposes(self):self.assertTrue(self.result()['proposal'])
 def test_named_graph_stays_pending(self):
  x=copy.deepcopy(self.sidecar);x['graph']={'ok':True,'failures':[]};self.assertFalse(self.result(sidecar=x)['proposal'])
 def test_literal_route_stays_pending(self):self.assertFalse(self.result(literal={'supported':True})['proposal'])
 def test_compile_error_never_semantic_failure(self):
  for which in ('baseline','instrumented'):
   x=copy.deepcopy(self.sidecar);x['runs'][which]['returncode']=1;self.assertFalse(self.result(sidecar=x)['proposal'])
 def test_instrumentation_changes_pixels_stays_pending(self):
  x=copy.deepcopy(self.sidecar);x['instrumentation_pdf_pixel_equivalence'][0]['pixel_identical']=False;self.assertFalse(self.result(sidecar=x)['proposal'])
 def test_missing_pixel_receipt_stays_pending(self):
  x=copy.deepcopy(self.sidecar);x.pop('instrumentation_pdf_pixel_equivalence');self.assertFalse(self.result(sidecar=x)['proposal'])
 def test_unknown_or_integrity_graph_failure_stays_pending(self):
  for reason in ('missing_executed_path_event','unexplained_event','marker_binding_unsupported'):
   x=copy.deepcopy(self.sidecar);x['graph']['failures']=[{'reason':reason}];self.assertFalse(self.result(sidecar=x)['proposal'])
 def test_unexplained_missing_node_or_label_events_stay_pending(self):
  x=copy.deepcopy(self.sidecar);x['graph']['failures'].append({'reason':'node_or_label_event_coverage_incomplete','missing':['999'],'extra':[]});self.assertFalse(self.result(sidecar=x)['proposal'])
 def test_existing_historical_success_or_unknown_trace_stays_pending(self):self.assertFalse(self.result(history={'possible_success':True})['proposal'])
 def test_runtime_asset_change_stays_pending(self):self.assertFalse(self.result(stable=False)['proposal'])
 def test_panel_asset_context_stays_pending(self):self.assertFalse(self.result(assets=True)['proposal'])
 def test_existing_candidate_control_never_abandoned(self):self.assertFalse(self.result(candidate=True)['proposal'])
 def test_context_unknown_never_terminal(self):self.assertFalse(self.result(context={'ok':False})['proposal'])
 def test_no_clock_io_or_conditional_source_proof(self):
  for command in (r'\time',r'\ifodd',r'\input{foo}',r'\csname time\endcsname',r'\def\x{1}',r'\write18{cmd}'):
   self.assertFalse(m.source_context_guard(command)['ok'])
 def test_static_simple_drawing_source_subset(self):
  self.assertTrue(m.source_context_guard(r'\documentclass{standalone}\usepackage{tikz}\begin{document}\begin{tikzpicture}\node(a){A};\draw (0,0)--(1,1);\end{tikzpicture}\end{document}')['ok'])
 def test_color_definitions_are_static_but_unknown_packages_not_proved(self):
  self.assertTrue(m.source_context_guard(r'\definecolor{foo}{RGB}{10,20,30}')['ok']);self.assertFalse(m.source_context_guard(r'\usepackage{unreviewed_environment}')['ok'])
 def test_external_plot_data_context_not_mistaken_for_closed_resources(self):self.assertFalse(m.source_context_guard(r'\addplot table {data.csv};')['ok'])
 def test_closed_basic_paint_gap_does_not_become_abandonment(self):
  result=m.include_paint_scope(self.result(),{'complete':True,'repair_route_candidates':['TikZ_to_PDF_to_SVG_closed_basic_paint_source_provenance_profile_bridge']});self.assertTrue(result['source_front_gate_failure_proved']);self.assertFalse(result['proposal'])
 def test_numeric_anchor_binding_candidate_stays_pending(self):
  result=m.include_paint_scope(self.result(),{'complete':True,'repair_route_candidates':['potential_generic_numeric_endpoint_to_recorded_anchor_geometry_binding']});self.assertFalse(result['proposal'])
 def test_unknown_paint_vs_graph_scope_stays_pending(self):self.assertFalse(m.include_paint_scope(self.result(),{'complete':False})['proposal'])
 def test_frozen_basic_shape_rule_needs_explicit_closure_and_does_not_accept_potential_mapping(self):
  prototype=Path(__file__).resolve().parent.parent/'prototype'
  if prototype.exists():sys.path.insert(0,str(prototype))
  import svg_source_scene_dom_v1 as scene
  import auto_quality_svg_closed_scene_v1 as closed
  obj={'type':'shape','tag':'path','attrs':{},'d':'M0,0L10,0L10,10L0,10L0,0','style':{'fill':'#aabbcc','stroke':'none','fillOpacity':1,'strokeOpacity':1,'opacity':1,'strokeWidth':0}}
  scene.enrich_scene({'objects':[obj],'issues':[]});self.assertIsNone(closed._basic_closed_geometry(obj));obj['d']+='Z';obj.pop('sceneGeometry',None);scene.enrich_scene({'objects':[obj],'issues':[]});self.assertEqual(closed._basic_closed_geometry(obj)['role'],'path_encoded_basic_frame')
 def test_static_comment_does_not_invent_runtime_dependency(self):self.assertTrue(m.source_context_guard('% \\input{unused}\n\\draw (0,0)--(1,1);')['ok'])
 def test_static_engine_ldd_nonzero_is_not_a_missing_library(self):
  with patch.object(m.subprocess,'run',return_value=types.SimpleNamespace(returncode=1,stdout='not a dynamic executable',stderr='')):self.assertEqual(m.runtime_libraries('/engine'),[])
 def test_unclassified_library_failure_is_pending(self):
  with patch.object(m.subprocess,'run',return_value=types.SimpleNamespace(returncode=1,stdout='',stderr='permission denied')):
   with self.assertRaises(ValueError):m.runtime_libraries('/engine')
 def test_frozen_profile_actual_AST_all_tikz_paths_require_one_of_two_gates(self):
  path=Path(__file__).with_name('auto_quality_batch_v4b.py');tree=ast.parse(path.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='profile')
  namespace={'sha':lambda b:'candidate-hash'};exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
  def graph(*args,**kwargs):return {'branch':'literal','evidence':{}}
  def execution(*args,**kwargs):return {'branch':'execution_v3','evidence':{}}
  modules={'auto_quality_source_graph':types.SimpleNamespace(check_graph_profile=graph),'tikz_execution_source_profile_v3':types.SimpleNamespace(check_execution_profile=execution)}
  for has_execution in (False,True):
   for canvas in (False,True):
    for html_flags in ({},{'html_actual_text_alignment':True},{'html_text_layout_v5':True},{'html_actual_text_alignment':True,'html_text_layout_v5':True}):
     record=dict(source_format='tikz',**html_flags);record['tikz_execution_source_v3']={'proof':True} if has_execution else None
     namespace['source_baseline']=lambda r,x:(dict(r),x) if canvas else (r,x)
     with patch.dict('sys.modules',modules):result=namespace['profile'](record,'xml','same original source')
     self.assertEqual(result['branch'],'execution_v3' if has_execution else 'literal')

if __name__=='__main__':unittest.main()
