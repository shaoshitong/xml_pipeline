from pathlib import Path
import json
R=Path('/backup/shaoshitong/img2code_20261029');p=R/'release/compiler_validation_v1/cluster_audit_20261101_v1/compiler_validation_development_ids.jsonl';d={json.loads(x)['id'] for x in p.read_text().splitlines()};ids=['0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641','741dba10f203580e613cfc70c0aa6e9d3650ef4188379018741dc6b7d762c1bd'];print(json.dumps({i:i in d for i in ids}))
