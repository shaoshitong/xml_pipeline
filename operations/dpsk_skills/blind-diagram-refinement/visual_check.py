"""Ask the case-local render service to measure one checkpoint."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time


def submit(request):
    token = hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()[:20]
    queue = Path('visual_checks')
    queue.mkdir(exist_ok=True)
    job, reply = queue/f'{token}.request.json',queue/f'{token}.reply.json'
    temporary=job.with_suffix('.tmp')
    temporary.write_text(json.dumps(request)+'\n')
    os.replace(temporary,job)
    for _ in range(52):
        if reply.is_file():
            result = json.loads(reply.read_text())
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return int(not result.get('ok'))
        time.sleep(1)
    print(json.dumps(dict(pending=True,request=token,message='Repeat the identical command to retrieve the result; it will not consume another render.')))
    return 0


def main():
    p = argparse.ArgumentParser()
    if sys.argv[1:2] == ['compare']:
        p.prog += ' compare'
        p.add_argument('before')
        p.add_argument('after')
        a = p.parse_args(sys.argv[2:])
        names = (a.before, a.after)
        for name in names:
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}\.drawio', name):
                p.error('use a case-local checkpoint filename ending in .drawio')
        return submit({'operation': 'compare', 'checkpoints': [
            {'name': name, 'sha256': hashlib.sha256(Path(name).read_bytes()).hexdigest()} for name in names
        ]})
    p.add_argument('candidate')
    p.add_argument('--against')
    a = p.parse_args()
    for name in filter(None, (a.candidate, a.against)):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}\.drawio', name):
            p.error('use a case-local checkpoint filename ending in .drawio')
    digest = hashlib.sha256(Path(a.candidate).read_bytes()).hexdigest()
    return submit(dict(candidate=a.candidate, against=a.against, sha256=digest))


if __name__=='__main__':
    raise SystemExit(main())
