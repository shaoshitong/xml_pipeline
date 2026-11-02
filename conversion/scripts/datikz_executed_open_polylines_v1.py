"""Normalize executed orthogonal operations using every original straight point."""
import collections,copy,hashlib
from tikz_literal_connectivity import Unsupported
from priority_datikz_execution_binding_v5 import _softpath_points

def normalize(graph):
 result=copy.deepcopy(graph);counts=collections.Counter((e['picture'],e['path'])for e in graph['edges']);proof=[]
 for edge in result['edges']:
  if edge['operation']not in('horizontal_vertical','vertical_horizontal'):continue
  key=(edge['picture'],edge['path'])
  if counts[key]!=1:raise Unsupported('orthogonal_path_has_multiple_semantic_owners')
  soft=graph['executed_softpaths'][':'.join(key)];points=_softpath_points(soft)
  if len(points)<2:raise Unsupported('executed_orthogonal_source_path_has_no_complete_line')
  proof.append(dict(picture=key[0],path=key[1],original_executed_operation=edge['operation'],complete_original_softpath_sha256=hashlib.sha256(soft.encode()).hexdigest(),all_original_points_pt=points,no_corner_or_endpoint_synthesized=True))
  edge['operation']='line'
 result['executed_orthogonal_polyline_lowering']=proof;return result
