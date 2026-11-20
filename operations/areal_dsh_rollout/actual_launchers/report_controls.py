"""Assemble the offline control report from actual outcomes and immutable first rounds."""
from pathlib import Path
import json
import re
import sys

root = Path('/DATA/disk1/zbw_tmp4/drawio-agent-qwen38')
sys.path.insert(0, str(root / 'source-snapshots/621ff21/operations/areal_dsh_rollout'))
from report import asset, collect_run, make_html

manifest = json.loads(Path(sys.argv[1]).read_text())
reference = root / 'inputs/022/reference.png'
baseline = root / 'reports/qwen38-h20-comparison/index.html'
data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', baseline.read_text(), re.S).group(1))
assert data['reference']['sha256'] == asset(reference)['sha256']
runs = data['runs']
for specification in manifest['runs']:
    run = collect_run(specification['name'], Path(specification['evaluation']))
    origin = Path(specification['first_generation'])
    first = collect_run('immutable first generation', origin)['rounds'][0]
    for field in ('xml', 'png'):
        run['rounds'][0][field] = first[field]
    run['first_generation_artifact_provenance'] = str(origin)
    run['outcome'] = specification['outcome']
    runs.append(run)
output = Path(manifest['output'])
output.parent.mkdir(parents=True, exist_ok=True)
html = make_html(reference, runs).replace('Reviewer JSON \u539f\u6587', 'Generator \u6536\u5230\u7684 Reviewer JSON')
output.write_text(html, encoding='utf-8')
print(json.dumps({'output': str(output), 'runs': len(runs), 'bytes': output.stat().st_size}))
