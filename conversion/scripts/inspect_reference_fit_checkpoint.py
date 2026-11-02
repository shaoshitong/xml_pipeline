import json,sqlite3,hashlib
from native_worker import R,W,now
from native_move_audit import audit
from svg_batch import metric
id='0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641'
B=W/'mermaid_reference_fit'/id
r=json.loads((B/'before_record.json').read_text())
xml=(B/'candidate.drawio').read_text()
moves=audit(xml)
(B/'moves.json').write_text(json.dumps(moves,indent=2))
dom=json.loads((B/'source_dom.json').read_text())
out={'at':now(),'id':id,'moves':moves,'source_dom_issues':dom['issues'],'source_reference_ssim':metric((R/r['original_reference']).read_bytes(),(B/'source_fit.png').read_bytes()),'native_reference_ssim':metric((R/r['original_reference']).read_bytes(),(B/'candidate.png').read_bytes()),'source_native_ssim':metric((B/'source_fit.png').read_bytes(),(B/'candidate.png').read_bytes()),'code_sha256':hashlib.sha256(xml.encode()).hexdigest()}
(B/'checkpoint_audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
