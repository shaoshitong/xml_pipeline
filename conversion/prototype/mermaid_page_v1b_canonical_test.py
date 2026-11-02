import sys,unittest,json,time,hashlib
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');sys.path[:0]=[str(W/'scripts'),str(W/'prototype')]
import mermaid_page_metadata_supervisor_v1b as m
import test_mermaid_page_metadata_supervisor_v1b as test
assert Path(m.__file__)==W/'scripts/mermaid_page_metadata_supervisor_v1b.py'
assert Path(test.__file__)==W/'scripts/test_mermaid_page_metadata_supervisor_v1b.py'
validation,supervisor,files=m.implementation()
print(json.dumps({'at':m.base.now(),'module':m.__file__,'test_module':test.__file__,'validation_policy':validation,'supervisor_policy':supervisor,'module_sha256':hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),'test_sha256':hashlib.sha256(Path(test.__file__).read_bytes()).hexdigest(),'producer_started':False}),flush=True)
suite=unittest.defaultTestLoader.loadTestsFromNames(['test_mermaid_page_metadata_supervisor_v1b','test_bounded_sqlite_transaction_v1','test_mermaid_page_metadata_v1']);started=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(suite)
receipt={'at':m.base.now(),'ok':result.wasSuccessful(),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'elapsed_seconds':time.monotonic()-started,'validation_policy':validation,'supervisor_policy':supervisor,'implementation':files,'producer_started':False,'canonical_database_touched':False,'model_calls':0}
target=W/'prototype/mermaid_page_metadata_v1b_canonical_tests_receipt.json';target.write_bytes(m.canonical(receipt));print(json.dumps({'receipt':str(target),**{k:v for k,v in receipt.items() if k!='implementation'}}),flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
