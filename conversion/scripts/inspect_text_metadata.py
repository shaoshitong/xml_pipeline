import json,shutil
from PIL import Image
from native_worker import R,W
out={'java':shutil.which('java'),'dot':shutil.which('dot'),'jars':[str(p) for p in (W/'runtime').rglob('*plantuml*.jar')],'images':[]}
for r in json.loads((W/'text_fidelity_selection.json').read_text()):
 im=Image.open(R/r['reference']);out['images'].append({'id':r['id'],'format':r['format'],'file_type':im.format,'info':{k:str(v)[:1800] for k,v in im.info.items()}})
print(json.dumps(out,ensure_ascii=False))
