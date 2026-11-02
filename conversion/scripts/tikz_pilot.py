import hashlib,json,sqlite3,subprocess
from pathlib import Path
from native_worker import R,W,now
from sandbox_runner import run
import sys
sys.path.insert(0,str(W/'runtime/python_packages'))
import fitz

def main():
 db=sqlite3.connect(W/'jobs.sqlite');rows=[]
 for source in ('Y36521478Y--omnidiagram_train_sft','nllg--DaTikZ-V4','allenai--CoSyn-400K'):rows.extend(db.execute('select id,input_record,input_manifest from jobs where format="tikz" and source=? order by id limit 1',(source,)).fetchall())
 results=[];runtime=W/'runtime/tectonic';cache=runtime/'cache'
 for id,raw,prepared in rows:
  inp=json.loads(prepared);source=json.loads(raw);D=W/'tikz_pilot'/id;D.mkdir(parents=True,exist_ok=True);code=(R/inp['source_code']).read_bytes();assert hashlib.sha256(code).hexdigest()==source['code_sha256'];(D/'source.tex').write_bytes(code)
  try:
   cmd=[str(runtime/'tectonic'),'--untrusted','--only-cached','--keep-logs','--keep-intermediates','/work/source.tex'];r=run(D,cmd,timeout=150,extra_ro=[(runtime,runtime)],extra_env={'XDG_CACHE_HOME':str(cache),'TECTONIC_CACHE_DIR':str(cache)});(D/'stdout.log').write_text(r.stdout);(D/'stderr.log').write_text(r.stderr);result={'id':id,'source':source['source'],'directory':str(D),'returncode':r.returncode,'stdout_tail':r.stdout[-2000:],'stderr_tail':r.stderr[-2000:]}
   if (D/'source.pdf').exists():
    doc=fitz.open(D/'source.pdf');result['pages']=len(doc);result['pdf_pages']=[]
    for i,page in enumerate(doc):
     (D/f'page{i}.svg').write_text(page.get_svg_image(text_as_path=False));(D/f'page{i}_text.json').write_text(json.dumps(page.get_text('dict'),ensure_ascii=False));page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(D/f'page{i}_mupdf.png');result['pdf_pages'].append({'page':i,'width_pt':page.rect.width,'height_pt':page.rect.height,'text_characters':len(page.get_text()),'drawing_paths':len(page.get_drawings())})
    subprocess.run(['pdftoppm','-r','144','-png','-singlefile',str(D/'source.pdf'),str(D/'page0_poppler')],check=True,capture_output=True,timeout=60)
  except Exception as e:result={'id':id,'error':str(e)}
  results.append(result);print(json.dumps(result),flush=True)
 (W/'tikz_pilot.json').write_text(json.dumps({'finished_at_utc':now(),'results':results},indent=2)+'\n')
if __name__=='__main__':main()
