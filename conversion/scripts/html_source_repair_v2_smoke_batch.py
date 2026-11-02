"""Read-only bounded cohort smoke. Writes versioned proposals, never jobs/canonical data."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import traceback
import auto_quality_source_vector_v2 as q
from html_source_repair_v2 import propose
sha=lambda b:hashlib.sha256(b).hexdigest()


def candidate(item):
    id,raw,kind=item;began=time.monotonic();record=json.loads(raw)
    work=q.W/'html_source_repair_v2_cohort_smoke'/id/record['code_sha256'];work.mkdir(parents=True,exist_ok=True)
    result={'id':id,'kind':kind,'input_code_sha256':record['code_sha256'],'record_sha256':sha(raw.encode()),'work':str(work.relative_to(q.R)),'accepted':False,'canonical_changed':False}
    try:
        xml=q._read_clean(record['code_file'],record['code_sha256']).decode();new,proof=propose(record,xml,work)
        (work/'baseline_record.json').write_text(raw);(work/'candidate.drawio').write_text(new);(work/'proposal.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
        result.update(state='source_verified_proposal',output_code_sha256=proof['output_code_sha256'],added_text_fragments=len(proof['new_editable_text_fragments']),paint_order_changed=proof['paint_order_changed'],source_clips_required=proof['added_text_source_clips']['required'])
    except Exception as error:
        result.update(state='repair_profile_failed',error=repr(error));(work/'traceback.txt').write_text(traceback.format_exc())
    result['seconds']=round(time.monotonic()-began,3);(work/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--per-kind',type=int,default=6);parser.add_argument('--workers',type=int,default=2);args=parser.parse_args()
    database=sqlite3.connect(f'file:{q.W}/jobs.sqlite?mode=ro',uri=True)
    rows=database.execute('''select distinct j.id,j.output_record,e.reason from jobs j join auto_quality_exceptions_v1 e on e.id=j.id and e.code_hash=json_extract(j.output_record,'$.code_sha256') and e.image_hash=json_extract(j.output_record,'$.image_sha256') where j.format='html' and j.worker_pid is null and j.state in ('rendered','needs_quality_repair','harness_review_pending') and (e.reason like '%word_spans_multiple_lines%' or e.reason like '%overlapping_source_css_paint_order_changed%') order by j.id''').fetchall()
    selected=[];counts={'wrapped_word':0,'paint_order':0};seen=set()
    for id,raw,reason in rows:
        if id in seen:continue
        kind='wrapped_word' if 'word_spans_multiple_lines' in reason else 'paint_order'
        if counts[kind]>=args.per_kind:continue
        selected.append((id,raw,kind));seen.add(id);counts[kind]+=1
    started=time.monotonic();results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(candidate,item) for item in selected]
        for future in concurrent.futures.as_completed(futures):
            result=future.result();results.append(result);print(json.dumps(result),flush=True)
    summary={'at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'selected':counts,'results':results,'elapsed_seconds':time.monotonic()-started,'canonical_changed':False,'jobs_changed':False,'accepted':0}
    (q.W/'html_source_repair_v2_cohort_smoke.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'summary':str((q.W/'html_source_repair_v2_cohort_smoke.json').relative_to(q.R)),'selected':counts,'source_verified_proposals':sum(r['state']=='source_verified_proposal' for r in results),'failed_proposals':sum(r['state']!='source_verified_proposal' for r in results),'elapsed_seconds':summary['elapsed_seconds'],'jobs_changed':False}),flush=True)

if __name__=='__main__':main()
