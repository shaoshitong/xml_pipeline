"""Inventory exact styled full names in preserved SVG sources; cache by source hash."""
import hashlib,json,re,sqlite3,subprocess,xml.etree.ElementTree as E
from pathlib import Path
from fontTools.ttLib import TTFont
from native_worker import R,W,now
from durable_sqlite import begin,commit

def scan():
 names=set()
 for line in subprocess.check_output(['fc-list','--format=%{file}\t%{index}\n'],text=True).splitlines():
  path,index=line.rsplit('\t',1)
  if Path(path).suffix.lower() not in ['.ttf','.otf','.ttc']:continue
  with TTFont(path,fontNumber=int(index or 0)) as f:
   families={n.toUnicode().casefold() for n in f['name'].names if n.nameID in [1,16]};names.update(n.toUnicode().casefold() for n in f['name'].names if n.nameID==4 and n.toUnicode().casefold() not in families)
 D=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(D);D.execute('create table if not exists svg_fullname_font_sources (id TEXT primary key,source_sha256 TEXT,record TEXT,error TEXT,updated_at TEXT)');commit(D);cached=dict(D.execute('select id,source_sha256 from svg_fullname_font_sources'));pending=[];counts={'scanned':0,'with_exact_fullnames':0,'errors':0,'cached':0}
 for id,raw in D.execute("select id,output_record from jobs where format in ('python','svg') and output_record is not null").fetchall():
  r=json.loads(raw);key='source_render_svg' if r['source_format']=='python' else 'original_source_code';hk='source_render_svg_sha256' if key=='source_render_svg' else 'source_code_sha256';h=r.get(hk)
  if not h or not r.get(key):continue
  if cached.get(id)==h:counts['cached']+=1;continue
  error=None;record={'id':id,'source_file':r[key],'source_sha256':h}
  try:
   path=R/r[key];assert path.resolve().is_relative_to(R/'clean');data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==h;root=E.fromstring(data);specs=set()
   for el in root.iter():
    if el.get('font-family'):specs.add(el.get('font-family'))
    css=(el.text or '') if el.tag.split('}')[-1]=='style' else el.get('style','');specs.update(re.findall(r'font-family\s*:\s*([^;{}]+)',css,re.I))
   found=set()
   for s in specs:
    whole=s.strip().strip('"\'')
    parts=[whole] if whole.casefold() in names else [p.strip().strip('"\'') for p in s.split(',')]
    found.update(p for p in parts if p.casefold() in names)
   record.update(family_specs=sorted(specs),exact_fullnames=sorted(found));counts['with_exact_fullnames']+=bool(found)
  except Exception as e:error=repr(e);counts['errors']+=1
  pending.append((id,h,json.dumps(record),error,now()));counts['scanned']+=1
  if len(pending)>=200:begin(D);D.executemany('insert or replace into svg_fullname_font_sources values (?,?,?,?,?)',pending);commit(D);pending=[]
 if pending:begin(D);D.executemany('insert or replace into svg_fullname_font_sources values (?,?,?,?,?)',pending);commit(D)
 out={'at':now(),**counts,'total_indexed':D.execute('select count(*) from svg_fullname_font_sources').fetchone()[0],'total_with_exact_fullnames':D.execute("select count(*) from svg_fullname_font_sources where error is null and json_array_length(json_extract(record,'$.exact_fullnames'))>0").fetchone()[0]};(W/'svg_fullname_source_scan.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True);D.close();return out
if __name__=='__main__':scan()
