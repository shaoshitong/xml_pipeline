#!/usr/bin/env python3
"""Bounded READ-ONLY RAP accepted-template audit. Metadata JSON stdout only.
Uses complete lines within a manifest-size snapshot, not the old catalog. Does
not execute HTML/JS, render, download, extract archives, or write remote files.
"""
import argparse,collections,hashlib,heapq,html,json,re,time,urllib.parse
from html.parser import HTMLParser
from pathlib import Path

class Resources(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.refs=[];self.styles=[];self.scripts=[];self.text=[];self.tags=collections.Counter();self.attrs=collections.Counter();self.inside=None
 def handle_starttag(self,tag,attrs):
  values=dict(attrs);self.tags[tag]+=1
  if tag in ('style','script'):self.inside=tag
  for key in ('src','poster'):
   if values.get(key):self.refs.append((values[key],tag+':'+key))
  if tag=='link' and set(values.get('rel','').lower().split()) & {'stylesheet','preload','modulepreload','icon','apple-touch-icon','manifest'} and values.get('href'):self.refs.append((values['href'],'link:href'))
  if tag=='object' and values.get('data'):self.refs.append((values['data'],'object:data'))
  if tag in ('image','use'):
   for key in ('href','xlink:href'):
    if values.get(key):self.refs.append((values[key],tag+':'+key))
  if values.get('style'):self.styles.append(values['style'])
  if values.get('srcset'):
   raw=values['srcset'].strip()
   if raw.lower().startswith('data:'):self.attrs['data_srcset_not_split']+=1
   else:
    for item in raw.split(','):
     if item.strip():self.refs.append((item.strip().split()[0],tag+':srcset'))
  if tag=='input':self.attrs['input_type_'+values.get('type','text').lower()]+=1
  if tag=='base' and values.get('href'):self.refs.append((values['href'],'base:href'))
  if tag=='iframe' and values.get('srcdoc'):
   nested=Resources();nested.feed(values['srcdoc']);self.refs.extend(nested.refs);self.styles.extend(nested.styles);self.scripts.extend(nested.scripts)
 def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
 def handle_endtag(self,tag):
  if self.inside==tag:self.inside=None
 def handle_data(self,value):
  if self.inside=='style':self.styles.append(value)
  elif self.inside=='script':self.scripts.append(value)
  elif len(self.text)<1024:self.text.append(value)

def digest_file(path,max_bytes=64*1024*1024):
 if path.stat().st_size>max_bytes:raise ValueError('hash_limit_exceeded')
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def css_refs(text):
 text=re.sub(r'/\*.*?\*/','',text,flags=re.S)
 refs=[(x,'css:url') for x in re.findall(r'url\(\s*[\'\"]?([^\s\)\'\";]+)',text,flags=re.I)]
 refs.extend((x,'css:import') for x in re.findall(r'@import\s+[\'\"]([^\'\"]+)',text,flags=re.I))
 return refs

def resolve_reference(ref,base,folder):
 ref=html.unescape(ref).strip();lower=ref.lower()
 if not ref or ref.startswith('#') or lower.startswith('data:'):return 'embedded',None
 if lower.startswith(('http:','https:','//','file:','ftp:')):return 'external',None
 if urllib.parse.urlsplit(ref).scheme:return 'nonfile_scheme',None
 value=urllib.parse.unquote(urllib.parse.urlsplit(ref).path);path=(base/value).resolve()
 if not path.is_relative_to(folder):return 'escapes_template_directory',None
 if not path.is_file():return 'missing',path
 return 'local',path

def inspect_template(row,root,deadline,hash_png=True):
 result={'issues':[],'counts':collections.Counter(),'review':None};folder=(root/(row.get('asset_root') or '')).resolve();codepath=(root/(row.get('code_file') or '')).resolve();imagepath=(root/(row.get('reference_image') or '')).resolve()
 def add(reason,**details):
  result['issues'].append({'reason':reason,**details})
 if not folder.is_relative_to(root/'clean') or not codepath.is_relative_to(folder) or not imagepath.is_relative_to(folder):add('accepted_paths_outside_template');return result
 if codepath.name!='generated.html' or imagepath.name!='rendered.png':add('unexpected_paired_file_names')
 for path,kind in ((codepath,'html'),(imagepath,'rendered_png')):
  if not path.is_file():add('accepted_pair_file_missing',kind=kind);return result
 try:
  if digest_file(codepath,8*1024*1024)!=row.get('code_sha256'):add('accepted_html_hash_mismatch')
  if hash_png and digest_file(imagepath)!=row.get('image_sha256'):add('accepted_rendered_png_hash_mismatch')
 except ValueError as exc:result['counts'][str(exc)]+=1
 code=codepath.read_text();parser=Resources();parser.feed(code);result['counts']['html_bytes']=len(code.encode());result['counts']['html_files_checked']=1;result['counts']['rendered_png_bytes']=imagepath.stat().st_size
 if row.get('category')!='poster' or row.get('format')!='html' or row.get('pairing')!='provided_template_render_and_code':add('accepted_rap_contract_mismatch')
 paper=str((row.get('annotation') or {}).get('paper_id',''))
 if paper and folder.name!=paper:add('paper_template_directory_mismatch')
 work=[(ref,kind,codepath.parent) for ref,kind in parser.refs]
 for style in parser.styles:work.extend((ref,kind,codepath.parent) for ref,kind in css_refs(style))
 seen=set();read_css=set();dynamic=[]
 while work and time.monotonic()<deadline:
  ref,kind,base=work.pop();key=(ref,kind,str(base))
  if key in seen:continue
  seen.add(key);status,path=resolve_reference(ref,base,folder);result['counts']['resource_'+status]+=1
  if status in ('external','missing','escapes_template_directory','nonfile_scheme'):
   clean=ref.split('?',1)[0].split('#',1)[0][:200];add('resource_'+status,kind=kind,reference=clean,referenced_from=str(base.relative_to(folder)) or '.')
  if status!='local' or path.suffix.lower()!='.css' or path in read_css:continue
  read_css.add(path)
  if path.stat().st_size>2*1024*1024:result['counts']['css_over_2MiB_not_read']+=1;continue
  css=path.read_text(errors='replace');result['counts']['css_files_checked']+=1;work.extend((value,why,path.parent) for value,why in css_refs(css))
 if work:result['counts']['resource_budget_incomplete']+=1
 # These are actual static literal loader calls; no JavaScript is executed.
 for script in parser.scripts:
  for loader,value in re.findall(r'\b(fetch|loadImage|d3\.(?:csv|json|tsv))\s*\(\s*[\'\"]([^\'\"]+)',script):
   status,path=resolve_reference(value,codepath.parent,folder);result['counts']['literal_js_loader_calls']+=1
   if status not in ('embedded','local'):add('js_loader_resource_'+status,kind=loader,reference=value.split('?',1)[0][:200])
 text=' '.join(parser.text).lower();webtokens=sorted(set(re.findall(r'\b(?:log\s*in|sign\s*in|sign\s*up|shopping\s*cart|add\s*to\s*cart|dashboard|checkout)\b',text)));academic=sum(bool(re.search(r'\b'+word+r'\b',text)) for word in ('abstract','introduction','method','results','conclusion','references','university','learning','dataset','model'))
 if parser.attrs['input_type_password'] or (parser.tags['form'] and webtokens) or (len(webtokens)>=2 and parser.tags['nav'] and parser.tags['button']):result['review']={'web_tokens':webtokens,'academic_text_term_count':academic,'tag_counts':{k:parser.tags[k] for k in ('form','input','nav','button')},'password_inputs':parser.attrs['input_type_password']}
 result['counts'].update(parser.attrs)
 return result

def main(args):
 root=args.root.resolve();started=time.monotonic();deadline=started+args.seconds;path=root/'manifests'/('VincentHancoder--RAP.jsonl');counts=collections.Counter();reasons=collections.Counter();examples=[];reviews=[];heap=[];tail=collections.deque(maxlen=min(24,args.samples));first=[];size=path.stat().st_size if path.is_file() else 0;mtime=path.stat().st_mtime if path.is_file() else None
 if size:
  with path.open('rb') as stream:
   while stream.tell()<size:
    line=stream.readline()
    if stream.tell()>size or not line.endswith(b'\n'):counts['snapshot_partial_line_excluded']+=1;break
    try:row=json.loads(line)
    except ValueError:counts['invalid_complete_jsonl_lines']+=1;continue
    counts['accepted_manifest_complete_rows_observed']+=1;ordinal=counts['accepted_manifest_complete_rows_observed'];row['_audit_ordinal']=ordinal
    if len(first)<8:first.append(row)
    tail.append(row);rank=int(hashlib.sha256((str(row.get('raw_row'))+'|'+str(row.get('code_sha256'))).encode()).hexdigest(),16);item=(-rank,ordinal,row)
    if len(heap)<args.samples:heapq.heappush(heap,item)
    elif item>heap[0]:heapq.heapreplace(heap,item)
 selected={row['_audit_ordinal']:row for row in first+list(tail)+[x[2] for x in heap]};counts['deterministic_samples_planned']=len(selected)
 for ordinal,row in sorted(selected.items()):
  if time.monotonic()>deadline:counts['samples_not_checked_time_budget']=len(selected)-counts['sampled_templates_checked'];break
  ref={'manifest_ordinal':ordinal,'raw_row':row.get('raw_row'),'paper_id':(row.get('annotation') or {}).get('paper_id'),'code_file':row.get('code_file'),'asset_root':row.get('asset_root')}
  try:
   result=inspect_template(row,root,deadline,not args.skip_png_hash);counts['sampled_templates_checked']+=1;counts.update(result['counts'])
   if result['review'] and len(reviews)<12:reviews.append({**ref,**result['review']})
   for issue in result['issues']:
    reasons[issue['reason']]+=1
    if len(examples)<args.issue_examples:examples.append({**ref,**issue})
  except Exception as exc:
   reasons['template_inspection_error']+=1
   if len(examples)<args.issue_examples:examples.append({**ref,'reason':'template_inspection_error','error':type(exc).__name__+':'+str(exc)[:160]})
 print(json.dumps({'read_only':True,'observed_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'source':'VincentHancoder--RAP','manifest_snapshot':{'file':str(path.relative_to(root)),'bytes':size,'mtime':mtime,'current_bytes_after_probe':path.stat().st_size if path.is_file() else None},'scope':'Complete accepted manifest lines up to initial file size; deterministic hash sample plus first8/last24. Sample checks only, no claim of complete RAP or current catalog total. No HTML/JS execution, models, renders, downloads or writes.','counts':dict(counts),'issue_counts':dict(reasons),'issue_examples':examples,'web_ui_review_candidates':reviews,'web_review_note':'Candidates require password input or concrete form/navigation/button structures plus web UI terms. Terms alone are not a web classification.','seconds':round(time.monotonic()-started,2)},ensure_ascii=False),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/backup/shaoshitong/img2code_20261029'));p.add_argument('--samples',type=int,default=160);p.add_argument('--seconds',type=int,default=45);p.add_argument('--issue-examples',type=int,default=12);p.add_argument('--skip-png-hash',action='store_true');main(p.parse_args())
