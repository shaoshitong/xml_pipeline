"""Stream atomically published first-round files; never locks its SQLite ledger."""
import collections,datetime,hashlib,json
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';FIRST=R/'release/fixed_batch_v1/initial_screen_20261031_1717'
def classify(r):
 text=json.dumps(r.get('detail') or r.get('quality_failures') or r.get('reason'),ensure_ascii=False)
 if 'actual_font_portability_requires_embedding' in text:return 'font_embedding'
 if any(s in text for s in ['source_profile_not_implemented','unsupported_source_graph_profile']):return 'source_semantic_profile_not_supported'
 if any(s in text for s in ['Native content requires full tight canvas','registration','reference_canvas','unsupported_native_canvas','outside_reference_canvas','outside_page','canvas']):return 'canvas_or_bounds'
 if any(s in text for s in ['missing_attached_native_marker','remains_standalone','connector_missing_native_edge','source_arrow','source_native_connector_path']):return 'source_connector_or_marker'
 if any(s in text for s in ['source_coverage_failure','source_object','poster_object','paint_style','css_paint_order','unsupported_fresh_source_features']):return 'source_object_or_paint_coverage'
 if 'invalid_editable_structure' in text:return 'editable_structure'
 if 'raster_anomaly' in text:return 'visual_alignment'
 if 'missing_cached_dependencies' in text:return 'cached_dependencies_missing'
 if r.get('phase')=='conversion':return 'other_conversion_failure'
 return r.get('reason','untyped_failure')
def selector(r):
 text=json.dumps(r.get('detail') or r.get('quality_failures') or '',ensure_ascii=False)
 actions=[]
 if any(s in text for s in ['source_coverage_failure','source_arrow','source_connector','source_object','poster_object','paint_style','css_paint_order','unsupported_fresh_source_features']):actions.append('source')
 if 'actual_font_portability_requires_embedding' in text:actions.append('font')
 if any(s in text for s in ['Native content requires full tight canvas','registration','reference_canvas','unsupported_native_canvas','outside_reference_canvas','outside_page','canvas']):actions.append('canvas')
 return actions
def main():
 source={}
 for line in (FIRST/'input_order.jsonl').open():
  r=json.loads(line);source[r['id']]=r
 assert len(source)==131904
 path=FIRST/('failed.jsonl' if (FIRST/'summary.json').exists() else 'inprogress.failed.jsonl');h=hashlib.sha256();groups=collections.Counter();reasons=collections.Counter();examples={};targets=collections.Counter();ids=set()
 outdir=W/'round2_v1';outdir.mkdir(exist_ok=True);snapshot=outdir/'failure_inventory_snapshot.jsonl';temp=snapshot.with_suffix('.tmp')
 with path.open('rb') as f,temp.open('wb') as out:
  for line in f:
   h.update(line);r=json.loads(line);i=r['id'];assert i not in ids;ids.add(i);s=source[i];assert (r.get('source_code_sha256'),r.get('source_image_sha256'))==(s['source_code_sha256'],s['source_image_sha256'])
   group=classify(r);key=(s['format'],r.get('phase','unknown'),group);groups[key]+=1;reasons[r.get('reason')]+=1;actions=selector(r)
   examples.setdefault('|'.join(key),[])
   if len(examples['|'.join(key)])<3:examples['|'.join(key)].append({'id':i,'evidence_directory':r.get('evidence_directory'),'quality_report':r.get('quality_report'),'detail':r.get('detail')})
   targets[','.join(actions) or 'no_current_generic_fix']+=1
   out.write((json.dumps({'id':i,'seq':s['seq'],'format':s['format'],'category':s['category'],'group':group,'actions':actions,'first_result':r},ensure_ascii=False)+'\n').encode())
 temp.replace(snapshot)
 result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_total':len(source),'first_run_live_snapshot':not(FIRST/'summary.json').exists(),'failed_index':str(path.relative_to(R)),'failed_index_sha256':h.hexdigest(),'failed_records':len(ids),'groups':[{'format':k[0],'phase':k[1],'group':k[2],'count':v} for k,v in groups.most_common()],'reasons':dict(reasons),'action_route_counts':dict(targets),'examples':examples,'snapshot':str(snapshot.relative_to(R)),'model_calls':0}
 (outdir/'failure_inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='examples'},ensure_ascii=False))
if __name__=='__main__':main()
