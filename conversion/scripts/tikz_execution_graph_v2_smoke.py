"""Real PGF execution proves historical instances, aliases and numeric rejection."""
import json,uuid
from native_worker import W,now
from tikz_execution_graph_v2 import compile_execution_graph

document=lambda body:('\\documentclass[tikz]{standalone}\n\\begin{document}\n\\begin{tikzpicture}\n'+body+'\n\\end{tikzpicture}\n\\end{document}\n').encode()
cases={
 'two_scopes_redefine_empty_circles':document(r'''
\begin{scope}
 \node[circle,draw,fill=gray!30,minimum size=17pt] (I-1) at (0,0) {};
 \node[circle,draw,fill=gray!30,minimum size=17pt] (I-2) at (0,1) {};
 \node[circle,draw,fill=gray!30,minimum size=17pt] (H-1) at (2,0) {};
 \node[circle,draw,fill=gray!30,minimum size=17pt] (H-2) at (2,1) {};
 \draw (I-1) -- (H-1); \draw (I-2) -- (H-2);
\end{scope}
\begin{scope}[yshift=-3cm]
 \node[circle,draw,fill=gray!30,minimum size=17pt] (I-1) at (0,0) {};
 \node[circle,draw,fill=gray!30,minimum size=17pt] (I-2) at (0,1) {};
 \node[circle,draw,fill=gray!30,minimum size=17pt] (H-1) at (2,0) {};
 \node[circle,draw,fill=gray!30,minimum size=17pt] (H-2) at (2,1) {};
 \draw (I-1) -- (H-1); \draw (I-2) -- (H-2);
\end{scope}'''),
 'copied_alias_survives_redefinition_and_rename':document(r'''
\node[draw] (A) at (0,0) {A}; \node[draw] (B) at (3,0) {B};
\pgfnodealias{savedA}{A}
\draw (A.east) -- (B.west);
\node[draw] (A) at (0,-2) {new A};
\draw (savedA.east) -- (B.west); \draw (A.east) -- (B.south);
\pgfnoderename{renamedA}{A}
\draw (renamedA.east) -- (B.west);'''),
 'foreach_redefinitions':document(r'''
\foreach \dy in {0,-3}{\begin{scope}[yshift=\dy cm]
 \foreach \i in {1,2,3}{\node[circle,draw,fill=gray!30,minimum size=17pt] (N-\i) at (\i,0) {};}
 \draw (N-1) -- (N-2); \draw (N-2) -- (N-3);
\end{scope}}'''),
 'numeric_endpoint_still_unsupported':document(r'''
\node[draw] (A) at (0,0) {A}; \node[draw] (B) at (2,0) {B};
\draw[->] (A) -- (1,2);''')}
root=W/'tikz_execution_graph_v2_prototype'/('smoke_'+uuid.uuid4().hex[:12]);rows=[]
for name,source in cases.items():
 result=compile_execution_graph(source,root/name);graph=result.get('graph',{});expected=name!='numeric_endpoint_still_unsupported';row={'case':name,'expected_graph_ok':expected,'ok':result.get('ok'),'instrumentation_ok':result.get('instrumentation_ok'),'identity_ok':graph.get('identity_ok'),'nodes':len(graph.get('nodes',[])),'edges':len(graph.get('edges',[])),'duplicate_groups':graph.get('duplicate_name_generations'),'source_instances':[e['source'] for e in graph.get('edges',[])],'target_instances':[e['target'] for e in graph.get('edges',[])],'failures':graph.get('failures'),'error':result.get('error'),'proof':str(root/name/'execution_graph.json')};rows.append(row);print(json.dumps(row),flush=True)
 assert row['instrumentation_ok'] and row['identity_ok'] and row['ok']==expected,row
 if name=='copied_alias_survives_redefinition_and_rename':assert row['source_instances'][0]==row['source_instances'][1] and row['source_instances'][2]==row['source_instances'][3] and row['source_instances'][0]!=row['source_instances'][2]
out={'at':now(),'ok':True,'published':False,'source_names_or_bytes_modified':False,'root':str(root),'cases':rows};(W/'tikz_execution_graph_v2_smoke.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'ok':True,'root':str(root),'cases':len(rows)}),flush=True)
