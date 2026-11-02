import importlib.util,unittest,sys
from pathlib import Path
D=Path(__file__).parent
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('types_ir',D/'compiler_types_source_ir_v1.py');iso=load('iso',D/'compiler_validation_dot_ir_v2.py');a=load('auditor',D/'compiler_types_unseen_audit_v1.py');old=load('old',D/'round2_heldout_select_v1.py');nat=load('nat',D.parent/'compiler_native_languages_v1.py' if (D.parent/'compiler_native_languages_v1.py').exists() else D/'compiler_native_languages_v1.py')
XML='<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="A" vertex="1" parent="1" value="Alpha" style="ellipse"/><mxCell id="B" vertex="1" parent="1" value="Beta" style="rectangle"/><mxCell id="C" vertex="1" parent="1" style="diamond"/><mxCell id="E" edge="1" parent="1" source="A" target="B"/></root></mxGraphModel>'
class SourceIRTests(unittest.TestCase):
 def eq(self,g,h):return iso.equivalent(g,h)
 def test_native_node_label_and_ID_alpha(self):
  b=XML.replace('"A"','"renamed"').replace('Alpha','Long changed text').replace('Beta','Other')
  self.assertTrue(self.eq(m.native(XML,old)[1],m.native(b,old)[1]))
 def test_native_real_topology_not_all_REF(self):
  self.assertFalse(self.eq(m.native(XML,old)[1],m.native(XML.replace('target="B"','target="C"'),old)[1]))
 def test_native_parent_group_preserved(self):
  self.assertFalse(self.eq(m.native(XML,old)[1],m.native(XML.replace('id="C" vertex="1" parent="1"','id="C" vertex="1" parent="A"'),old)[1]))
 def test_native_named_ports_resolved(self):
  good=XML.replace('id="E" edge=', 'id="E" style="sourcePort=C;" edge=')
  self.assertFalse(self.eq(m.native(XML,old)[1],m.native(good,old)[1]));self.assertRaises(ValueError,m.native,good.replace('sourcePort=C','sourcePort=missing'),old)
 def test_native_style_preserved(self):self.assertFalse(self.eq(m.native(XML,old)[1],m.native(XML.replace('style="ellipse"','style="ellipse;fillColor=red"'),old)[1]))
 def test_mermaid_complete_style_and_graph(self):
  x='flowchart LR\nA[Alpha]-->B[Beta]\nstyle A fill:red'
  y='flowchart LR\nX[Different]-->Y[Longer text]\nstyle X fill:red'
  self.assertTrue(self.eq(m.language(x,'mermaid',nat)[1],m.language(y,'mermaid',nat)[1]));self.assertRaises(ValueError,m.language,x+'\nunsupported command','mermaid',nat)
 def test_mermaid_style_not_ignored(self):
  x='flowchart LR\nA[Alpha]-->B[Beta]\nstyle A fill:red';self.assertFalse(self.eq(m.language(x,'mermaid',nat)[1],m.language(x.replace('fill:red','fill:blue'),'mermaid',nat)[1]))
 def test_plantuml_complete_program(self):
  x='@startuml\ncomponent "A" as A\nrectangle "B" as B\nA --> B\n@enduml';self.assertEqual(m.language(x,'plantuml',nat)[2]['edges'],1);self.assertRaises(ValueError,m.language,x.replace('A --> B','skinparam note red'),'plantuml',nat)
 def test_svg_role_topology_label_alpha(self):
  x='<svg><g class="node" id="n"><title>A</title><rect/><text>One</text></g><g class="node" id="m"><title>B</title><ellipse/></g><g class="edge"><title>A-&gt;B</title><path d="M1 2 L3 4"/></g></svg>';y=x.replace('>A<','>X<').replace('>B<','>Y<').replace('A-&gt;B','X-&gt;Y').replace('One','Different');self.assertTrue(self.eq(m.svg(x)[1],m.svg(y)[1]))
 def test_svg_without_roles_unknown(self):self.assertRaises(ValueError,m.svg,'<svg><path d="M0 0L1 1"/></svg>')
 def test_html_DOM_multiplicity_preserved(self):
  x='<html><body><div>A</div></body></html>';y='<html><body><div>A</div><div>B</div></body></html>';self.assertFalse(self.eq(m.html_ir(x)[1],m.html_ir(y)[1]))
 def test_html_label_ID_alpha_with_CSS(self):
  x='<html><style>#a {color:red}</style><body><div id="a">Text</div></body></html>';y=x.replace('#a','#renamed').replace('id="a"','id="renamed"').replace('>Text<','>Changed<');self.assertTrue(self.eq(m.html_ir(x)[1],m.html_ir(y)[1]))
 def test_html_dynamic_unknown(self):self.assertRaises(ValueError,m.html_ir,'<html><canvas></canvas></html>')
 def test_tikz_closedbasic_static_not_compile(self):
  x=r'\begin{tikzpicture}\draw (0,0) rectangle (1,1);\end{tikzpicture}';u,g,e=m.closed_basic(x);self.assertTrue(e['static_only']);self.assertFalse(e['source_compilation_proven'])
 def test_tikz_openpaint_not_closedbasic(self):self.assertRaises(ValueError,m.closed_basic,r'\begin{tikzpicture}\draw (0,0)--(1,1);\end{tikzpicture}')
 def test_fixed_pool_order_and_code_duplicates_excluded(self):
  rr=[{'id':str(i).zfill(64),'format':'svg','source_code_sha256':str(i),'source_image_sha256':'i'+str(i)} for i in range(800)];x,_=a.pool(rr,set(),{'1'},set());y,_=a.pool(list(reversed(rr)),set(),{'1'},set());self.assertEqual([r['id'] for r in x['svg']],[r['id'] for r in y['svg']]);self.assertEqual(len(x['svg']),500);self.assertNotIn(str(1).zfill(64),{r['id'] for r in x['svg']})
if __name__=='__main__':unittest.main()
