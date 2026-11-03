"""Read-only inventory of direct author drawio sources; no conversion or replay."""
from pathlib import Path
import collections,hashlib,json,sqlite3,subprocess,sys
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';S=R/'conversion/scripts';sys.path.insert(0,str(S))
from arxiv_math_source_repair_v1 import native,valuable,classify
from arxiv_author_native_assets_v1 import models
sha=lambda b:hashlib.sha256(b).hexdigest()
def graphhash(blob):
 def node(n):return [n.tag,sorted(n.attrib.items()),(n.text or '').strip(),[node(c) for c in n]]
 return sha(json.dumps([node(m.find('root')) for m in models(blob)[1]],ensure_ascii=True).encode())
def main():
 base=P/'recent_ai_source_expansion_v2/papers';paths=[Path(f) for f in subprocess.check_output(['find',str(base),'-type','f','-iname','*.drawio'],text=True,timeout=25).splitlines()];papers={f.relative_to(base).parts[0] for f in paths}
 known_bytes=set();known_graphs=collections.defaultdict(set);prior_paths={};stats=collections.Counter();rows=[]
 for source in ['new_bulk_200_v1','recent_ai_source_expansion_v2']:
  with sqlite3.connect((P/source/'once.sqlite').as_uri()+'?mode=ro',uri=True) as c:
   for raw, in c.execute("select record from pdfs where json_extract(record,'$.author_xml_sha256') is not null"):
    r=json.loads(raw)
    if r.get('paper') in papers:
     known_bytes.add(r['author_xml_sha256']);prior_paths[r['author_xml_file']]=r['paper']
 a=P/'goal500_progress_v1/accepted_new_pairs.jsonl'
 for r in map(json.loads,a.read_text().splitlines()):
  if r.get('paper') in papers:prior_paths[r['code_file']]=r['paper']
 for f,paper in prior_paths.items():
  p=R/f
  if not p.exists():continue
  try:known_graphs[paper].add(graphhash(p.read_bytes()))
  except (ValueError,TypeError,KeyError):stats['prior_model_not_decoded']+=1
 seen=set()
 for p in paths:
  b=p.read_bytes();h=sha(b);paper=p.relative_to(base).parts[0]
  try:
   f=native(b.decode('utf-8-sig'));kind,_=classify(f,'drawio',{});v=kind=='complex_candidate' and f['native_pages']==1 and valuable(f);stats['valuable' if v else 'below_policy']+=1
   if not v:continue
   gh=graphhash(b)
   if h in known_bytes:state='exact_XML_already_processed'
   elif gh in known_graphs[paper]:state='decoded_source_graph_already_processed'
   elif gh in seen:state='same_inventory_graph_variant'
   else:state='unseen_source_graph';seen.add(gh)
   stats[state]+=1;rows.append(dict(file=str(p.relative_to(R)),paper=paper,sha256=h,decoded_graph_sha256=gh,state=state,features=f))
  except Exception as e:stats['parse_failed']+=1
 D=P/'author_XML_inventory_v1';D.mkdir(exist_ok=True);result=dict(drawio_files=len(paths),stats=dict(stats),candidates=rows,new_PDF_import_calls=0,new_model_calls=0,new_source_replay_calls=0,graph_fingerprint_scope='decoded source cells/geometry/topology only; editor metadata excluded for conservative duplicate detection; never an acceptance gate')
 (D/'inventory.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='candidates'}))
if __name__=='__main__':main()
