import json
from native_worker import W,now
from tikz_literal_graph import parse_literal
base=r'''\begin{tikzpicture}[arrow/.style={->,thick},node distance=2cm]
\node[draw,fill=blue!10] (a) {First};
\node[draw,fill=green!10,right=of a] (b) {Second};
\node[draw,fill=red!10,below=of b] (c) {Third};
\draw[arrow] (a) -- node[fill=white] {Data} (b);
\draw[<-] (b) -- (c);
\end{tikzpicture}'''
r=parse_literal(base);assert len(r['nodes'])==3 and len(r['edges'])==2 and r['edges'][0]['end_arrow'] and r['edges'][1]['start_arrow'];negative=[]
for name,s in [('macro',r'\newcommand{\x}{First}'+base),('hidden_path',base.replace('\\end{tikzpicture}',r'\path (a) edge (c);\end{tikzpicture}')),('loop',base.replace('\\end{tikzpicture}',r'\foreach \x in {1,2}{\draw (a)--(b);}\end{tikzpicture}')),('unknown_terminal',base.replace('(c);','(missing);')),('duplicate_label',base.replace('{Third}','{Second}')),('extra_segment',base.replace('{Data} (b);','{Data} (b) -- (c);')),('unknown_style',base.replace('[arrow]','[drawfoo]')),('curve',base.replace('-- (c)','to[bend left] (c)')),('style_cycle',base.replace('arrow/.style={->,thick}','arrow/.style={arrow}')),('nested_scope',base.replace('\\node[draw,fill=blue!10]',r'\begin{scope}\node[draw,fill=blue!10]')),('nonliteral_text',base.replace('{First}',r'{$\alpha$}'))]:
 try:parse_literal(s)
 except ValueError:negative.append(name)
 else:raise AssertionError('Unsupported source was silently consumed: '+name)
out={'at':now(),'ok':True,'positive_source_nodes':3,'positive_source_edges':2,'rejected_cases':negative,'scope':'Parser rejects unsupported commands/styles/labels rather than silently dropping graph semantics.'};(W/'tikz_literal_parser_tests.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
