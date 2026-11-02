"""Corruption fixtures for the automatic source profiles; no browser required."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E
import auto_quality_source_vector_v2 as q

sha=lambda b:hashlib.sha256(b).hexdigest()


def fixture():
    xml='''<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="node_a" vertex="1" parent="1"/><mxCell id="node_b" vertex="1" parent="1"/>
<mxCell id="v1" vertex="1" parent="node_a"/><mxCell id="v2t0" vertex="1" parent="node_a" value="A"/>
<mxCell id="v3" vertex="1" parent="node_b"/><mxCell id="v4t0" vertex="1" parent="node_b" value="B"/>
<mxCell id="v5" edge="1" parent="1" source="node_a" target="node_b" style="endArrow=classic;"/>
</root></mxGraphModel></diagram></mxfile>'''
    edge={'id':'edge1','title':'A-&gt;B'}
    edge['title']='A->B'
    dom={'nodes':{'a':{'title':'A'},'b':{'title':'B'}},'issues':[],'objects':[
        {'id':'v1','node':'a','type':'shape'}, {'id':'v2t0','node':'a','type':'text','text':'A'},
        {'id':'v3','node':'b','type':'shape'}, {'id':'v4t0','node':'b','type':'text','text':'B'},
        {'id':'v5','type':'shape','tag':'path','style':{'fill':'none'},'edge':edge,'sampledPoints':[[20,10],[90,10]]},
        {'id':'v6','type':'shape','tag':'polygon','edge':edge,'bbox':{'x':86,'y':8,'w':4,'h':4}}]}
    stats={'native_graphviz_arrowheads':[{'source_arrow_object':'v6'}]}
    return dom,xml,stats


class Tests(unittest.TestCase):
    def test_positive_source_graph_and_marker(self):
        dom,xml,stats=fixture()
        self.assertTrue(q._graphviz_coverage(dom,xml,stats)['ok'])
    def test_source_graph_corruptions(self):
        dom,xml,stats=fixture()
        changes={
            'wrong_terminal':xml.replace('target="node_b"','target="node_a"'),
            'missing_text':xml.replace('value="B"','value=""'),
            'changed_text':xml.replace('value="B"','value="C"'),
            'missing_marker':xml.replace('endArrow=classic','endArrow=none'),
            'wrong_node_membership':xml.replace('id="v4t0" vertex="1" parent="node_b"','id="v4t0" vertex="1" parent="node_a"'),
            'extra_native_edge':xml.replace('</root>','<mxCell id="extra" edge="1" source="node_a" target="node_b"/></root>'),
            'standalone_arrow':xml.replace('</root>','<mxCell id="v6" vertex="1" parent="1"/></root>')}
        for name,changed in changes.items():
            with self.subTest(name=name):
                self.assertFalse(q._graphviz_coverage(dom,changed,stats)['ok'])
    def test_font_spans_preserve_logical_text(self):
        dom,xml,stats=fixture();root=E.fromstring(xml)
        for c in root.iter('mxCell'):
            if c.get('id')=='v4t0':c.set('value','<span style="font-family:embedded">B</span>')
        self.assertTrue(q._graphviz_coverage(dom,E.tostring(root,encoding='unicode'),stats)['ok'])
    def test_html_object_and_text_coverage(self):
        dom={'objects':[
            {'id':1,'type':'rect','x':0,'y':0,'w':100,'h':20,'fill':{'color':'#ffffff','opacity':1},'stroke':{'color':'#000000'},'bw':0,'opacity':1,'radius':0},
            {'id':2,'type':'text','text':'Hello','x':5,'y':2,'w':30,'h':15,'fontSize':12,'color':{'color':'#000000'},'opacity':1}]}
        xml='<mxfile><mxCell id="2" vertex="1" style="fillColor=#ffffff;fillOpacity=100;strokeColor=none;strokeWidth=0;opacity=100;"><mxGeometry x="0" y="0" width="100" height="20"/></mxCell><mxCell id="3" vertex="1" value="Hello" style="shape=text;fontSize=12;fontColor=#000000;opacity=100;"><mxGeometry x="5" y="2" width="30" height="15"/></mxCell></mxfile>'
        self.assertTrue(q._html_coverage(dom,xml,{})['ok'])
        for changed in [xml.replace('Hello','Goodbye'),xml.replace('shape=text;','shape=image;'),xml.replace('id="2"','id="7"'),xml.replace('width="100"','width="1"'),xml.replace('fillColor=#ffffff','fillColor=none'),xml.replace('opacity=100','opacity=0'),xml.replace('x="5"','x="50"')]:
            self.assertFalse(q._html_coverage(dom,changed,{})['ok'])
    def test_svg_stencil_and_geometry(self):
        from svg_convert_v2 import stencil,style
        obj={'id':'v1','type':'shape','tag':'rect','attrs':{'x':5,'y':7,'width':20,'height':10,'rx':0,'ry':0},'matrix':[1,0,0,1,0,0],'bbox':{'x':5,'y':7,'w':20,'h':10},'style':{'fill':'rgb(255, 255, 255)','stroke':'rgb(0, 0, 0)','strokeWidth':1,'fillOpacity':1,'strokeOpacity':1,'opacity':1,'linecap':'butt','linejoin':'miter','dash':'none'}}
        dom={'objects':[obj]};shape,box=stencil(obj);native_style=style(obj);native_style['shape']=shape
        root=E.Element('mxfile');cell=E.SubElement(root,'mxCell',id='v1',vertex='1',style=';'.join(k+'='+str(v) for k,v in native_style.items())+';');E.SubElement(cell,'mxGeometry',x='5',y='7',width='20',height='10');xml=E.tostring(root,encoding='unicode')
        self.assertTrue(q._paint_coverage(dom,xml)['ok'])
        for changed in [xml.replace(shape,'rectangle'),xml.replace('width="20"','width="1"'),xml.replace('fillColor=#ffffff','fillColor=none')]:
            self.assertFalse(q._paint_coverage(dom,changed)['ok'])
    def test_decorative_classification_rejects_arrows(self):
        basic={'id':'v1','type':'shape','tag':'rect','bbox':{'w':30,'h':20}}
        self.assertTrue(q._decorative_profile({'objects':[basic]})['ok'])
        for mutation in [{'tag':'path'},{'tag':'line'},{'markerEnd':'url(#arrow)'},{'bbox':{'w':100,'h':1}}]:
            self.assertFalse(q._decorative_profile({'objects':[{**basic,**mutation}]})['ok'])
    def test_html_original_asset_bytes_and_paint(self):
        import io
        from PIL import Image
        buf=io.BytesIO();Image.new('RGB',(2,2),'blue').save(buf,format='PNG');blob=buf.getvalue();encoded=base64.b64encode(blob).decode()
        dom={'objects':[{'id':1,'type':'image','loaded':True,'src':'data:image/png;base64,'+encoded,'x':0,'y':0,'w':20,'h':20,'opacity':1},{'id':2,'type':'text','text':'Hello','x':5,'y':22,'w':30,'h':15,'fontSize':12,'color':{'color':'#000000'},'opacity':1}]}
        xml='<mxfile><mxCell id="2" vertex="1" style="shape=image;image=data:image/png,'+encoded+';opacity=100;"><mxGeometry x="0" y="0" width="20" height="20"/></mxCell><mxCell id="3" vertex="1" value="Hello" style="shape=text;fontSize=12;fontColor=#000000;opacity=100;"><mxGeometry x="5" y="22" width="30" height="15"/></mxCell></mxfile>'
        self.assertTrue(q._html_coverage(dom,xml,{})['ok'])
        self.assertFalse(q._html_coverage(dom,xml.replace(encoded,base64.b64encode(blob+b'changed').decode()),{})['ok'])
        self.assertFalse(q._html_coverage(dom,xml.replace('shape=image','shape=rectangle'),{})['ok'])
    def test_actual_css_paint_order_gate(self):
        dom={'objects':[{'id':1,'type':'text','x':0,'y':0,'w':20,'h':20},{'id':2,'type':'text','x':5,'y':5,'w':20,'h':20}],'_source_paint_order':{'1':1,'2':2}}
        xml='<mxfile><mxCell id="2"/><mxCell id="3"/></mxfile>'
        self.assertTrue(q._html_paint_order(dom,xml)['ok'])
        dom['_source_paint_order']={'1':2,'2':1}
        self.assertFalse(q._html_paint_order(dom,xml)['ok'])
        dom['_source_paint_order']={'1':2,'2':2}
        self.assertFalse(q._html_paint_order(dom,xml.replace('id="2"','id="9"').replace('id="3"','id="2"').replace('id="9"','id="3"'))['ok'])
        dom['objects'][1]['x']=50
        self.assertTrue(q._html_paint_order(dom,xml)['ok'])
    def test_css_snapshot_identity_mapping(self):
        dom={'qaElementCount':2,'objects':[{'id':1,'type':'text','qaOwner':1,'qaOwnerTag':'DIV'}]}
        snapshot={'strings':['HTML','DIV','#text'],'documents':[{'nodes':{'nodeType':[1,1,3],'nodeName':[0,1,2],'parentIndex':[-1,0,1]},'layout':{'nodeIndex':[0,1,2],'paintOrders':[1,2,2]}}]}
        self.assertEqual(q._snapshot_paint_orders(dom,snapshot),{'1':2})
        snapshot['documents'][0]['nodes']['nodeName'][1]=0
        with self.assertRaises(AssertionError):q._snapshot_paint_orders(dom,snapshot)
    def test_revision_and_source_hash_guards(self):
        dom,xml,stats=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'clean').mkdir();(root/'clean/source.svg').write_bytes(b'<svg/>')
            record={'source_format':'svg','original_source_code':'clean/source.svg','source_code_sha256':sha(b'<svg/>'),'code_sha256':sha(xml.encode())}
            with patch.object(q,'R',root):
                self.assertEqual(q._identity(record,xml),b'<svg/>')
                with self.assertRaises(AssertionError):q._identity(record,xml+' ')
                (root/'clean/source.svg').write_bytes(b'<svg>changed</svg>')
                with self.assertRaises(AssertionError):q._identity(record,xml)
    def test_unsupported_not_silently_accepted(self):
        self.assertFalse(q.check_vector_profile({'source_format':'plantuml'},'')['ok'])
        result=q.check_vector_profile({'source_format':'html','category':'scientific_diagram'},'')
        self.assertFalse(result['supported']);self.assertFalse(result['ok'])

if __name__=='__main__':unittest.main()
