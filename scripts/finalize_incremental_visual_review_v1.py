"""Bind recorded actual-PNG decisions to immutable, hash-checked review inputs."""
from pathlib import Path
import argparse, hashlib, json, uuid
R=Path('/backup/shaoshitong/img2code_20261029')
def asset(p):
    return dict(file=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--decisions',type=Path,required=True);a=p.parse_args()
    summary=json.loads((a.input/'summary.json').read_bytes())
    for key in ['pairs','occlusion']: assert asset(R/summary[key]['file'])==summary[key]
    rows=[json.loads(x)for x in(R/summary['pairs']['file']).read_text().splitlines()]
    decisions=json.loads(a.decisions.read_bytes());assert set(decisions)=={r['id']for r in rows}
    for r in rows:
        decision=decisions[r['id']];assert decision['actual_native_PNG_inspected'] and decision['note'].strip()
        assert r['full_eight_quality_reverified']
        assert asset(R/r['quality_report']['file'])==r['quality_report']
        layout=r['paired_native_text_layout'];assert asset(R/layout['native_render']['file'])==layout['native_render']
        if decision['approved']:
            assert not layout['needs_content_review'] and not r['source_content_visibility']['labels']
        r.update(approved_for_strict_main=decision['approved'],direct_native_PNG_visual_inspection=True,visual_note=decision['note'],visual_value_status='approved_complete_complex_research_content'if decision['approved']else'hold_source_value_or_layout')
    output=a.input.parent/('actual_PNG_incremental_'+uuid.uuid4().hex);output.mkdir()
    pairs=output/'reviewed_pairs.jsonl';pairs.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in rows))
    (output/'decisions.json').write_bytes(a.decisions.read_bytes())
    result=dict(root=str(output),pairs=asset(pairs),occlusion=summary['occlusion'],input_summary=asset(a.input/'summary.json'),decisions=asset(output/'decisions.json'),approved_ids=[r['id']for r in rows if r['approved_for_strict_main']],held_ids=[r['id']for r in rows if not r['approved_for_strict_main']],actual_native_PNG_inspected_ids=[r['id']for r in rows],technical_qualifications_unchanged=True,new_normal_calls=0,new_QA_calls=0,model_calls=0)
    (output/'summary.json').write_text(json.dumps(result,indent=2))
    for f in output.iterdir():f.chmod(0o444)
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
