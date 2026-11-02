from pathlib import Path
import json,re,sqlite3,sys
R=Path('/backup/shaoshitong/img2code_20261029');sys.path[:0]=[str(R/'conversion/scripts'),str(R/'env')]
from arxiv_native_reference_audit_v2 import Auditor,base
ident=sys.argv[1];folder=Path(sys.argv[2]);assert re.fullmatch('[0-9a-f]{64}',ident)
record=None
for name in ['new_bulk_200_v1','recent_ai_source_expansion_v2']:
 with sqlite3.connect((base.P/name/'once.sqlite').as_uri()+'?mode=ro',uri=True) as db:
  row=db.execute('select record from pdfs where id=? and status=?',(ident,'qualified_native_xml_png_pair')).fetchone()
 if row:record=json.loads(row[0]);break
assert record,'official_native_recovery_authority_not_found'
auditor=Auditor()
try:
 result=auditor.audit(record,folder)
 print(json.dumps({'id':ident,'status':result['status'],'seconds':result['seconds'],'reason':result.get('reason')},ensure_ascii=True))
finally:auditor.close()
