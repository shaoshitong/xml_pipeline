"""Read-only CLI task evidence, with no credential file access."""
import collections,datetime,json,re
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion/dpsk_svg_png_compiler_20261103')
D=W.parents[1]/'clean/arxiv_research_figures_v1/embedded_XML_compiler_dpsk_v1'
def safe(s):
 s=re.sub(r'(?i)(bearer\s+|x-dsh-auth-token[\s:=]+)\S+',r'\1[REDACTED]',s)
 return re.sub(r'\bsk-[A-Za-z0-9_-]{12,}','[REDACTED]',s)
print('AT',datetime.datetime.now(datetime.timezone.utc).isoformat())
for p in [W/'launcher_status.json',W/'launcher.log',W/'stderr.log',W/'status.json',D/'status.json']:
 if p.exists():print(str(p.relative_to(W) if p.is_relative_to(W) else p),safe(p.read_text(errors='replace')[-3500:]))
p=W/'events.jsonl'
if p.exists():
 rows=[]
 with p.open() as f:
  for line in f:
   try:rows.append(json.loads(line))
   except ValueError:pass
 print('EVENT_BYTES',p.stat().st_size,'EVENT_TYPES',dict(collections.Counter(r.get('type') for r in rows)))
 for r in rows[-6:]:print('LAST_EVENT',safe(json.dumps(r,ensure_ascii=False)[:2300]))
print('GENERATED',[(str(p.relative_to(W)),p.stat().st_size) for p in W.glob('scripts/*') if p.is_file()])
