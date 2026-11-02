"""Finite systematic cases from the already seen typed development inventory."""
from pathlib import Path
import json,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_tikz_poppler_source_v2 as compiler
from compiler_tikz_quality_ro_v2 import verify
INVENTORY=W/'compiler_tikz_free_paths_v1/development/typed_graph_inventory.json'
SELECTED=['0036b5425c60a565c4de754bd9940630f0cacb14f7813e9c83eda930de1d1a7e']


def main():
 inventory=json.loads(INVENTORY.read_bytes());seen={r['id'] for r in inventory['rows']};assert set(SELECTED)<=seen
 directory=W/compiler.VERSION/'development'/('known_structural_'+uuid.uuid4().hex);directory.mkdir(parents=True,exist_ok=False);report={'source_inventory':str(INVENTORY),'source_inventory_sha256':compiler.sha(INVENTORY.read_bytes()),'unseen_consumed':0,'model_calls':0,'selected_previously_seen_ids':SELECTED,'records':[]}
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:
  for identifier in SELECTED:
   job=db.execute('select * from jobs where id=?',(identifier,)).fetchone();assert job[3]=='Y36521478Y--omnidiagram_train_sft'
   result=compiler.convert({},job,directory/identifier);item={k:v for k,v in result.items() if k not in ('record','source_reproduction')};item['id']=identifier
   if result.get('record'):
    record=result['record'];item['native_canvas_qualified']=record[compiler.FIELD]['native_canvas_qualified'];quality_work=W/'prototype/candidate_quality_ro_v1'/('tikz_final_known_'+identifier[:12]+'_'+uuid.uuid4().hex)
    quality=verify(identifier,result['record_file'],R,Path(compiler.__file__),quality_work);item.update(independent_quality_ok=quality['ok'],quality_failures=quality['failures'],quality_report=quality['evidence_file'])
   report['records'].append(item);(directory/'progress.json').write_bytes(compiler.raw(report));print(json.dumps(item,ensure_ascii=False),flush=True)
   assert db.execute('select * from jobs where id=?',(identifier,)).fetchone()==job
 (directory/'report.json').write_bytes(compiler.raw(report));print(json.dumps({'report':str(directory/'report.json')}),flush=True)

if __name__=='__main__':main()
