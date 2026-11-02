"""Two seen Y365 source compiles only; never selects or releases heldout cases."""
from pathlib import Path
import hashlib,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
from tikz_pdftex_execution_v1 import compile_execution_graph,density
from auto_quality_common_v4 import image_quality
from tikz_execution_graph import parse_events
from tikz_execution_binding_v3 import graph_from_events
from PIL import Image
sha=lambda b:hashlib.sha256(b).hexdigest()
SEEN={'0002d1280db280c2d9227e7d2188cd20f0cbc446310f112772df3d9b62cca423','0036b5425c60a565c4de754bd9940630f0cacb14f7813e9c83eda930de1d1a7e'}
INPUT=W/'compiler_tikz_free_paths_v1/development/46015474892e4c8c84668e50a86ae648/report.json'

def positions(page,scale):
 rows=[]
 for n,t in enumerate(page.get_texttrace()):
  if t['type']==3:continue
  chars=[]
  for unicode,gid,origin,bbox in t['chars']:
   x0,y0,x1,y1=bbox;chars.append({'text':chr(unicode) if 0<=unicode<=0x10ffff else '\ufffd','x':x0*scale,'y':y0*scale,'width':(x1-x0)*scale,'height':(y1-y0)*scale})
  rows.append({'cell':'actual_pdf_display_list_text_'+str(n),'runs':[{'chars':chars}]})
 return rows

def main():
 sys.path.append(str(W/'runtime/python_packages'));import pymupdf
 folder=W/'compiler_tikz_poppler_source_v2/development'/('pdftex2025_source_'+uuid.uuid4().hex);folder.mkdir(parents=True,exist_ok=False)
 result={'schema':'tikz_pdftex2025_development_probe_v1','unseen_consumed':0,'model_calls':0,'records':[]}
 for row in json.loads(INPUT.read_bytes())['results']:
  if row['id'] not in SEEN:continue
  r=json.loads(Path(row['record_file']).read_bytes());code=(R/r['original_source_code']).read_bytes();reference=(R/r['original_reference']).read_bytes()
  assert sha(code)==r['source_code_sha256'] and sha(reference)==r['source_image_sha256']
  work=folder/r['id'];trace=compile_execution_graph(code,work,density(reference));item={'id':r['id'],'source_code_sha256':sha(code),'source_image_sha256':sha(reference),'compile_ok':not trace.get('error'),'trace_error':trace.get('error'),'work':str(work),'original_bytes_preserved':True}
  if not trace.get('error'):
   graph=graph_from_events(parse_events((work/'instrumented/source.iic').read_text()));item.update(typed_graph_ok=graph['ok'],typed_graph_failures=graph['failures'])
   png=(work/'baseline/actual_Poppler100dpi/source.png').read_bytes();item.update(actual_PDF_png=str(work/'baseline/actual_Poppler100dpi/source.png'),actual_PDF_canvas=list(Image.open(work/'baseline/actual_Poppler100dpi/source.png').size),reference_canvas=list(Image.open(R/r['original_reference']).size))
   with pymupdf.open(work/'baseline/source.pdf') as doc:
    page=doc[0];item['pdf_page_pt']=list(page.rect);text=positions(page,100/72);item['actual_PDF_glyph_count']=sum(len(x['runs'][0]['chars']) for x in text)
    item['source_reference_quality']=image_quality(reference,png,{},text) if item['actual_PDF_canvas']==item['reference_canvas'] else {'ok':False,'reason':'actual_density_source_canvas_differs','no_reference_resizing_or_fitting':True}
  result['records'].append(item);(folder/'progress.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps(item),flush=True)
  assert sha((R/r['original_source_code']).read_bytes())==r['source_code_sha256'] and sha((R/r['original_reference']).read_bytes())==r['source_image_sha256']
 assert {x['id'] for x in result['records']}==SEEN
 (folder/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'report':str(folder/'report.json')}),flush=True)

if __name__=='__main__':main()
