"""Remote-only synthetic compilation proof for execution semantic extraction."""
import json,uuid
from pathlib import Path
from native_worker import W,now
from tikz_execution_graph import compile_execution_graph

document=lambda body:(r'\documentclass[tikz,border=3pt]{standalone}'+'\n'+r'\begin{document}'+'\n'+body+'\n'+r'\end{document}').encode()
cases={
 'foreach_macro_labels':(document(r'''\newcommand{\NodeText}[1]{N #1}
\begin{tikzpicture}
\foreach \i in {1,2,3}{\node[draw] (n\i) at (\i*2,0) {\NodeText{\i}};}
\foreach \a/\b in {1/2,2/3}{\draw[->] (n\a.east) -- node[above]{L\a} (n\b.west);}
\node at (2,-1) {Caption};
\end{tikzpicture}'''),{'nodes':{'n1':'N 1','n2':'N 2','n3':'N 3'},'edges':[('n1','n2',['L1'],False,True),('n2','n3',['L2'],False,True)],'decorative':1,'ok':True}),
 'macro_nodes_orthogonal':(document(r'''\newcommand{\BoxAt}[4]{\node[draw] (#1) at (#2,#3) {#4};}
\newcommand{\IICConnect}[2]{\draw[<->] (#1.south) |- node[right]{Return} (#2.west);}
\begin{tikzpicture}\BoxAt{top}{0}{2}{Input}\BoxAt{bottom}{3}{0}{Output}\IICConnect{top}{bottom}\end{tikzpicture}'''),{'nodes':{'top':'Input','bottom':'Output'},'edges':[('top','bottom',['Return'],True,True)],'ok':True}),
 'multi_segment':(document(r'''\begin{tikzpicture}\foreach \x/\t in {0/a,2/b,4/c}{\node[draw] (\t) at (\x,0) {\t};}
\draw[->] (a) -- node[above]{AB} (b) -- node[above]{BC} (c);\end{tikzpicture}'''),{'nodes':{'a':'a','b':'b','c':'c'},'edges':[('a','b',['AB'],False,False),('b','c',['BC'],False,True)],'ok':True}),
 'negative_unbound_numeric':(document(r'''\begin{tikzpicture}\node[draw] (a) {A};\draw[->] (a) -- (2,0);\end{tikzpicture}'''),{'ok':False}),
 'post_terminal_midway_label':(document(r'''\begin{tikzpicture}\node[draw] (a) {Start};\node[draw] (b) at (3,0) {End};\draw[->] (a) -- (b) node[midway,above]{Mid};\end{tikzpicture}'''),{'nodes':{'a':'Start','b':'End'},'edges':[('a','b',['Mid'],False,True)],'ok':True}),
 'negative_direct_pgf':(document(r'''\begin{tikzpicture}\node[draw] (a) {A};\pgfpathmoveto{\pgfpoint{0pt}{0pt}}\pgfpathlineto{\pgfpoint{40pt}{0pt}}\pgfusepath{stroke}\end{tikzpicture}'''),{'ok':False,'reason':'direct_pgf_paint_outside_recorded_tikz_pipeline'}),
 'negative_untracked_cycle':(document(r'''\begin{tikzpicture}\node[draw] (a) {A};\node[draw] (b) at (2,0) {B};\draw (a) -- (b) -- cycle;\end{tikzpicture}'''),{'ok':False,'reason':'uncovered_executed_softpath_operations'}),
}
root=W/'tikz_execution_graph_prototype'/('smoke_'+uuid.uuid4().hex[:12]);root.mkdir(parents=True);results=[]
for name,(source,expected) in cases.items():
 result=compile_execution_graph(source,root/name);graph=result.get('graph',{});errors=[]
 if result.get('ok')!=expected['ok']:errors.append('unexpected_sidecar_result')
 if expected['ok']:
  found={n['name']:n['expanded_label_tex'].strip() for n in graph.get('nodes',[])}
  if found!=expected['nodes']:errors.append({'node_mismatch':found})
  edges=[(e['source'],e['target'],[s.strip() for s in e['expanded_labels_tex']],e['start_arrow'],e['end_arrow']) for e in graph.get('edges',[])]
  if edges!=expected['edges']:errors.append({'edge_mismatch':edges})
  if len(graph.get('decorative_nodes',[]))!=expected.get('decorative',0):errors.append('anonymous_annotation_count_mismatch')
  if expected.get('decorative'):
   note=graph['decorative_nodes'][0]
   if note['expanded_label_tex']!='Caption' or abs(float(note['center_pt'][0][:-2])-56.9055)>.002 or abs(float(note['center_pt'][1][:-2])+28.4527)>.002:errors.append({'anonymous_annotation_position_or_text_mismatch':note})
 else:
  if not graph or not any(f['reason']==expected.get('reason','numeric_or_unbound_path_terminal') for f in graph.get('failures',[])):errors.append('negative_did_not_fail_for_expected_semantic_reason')
 summary={'case':name,'ok':not errors,'errors':errors,'compile_error':result.get('error'),'graph_ok':graph.get('ok'),'source_nodes':len(graph.get('nodes',[])),'source_edges':len(graph.get('edges',[])),'graph_failures':graph.get('failures'),'proof_file':str(root/name/'execution_graph.json')};results.append(summary);print(json.dumps(summary),flush=True)
report={'at':now(),'root':str(root),'ok':all(r['ok'] for r in results),'results':results,'published':False};(W/'tikz_execution_graph_smoke.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
