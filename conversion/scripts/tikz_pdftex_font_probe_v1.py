"""Finite actual embedded-font extraction on only the two seen pdfLaTeX cases."""
from pathlib import Path
import json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'));sys.path.append(str(W/'runtime/python_packages'))
import pymupdf
from pdf_to_native_pdftex_v1 import source_svg
INPUT=W/'compiler_tikz_poppler_source_v2/development/pdftex2025_source_202c772109ce4de984728f73fcdbed11/report.json'

def main():
 target=W/'compiler_tikz_poppler_source_v2/development'/('pdftex_actual_font_'+uuid.uuid4().hex);target.mkdir(parents=True,exist_ok=False);out=[]
 for item in json.loads(INPUT.read_bytes())['records']:
  work=target/item['id'];work.mkdir()
  try:
   with pymupdf.open(Path(item['work'])/'baseline/source.pdf') as doc:
    svg,fonts,stats=source_svg(doc,doc[0],work)
   (work/'source.svg').write_text(svg);(work/'font_sources.json').write_text(json.dumps(fonts,ensure_ascii=False,indent=2)+'\n')
   result={'id':item['id'],'ok':True,'source_svg':str(work/'source.svg'),'fonts':[{k:f[k] for k in ('family','glyphs','source_type','source_font_sha256')} for f in fonts.values()],'stats':stats}
  except Exception as error:result={'id':item['id'],'ok':False,'error_type':type(error).__name__,'reason':str(error)}
  out.append(result);print(json.dumps({k:v for k,v in result.items() if k!='stats'}),flush=True)
 (target/'report.json').write_text(json.dumps({'records':out,'unseen_consumed':0,'model_calls':0},ensure_ascii=False,indent=2)+'\n');print(json.dumps({'report':str(target/'report.json')}),flush=True)

if __name__=='__main__':main()
