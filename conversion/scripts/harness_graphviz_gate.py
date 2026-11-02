"""Source-derived guard against declaring fixed standalone arrow polygons editable."""
import json,math,hashlib,xml.etree.ElementTree as E
from native_worker import R

def check(previous,xml):
 proof=(previous or {}).get('native_source_font_repair',{});dompath=proof.get('source_after_dom_file')
 if not dompath:return {'ok':True,'applicable':False,'scope':'No preserved source Graphviz DOM available; independent acceptance still required.'}
 path=(R/dompath).resolve();assert path.is_relative_to(R/'clean');blob=path.read_bytes();assert hashlib.sha256(blob).hexdigest()==proof['source_after_dom_sha256'];dom=json.loads(blob);groups={}
 for o in dom['objects']:
  if o.get('edge'):groups.setdefault(o['edge']['id'],[]).append(o)
 cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')};errors=[];requirements=[]
 for group,items in groups.items():
  paths=[o for o in items if o['tag']=='path' and o.get('sampledPoints')];arrows=[o for o in items if o['tag']=='polygon']
  if not arrows:continue
  if len(paths)!=1:errors.append({'group':group,'reason':'source_arrow_to_edge_mapping_ambiguous'});continue
  p=paths[0];c=cells.get(p['id'])
  if c is None or c.get('edge')!='1':errors.append({'group':group,'reason':'changed_cell_ids_require_explicit_source_mapping'});continue
  st=dict(v.split('=',1) for v in c.get('style','').split(';') if '=' in v)
  for a in arrows:
   b=a['bbox'];center=[b['x']+b['w']/2,b['y']+b['h']/2];dist=[math.dist(center,p['sampledPoints'][i]) for i in [0,-1]]
   if abs(dist[0]-dist[1])<1:errors.append({'arrow':a['id'],'reason':'arrow_side_ambiguous'});continue
   side='start' if dist[0]<dist[1] else 'end';r={'edge':p['id'],'arrow':a['id'],'side':side,'source_group':group};requirements.append(r)
   if st.get(side+'Arrow','none')=='none':errors.append({**r,'reason':'source_arrow_missing_native_attached_marker'})
   if a['id'] in cells:errors.append({**r,'reason':'source_arrow_still_a_separate_vertex'})
 return {'ok':not errors,'applicable':bool(requirements),'requirements':requirements,'errors':errors,'scope':'Exact preserved Graphviz edge IDs and source arrow side; requires native attached marker and removal of old standalone arrow object. Does not establish visual fidelity or final acceptance.'}
