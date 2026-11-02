"""Complete static named TikZ families; unknown programs remain bulk-pending."""
import hashlib,json

def family(code):
 import compiler_types_source_ir_v1 as ir
 import compiler_validation_dot_ir_v2 as iso
 import tikz_literal_graph as parser
 unit,graph,evidence=ir.tikz(code,parser)
 if unit!='tikz_literal_named_graph_inventory_v1':raise ValueError('source_family_requires_complete_static_named_graph')
 value=(json.dumps(['tikz_complete_static_named_endpoint_family_v1'],sort_keys=True,separators=(',',':'))+'\n').encode()
 graph.nodes['ROOT']['signature']=hashlib.sha256(value).hexdigest()
 cluster='tikz_observed_typed_source_family_v1:'+iso.invariant(graph)
 return cluster,{cluster},evidence
