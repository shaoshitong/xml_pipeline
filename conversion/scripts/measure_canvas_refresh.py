import json,sqlite3
from native_worker import R,W
from svg_pilot import metrics
D=sqlite3.connect(W/'jobs.sqlite');p=next(p for p in (W/'font_native_stack_tests').iterdir() if p.name.startswith('00415'));old=json.loads(D.execute('select output_record from jobs where id=?',(p.name,)).fetchone()[0]);ref=(R/old['original_reference']).read_bytes();result={'id':p.name,'before':metrics(ref,(R/old['image_file']).read_bytes()),'strict_fresh_native':metrics(ref,(p/'strict_fresh_before.png').read_bytes()),'font_embedded':metrics(ref,(p/'candidate.png').read_bytes()),'note':'Diagnostic only; no acceptance or publication.'};(p/'refresh_reference_metrics.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
