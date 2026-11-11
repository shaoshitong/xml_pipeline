"""Resume five local DSH sessions, using HKUST3 for every verification render."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time

REPO = Path(__file__).resolve().parents[1]
DSH = Path('/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh')
PATCH = REPO/'operations/dpsk_img2code_max.patch.yml'
SSH = ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3']
SCP = ['scp','-q','-o','BatchMode=yes','-o','ConnectTimeout=8']
R = '/backup/shaoshitong/img2code_20261029'
REMOTE = R+'/conversion/dpsk_img2code_max_pilot_20261111'
SCRIPT = REMOTE+'/verify_dpsk_img2code_round_v1.py'
PYTHON = '/home/shaoshitong/anaconda3/bin/python'
INITIAL = ('Image-to-editable-draw.io reconstruction, round 1. Use your file read tool to open the local target.png as an IMAGE, not as base64 text. '
           'Do not open any files outside this case directory, use web, or seek original XML. If the image tool fails, explicitly report that and stop. '
           'From the image, inventory panels, labels, shapes, and directed edges in the visible response as a brief structured construction record (include uncertainties). '
           'Then write round1.drawio in this directory as a single uncompressed native draw.io XML document: text, shapes, connectors and groups must remain editable; '
           'never embed the input image, external resources, or a flat visual substitute. Use native geometry and explicit edge source/target references. '
           'Reproduce the image layout, connectors and readable labels as faithfully as possible. Stop after writing round1.drawio; independent rendering and feedback will follow. '
           'In the final response record concrete choices, unresolved uncertainties, and artifact filename.')


def ssh(*args):
    return subprocess.run(SSH+[shlex.join(args)],check=True,timeout=180,capture_output=True,text=True)


def scp(src, dst):
    subprocess.run(SCP+[str(src),str(dst)],check=True,timeout=90)


def events(path):
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith('{'):
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # CLI may still be writing the last line
    return rows


def wait_for_turn(path):
    until = time.monotonic()+1000
    while time.monotonic()<until:
        rows = events(path)
        if any(r.get('type') in {'final','result','error'} for r in rows):
            return rows
        time.sleep(2)
    raise TimeoutError('initial_harness_turn_did_not_end')


def model_round(d,n,prompt,sid=None):
    args = ['--session-id',sid] if sid else []
    log = d/f'round{n}.events.jsonl'
    if log.exists():
        return wait_for_turn(log)
    (d/f'round{n}.prompt.txt').write_text(prompt+'\n')
    with log.open('x') as out, (d/f'round{n}.stderr.log').open('x') as err:
        proc = subprocess.run([str(DSH),'headless','--patch',str(PATCH),'--json',*args,prompt],
                              cwd=d,stdout=out,stderr=err,timeout=1200)
    (d/f'round{n}.exit.json').write_text(json.dumps({'exit_code':proc.returncode})+'\n')
    return events(log)


def verify(d, record, n, remote_case, gold=False):
    stage = f'{remote_case}/round{n}'
    local_code = d/f'round{n}.drawio'
    feedback = d/f'round{n}.feedback.json'
    if not local_code.is_file():
        failure = {'native_gate':False,'error':'no candidate file was written by harness'}
        feedback.write_text(json.dumps(failure,indent=2)+'\n')
        return failure
    if not gold and feedback.exists():
        previous = json.loads(feedback.read_text())
        if (previous.get('native_gate') and previous.get('code_sha256')==hashlib.sha256(local_code.read_bytes()).hexdigest()
                and (d/f'round{n}.png').is_file()
                and previous['render']['png_sha256']==hashlib.sha256((d/f'round{n}.png').read_bytes()).hexdigest()):
            return previous
    ssh('mkdir','-p',stage)
    scp(local_code,f'hkust3:{stage}/candidate.drawio')
    flags = ['--compare-only','--gold',R+'/'+record['code_file'],'--gold-sha256',record['code_sha256']] if gold else []
    ssh('env','PYTHONPATH='+R+'/conversion/scripts',PYTHON,SCRIPT,'--code',stage+'/candidate.drawio',
        '--reference',R+'/'+record['image_file'],'--image-sha256',record['image_sha256'],'--out',stage,*flags)
    if gold:
        feedback = d/f'round{n}.gold_diagnostic.json'
        scp(f'hkust3:{stage}/gold_diagnostic.json',feedback)
    else:
        scp(f'hkust3:{stage}/feedback.json',feedback)
        if json.loads(feedback.read_text()).get('native_gate'):
            scp(f'hkust3:{stage}/official.png', d/f'round{n}.png')
    return json.loads(feedback.read_text())


def run(d, record, rounds, verify_only=False):
    if hashlib.sha256((d/'target.png').read_bytes()).hexdigest()!=record['image_sha256']:
        raise ValueError('local reference bytes do not match verified snapshot')
    remote_case = f'{REMOTE}/{d.name}'
    rows = model_round(d,1,INITIAL) if not verify_only else []
    sid = next((r['sessionId'] for r in rows if r.get('type')=='session'),None)
    for n in range(1,rounds+1):
        if verify_only and not any(e.get('type')=='final' for e in events(d/f'round{n}.events.jsonl')):
            continue
        if n>1 and not verify_only:
            prev = n-1
            prompt = f'''Blind reconstruction refinement round {n}. Read target.png and, if available, round{prev}.png as images, read round{prev}.feedback.json for measured errors, and inspect round{prev}.drawio if present. Use only these case files. Identify 2–5 concrete discrepancies, including visible evidence by region, and fix their editable XML elements. Preserve correct parts; prioritize missing or mislabelled nodes, misdirected edges, panel positions and font sizing over cosmetic tweaking. Scores are diagnostics, not objectives to game. If previous render failed, fix its actual XML/renderer error. Write the complete updated native XML as round{n}.drawio without overwriting previous rounds. Do not embed images, read gold XML, or use the web. Stop after writing; state what changed, which cell IDs you changed and what remains uncertain.'''
            model_round(d,n,prompt,sid)
        metrics = verify(d, record, n, remote_case)
        print(json.dumps(dict(case=d.name, round=n, native_gate=metrics.get('native_gate'),
                              visual=metrics.get('visual'),error=metrics.get('error'))),flush=True)
    for n in range(1,rounds+1):
        if (d/f'round{n}.drawio').is_file() and any(e.get('type')=='final' for e in events(d/f'round{n}.events.jsonl')):
            verify(d,record,n,remote_case,gold=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_root',type=Path)
    parser.add_argument('sample_manifest',type=Path)
    parser.add_argument('--rounds',type=int,default=3)
    parser.add_argument('--case',action='append',choices=('002','012','013','017','022'))
    parser.add_argument('--verify-only',action='store_true')
    args = parser.parse_args()
    records = {f"{r['number']:03d}":r['source_record'] for r in json.loads(args.sample_manifest.read_text())['records']}
    ssh('mkdir','-p',REMOTE)
    scp(REPO/'conversion/scripts/verify_dpsk_img2code_round_v1.py','hkust3:'+SCRIPT)
    want = hashlib.sha256((REPO/'conversion/scripts/verify_dpsk_img2code_round_v1.py').read_bytes()).hexdigest()
    if ssh('sha256sum',SCRIPT).stdout.split()[0]!=want:
        raise ValueError('deployed verifier differs from local source')
    dirs = [args.run_root.resolve()/case for case in dict.fromkeys(args.case or ('002','012','013','017','022'))]
    fails = []
    with ThreadPoolExecutor(max_workers=len(dirs)) as pool:
        jobs = {pool.submit(run,d,records[d.name],args.rounds,args.verify_only):d for d in dirs}
        for job in as_completed(jobs):
            try:
                job.result()
            except Exception as e:
                failure = {'case':jobs[job].name,'error':type(e).__name__+': '+str(e)[:800]}
                fails.append(failure)
                print(json.dumps(failure),flush=True)
    return bool(fails)


if __name__=='__main__':
    raise SystemExit(main())
