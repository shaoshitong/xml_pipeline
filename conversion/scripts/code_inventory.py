import ast,collections,json,re,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';db=sqlite3.connect(W/'jobs.sqlite');out={}
for fmt in ['python','tikz']:
 imports=collections.Counter();flags=collections.Counter();examples=[];sources=collections.Counter()
 for id,source,prep in db.execute('select id,source,input_manifest from jobs where format=? order by id',(fmt,)):
  code=(R/json.loads(prep)['source_code']).read_text();sources[source]+=1
  if fmt=='python':
   try:
    tree=ast.parse(code);names=set()
    for n in ast.walk(tree):
     if isinstance(n,ast.Import):names.update(a.name.split('.')[0] for a in n.names)
     elif isinstance(n,ast.ImportFrom) and n.module:names.add(n.module.split('.')[0])
    imports.update(names)
   except Exception:flags['invalid_syntax']+=1
  else:
   imports.update(set(re.findall(r'\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}',code)))
   for token in ['documentclass','begin{document}','begin{tikzpicture}','includegraphics','pgfplots','input{','write18']:
    if token in code:flags[token]+=1
  if len(examples)<3:examples.append({'id':id,'source':source,'code':code[:4000]})
 out[fmt]={'sources':sources,'imports':imports,'flags':flags,'examples':examples}
(W/'code_format_inventory.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False))
