import json,sqlite3
from native_worker import W,now
from harness_pool_v3 import seed
D=sqlite3.connect(W/'jobs.sqlite',timeout=120);ids=[r[0] for r in D.execute("select id from plantuml_geometry_repairs where state='failed'")];out={'at':now(),'new_failed_and_quality_records_seeded':seed(),'plantuml_unsupported_route_ids':ids,'extra_plantuml_rendered_records_seeded':seed(ids) if ids else 0};(W/'harness_reseed_after_plantuml.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
