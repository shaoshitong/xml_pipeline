import json,sqlite3
from PIL import Image
from native_worker import R,W
D=sqlite3.connect(W/'jobs.sqlite')
for id in ['4b9f5161955963bf7502185ac81bfd2d83d13a3c4dfd2e0183a8c7e4f40e6759','e647ce1486f91f14571889932f1ac166004219b8bba528ac469587f6107d0e6e']:
 o=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);print(json.dumps({'id':id,'render':o['render'],'size':Image.open(R/o['image_file']).size}))
