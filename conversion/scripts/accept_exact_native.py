import hashlib,json,sqlite3,xml.etree.ElementTree as ET
from pathlib import Path
from native_worker import R,W,now
D=sqlite3.connect(W/'jobs.sqlite');D.execute('PRAGMA busy_timeout=30000');accepted=[];issues=[]
for id,raw in D.execute('SELECT id,output_record FROM jobs WHERE state="rendered" AND route="native" AND output_record IS NOT NULL').fetchall():
 x=json.loads(raw)
 if not x.get('metrics',{}).get('exact_reference_pixels'):continue
 if x['source_page_count']!=1 or x['bound_edges']!=x['edges']:continue
 xml=(R/x['code_file']).read_bytes();png=(R/x['image_file']).read_bytes();root=ET.fromstring(xml);cells=list(root.iter('mxCell'));parents={child:parent for parent in root.iter() for child in parent};cell_id=lambda c:c.get('id') or parents.get(c,ET.Element('none')).get('id');ids=[cell_id(c) for c in cells];vertices={cell_id(c) for c in cells if c.get('vertex')=='1'}
 checks={'xml_hash':hashlib.sha256(xml).hexdigest()==x['code_sha256'],'png_hash':hashlib.sha256(png).hexdigest()==x['image_sha256'],'unique_cell_ids':all(ids) and len(set(ids))==len(ids),'valid_bound_edges':all(c.get('source') in vertices and c.get('target') in vertices for c in cells if c.get('edge')=='1'),'nonempty_editable_vertices':bool(vertices),'no_embedded_raster':b'data:image' not in xml,'no_blocked_resources':x['render'].get('blocked_resource_requests')==0,'complete_graph_render':not x['render'].get('content_outside_declared_canvas') or x['render'].get('selected_image')=='complete_tight_graph','exact_reference_pixels':True,'single_source_page':True}
 if not all(checks.values()):issues.append({'id':id,'checks':checks});continue
 x.update(quality_state='accepted_exact_native',validation=checks,model=None,model_configuration=None,accepted_at_utc=now(),fidelity_basis=('Actual rendered pixels exactly equal original reference after alpha-on-white composition; uniquely touching rectangular node boundaries were bound with unchanged pixel rendering, and all terminals are valid vertices.' if x.get('binding_repair') else 'Actual rendered pixels exactly equal original reference pixels after explicit alpha-on-white composition, with unchanged native graph and all edges bound to valid vertices.'))
 (R/x['code_file']).parent.joinpath('conversion.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');D.execute('UPDATE jobs SET state="accepted",output_record=?,updated_at=? WHERE id=?',(json.dumps(x,ensure_ascii=False),now(),id));accepted.append(id)
D.commit()
# The Harness pilot visibly misroutes policy revitalization; keep it open for repair.
id='012a101c6590f806e7e3e26853ae18d9d98a6bc7e58f765a1c674d76a21b0732';D.execute('UPDATE jobs SET state="needs_quality_repair",error=?,updated_at=? WHERE id=? AND state="harness_rendered"',('Root visual review: policy-revitalization arrows route through panel interiors instead of original outer loop; panel proportions and typography differ. Two render-successful rounds are NOT accepted.',now(),id));D.commit()
index=R/'release/drawio_manifest.inprogress.jsonl'
with index.open('w') as f:
 for (raw,) in D.execute('SELECT output_record FROM jobs WHERE state="accepted" ORDER BY id'):f.write(raw+'\n')
result={'created_at_utc':now(),'newly_accepted':len(accepted),'failed_strict_checks':issues,'all_job_states':dict(D.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state').fetchall()),'index':str(index),'goal_complete':False,'note':'Strict native exact-pixel/structure acceptance only; final corpus-wide stratified visual audit and all other jobs remain required.'};(W/'native_exact_acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
