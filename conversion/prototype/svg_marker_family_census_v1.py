"""Hash-verified static marker-owner families; no acceptance or candidate writes."""
import collections,concurrent.futures,hashlib,json,math,re,time,datetime
from pathlib import Path
import xml.etree.ElementTree as E
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'conversion/prototype/svg_source_profile_scope_v1';metadata=json.loads((P/'current_metadata_aggregate.json').read_text());static=json.loads((P/'static_source_scan.json').read_text());ids={r['id'] for r in static['records'] if r['kind']=='source_marker_owners_without_declared_graph_nodes'};rows=[r for r in metadata['records'] if r['id'] in ids];sha=lambda b:hashlib.sha256(b).hexdigest();local=lambda tag:tag.rsplit('}',1)[-1]
def shape_kind(marker):
 visible=[e for e in marker.iter() if local(e.tag) in ('path','polygon','polyline','line','rect','circle','ellipse','use','image')]
 if len(visible)!=1:return 'compound_marker_'+str(len(visible))
 element=visible[0];tag=local(element.tag)
 if tag in ('circle','ellipse'):return 'circle_or_ellipse'
 if tag in ('use','image'):return 'referenced_or_raster_marker'
 pen=RecordingPen()
 try:
  if tag=='path':parse_path(element.get('d',''),pen)
  elif tag in ('polygon','polyline'):parse_path('M'+element.get('points','')+(' Z' if tag=='polygon' else ''),pen)
  elif tag=='line':parse_path('M'+element.get('x1','0')+','+element.get('y1','0')+' L'+element.get('x2','0')+','+element.get('y2','0'),pen)
  else:return tag+'_marker'
  if any(op not in ('moveTo','lineTo','closePath','endPath') for op,points in pen.value):return 'curved_marker'
  if sum(op=='moveTo' for op,points in pen.value)!=1:return 'multiple_subpath_marker'
  points=[tuple(p[0]) for op,p in pen.value if op in ('moveTo','lineTo')]
  if len(points)>1 and math.dist(points[0],points[-1])<1e-8:points.pop()
  closed=any(op=='closePath' for op,p in pen.value)
  if len(points)==3 and closed:
   area=abs(sum(points[i][0]*points[(i+1)%3][1]-points[(i+1)%3][0]*points[i][1] for i in range(3)))
   return 'closed_triangle' if area>1e-8 else 'degenerate_triangle'
  if len(points)==3 and not closed:return 'open_two_segment_vee'
  if len(points)==4 and closed:
   dx=max(abs(points[0][i]+points[2][i]-points[1][i]-points[3][i]) for i in (0,1));return 'closed_parallelogram_or_diamond' if dx<1e-7 else 'other_closed_quadrilateral'
  return ('closed' if closed else 'open')+'_line_only_'+str(len(points))
 except Exception:return 'marker_geometry_parse_failed'
def normalized(element):
 return [local(element.tag),{k:v for k,v in sorted(element.attrib.items()) if k not in ('id',)},(element.text or '').strip(),[normalized(e) for e in element]]
def scan(row):
 out={'id':row['id'],'code_sha256':row['code_sha256'],'image_sha256':row['image_sha256'],'source_code_sha256':row['source_code_sha256'],'qa3_group':row['qa3_group'],'owners':[],'definitions':[],'unresolved_references':[]}
 try:
  path=(R/row['original_source_code']).resolve();assert path.is_relative_to((R/'clean').resolve());raw=path.read_bytes();assert sha(raw)==row['source_code_sha256'];tree=E.fromstring(raw);definitions={e.get('id'):e for e in tree.iter() if local(e.tag)=='marker' and e.get('id')};summary={}
  for id,marker in definitions.items():
   kind=shape_kind(marker);attributes={k:marker.get(k) for k in ('viewBox','markerWidth','markerHeight','refX','refY','markerUnits','orient','overflow','preserveAspectRatio','style')};definition={'id':id,'kind':kind,'definition_sha256':sha(json.dumps(normalized(marker),sort_keys=True,separators=(',',':')).encode()),'attributes':attributes,'explicit_overflow':marker.get('overflow') or ('style:'+marker.get('style','') if 'overflow' in marker.get('style','') else None),'native_fit_and_viewport_proof_required':True};out['definitions'].append(definition);summary[id]=definition
  def walk(element,ignored=False):
   tag=local(element.tag);ignored=ignored or tag in ('defs','marker','symbol','clipPath','mask','pattern')
   if not ignored:
    style=dict((k.strip(),v.strip()) for declaration in element.get('style','').split(';') if ':' in declaration for k,v in [declaration.split(':',1)])
    for side in ('start','mid','end'):
     value=style.get('marker-'+side,element.get('marker-'+side,''));match=re.fullmatch(r'url\([\s\'\"]*#([^\s\'\")]+)[\s\'\"]*\)',value.strip())
     if not value or value=='none':continue
     if not match:out['unresolved_references'].append({'source_id':element.get('id'),'side':side,'value':value});continue
     marker=summary.get(match[1]);out['owners'].append({'source_id':element.get('id'),'tag':tag,'side':side,'marker_id':match[1],'kind':marker['kind'] if marker else 'missing_definition','definition_sha256':marker['definition_sha256'] if marker else None,'owner_stroke_width':style.get('stroke-width',element.get('stroke-width')),'owner_transform':element.get('transform'),'owner_style':element.get('style'),'owner_geometry_sha256':sha(json.dumps({k:element.get(k) for k in ('d','points','x1','y1','x2','y2')},sort_keys=True).encode())})
   for child in element:walk(child,ignored)
  walk(tree);css='\n'.join(e.text or '' for e in tree.iter() if local(e.tag)=='style');out['stylesheet_marker_declarations']=bool(re.search(r'marker-(?:start|mid|end)\s*:',css));out['source_hash_verified']=True
 except Exception as error:out['error']=repr(error)
 return out
started=time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:results=list(executor.map(scan,rows))
kinds=collections.Counter();cases=collections.Counter();families={};viewport=collections.Counter();owner_sides=collections.Counter()
for row in results:
 cases.update(set(owner['kind'] for owner in row['owners']))
 for owner in row['owners']:
  kinds[owner['kind']]+=1;owner_sides[owner['side']]+=1;digest=owner['definition_sha256'];family=families.setdefault(digest,{'kind':owner['kind'],'owner_count':0,'record_ids':[],'definition':next((d for d in row['definitions'] if d['definition_sha256']==digest),None)});family['owner_count']+=1
  if row['id'] not in family['record_ids'] and len(family['record_ids'])<4:family['record_ids'].append(row['id'])
 for definition in row['definitions']:viewport[str(definition['attributes'].get('overflow') or 'default_hidden_requires_actual_viewport_proof')]+=1
families=sorted(families.values(),key=lambda r:r['owner_count'],reverse=True)
report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'records':results,'scope_records':len(results),'hash_verified_records':sum(r.get('source_hash_verified',False) for r in results),'owner_occurrences_by_kind':dict(kinds),'records_by_marker_kind':dict(cases),'owner_sides':dict(owner_sides),'exact_definition_families':len(families),'top_definition_families':families[:40],'marker_overflow_declarations':dict(viewport),'stylesheet_marker_records':sum(r.get('stylesheet_marker_declarations',False) for r in results),'elapsed_seconds':time.time()-started,'scope':'Static original marker definitions plus direct/inline-style owner references only. CSS cascade/computed physical dimensions/source actual viewport/endpoint binding remain fresh DOM proof obligations; no source/quality acceptance, candidate, DB, queue or API writes.'};(P/'marker_family_census_v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('records','top_definition_families')}|{'top_definition_families':[{'kind':f['kind'],'owner_count':f['owner_count'],'record_ids':f['record_ids'],'attributes':f['definition']['attributes'] if f['definition'] else None} for f in families[:8]],'report':str(P/'marker_family_census_v1.json')},ensure_ascii=False),flush=True)
