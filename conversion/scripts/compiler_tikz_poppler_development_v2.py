"""Finite original-source native compiler probe on the same two seen cases."""
from pathlib import Path
import json,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_tikz_poppler_source_v2 as compiler
from compiler_tikz_quality_ro_v2 import verify
INPUT=W/'compiler_tikz_free_paths_v1/development/46015474892e4c8c84668e50a86ae648/report.json'
SEEN={'0002d1280db280c2d9227e7d2188cd20f0cbc446310f112772df3d9b62cca423','0036b5425c60a565c4de754bd9940630f0cacb14f7813e9c83eda930de1d1a7e'}

def main():
 folder=W/compiler.VERSION/'development'/uuid.uuid4().hex;folder.mkdir(parents=True,exist_ok=False);report={'unseen_consumed':0,'model_calls':0,'records':[]}
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:
  for old in json.loads(INPUT.read_bytes())['results']:
   if old['id'] not in SEEN:continue
   j=db.execute('select * from jobs where id=?',(old['id'],)).fetchone();record=json.loads(Path(old['record_file']).read_bytes());result=compiler.convert(record,j,folder/old['id']);item={k:v for k,v in result.items() if k not in ('record','source_reproduction')};item['id']=old['id']
   if result.get('source_reproduction'):item['source_reproduction']={k:v for k,v in result['source_reproduction'].items() if k!='visual'};item['source_reference_quality']={k:v for k,v in result['source_reproduction'].get('visual',{}).items() if k!='worst_text_regions'}
   if result.get('record'):
    rr=result['record'];stats=json.loads((R/rr[compiler.FIELD]['files']['source_stats']['file']).read_bytes());item['source_actual_PDF_to_SVG_quality']={k:v for k,v in stats['actual_PDF_to_SVG_quality'].items() if k!='worst_text_regions'};item['glyph_anchor_corrections']=len(stats['glyph_anchor_corrections']);item['native_canvas_qualified']=rr[compiler.FIELD]['native_canvas_qualified']
    quality_work=W/'prototype/candidate_quality_ro_v1'/('tikz_pdftex_v2_'+old['id'][:12]+'_'+uuid.uuid4().hex)
    quality=verify(old['id'],result['record_file'],R,Path(compiler.__file__),quality_work)
    item.update(independent_quality_ok=quality['ok'],quality_failures=quality['failures'],quality_report=quality['evidence_file'])
   report['records'].append(item);(folder/'progress.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(item,ensure_ascii=False),flush=True)
   assert db.execute('select * from jobs where id=?',(old['id'],)).fetchone()==j
 (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'report':str(folder/'report.json')}),flush=True)

if __name__=='__main__':main()
