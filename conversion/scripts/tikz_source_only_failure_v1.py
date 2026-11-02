"""Nonpublishing source-only TikZ front-gate failure experiment.

Scope is the currently installed/frozen production routes and their actual
runtime/assets, NOT every conceivable TeX engine, bundle, candidate or future
converter. No native XML/PNG is generated. Compiles run in the existing offline
sandbox against a private byte-identical read-only runtime snapshot; no fetch.
The frozen PGF extractor, wrappers, hook, parser and graph replay are unchanged.
"""
from __future__ import annotations
import ast,contextlib,hashlib,json,os,re,shlex,shutil,sqlite3,subprocess,sys,time
from pathlib import Path
import svg_failure_closure_v1 as shared

SCHEMA='tikz_source_only_frozen_front_gate_failure_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
canonical=shared.canonical
LOADED_SHA256=sha(Path(__file__).read_bytes())
IDLE={'queued','tikz_source_rendered','initial_conversion_deferred_v1','needs_fallback','needs_quality_repair','rendered','harness_review_pending'}
# A deliberately bounded, static source subset. Unknown primitives are deferred,
# not called unsupported. These prevent source-controlled environment/clock/
# random/TeX-I/O or hook-dependent trace changes from becoming terminal proof.
STATIC_COMMANDS=set('documentclass usepackage usetikzlibrary begin end node draw path tikzset foreach matrix coordinate fill filldraw clip addplot addlegendentry pgfplotsset pgfmathsetmacro pgfmathtruncatemacro centering textbf textit textsf textrm texttt textnormal emph underline color textcolor tiny scriptsize footnotesize small normalsize large Large LARGE huge Huge bfseries mdseries itshape slshape upshape sffamily rmfamily ttfamily selectfont fontsize fontfamily linespread setlength hspace vspace newline quad qquad alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega frac sqrt mathbf mathit mathrm mathcal mathbb operatorname sum prod int lim log exp sin cos tan min max left right cdot times pm leq geq neq infty in notin subset subseteq cup cap ldots cdots dots vec hat bar overline underbrace overbrace bf it tt sf rm relax label caption'.split())
STATIC_COMMANDS.add('definecolor')
STATIC_PACKAGES=set('tikz pgfplots xcolor amsmath amssymb amsfonts bm fontenc inputenc lmodern fontspec geometry'.split())
STATIC_CLASSES={'standalone','article','minimal'}
STATIC_LIBRARIES=set('positioning arrows.meta arrows calc fit matrix backgrounds shapes shapes.geometric shapes.misc shapes.multipart shapes.symbols chains quotes patterns intersections through angles decorations.pathreplacing decorations.markings decorations.text'.split())
DYNAMIC=re.compile(r'\\(?:if[A-Za-z@]*|else|fi|def|gdef|xdef|edef|newcommand|renewcommand|let|futurelet|csname|endcsname|catcode|scantokens|input|include|includegraphics|openin|openout|read|write|immediate|special|directlua|time|year|month|day|jobname|pdf[A-Za-z@]*|randomseed|uniformdeviate|normaldeviate|pgfmathsetseed|pgfmathrandom[A-Za-z@]*)\b')
def require(ok,reason):
 if not ok:raise ValueError(reason)
def source_context_guard(code):
 text=re.sub(r'(?<!\\)%[^\n]*','',code);problems=[]
 forbidden=sorted(set(DYNAMIC.findall(text)))
 if forbidden:problems.append({'reason':'source_context_dynamic_IO_macro_or_conditional_unproved','tokens':forbidden})
 if re.search(r'\b(?:rnd|rand|random)\s*\(|random\s+(?:steps|seed)|\.code\b|execute\s+at|/utils/exec|iic@|IIC(?:header|node|path|anchor)',text,re.I):problems.append({'reason':'source_random_callback_or_hook_interaction_unproved'})
 if re.search(r'https?://|/(?:etc|usr|home|backup)/|\.(?:csv|dat|tsv)\b|\b(?:table|file)\s*(?:\[[^\]]*\])?\s*\{',text):problems.append({'reason':'source_external_file_or_plot_data_context_unproved'})
 commands=set(re.findall(r'\\([A-Za-z@]+)',text));loopvars=set(re.findall(r'\\foreach\s+\\([A-Za-z]+)\s+in\s*\{[-0-9.,\s]+\}',text))
 if len(re.findall(r'\\foreach\b',text))!=len(loopvars):problems.append({'reason':'foreach_domain_not_proved_literal_finite_numeric'})
 unknown=sorted(commands-STATIC_COMMANDS-loopvars)
 if unknown:problems.append({'reason':'source_commands_outside_verified_static_context_subset','commands':unknown})
 for command,allowed in [('documentclass',STATIC_CLASSES),('usepackage',STATIC_PACKAGES),('usetikzlibrary',STATIC_LIBRARIES)]:
  matches=list(re.finditer(r'\\'+command+r'\s*(?:\[[^\]]*\]\s*)?\{([^{}]*)\}',text))
  names={name.strip() for match in matches for name in match[1].split(',')}
  if len(matches)!=len(re.findall(r'\\'+command+r'\b',text)) or not names<=allowed:problems.append({'reason':'source_class_package_or_library_outside_static_context','command':command,'unreviewed':sorted(names-allowed)})
 return {'ok':not problems,'failures':problems,'scope':'bounded static-source context; no inference from an unhandled macro or missing asset'}
def ast_function(path,name):
 tree=ast.parse(Path(path).read_text());found=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name];require(len(found)==1,'missing/ambiguous function '+name)
 node=found[0];return {'file':str(path),'function':name,'ast_sha256':sha(ast.dump(node,include_attributes=False).encode()),'calls':sorted({ast.unparse(c.func) for c in ast.walk(node) if isinstance(c,ast.Call)}),'source':ast.get_source_segment(Path(path).read_text(),node)}
def configuration(root):
 require(sha(Path(__file__).read_bytes())==LOADED_SHA256,'collector changed after import')
 root=Path(root).resolve();w=root/'conversion';s=w/'scripts';sys.path.insert(0,str(s))
 import auto_quality_batch_v4b as qa
 import tikz_execution_candidate_batch_v1 as producer
 qa.ensure_pinned();owner=json.loads((w/'auto_quality_owner.json').read_text());require(owner['policy']==qa.POLICY=='bounded_deterministic_clip_canvas_and_native_quality_v4b:a8446927202f282d','active QA owner is not the reviewed frozen module policy')
 policy,producer_pins=producer.implementation()
 require(policy=='pgf_execution_candidate_v1:bc199b55e7dc7b08836f','unreviewed PGF producer policy')
 pins={str((Path(k) if Path(k).is_absolute() else s/k).resolve()):v for k,v in qa.IMPLEMENTATION.items()};pins.update(producer_pins)
 for name in ('tikz_source_only_failure_v1.py','svg_failure_closure_v1.py','bounded_program_terminal_planner_v1.py','initial_conversion_case_v1.py','initial_conversion_supervisor_v1.py','initial_conversion_supervisor_v1b.py','harness_source_provenance.py','harness_canvas_contract.py','html_actual_text_registration.py','html_text_layout_registration_v5.py','pdf_to_native.py','pdf_fonts.py'):
  p=s/name;require(p.exists(),'missing production/guard dependency '+name);pins[str(p)]=sha(p.read_bytes())
 handoff=w/'prototype/svg_source_profile_scope_v1/frozen_source_marker_handoff_v1.json';frozen=json.loads(handoff.read_text());pins[str(handoff)]=sha(handoff.read_bytes())
 for name in ('svg_source_scene_dom_v1.py','auto_quality_svg_closed_scene_v1.py'):
  p=w/'prototype'/name;expected=frozen['implementation_sha256'][str(p)];require(sha(p.read_bytes())==expected,'frozen paint classifier changed');pins[str(p)]=expected
 gates=[('auto_quality_batch_v4b.py','profile'),('auto_quality_batch_v4b.py','source_baseline'),('auto_quality_batch_v4b.py','verify'),('auto_quality_source_graph.py','_check_tikz'),('auto_quality_source_graph.py','check_graph_profile'),('tikz_execution_source_profile_v3.py','prepare'),('tikz_execution_binding.py','bind_execution'),('tikz_execution_candidate_batch_v1.py','generate'),('tikz_execution_graph.py','compile_execution_graph'),('auto_quality_common_v2.py','registration_record'),('auto_quality_canvas_repair.py','validate_registration'),('initial_conversion_case_v1.py','inputs'),('initial_conversion_case_v1.py','native_case')]
 astproof=[ast_function(s/file,fn) for file,fn in gates]
 dispatch=astproof[0]['source'];require("fmt=='tikz' and before.get('tikz_execution_source_v3')" in dispatch and "elif fmt in ('mermaid','tikz')" in dispatch,'unreviewed TikZ dispatch shape')
 literal=astproof[3]['source'];require(literal.index('parse_literal(code)')<literal.index('archive_name ='),'literal parser is no longer source-first')
 binding=astproof[6]['source'];require("not sidecar.get('ok') or not sidecar['graph'].get('ok')" in binding,'execution source graph is not an obligatory pre-binding guard')
 emitters=[]
 for p in sorted(s.glob('*.py')):
  if p.name.startswith('test_') or p.name==Path(__file__).name:continue
  text=p.read_text(errors='replace')
  if 'tikz_execution_source_profile_v3' not in text:continue
  parsed=ast.parse(text)
  if any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='manifest' for n in ast.walk(parsed)):emitters.append(p.name)
 require(emitters==['tikz_execution_candidate_batch_v1.py'],'additional/unreviewed execution-v3 production manifest emitter')
 return {'root':str(root),'policy':qa.POLICY,'execution_policy':policy,'pins':pins,'owner_policy_file':str(w/'auto_quality_owner.json'),'ast_proof':astproof,'v3_manifest_emitters':emitters,'scope_note':'Verifier accepts runtime paths under conversion/runtime, not only one filename. This certificate additionally binds the actual existing producer and searches matching-source owned historical traces; any possible historical success is pending.'}
def pins_ok(config):
 require(json.loads(Path(config['owner_policy_file']).read_text())['policy']==config['policy'],'active QA policy changed')
 for p,h in config['pins'].items():require(sha(Path(p).read_bytes())==h,'program/runtime pin changed: '+p)
def runtime_libraries(binary):
 result=subprocess.run(['ldd',str(binary)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE);text=result.stdout+'\n'+result.stderr
 require(result.returncode==0 or 'not a dynamic executable' in text or 'statically linked' in text,'cannot establish engine library dependencies')
 paths=[]
 for line in text.splitlines():
  match=re.search(r'(?:=>\s*)?(/[^\s]+)',line)
  if match and Path(match[1]).is_file():paths.append(Path(match[1]).resolve())
 return paths
def environment_files(root):
 """Complete cache/runtime roster, system font roster/config and engine libs."""
 root=Path(root);runtime=root/'conversion/runtime/tectonic';paths=set()
 for p in runtime.rglob('*'):
  if p.is_file():paths.add(p.resolve())
 for parent in ('/etc/fonts','/usr/share/fonts','/usr/local/share/fonts'):
  p=Path(parent)
  if p.exists():paths.update(q.resolve() for q in p.rglob('*') if q.is_file())
 for name in subprocess.check_output(['fc-list','--format=%{file}\n'],text=True).splitlines():
  p=Path(name)
  if p.is_file():paths.add(p.resolve())
 paths.update(runtime_libraries(runtime/'tectonic'))
 for p in ('/usr/bin/bwrap','/etc/localtime'):
  if Path(p).is_file():paths.add(Path(p).resolve())
 return {str(p):{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(paths)}
def private_environment(config,folder):
 root=Path(config['root']);runtime=root/'conversion/runtime/tectonic';manifest=environment_files(root);private=Path(folder)/'runtime';private.mkdir(parents=True,exist_ok=False)
 for name,item in manifest.items():
  p=Path(name)
  if p.is_relative_to(runtime):
   dest=private/p.relative_to(runtime);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);require(sha(dest.read_bytes())==item['sha256'],'runtime snapshot copy differs')
 os.chmod(private/'tectonic',0o755)
 require(environment_files(root)==manifest,'environment changed during private runtime snapshot')
 return {'runtime':str(runtime),'private_runtime':str(private),'files':manifest,'manifest_sha256':sha(canonical(manifest)),'network_and_dependency_fetch':False}
def historical_traces(db,source_hash,root):
 """All matching authoritative source IDs in the two v3-owned proof areas."""
 root=Path(root);ids=[r[0] for r in db.execute('select id from processing_outcomes_v2 where source_code_hash=?',(source_hash,))];paths=set()
 for identifier in ids:
  for parent in (root/'conversion/tikz_execution_candidates_v1'/identifier,root/'clean/drawio_unified'/identifier[:2]/identifier):
   if parent.exists():paths.update(parent.rglob('execution_graph.json'))
 records=[]
 for path in sorted(paths):
  try:
   blob=path.read_bytes();r=json.loads(blob)
   if r.get('source_sha256')!=source_hash:continue
   records.append({'file':str(path),'sha256':sha(blob),'ok':r.get('ok'),'graph_ok':(r.get('graph') or {}).get('ok'),'hook_sha256':r.get('hook_sha256'),'engine_file':r.get('engine_file'),'engine_sha256':r.get('engine_sha256'),'possible_success':r.get('ok') is True or (r.get('graph') or {}).get('ok') is True})
  except Exception as exc:records.append({'file':str(path),'uncertain':repr(exc),'possible_success':True})
 return {'source_ids':ids,'records':records,'possible_success':any(r['possible_success'] for r in records)}
@contextlib.contextmanager
def cache_only_adapter(environment):
 """Only the compile transport changes; frozen extraction/protocol stays intact."""
 import tectonic_compile as compiler
 import sandbox_runner
 previous=compiler.compile_case;runtime=Path(environment['runtime']);private=Path(environment['private_runtime'])
 def compile_cached(directory,max_rounds=2):
  directory=Path(directory);argv=[str(runtime/'tectonic'),'--untrusted','--only-cached','--keep-logs','--keep-intermediates','--makefile-rules','/work/asset_dependencies.mk','/work/source.tex']
  run=sandbox_runner.run(directory,argv,timeout=150,extra_ro=[(private,runtime)],extra_env=dict(compiler.ENV))
  (directory/'compile_0.stdout').write_text(run.stdout);(directory/'compile_0.stderr').write_text(run.stderr)
  attempts=[{'round':0,'returncode':run.returncode,'cache_only':True,'fetch_allowed':False,'private_runtime_manifest_sha256':environment['manifest_sha256'],'argv':argv}]
  (directory/'compile_attempts.json').write_bytes(canonical(attempts));return run,attempts
 compiler.compile_case=compile_cached
 try:yield
 finally:compiler.compile_case=previous
def literal_result(code):
 from tikz_literal_graph import parse_literal
 try:r=parse_literal(code.decode());return {'supported':True,'parser':r.get('parser'),'nodes':len(r['nodes']),'edges':len(r['edges'])}
 except ValueError as exc:return {'supported':False,'error_type':type(exc).__name__,'error':str(exc),'pure_source_parse_rejection':True}
def paint_topology(sidecar,execution,folder,root):
 """Source PDF/PGF taxonomy only. No native render or acceptance implication."""
 sys.path.append(str(Path(root)/'conversion/runtime/python_packages'));sys.path.append(str(Path(root)/'conversion/prototype'))
 import pymupdf
 import svg_source_scene_dom_v1 as scene
 import auto_quality_svg_closed_scene_v1 as closed
 from pdf_to_native import pathdata,rgb,source_svg
 events=sidecar.get('_events',[]);graph=sidecar.get('graph') or {};paths=[];arrows=[]
 for event in events:
  if event['kind']=='finish':
   f=event['fields'];row={'picture':f[0],'path':f[1],'arrows_tex':f[2],'start_arrow':f[3]=='1','end_arrow':f[4]=='1','painted_softpath':bool(f[5].strip())};paths.append(row)
   if row['start_arrow'] or row['end_arrow']:arrows.append(row)
 anchors=[]
 def pt(value):return float(value.removesuffix('pt'))
 for ref in graph.get('reference_events',[]):
  try:anchors.append({'picture':ref['picture'],'node':ref['name'],'anchor':ref['anchor'],'point_pt':[pt(v) for v in ref['point_pt']]})
  except (ValueError,KeyError):pass
 numeric_matches=[]
 fatal={(x.get('picture'),x.get('path')) for x in graph.get('failures',[]) if x.get('reason')=='numeric_or_unbound_path_terminal'}
 for event in events:
  if event['kind']!='finish' or tuple(event['fields'][:2]) not in fatal:continue
  f=event['fields'];points=[(float(x),float(y)) for x,y in re.findall(r'\\pgfsyssoftpath@(?:movetotoken|linetotoken|curvetotoken)\s*\{([-+0-9.]+)pt\}\s*\{([-+0-9.]+)pt\}',f[5])]
  for side,point in [('start',points[0] if points else None),('end',points[-1] if points else None)]:
   if point is None:continue
   matches={(a['node'],a['anchor']) for a in anchors if a['picture']==f[0] and sum((v-z)**2 for v,z in zip(a['point_pt'],point))<=.03**2}
   numeric_matches.append({'picture':f[0],'path':f[1],'side':side,'point_pt':point,'recorded_anchor_matches':sorted(matches),'unique_match':len(matches)==1})
 result={'complete':False,'pgf_painted_path_count':sum(x['painted_softpath'] for x in paths),'pgf_arrow_paths':arrows,'pgf_named_nodes':[{'name':n['name'],'shape':n['shape'],'picture':n['picture'],'center_pt':n['center_pt'],'individual_node_paint_ownership':'not proved from a PGF node class alone'} for n in graph.get('nodes',[])],'pgf_unnamed_node_count':len(graph.get('decorative_nodes',[])),'pgf_recorded_anchor_count':len(anchors),'numeric_endpoint_anchor_matches':numeric_matches,'PDF_paint_paths':[],'repair_route_candidates':[],'native_render_calls':0}
 pdf=Path(execution)/'baseline/source.pdf'
 if not pdf.exists():result['reason']='no_successful_source_pdf_for_taxonomy';return result
 with pymupdf.open(pdf) as doc:
  result['pages']=len(doc);result['raster_images']=sum(len(page.get_images()) for page in doc);result['source_text_spans']=sum(len(page.get_texttrace()) for page in doc)
  for page_number,page in enumerate(doc):
   for number,d in enumerate(page.get_drawings(extended=True)):
    if d['type'] in ('clip','group'):
     result['PDF_paint_paths'].append({'page':page_number,'id':number,'type':d['type'],'basic_closed_role':None});continue
    item={'page':page_number,'id':number,'type':d['type'],'bbox':list(d['rect']),'closed_by_PDF_operator':d.get('closePath'),'segment_types':[str(t[0]) for t in d['items']],'fill':rgb(d.get('fill')),'stroke':rgb(d.get('color'))}
    obj={'id':str(number),'type':'shape','tag':'path','attrs':{},'d':pathdata(d),'bbox':{'x':d['rect'].x0,'y':d['rect'].y0,'w':d['rect'].width,'h':d['rect'].height},'matrix':[1,0,0,1,0,0],'style':{'fill':item['fill'],'stroke':item['stroke'],'strokeWidth':d.get('width') or 0,'fillOpacity':d.get('fill_opacity') if d.get('fill_opacity') is not None else 1,'strokeOpacity':d.get('stroke_opacity') if d.get('stroke_opacity') is not None else 1,'opacity':1}}
    enriched=scene.enrich_scene({'objects':[obj],'issues':[]});item['topology']=obj.get('sceneGeometry',{}).get('topology');item['basic_closed_role']=closed._basic_closed_geometry(obj)
    # PDF extractors can emit a closed-looking path as a final segment back to
    # its first point without an explicit SVG Z. Test the existing basic-shape
    # checker on that candidate only to identify a repair family. This is NOT a
    # paint-equivalence proof and does not modify the saved source-derived SVG.
    parts=(item['topology'] or {}).get('subpaths',[])
    if len(parts)==1:
     ops=parts[0]['operations'];moves=[o['points'][0] for o in ops if o['operation']=='moveTo'];ends=[o['points'][-1] for o in ops if o['points'] and o['operation'] in ('lineTo','curveTo','qCurveTo')]
     endpoint_closed=bool(moves and ends and sum((a-b)**2 for a,b in zip(moves[0],ends[-1]))<=.01**2);item['endpoint_geometrically_closed']=endpoint_closed
     if endpoint_closed:
      candidate=json.loads(json.dumps(obj));candidate['d']+=' Z';candidate.pop('sceneGeometry',None);scene.enrich_scene({'objects':[candidate],'issues':[]});role=closed._basic_closed_geometry(candidate)
      if role:item['potential_basic_closed_mapping']={'role':role,'status':'requires independent lossless PDF-to-SVG closure/stroke-join proof; not accepted or silently normalized'}
    result['PDF_paint_paths'].append(item)
  # A real derived SVG, never passed off as authoritative original SVG input.
  if len(doc)==1:
   try:
    output=Path(folder)/'pdf_to_svg';output.mkdir(exist_ok=False);svg,fonts,stats=source_svg(doc,doc[0],output);(output/'source_derived_from_original_tikz.pdf.svg').write_text(svg)
    result['derived_source_svg']={'file':str(output/'source_derived_from_original_tikz.pdf.svg'),'sha256':sha(svg.encode()),'source_pdf_sha256':sha(pdf.read_bytes()),'converter_file':str(Path(source_svg.__code__.co_filename)),'converter_sha256':sha(Path(source_svg.__code__.co_filename).read_bytes()),'font_count':len(fonts),'issues':json.loads(json.dumps(stats.get('issues',[]),default=lambda v:list(v) if hasattr(v,'__iter__') and not isinstance(v,(str,bytes,dict)) else repr(v))),'provenance_bridge_registered_in_QA4b':False}
   except Exception as exc:result['derived_source_svg']={'ok':False,'error':repr(exc),'provenance_bridge_registered_in_QA4b':False}
 painted=result['PDF_paint_paths'];basic=sum(bool(p.get('basic_closed_role')) for p in painted);potential=sum(bool(p.get('basic_closed_role') or p.get('potential_basic_closed_mapping')) for p in painted);result['basic_closed_path_count']=basic;result['potential_basic_closed_path_count']=potential;result['non_basic_or_open_path_count']=len(painted)-basic;result['complete']=not any((p.get('topology') or {}).get('error') for p in painted)
 if not arrows and painted and potential==len(painted) and not result['raster_images']:
  result['repair_route_candidates'].append('TikZ_to_PDF_to_SVG_closed_basic_paint_source_provenance_profile_bridge')
 elif not result['pgf_named_nodes'] and not result['raster_images']:
  result['repair_route_candidates'].append('TikZ_plot_paint_and_axis_arrow_owner_source_profile_gap')
 if result['pgf_named_nodes'] and any(x['unique_match'] for x in numeric_matches):result['repair_route_candidates'].append('potential_generic_numeric_endpoint_to_recorded_anchor_geometry_binding')
 return result
def include_paint_scope(front_gate,topology):
 """A graph-only profile failure is not automatically whole-program exhaustion."""
 out=dict(front_gate);out['source_front_gate_failure_proved']=bool(front_gate.get('proposal'));out['paint_topology']=topology
 if front_gate.get('proposal') and (not topology.get('complete') or topology.get('repair_route_candidates')):
  out.update(proposal=False,reason='source_profile_gap_retain_pending',deferred_reasons=['known_paint_or_geometry_profile_bridge_requires_bounded_evaluation'] if topology.get('complete') else ['paint_vs_graph_scope_not_complete'])
 return out
def classify(literal,sidecar,context,history,environment_stable,has_candidate=False,source_assets=False):
 reasons=[];classes=[]
 if literal.get('supported'):reasons.append('literal_source_route_remains_supported')
 runs=sidecar.get('runs',{});compiled=set(runs)=={'baseline','instrumented'} and all(x.get('returncode')==0 for x in runs.values())
 pages=sidecar.get('instrumentation_pdf_pixel_equivalence') or []
 if not compiled or not pages or not all(x.get('pixel_identical') is True for x in pages):reasons.append('runtime_resource_or_instrumentation_failure_not_semantic')
 graph=sidecar.get('graph') or {}
 if graph.get('ok') is True:reasons.append('execution_named_graph_route_remains_supported')
 if compiled and pages and graph.get('ok') is False:
  try:
   from bounded_program_terminal_planner_v1 import semantic_classes
   classes=semantic_classes(graph,sidecar.get('_events',[]))
  except Exception as exc:reasons.append('execution_failure_is_integrity_unknown_or_unexplained_event: '+str(exc))
 elif not graph:reasons.append('no_complete_source_trace_graph')
 if not context.get('ok'):reasons.append('source_execution_context_not_in_proved_static_subset')
 if history.get('possible_success'):reasons.append('matching_source_historical_success_or_unclassified_trace_environment')
 if not environment_stable:reasons.append('actual_allowed_runtime_or_asset_roster_changed')
 if source_assets:reasons.append('source_asset_mapping_environment_not_closed')
 if has_candidate:reasons.append('existing_native_candidate_is_outside_no_output_optimization_control')
 if not classes:reasons.append('no_specific_supported_SEMANTIC_failure_certificate')
 return {'proposal':not reasons,'reason':'current_frozen_program_source_front_gates_unreachable' if not reasons else 'retain_pending','deferred_reasons':sorted(set(reasons)),'semantic_classes':classes,'native_screenshot_required_for_this_failure_proof':False,'scope':'current frozen route/runtime/asset catalogue only; no future-version/native-impossibility claim'}
def prepare(db,identifier,config,work):
 require(not db.in_transaction,'source-only preparation requires autocommit RO connection');pins_ok(config);root=Path(config['root']);folder=Path(work).resolve();require(folder.is_relative_to(root/'conversion/prototype/tikz_source_only_failure_v1'),'work outside private source-only prototype');folder.mkdir(parents=True,exist_ok=False)
 report={'schema':SCHEMA,'id':identifier,'at':shared.now(),'models_called':0,'native_render_calls':0,'published':False,'accepted':False,'proposal':False};files={}
 def save(name,value):
  blob=value if isinstance(value,bytes) else canonical(value);path=folder/name;path.write_bytes(blob);files[str(path)]=sha(blob)
 try:
  db.execute('BEGIN');before=shared.snapshot(db,identifier);row=db.execute('select format,category,source,state,worker_pid,input_record,input_manifest,output_record from jobs where id=?',(identifier,)).fetchone();require(row and row[0]=='tikz' and row[3] in IDLE and row[4] is None,'source is not idle authoritative TikZ');require(not shared.busy_rows(db,identifier),'active deterministic/model owner')
  src=json.loads(row[5]);manifest=json.loads(row[6]);outcome=db.execute('select category,format,source_code_hash,source_image_hash,status from processing_outcomes_v2 where id=?',(identifier,)).fetchone();require(outcome and outcome[4]=='pending','not pending scope')
  require(src['pair_sha256']==manifest['id']==identifier and src['format']==manifest['source_format']=='tikz' and (row[1],row[0])==outcome[:2] and src['category']==row[1] and src['source']==row[2],'source scope/manifest identity differs')
  require((src['code_sha256'],src['image_sha256'])==(manifest['code_sha256'],manifest['image_sha256'])==outcome[2:4],'source hashes differ')
  code_path=(root/manifest['source_code']).resolve();image_path=(root/manifest['reference_image']).resolve();require(code_path.is_relative_to(root) and image_path.is_relative_to(root),'source paths outside registered root');code=code_path.read_bytes();image=image_path.read_bytes();require((sha(code),sha(image))==outcome[2:4],'actual original source/reference differs')
  files.update({str(code_path):sha(code),str(image_path):sha(image)});save('original_source.tex',code);save('input_record.json',src);save('input_manifest.json',manifest);history=historical_traces(db,src['code_sha256'],root);save('historical_traces.json',history);db.rollback()
  literal=literal_result(code);context=source_context_guard(code.decode());save('literal.json',literal);save('source_context.json',context)
  environment=private_environment(config,folder);save('environment.json',environment)
  from tikz_execution_graph import compile_execution_graph,parse_events,graph_from_events
  with cache_only_adapter(environment):sidecar=compile_execution_graph(code,folder/'execution')
  require(sidecar.get('source_sha256')==src['code_sha256'] and sidecar.get('source_bytes_unchanged') is True and sidecar.get('published') is False,'fresh source execution identity/provenance differs')
  from tikz_execution_source_profile import WRAPPERS
  for mode,run in sidecar.get('runs',{}).items():
   require(mode in WRAPPERS and run.get('wrapper_sha256')==sha(WRAPPERS[mode]),'unreviewed source execution wrapper')
   require(sha((folder/'execution'/mode/'original_source.tex').read_bytes())==src['code_sha256'],'executed source file differs')
  trace=folder/'execution/instrumented/source.iic'
  if trace.exists():
   events=parse_events(trace.read_text());require(graph_from_events(events)==sidecar.get('graph'),'fresh complete trace replay differs');sidecar['_events']=events
  for path in (folder/'execution').rglob('*'):
   if path.is_file():require(not path.is_symlink(),'execution sidecar contains symlink');files[str(path)]=sha(path.read_bytes())
  for original,item in environment['files'].items():
   p=Path(original)
   if p.is_relative_to(Path(environment['runtime'])):
    private=Path(environment['private_runtime'])/p.relative_to(environment['runtime']);require(sha(private.read_bytes())==item['sha256'],'private runtime changed during compilation');files[str(private)]=item['sha256']
  topology=paint_topology(sidecar,folder/'execution',folder,root);save('paint_topology.json',topology)
  for path in (folder/'pdf_to_svg').rglob('*'):
   if path.is_file():files[str(path)]=sha(path.read_bytes())
  stable=environment_files(root)==environment['files'];decision=include_paint_scope(classify(literal,sidecar,context,history,stable,bool(row[7]),bool(manifest.get('panel_assets'))),topology)
  report.update(decision,source_code_sha256=src['code_sha256'],source_image_sha256=src['image_sha256'],source_state=row[3],has_output_record=bool(row[7]),literal=literal,source_context=context,execution={'ok':sidecar.get('ok'),'error':sidecar.get('error'),'runs':sidecar.get('runs'),'graph_failures':(sidecar.get('graph') or {}).get('failures'),'graph_ok':(sidecar.get('graph') or {}).get('ok'),'pixel_equivalence':sidecar.get('instrumentation_pdf_pixel_equivalence')},environment_manifest_sha256=environment['manifest_sha256'],environment_stable=stable,historical_trace_summary={'count':len(history['records']),'possible_success':history['possible_success']},policy=config['policy'],execution_policy=config['execution_policy'],snapshot=before,pins=config['pins'],files=files,ast_proof=config['ast_proof'],v3_manifest_emitters=config['v3_manifest_emitters'])
  pins_ok(config);db.execute('BEGIN');require(shared.snapshot(db,identifier)==before,'source/full owner/outcome/manifest snapshot changed during experiment');require(historical_traces(db,src['code_sha256'],root)==history,'matching-source owned historical trace catalogue changed');db.rollback();require(environment_files(root)==environment['files'],'runtime/assets changed after source proof')
  for p,h in files.items():require(sha(Path(p).read_bytes())==h,'source/evidence changed after experiment')
 except Exception as exc:
  if db.in_transaction:db.rollback()
  report.update(proposal=False,reason='retain_pending',deferred_reasons=['source_evidence_environment_or_CAS_incomplete'],error=repr(exc))
 report['evidence_directory']=str(folder);report['certificate_sha256']=sha(canonical(report));(folder/'report.json').write_bytes(canonical(report));return report
def revalidate(db,plan,config,check_files=True):
 """Read-only source/runtime/owner CAS. No candidate or outcome publication."""
 try:
  require(plan.get('schema')==SCHEMA and plan.get('proposal') is True,'not a source-only proposal')
  body={k:v for k,v in plan.items() if k!='certificate_sha256'};require(sha(canonical(body))==plan['certificate_sha256'],'source-only certificate damaged')
  pins_ok(config);require(plan['pins']==config['pins'] and plan['policy']==config['policy'] and plan['execution_policy']==config['execution_policy'],'different allowed programme catalogue')
  require(shared.snapshot(db,plan['id'])==plan['snapshot'],'source/owner/outcome/manifest state changed')
  if check_files:
   for p,h in plan['files'].items():require(sha(Path(p).read_bytes())==h,'source/runtime/proof file changed: '+p)
  folder=Path(plan['evidence_directory']);environment=json.loads((folder/'environment.json').read_text());require(environment_files(config['root'])==environment['files'],'allowed asset/runtime roster changed')
  history=historical_traces(db,plan['source_code_sha256'],config['root']);require(history==json.loads((folder/'historical_traces.json').read_text()),'historical source trace environments changed')
  code=(folder/'original_source.tex').read_bytes();require(sha(code)==plan['source_code_sha256'],'preserved source changed');sidecar=json.loads((folder/'execution/execution_graph.json').read_text())
  from tikz_execution_graph import parse_events,graph_from_events
  events=parse_events((folder/'execution/instrumented/source.iic').read_text());require(graph_from_events(events)==sidecar['graph'],'source trace replay changed');sidecar['_events']=events
  topology=json.loads((folder/'paint_topology.json').read_text());require(include_paint_scope(classify(literal_result(code),sidecar,source_context_guard(code.decode()),history,True,False,False),topology)['proposal'],'fresh pure failure replay or source-paint scope no longer terminal')
  return {'current':True,'id':plan['id']}
 except Exception as exc:return {'current':False,'id':plan.get('id'),'reason':repr(exc)}
