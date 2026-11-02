"""Actual saved source proofs plus ambiguous/wrong-label/frame negative controls."""
from pathlib import Path
import collections,copy,hashlib,json,re,sqlite3,sys,uuid,xml.etree.ElementTree as E
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 from priority_datikz_execution_binding_v5 import graph_from_events
 from tikz_execution_graph import parse_events
 from datikz_source_frame_ownership_v1 import ownership
 from datikz_source_node_glyph_prefix_v1 import collect
 from tikz_literal_connectivity import Unsupported,source_text_match
 results=[];controls={}
 for raw in ['4972350fae3aa6b6abe3d600011fa3c1e8bef241d4c05d9480e7f2be22fc0d74','d33bf4c3f050929ae2907cf8c94f46be081fbe626e11d747d933c2e938982c5b']:
  root=R/'conversion/priority_datikz_source_viewport_v3/program_runs/bdda92b0e0ae42058f682bdb55efa270'/raw/'source';pins={str(p):sha(p.read_bytes())for p in[root/'source_dom.json',root/'source.svg',root/'execution/instrumented/source.iic']};dom=json.loads((root/'source_dom.json').read_bytes());graph=graph_from_events(parse_events((root/'execution/instrumented/source.iic').read_text()));element=next(e for e in E.fromstring((root/'source.svg').read_bytes()).iter()if e.get('data-tikz-physical-pdf-frame')=='1');scale=float(re.fullmatch(r'scale\(([0-9.]+)\)',element.get('transform'))[1]);matrix=[scale,0,0,scale,0,0];before=json.dumps(dom,sort_keys=True);proof=ownership(dom,graph,matrix);assert proof['all_required_named_nodes_owned'];assert proof['nodes']['AB']['kind']=='source_text_only_named_terminal';results.append(dict(raw_id=raw,proof=proof,source_pins=pins,node_kinds=dict(collections.Counter(r['kind']for r in proof['nodes'].values()))))
  def reject(name,d,g,m):
   try:ownership(d,g,m)
   except Unsupported as e:controls[raw[:12]+'_'+name]=dict(rejected=True,reason=str(e));return
   raise AssertionError('Invalid source owner accepted:'+name)
  wrong=copy.deepcopy(graph);next(n for n in wrong['nodes']if n['name']=='AB')['expanded_label_tex']='Wrong source label';reject('wrong_executed_text_label',dom,wrong,matrix)
  duplicate=copy.deepcopy(dom);ids=set(proof['nodes']['AB']['glyphs']);addition=[]
  for i,o in enumerate(duplicate['objects']):
   if o['id']in ids:q=copy.deepcopy(o);q['id']='negative_duplicate_'+str(i);q['sourceId']='negative_duplicate_block_'+str(i);addition.append(q)
  duplicate['objects']+=addition;reject('duplicate_source_glyph_group',duplicate,graph,matrix)
  wrongscale=[scale*1.01,0,0,scale*1.01,0,0];reject('wrong_physical_unit_scale',dom,graph,wrongscale)
  if raw.startswith('d33'):
   shape=next(o for o in dom['objects']if o['id']=='v3');ts,prefix=collect(shape,dom['objects']);assert source_text_match(ts,'Gene Expression Profile')and prefix['first_unowned_source_object']['id']=='v8t0';controls['gene_prefix_excludes_following_edge_annotation']=prefix
   gap=copy.deepcopy(dom['objects']);gap[3]['bbox']['y']=-100;assert collect(gap[2],gap)[0]==[];controls['outside_first_glyph_is_not_skipped']=True
  assert json.dumps(dom,sort_keys=True)==before
  for p,h in pins.items():assert sha(Path(p).read_bytes())==h
 root=R/'conversion/datikz_source_ownership_development_v1'/uuid.uuid4().hex;root.mkdir(parents=True);result=dict(root=str(root),results=results,controls=controls,new_normal_calls=0,new_QA_calls=0,source_recaptures=0,model_calls=0,candidate_qualification_claimed=False,original_source_bytes_unchanged=True)
 (root/'proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(root=str(root),proof=dict(file=str((root/'proof.json').relative_to(R)),sha256=sha((root/'proof.json').read_bytes())),actual_source_cases=len(results),negative_controls=6,glyph_boundary_controls=2,new_normal_calls=0,new_QA_calls=0,model_calls=0)))
if __name__=='__main__':main()
