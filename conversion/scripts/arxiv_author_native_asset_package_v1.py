"""Close relative asset layouts without rewriting any author XML bytes."""
from pathlib import Path
import json,urllib.parse
from arxiv_author_native_assets_v1 import inventory,sha
def package(xml,dependencies,folder):
 folder=Path(folder);_,_,refs,_,_=inventory(xml);relative=[];allowed={'source_only_relative_asset_needs_portable_closure','author_adjacent_file'}
 statuses={a['uri_sha256']:a for a in dependencies['assets'] if a.get('status') in allowed}
 for ref in refs:
  row=statuses.get(sha(ref['uri'].encode()))
  if row:relative.append((ref,row))
 if any(a['status'] not in allowed for a in dependencies['issues']):raise ValueError('unresolved_or_non_relative_asset_cannot_be_packaged')
 deficit=0
 for ref,row in relative:
  depth=0
  for piece in Path(urllib.parse.unquote(urllib.parse.urlparse(ref['uri']).path)).parts:
   if piece=='..':depth-=1;deficit=max(deficit,-depth)
   elif piece not in {'.','/',''}:depth+=1
 anchor=folder/'document'
 for i in range(deficit):anchor=anchor/('level_'+str(i))
 anchor.mkdir(parents=True,exist_ok=False);author=anchor/'author.drawio';author.write_bytes(xml if isinstance(xml,bytes) else xml.encode());asset_map={};manifest=[]
 for ref,row in relative:
  url=urllib.parse.urlparse(ref['uri']);path=urllib.parse.unquote(url.path)
  if Path(path).is_absolute():raise ValueError('absolute_file_asset_not_portable')
  target=(anchor/path).resolve()
  if not target.is_relative_to(folder.resolve()):raise ValueError('relative_asset_escaped_portable_package')
  source=Path(row['file']);blob=source.read_bytes();assert sha(blob)==row['sha256'];target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists():assert target.read_bytes()==blob,'conflicting_relative_asset_paths'
  else:target.write_bytes(blob)
  key=urllib.parse.urlparse(urllib.parse.urljoin('http://source.invalid/',ref['uri'])).path.lstrip('/');asset_map[key]=target;manifest.append({'role':ref['role'],'page':ref['page'],'cell':ref['cell'],'original_URI':ref['uri'],'original_asset_file':str(source),'portable_asset_file':str(target),'sha256':sha(blob),'bytes':len(blob)})
 result={'author_XML_bytes_unchanged':author.read_bytes()==(xml if isinstance(xml,bytes) else xml.encode()),'author_XML_file':str(author),'author_XML_sha256':sha(author.read_bytes()),'resource_dependencies':manifest,'no_asset_content_substitution':True,'resource_source_directory_needed_after_packaging':False,'font_portability_not_asserted_by_resource_packaging':True};(folder/'asset_package_manifest.json').write_text(json.dumps(result,indent=2)+'\n');return author,asset_map,result
