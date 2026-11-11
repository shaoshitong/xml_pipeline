"""Index the full DSH transcript and measured checkpoints; no model calls."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def dump(obj):
    return json.dumps(obj,ensure_ascii=False)


def take(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(case, round_no, out):
    prefix = f'round{round_no}'
    log = case/f'{prefix}.events.jsonl'
    if not log.is_file():
        return None
    thoughts = []
    status, tools, final, usage, session = Counter(), Counter(), None, Counter(), None
    step = None
    non_events = 0
    failures = []
    for line_no, line in enumerate(log.read_text().splitlines(), 1):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            non_events += 1
            continue
        kind = e['type']
        status[kind] += 1
        if kind=='session':
            session = e['sessionId']
        elif kind=='status':
            if e['phase']=='step_start':
                step = e['step']
            if e['phase']=='step_end':
                usage.update({k:v for k,v in e.get('usage',{}).items() if isinstance(v,int)})
            status[e['phase']] += 1
        elif kind=='thinking':
            thoughts.append(dict(case=case.name,round=round_no,step=step,line=line_no,text=e['text']))
        elif kind=='tool_call':
            tools[e['tool']] += 1
        elif kind=='tool_result' and e.get('status')=='error':
            failures.append(e['result'])
        elif kind=='final':
            final = e.get('text')
    out.writelines(dump(t)+'\n' for t in thoughts)
    feedback = take(case/f'{prefix}.feedback.json')
    gold = take(case/f'{prefix}.gold_diagnostic.json')
    raw_hash = sha(log)
    code = case/f'{prefix}.drawio'
    image = case/f'{prefix}.png'
    if feedback.get('native_gate') and (sha(code)!=feedback['code_sha256'] or sha(image)!=feedback['render']['png_sha256']):
        raise ValueError(f'{case.name}/{prefix}: artifacts not bound to verification evidence')
    return dict(round=round_no,session_id=session,final_received=final is not None,turn_end_count=status['turn_end'],
                thinking_events=len(thoughts),thinking_chars=sum(len(t['text']) for t in thoughts),
                raw_log=str(log.relative_to(case.parent)),raw_log_sha256=raw_hash,non_json_cli_lines=non_events,
                tool_calls=dict(tools),tool_errors=failures,usage=dict(usage),final=final,
                xml_sha256=sha(code) if code.is_file() else None,png_sha256=sha(image) if image.is_file() else None,
                native_gate=feedback.get('native_gate'),native_error=feedback.get('error'),
                graph=feedback.get('graph'),visual=feedback.get('visual'),gold_diagnostic=gold,
                cli_exit=take(case/f'{prefix}.exit.json').get('exit_code'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root',type=Path)
    p.add_argument('--rounds',type=int,default=3)
    p.add_argument('--partial',action='store_true')
    args = p.parse_args()
    records = []
    with (args.root/'thinking.jsonl').open('w') as out:
        for case in ('002','012','013','017','022'):
            records.append(dict(case=case,rounds=[r for n in range(1,args.rounds+1)
                            if (r:=collect(args.root/case,n,out)) is not None]))
    rounds = [r for rec in records for r in rec['rounds']]
    complete = (len(rounds)==args.rounds*len(records) and
                all(r['final_received'] and r['turn_end_count']==1 and r['thinking_events'] for r in rounds))
    result = dict(complete=complete,expected_rounds=len(records)*args.rounds,observed_rounds=len(rounds),
                  native_gate_passes=sum(r['native_gate'] is True for r in rounds),
                  thinking_sha256=sha(args.root/'thinking.jsonl'),
                  thinking_events=sum(r['thinking_events'] for r in rounds),
                  thinking_chars=sum(r['thinking_chars'] for r in rounds),cases=records)
    (args.root/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(dump({k:v for k,v in result.items() if k!='cases'}))
    if not (complete or args.partial):
        raise SystemExit(1)


if __name__=='__main__':
    main()
