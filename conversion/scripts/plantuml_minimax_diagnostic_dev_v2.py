"""Finite two already-consumed source/paint diagnostics, no acceptance."""
import json,sys,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'));sys.path.append(str(W/'prototype'))

def main():
 import compiler_plantuml_natural_candidate_v7 as c
 from plantuml_marker_minimax_v1 import classic
 base=W/'compiler_plantuml_natural_candidate_v7/development/cfcc53b6bef448e2aa16cfbe581b97a8';out=W/'plantuml_minimax_diagnostic_dev_v2'/uuid.uuid4().hex;out.mkdir(parents=True);results=[]
 for summary in sorted(base.glob('*/summary.json')):
  item=json.loads(summary.read_text());record=json.loads(Path(item['candidate_record']).read_text());parent=(R/record['code_file']).parent;data=c._source_data(json.loads((parent/'source_proof.json').read_text()));xml=(R/record['code_file']).read_text();row={'id':record['id'],'source_fits':[]}
  paths=[p for p in data['dom']['objects'] if p.get('edge') and p['tag']=='path']
  for head in [o for o in data['dom']['objects'] if o.get('edge') and o['tag']=='polygon']:
   path=next(p for p in paths if p['edge']['id']==head['edge']['id']);trace=[];fit=classic(head,path['sampledPoints'],'end',diagnostic=trace);row['source_fits'].append({'source_arrow':head['id'],'fit':fit,'trace':trace})
  try:match=c._match_candidate(data['dom'],data['metadata'],xml);marker=c._marker_gate(data,xml,match,(R/record['image_file']).read_bytes(),json.loads((parent/'source_proof.json').read_text())['reference_size']);row['marker']=marker
  except Exception as error:row['marker_error']=str(error)
  results.append(row);(out/'progress.json').write_bytes(c.raw(results));print(json.dumps({'id':row['id'],'fits':[{'source_arrow':r['source_arrow'],'ok':r['fit'] is not None,'trace':r['trace'] if r['fit'] is None else None} for r in row['source_fits']],'marker_ok':row.get('marker',{}).get('ok'),'marker_error':row.get('marker_error'),'raster_markers':row.get('marker',{}).get('markers'),'closed_paint':[m['continuous_full_paint_certificate'] for m in row.get('marker',{}).get('actual_full_closed_marker_paint_and_editing',{}).get('markers',[])]}),flush=True)
 report={'schema':'plantuml_source_and_actual_paint_diagnostic_v2','results':results,'samples_accepted':0,'new_heldout_consumed':0,'model_calls':0};(out/'report.json').write_bytes(c.raw(report));print(json.dumps({'report':str(out/'report.json')}),flush=True)

if __name__=='__main__':main()
