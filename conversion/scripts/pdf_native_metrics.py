import json,sqlite3
from pathlib import Path
from native_worker import R,W
from svg_batch import metric
D=sqlite3.connect(W/'jobs.sqlite');out=[]
for item in json.loads((W/'tikz_pilot.json').read_text())['results']:
 id=item['id'];work=W/'pdf_native_pilot'/id;inp=json.loads(D.execute('select input_manifest from jobs where id=?',(id,)).fetchone()[0]);ref=(R/inp['reference_image']).read_bytes();pdf=(Path(item['directory'])/'page0_poppler.png').read_bytes();svg=(work/'reconstructed_source.png').read_bytes();pred=(work/'image.png').read_bytes();report=json.loads((work/'summary.json').read_text());out.append({'id':id,'original_vs_pdf':metric(ref,pdf),'pdf_vs_svg':metric(pdf,svg),'pdf_vs_native':metric(pdf,pred),'issues':report['source']['issues'],'loaded_fonts':report['render'].get('loaded_fonts')})
print(json.dumps(out,default=lambda x:list(x)))
