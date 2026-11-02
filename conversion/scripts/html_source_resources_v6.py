"""Source-only optional directory proof; actual browser fetches remain fail closed.

HTML anchors are navigation rather than paint resource dependencies. All CSS URL
values, fetch-bearing HTML attributes and srcset are inspected before permitting
an absent original asset root. No empty assets or substitute bytes are created.
"""
import hashlib,json
from html.parser import HTMLParser
from pathlib import Path
import tinycss2
VERSION='HTML_original_resource_dependencies_optional_directory_v6'
sha=lambda b:hashlib.sha256(b).hexdigest()

def resource_inventory(code):
 text=code.decode('utf-8') if isinstance(code,bytes) else code
 rows=[]
 def add(value,origin):
  value=value.strip()
  # Even empty resource attributes are conservative dependencies: some fetch
  # algorithms resolve them to the document rather than safely doing nothing.
  inline=value.lower().startswith('data:')
  rows.append(dict(origin=origin,inline_data=inline,value_sha256=sha(value.encode()),url=value if not inline else 'data:'+value[5:].split(',',1)[0]))
 def css(text,origin):
  def walk(tokens):
   for t in tokens:
    if t.type=='error':raise ValueError('fresh_html_resource_CSS_parse_pending')
    if t.type=='url':add(t.value,origin+':url')
    elif t.type=='function':
     if t.lower_name=='url':
      args=[x for x in t.arguments if x.type not in ('whitespace','comment')]
      if len(args)!=1 or args[0].type!='string':raise ValueError('fresh_html_resource_CSS_url_pending')
      add(args[0].value,origin+':url')
     else:
      # CSS image-set/string image references need a dedicated grammar.
      if t.lower_name in ('image-set','-webkit-image-set','image'):
       for x in t.arguments:
        if x.type=='string':add(x.value,origin+':'+t.lower_name)
      walk(t.arguments)
    elif hasattr(t,'content'):walk(t.content)
  tokens=tinycss2.parse_component_value_list(text,skip_comments=True)
  # @import quoted syntax has no URLToken; count it explicitly. The frontend
  # still rejects external CSS in the unchanged HTML grammar.
  for i,t in enumerate(tokens):
   if t.type=='at-keyword' and t.lower_value=='import':
    rest=[x for x in tokens[i+1:] if x.type not in ('whitespace','comment')]
    if rest and rest[0].type=='string':add(rest[0].value,origin+':import')
  walk(tokens)
 class Parser(HTMLParser):
  def __init__(self):super().__init__(convert_charrefs=True);self.style=False;self.style_parts=[]
  def handle_starttag(self,tag,attrs):
   a=dict(attrs)
   if tag=='style':self.style=True;self.style_parts=[]
   if 'style' in a:css(a['style'] or '',tag+'@style')
   if 'srcset' in a:raise ValueError('fresh_html_resource_srcset_pending')
   for k in ('src','poster','background'):
    if k in a:add(a[k] or '',tag+'@'+k)
   if tag=='link' and 'href' in a:add(a['href'] or '',tag+'@href')
   if tag in ('image','use'):
    for k in ('href','xlink:href'):
     if k in a:add(a[k] or '',tag+'@'+k)
   if tag=='object' and 'data' in a:add(a['data'] or '',tag+'@data')
   if tag=='base' and 'href' in a:raise ValueError('fresh_html_resource_base_URL_pending')
   if tag=='meta' and (a.get('http-equiv') or '').lower()=='refresh':raise ValueError('fresh_html_resource_meta_refresh_pending')
  def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs)
  def handle_endtag(self,tag):
   if tag=='style':css(''.join(self.style_parts),'style');self.style=False;self.style_parts=[]
  def handle_data(self,data):
   if self.style:self.style_parts.append(data)
 p=Parser();p.feed(text);p.close()
 if p.style:css(''.join(p.style_parts),'style')
 return dict(version=VERSION,source_code_sha256=sha(text.encode()),resources=rows,resource_count=len(rows),inline_data_resources=sum(x['inline_data'] for x in rows),directory_resource_count=sum(not x['inline_data'] for x in rows),requires_asset_directory=any(not x['inline_data'] for x in rows),parser='stdlib_HTMLParser_and_tinycss2',tinycss2_version=tinycss2.__version__)

def original_asset_root(source,manifest):return manifest.get('asset_root') or source.get('asset_root') or None

def asset_contract(code,original_root,data_root):
 root=Path(data_root).resolve();clean=(root/'clean').resolve();proof=resource_inventory(code);assets=None
 if original_root:
  assets=(root/original_root).resolve()
  if not assets.is_relative_to(clean):raise ValueError('fresh_html_original_assets_not_in_clean')
  if assets.exists() and not assets.is_dir():raise ValueError('fresh_html_original_assets_not_directory')
 if proof['requires_asset_directory'] and (assets is None or not assets.is_dir()):raise ValueError('fresh_html_required_asset_directory_missing')
 proof.update(original_asset_root=original_root,asset_directory_exists=bool(assets is not None and assets.is_dir()),missing_directory_allowed=bool((assets is None or not assets.is_dir()) and not proof['requires_asset_directory']),no_fabricated_resource_bytes=True)
 return assets,proof

def verify_served(served,assets,proof):
 if not proof['requires_asset_directory'] and served:raise ValueError('fresh_html_uninventoried_directory_fetch')
 if served and (assets is None or not assets.is_dir()):raise ValueError('fresh_html_served_without_original_asset_directory')
 return dict(actual_directory_fetches=len(served),source_only_resource_proof=proof,no_fabricated_resource_bytes=True)
