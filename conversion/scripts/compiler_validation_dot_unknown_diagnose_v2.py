from pathlib import Path
import json,collections
P=Path('/backup/shaoshitong/img2code_20261029/release/compiler_validation_v1/python_graphviz_reservoir_20261101_v2')
r=[json.loads(x) for x in (P/'compiler_validation_DOT_audit.jsonl').read_text().splitlines()]
print(json.dumps({'candidate_unknown':dict(collections.Counter(x.get('reason') for x in r if x['role']=='candidate' and x['status']=='DOT_audit_unknown')),'development_unknown':dict(collections.Counter(x.get('reason') for x in r if x['role']=='development' and x['status']=='DOT_audit_unknown'))}))
