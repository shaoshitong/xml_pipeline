"""Case-local file queue; only HKUST3 runs the renderer/metrics."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time

R='/backup/shaoshitong/img2code_20261029'
PY='/home/shaoshitong/anaconda3/bin/python'
S=R+'/conversion/scripts'
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=6','hkust3']
SCP=['scp','-q','-o','BatchMode=yes','-o','ConnectTimeout=6']


def ssh(*args):
    return subprocess.run(SSH+[shlex.join(args)],text=True,capture_output=True,check=True,timeout=135).stdout


def scp(src,dst):
    subprocess.run(SCP+[str(src),str(dst)],capture_output=True,check=True,timeout=30)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path,value):
    stage=path.with_suffix('.tmp')
    stage.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    stage.replace(path)


def name_ok(name):
    return isinstance(name,str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,40}\.drawio',name) is not None


def main():
    p=argparse.ArgumentParser()
    p.add_argument('case',type=Path)
    p.add_argument('remote',help='isolated run directory below conversion')
    p.add_argument('--limit',type=int,default=6)
    p.add_argument('--idle-timeout',type=int,default=1200)
    p.add_argument('--cached-seed',type=Path,help='seed proof, render and precomputed localization from HKUST3')
    args=p.parse_args()
    c=args.case.resolve()
    q=c/'visual_checks'; q.mkdir(exist_ok=True)
    remote=args.remote
    if not re.fullmatch(re.escape(R+'/conversion/')+r'[a-zA-Z0-9_/-]+',remote) or '..' in remote:
        p.error('invalid isolated remote directory')
    target_sha=sha(c/'target.png')
    verify_src=Path(__file__).resolve().parents[1]/'conversion/scripts/verify_dpsk_img2code_round_v1.py'
    locate_src=verify_src.with_name('patch_mse_focus_v1.py')
    cache=args.cached_seed
    setup_complete=False
    if cache:
        cache_proof=json.loads((cache/'render_feedback.json').read_text())
        cache_localize=json.loads((cache/'patch_feedback.json').read_text())
        if not (cache_proof.get('native_gate') and cache_proof['target_sha256']==target_sha and
                cache_proof['code_sha256']==sha(c/'seed.drawio') and cache_proof['render']['png_sha256']==sha(cache/'candidate.png')):
            raise ValueError('cached seed does not match input hashes')

    def setup():
        nonlocal setup_complete
        if setup_complete:
            return
        ssh('mkdir','-p',remote)
        scp(c/'target.png','hkust3:'+remote+'/target.png')
        for src in (verify_src,locate_src):
            scp(src,'hkust3:'+remote+'/'+src.name)
            if ssh('sha256sum',remote+'/'+src.name).split()[0]!=sha(src):
                raise ValueError('deployed source hash mismatch')
        if cache:
            ssh('mkdir','-p',remote+'/cached_seed/render',remote+'/cached_seed/locate')
            scp(cache/'candidate.png','hkust3:'+remote+'/cached_seed/render/official.png')
            scp(cache/'patch_feedback.json','hkust3:'+remote+'/cached_seed/locate/patch_feedback.json')
        setup_complete=True

    if not cache:
        setup()
    done={}; used=0; deadline=time.monotonic()+args.idle_timeout
    print(json.dumps({'state':'ready','limit':args.limit,'target_sha256':target_sha}),flush=True)
    while time.monotonic()<deadline:
        if (c/'service.stop').is_file():
            break
        for job in sorted(q.glob('*.request.json'),key=lambda path:path.stat().st_mtime):
            reply=job.with_name(job.name.replace('.request.','.reply.'))
            token=job.name.split('.',1)[0]
            if reply.exists() or not re.fullmatch(r'[a-f0-9]{20}',token):
                continue
            request=json.loads(job.read_text()); candidate=request.get('candidate'); against=request.get('against')
            outcome={'ok':False,'candidate':candidate,'against':against}
            try:
                if not name_ok(candidate) or (against is not None and (not name_ok(against) or against not in done)):
                    raise ValueError('checkpoint or comparison baseline is invalid or not previously rendered')
                if not done and candidate!='seed.drawio':
                    raise ValueError('render seed.drawio first')
                if candidate in done:
                    raise ValueError('checkpoint already rendered; use a new filename for a new version')
                f=c/candidate
                if f.is_symlink() or f.stat().st_size>2_000_000 or sha(f)!=request.get('sha256'):
                    raise ValueError('checkpoint changed or is not an allowed file')
                if used>=args.limit:
                    raise ValueError('render budget exhausted; choose among measured checkpoints')
                stage=f'{remote}/{token}'
                folder=q/token; folder.mkdir(exist_ok=True)
                previous=None
                if cache and candidate=='seed.drawio':
                    if cache_proof['code_sha256']!=request['sha256']:
                        raise ValueError('cached seed cannot be modified')
                    used+=1
                    stage=remote+'/cached_seed'
                    proof,fresh=cache_proof,cache_localize
                    for k in ['overview','candidate']+[x['id'] for x in fresh['patches']]:
                        shutil.copyfile(cache/(k+'.png'),folder/(k+'.png'))
                else:
                    setup()
                    ssh('mkdir','-p',stage)
                    scp(f,'hkust3:'+stage+'/input.drawio')
                    used+=1
                    proof=json.loads(ssh('env','PYTHONPATH='+S,PY,remote+'/'+verify_src.name,'--code',stage+'/input.drawio',
                        '--reference',remote+'/target.png','--image-sha256',target_sha,'--out',stage+'/render'))
                    if not proof.get('native_gate'):
                        raise ValueError('native renderer rejected XML: '+proof.get('error','unknown error'))
                    alignment=['--alignment-from',done['seed.drawio']+'/locate/patch_feedback.json'] if done else []
                    fresh=json.loads(ssh(PY,remote+'/'+locate_src.name,remote+'/target.png',stage+'/render/official.png',stage+'/locate',*alignment))
                    if against:
                        old=done[against]
                        previous=json.loads(ssh(PY,remote+'/'+locate_src.name,remote+'/target.png',stage+'/render/official.png',stage+'/delta',
                            '--freeze',old+'/locate/patch_feedback.json','--baseline-image',old+'/render/official.png'))
                    for k in ['overview']+[x['id'] for x in fresh['patches']]:
                        scp('hkust3:'+stage+'/locate/'+k+'.png',folder/(k+'.png'))
                    scp('hkust3:'+stage+'/render/official.png',folder/'candidate.png')
                put(folder/'metrics.json',dict(current=fresh,against_previous=previous,native=proof))
                done[candidate]=stage
                outcome.update(ok=True,native_gate=True,metrics_path=str((folder/'metrics.json').relative_to(c)),
                    render_path=str((folder/'candidate.png').relative_to(c)),overview_path=str((folder/'overview.png').relative_to(c)),
                    crops=[str((folder/(x['id']+'.png')).relative_to(c)) for x in fresh['patches']],
                    global_mse=fresh['global_metrics']['mse'],candidate_sha256=request['sha256'])
            except (OSError,ValueError,subprocess.SubprocessError) as exc:
                outcome['error']=str(exc)[:500]
            outcome['renders_used']=used
            outcome['renders_remaining']=args.limit-used
            put(reply,outcome)
            print(json.dumps(outcome),flush=True)
            deadline=time.monotonic()+args.idle_timeout
        time.sleep(.4)


if __name__=='__main__':
    main()
