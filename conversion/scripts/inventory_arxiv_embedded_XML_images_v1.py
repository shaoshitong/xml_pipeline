"""Bounded read-only SVG/PNG native XML marker inventory; never decodes pixels."""
from pathlib import Path
import json,os,struct,time
R=Path('/backup/shaoshitong/img2code_20261029');BASE=R/'clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2/papers';D=R/'clean/arxiv_research_figures_v1/embedded_XML_image_inventory_v1'
def main():
 started=time.monotonic();counts={'svg':0,'png':0};rows=[];complete=True;io_errors=0
 for root,_,names in os.walk(BASE):
  if time.monotonic()-started>55:complete=False;break
  if '/source' not in root:continue
  for name in names:
   if time.monotonic()-started>55:complete=False;break
   p=Path(root)/name;ext=p.suffix.lower()
   try:
    if ext=='.svg':
     counts['svg']+=1
     with p.open('rb') as f:b=f.read(65536)
     if b'mxfile' in b or b'mxGraphModel' in b:rows.append(dict(file=str(p.relative_to(R)),kind='SVG_native_XML_marker'))
    elif ext=='.png':
     counts['png']+=1
     with p.open('rb') as f:
      file_size=os.fstat(f.fileno()).st_size
      if f.read(8)!=b'\x89PNG\r\n\x1a\n':continue
      for chunk in range(10000):
       head=f.read(8)
       if len(head)!=8:break
       size,kind=struct.unpack('>I4s',head)
       if size>file_size:break
       if kind in [b'tEXt',b'zTXt',b'iTXt']:
        prefix=f.read(min(size,128));key=prefix.split(b'\0',1)[0]
        if key.lower() in [b'mxfile',b'mxgraphmodel',b'drawio']:rows.append(dict(file=str(p.relative_to(R)),kind='PNG_native_XML_marker',keyword=key.decode(errors='replace')))
        f.seek(size-len(prefix)+4,1)
       else:f.seek(size+4,1)
       if kind==b'IEND':break
   except OSError:io_errors+=1
 result=dict(directory_walk_complete=complete,io_errors=io_errors,scan_scope="SVG first64KiB; PNG text-chunk keywords only; no parsed XML or product claim",scanned=counts,native_XML_markers=len(rows),candidates=rows,seconds=time.monotonic()-started,new_PDF_import_calls=0,new_model_calls=0,new_source_downloads=0,new_source_replay_calls=0,pixel_data_not_decoded=True)
 D.mkdir(exist_ok=True);(D/'inventory.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='candidates'}))
if __name__=='__main__':main()
