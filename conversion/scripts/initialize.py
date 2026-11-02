import collections,datetime,hashlib,json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';W.mkdir(exist_ok=True)
manifest=R/'release/manifest.jsonl';accept=json.loads((R/'release/acceptance.json').read_text());assert accept['ok']
conn=sqlite3.connect(W/'jobs.sqlite');conn.execute('PRAGMA journal_mode=WAL');conn.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, category TEXT NOT NULL, format TEXT NOT NULL, source TEXT NOT NULL, input_record TEXT NOT NULL, state TEXT NOT NULL DEFAULT "queued", route TEXT, attempts INTEGER NOT NULL DEFAULT 0, updated_at TEXT, output_record TEXT, error TEXT)')
counts=collections.Counter();formats=collections.Counter();cross=collections.Counter();sources=collections.Counter();digest=hashlib.sha256();now=datetime.datetime.now(datetime.timezone.utc).isoformat()
with manifest.open('rb') as f:
 for line in f:
  digest.update(line);x=json.loads(line)
  if x['category'] not in ('scientific_diagram','poster'):continue
  fmt=x['format'];route={'drawio':'native','svg':'svg','html':'html','mermaid':'mermaid','plantuml':'plantuml','tikz':'tikz','python':'python'}.get(fmt,'harness')
  conn.execute('INSERT OR IGNORE INTO jobs(id,category,format,source,input_record,route,updated_at) VALUES (?,?,?,?,?,?,?)',(x['pair_sha256'],x['category'],fmt,x['source'],json.dumps(x,ensure_ascii=False),route,now));counts[x['category']]+=1;formats[fmt]+=1;cross[(x['category'],fmt)]+=1;sources[x['source']]+=1
assert digest.hexdigest()==accept['manifest_sha256'];assert dict(counts)=={'scientific_diagram':107161,'poster':24743},dict(counts)
assert conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==131904
conn.commit();conn.close()
result={'created_at_utc':now,'input_manifest':str(manifest),'input_manifest_sha256':digest.hexdigest(),'total_target_pairs':sum(counts.values()),'categories':dict(counts),'formats':dict(formats),'category_formats':[{'category':k[0],'format':k[1],'pairs':v} for k,v in sorted(cross.items())],'sources':dict(sources),'goal_complete':False,'required_output':'Every target pair must produce editable drawio/mxGraph XML and a newly rendered PNG, with original image/code provenance retained. No full-image raster wrapper accepted as diagram conversion. Photos/raster panels may remain raster assets within editable posters. Unsupported/failing jobs remain pending for Harness correction, never silently dropped.','output_payload_root':'clean/drawio_unified','output_manifest':'release/drawio_manifest.jsonl','execution_host':'hkust3','strategy':'Deterministic code conversion first, remote parallel DeepSeek Harness fallback; actual render, content/structure checks, fidelity diagnostics and complete source coverage required.'}
(W/'scope.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
