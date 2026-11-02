"""Finite editing-only diagnosis on two already source-verified seen cases."""
from pathlib import Path
import hashlib,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
from tikz_native_free_v1 import audit
INPUT=W/'compiler_tikz_poppler_source_v2/development/55df941c120648e98181d568b73fb30e/report.json'

def main():
 target=W/'compiler_tikz_poppler_source_v2/development'/('actual_editing_'+uuid.uuid4().hex);target.mkdir(parents=True,exist_ok=False);out=[]
 for row in json.loads(INPUT.read_bytes())['records']:
  raw=Path(row['record_file']).read_bytes();record=json.loads(raw);qa=json.loads(Path(row['quality_report']).read_bytes());assert qa['input_record_sha256']==hashlib.sha256(raw).hexdigest();source=qa['checks']['source'];assert source['ok'] and source['evidence']['complete_source_coverage']
  try:
   result=audit((R/record['code_file']).read_text(),record=record,source_profile=source);(target/(row['id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');item={'id':row['id'],'ok':result['ok'],'vertices':result['vertex_count'],'connector_sides':len(result['moves'])}
  except Exception as error:item={'id':row['id'],'ok':False,'error_type':type(error).__name__,'reason':str(error)}
  out.append(item);print(json.dumps(item),flush=True)
 (target/'report.json').write_text(json.dumps({'records':out,'new_qualification_claimed':False,'unseen_consumed':0,'model_calls':0},indent=2)+'\n');print(json.dumps({'report':str(target/'report.json')}),flush=True)

if __name__=='__main__':main()
