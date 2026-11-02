"""Source-only Python templates and typed DOT topology; never layout/render."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess

W=Path('/backup/shaoshitong/img2code_20261029/conversion')
DOT=W/'runtime/graphviz/bin/dot'
VERSION='python_ast_and_actual_dot_semantic_family_v1'


def raw(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def sha(value):return hashlib.sha256(value).hexdigest()


def parse_dot(dot):
    if not isinstance(dot,bytes)or len(dot)>4*1024*1024:raise ValueError('source_DOT_budget_or_type')
    runtime=W/'runtime/graphviz'
    process=subprocess.run([str(DOT),'-Tdot_json'],input=dot,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,
                           env={**os.environ,'LD_LIBRARY_PATH':str(runtime/'lib'),'GVBINDIR':str(runtime/'lib/graphviz'),
                                'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
    if process.returncode:raise ValueError('source_DOT_syntax_parse_failed:'+process.stderr.decode(errors='replace')[:250])
    if len(process.stdout)>16*1024*1024:raise ValueError('source_DOT_JSON_budget')
    document=json.loads(process.stdout)
    if 'bb'in document or any(any(key.endswith('draw_')for key in obj)for obj in [document]+document.get('objects',[])+document.get('edges',[])):
        raise ValueError('syntax_only_DOT_parser_must_not_create_layout_or_drawing')
    return document,process.stdout


def explicit_nonpainting_profile(document):
    def invisible(obj):return 'invis'in {x.strip()for x in str(obj.get('style','')).split(',')}
    subcount=int(document.get('_subgraph_cnt',0));nodes=document.get('objects',[])[subcount:]
    edges=document.get('edges',[]);nonpaint=[e for e in edges if invisible(e)]
    if not nonpaint:raise ValueError('source_has_no_explicit_invisible_edge')
    if any(invisible(n)for n in nodes):raise ValueError('source_invisible_nodes_outside_current_handler')
    return dict(explicit_nonpainting_source_edges=len(nonpaint),visible_source_edges=len(edges)-len(nonpaint),
                source_nodes=len(nodes),source_subgraphs=subcount,syntax_only_without_layout=True)


def python_template(code):
    from compiler_validation_cluster_audit_v1 import ProgramSkeleton
    if len(code.encode())>4*1024*1024:raise ValueError('source_Python_budget')
    template=ast.dump(ProgramSkeleton().visit(ast.parse(code)),include_attributes=False)
    return 'python_graphviz_AST_template_v1:'+sha(template.encode())


def family(code,document):
    import compiler_validation_dot_ir_v2 as typed
    template_key=python_template(code)
    graph=typed.typed_graph(document)
    dot_key='python_graphviz_actual_DOT_semantic_v1:'+typed.invariant(graph)
    evidence=dict(method=VERSION,actual_DOT_semantics=True,Python_AST_template_sha256=template_key.rsplit(':',1)[1],
                  DOT_typed_invariant=typed.invariant(graph),typed_nodes=graph.number_of_nodes(),typed_relations=graph.number_of_edges(),
                  topology_direction_multiplicity_ports_shapes_styles_fonts_dimensions_clusters_preserved=True,
                  labels_and_arbitrary_IDs_normalized=True,
                  invariant_collision_policy='Conservatively merge; never split an equivalent typed DOT family.',
                  hidden_generator_independence_proven=False)
    return dot_key,{dot_key,template_key},evidence
