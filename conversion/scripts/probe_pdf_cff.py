import io,json,sys
from pathlib import Path
from native_worker import R,W
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
from fontTools.cffLib import CFFFontSet
items=json.loads((W/'tikz_pilot.json').read_text())['results']
for item in items[:2]:
 d=pymupdf.open(Path(item['directory'])/'source.pdf');fonts=[]
 for f in d[0].get_fonts(full=True):
  name,ext,typ,data=d.extract_font(f[0]);c=CFFFontSet()
  try:
   c.decompile(io.BytesIO(data),None);top=c.topDictIndex[0];extra={'charset':top.charset[:30],'matrix':top.FontMatrix,'bbox':top.FontBBox,'fontNames':c.fontNames}
  except Exception as e:extra={'error':str(e),'signature':data[:4].hex()}
  fonts.append({'xref':f[0],'name':name,'ext':ext,'type':typ,'bytes':len(data),**extra})
 traces=d[0].get_texttrace();print(json.dumps({'id':item['id'],'fonts':fonts,'traces':[{k:v for k,v in t.items() if k!='chars'}|{'chars':t['chars'][:6]} for t in traces[:5]]}))
