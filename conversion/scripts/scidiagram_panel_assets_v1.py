"""Resolve only the dataset's hash-bound original PNG/JPEG panel assets."""
from pathlib import Path
import base64,hashlib,io,json,sqlite3,xml.etree.ElementTree as E
R=Path('/backup/shaoshitong/img2code_20261029')
sha=lambda b:hashlib.sha256(b).hexdigest()

def inventory(record,job=None):
 from PIL import Image
 identifier=record['id']
 if job is not None:
  given=(job['input_record'],job['input_manifest'])if isinstance(job,dict)else(job[4],job[11])
  with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as d:authoritative=d.execute('select input_record,input_manifest from jobs where id=?',(identifier,)).fetchone()
  if authoritative!=given:raise ValueError('source_panel_job_not_authoritative_original')
 if job is None:
  with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as d:row=d.execute('select input_record,input_manifest from jobs where id=?',(identifier,)).fetchone()
  if row is None:raise ValueError('source_asset_original_job_missing')
  source,manifest=map(json.loads,row)
 else:
  if isinstance(job,dict):source=json.loads(job['input_record']);manifest=json.loads(job['input_manifest'])
  else:source=json.loads(job[4]);manifest=json.loads(job[11])
 assert source['pair_sha256']==identifier==manifest['id']
 assert source['source']=='yashengsun--SciDiagramRevision'and source['gold_code_provenance']=='dataset_input_svg_before_edit'
 declarations={r['file_name']:r for r in source.get('panel_assets',[])};aliases={};assets=[]
 for entry in manifest.get('panel_assets',[]):
  declaration=declarations.get(entry['source_name'])
  if not declaration or declaration['image_sha256']!=entry['sha256']:raise ValueError('source_asset_not_declared_by_original_provider_record')
  p=(R/entry['file']).resolve(strict=True);allowed=(R/'conversion/inputs'/identifier[:2]/identifier/'assets').resolve();assert p.is_relative_to(allowed),'source_asset_outside_original_case'
  blob=p.read_bytes()
  if sha(blob)!=entry['sha256']:raise ValueError('source_asset_payload_hash_mismatch')
  if len(blob)>32*1024*1024:raise ValueError('source_asset_resource_bound')
  with Image.open(io.BytesIO(blob))as image:
   if image.format not in('PNG','JPEG')or image.width*image.height>64000000:raise ValueError('source_asset_requires_known_bounded_raster')
   mime='image/png'if image.format=='PNG'else'image/jpeg';size=[image.width,image.height];image.verify()
  names=declaration.get('allowed_svg_references',[])
  if not names or any(n.startswith(('/', 'http:', 'https:', 'file:', 'data:'))or'..'in Path(n).parts for n in names):raise ValueError('source_asset_invalid_original_alias')
  asset=dict(file=str(p.relative_to(R)),sha256=entry['sha256'],mime=mime,size=size,aliases=names,bytes=len(blob));assets.append(asset)
  for name in names:
   if name in aliases and aliases[name]['sha256']!=entry['sha256']:raise ValueError('source_asset_alias_ambiguous')
   aliases[name]=dict(asset,blob=blob,uri='data:'+mime+';base64,'+base64.b64encode(blob).decode())
 return dict(id=identifier,source=source,manifest=manifest,aliases=aliases,assets=assets)

def resolve(code,context):
 E.register_namespace('','http://www.w3.org/2000/svg');E.register_namespace('xlink','http://www.w3.org/1999/xlink');root=E.fromstring(code);resolved=[]
 for index,element in enumerate(root.iter()):
  if element.tag.split('}')[-1]!='image':continue
  hrefs=[(k,v)for k,v in element.attrib.items()if k.split('}')[-1]=='href']
  if len(hrefs)!=1:raise ValueError('source_image_requires_one_explicit_original_reference')
  key,name=hrefs[0];asset=context['aliases'].get(name)
  if asset is None:raise ValueError('source_image_reference_not_in_original_hashed_manifest:'+name[:150])
  element.set(key,asset['uri']);resolved.append(dict(source_element_index=index,source_href=name,asset_file=asset['file'],asset_sha256=asset['sha256'],mime=asset['mime'],size=asset['size']))
 return E.tostring(root,encoding='utf-8'),dict(method='exact_original_declared_panel_bytes_to_data_URI_v1',source_code_sha256=sha(code),resolved_images=resolved,source_coordinates_text_styles_and_tree_preserved=True,original_source_file_changed=False,network_or_filesystem_fallback=False)
