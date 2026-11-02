"""Verify supplemental recovery is bound into the final fully audited catalog."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root=Path('/backup/shaoshitong/img2code_20261029')
receipt=json.loads((root/'reports/realchart_recovery_summary.json').read_text())
catalog=json.loads((root/'reports/catalog_summary.json').read_text())
content=json.loads((root/'reports/content_audit.json').read_text())
def stamp(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
published=stamp(receipt['finished_at_utc'])
if stamp(catalog['created_at'])<published or stamp(content['finished_at'])<published:
    print(json.dumps({'status':'pending','reason':'Final catalog/content audit does not yet postdate supplemental publication.'}))
    raise SystemExit(0)
checks={}
def check(name,ok):checks[name]=bool(ok)
manifest=root/receipt['manifest']
rejected=root/receipt['rejected_manifest']
check('supplement_manifest_sha',sha(manifest)==receipt['manifest_sha256'])
check('rejection_manifest_sha',sha(rejected)==receipt['rejected_manifest_sha256'])
check('original_archive_stage_preserved',sha(root/'reports/archive_summary.json')==receipt['original_archive_report_sha256'])
for rel,digest in receipt['clean_part_sha256'].items():
    p=(root/rel).resolve()
    check('clean_part_sha:'+rel,p.is_relative_to(root) and sha(p)==digest)
supplement=[json.loads(line) for line in manifest.open() if line.strip()]
expected={(r['image_sha256'],r['code_sha256']) for r in supplement}
stats=receipt['statistics']
rejected_count=sum(1 for line in rejected.open() if line.strip())
check('candidate_accounting',len(supplement)==stats['paired_image_code']==51 and rejected_count==stats['rejected'] and len(supplement)+rejected_count==stats['raw_candidates']==10542)
check('supplement_no_duplicate_pairs',len(expected)==len(supplement))
actual=set();source_rows=0;total=0;bad=[];digest=hashlib.sha256()
with (root/'clean/manifest.jsonl').open('rb') as stream:
    for line in stream:
        digest.update(line)
        if not line.strip():continue
        row=json.loads(line);total+=1
        if row.get('source')!=receipt['source']:continue
        source_rows+=1;actual.add((row['image_sha256'],row['code_sha256']))
        if (row.get('source_manifest')!=receipt['manifest'] or row.get('recovery_report')!='reports/realchart_recovery_summary.json'
            or row.get('category')!='chart' or row.get('format')!='python'
            or row.get('image_provenance')!='synthetic_render_provided_by_dataset'
            or row.get('gold_code_provenance')!='dataset_generated_or_refined_plot_source'):
            bad.append({'clean_file':row.get('clean_file'),'clean_row':row.get('clean_row')})
check('canonical_contains_exact_supplement_pairs',actual==expected and source_rows==len(expected))
check('canonical_source_provenance',not bad)
group=catalog['groups']['provided']
check('catalog_source_count',group['sources'].get(receipt['source'])==source_rows==51)
check('catalog_total_count',group['pairs']==total)
check('global_full_content_audit_current',content.get('ok') is True and content.get('errors')==0 and not content.get('manifest_changes_during_audit') and content.get('input_manifest_sha256',{}).get('clean')==digest.hexdigest())
check('global_full_content_audit_covers_all_rows',content.get('groups',{}).get('clean',{}).get('checked')==total)
out={'observed_at_utc':datetime.now(timezone.utc).isoformat(),'ok':all(checks.values()),
     'scope':'RealChart supplemental recovery and its inclusion in the fully content-audited provided catalog; visual and overall goal acceptance remain separate.',
     'checks':checks,'failed_checks':[k for k,v in checks.items() if not v],
     'canonical_source_rows':source_rows,'provided_catalog_rows':total,
     'provided_catalog_sha256':digest.hexdigest(),'provenance_issues':bad}
(root/'reports/realchart_recovery_final_audit.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out),flush=True)
