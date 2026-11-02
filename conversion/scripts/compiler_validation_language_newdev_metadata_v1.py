from pathlib import Path
import json
R=Path('/backup/shaoshitong/img2code_20261029');target='0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641'
for line in (R/'release/fixed_batch_v1/initial_screen_20261031_1717/input_order.jsonl').open():
 r=json.loads(line)
 if r['id']==target:print(json.dumps(r));break
