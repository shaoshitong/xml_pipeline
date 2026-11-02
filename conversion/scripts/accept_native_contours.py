import sys,json,sqlite3,hashlib,io,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now,pair
D=sqlite3.connect(W/'jobs.sqlite',timeout=120);B=W/'native_contour_repair';review=json.loads((B/'root_visual_review.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest();results=[]
canon=r'''xml=>{document.body.innerHTML='<div id="g" style="position:relative;width:8192px;height:8192px"></div>';const g=new Graph(document.getElementById('g')),d=mxUtils.parseXml(xml);new mxCodec(d).decode(d.getElementsByTagName('mxGraphModel')[0],g.model);const result=mxUtils.getXml(new mxCodec().encode(g.model));g.destroy();return result;}'''
def restricted_canonical(xml,changes):
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};by={}
 for c in changes:by.setdefault(c['edge'],[]).append(c['terminal'])
 for id,sides in by.items():
  c=cells[id];parts=(c.get('style') or '').split(';');drop=set()
  for side in sides:
   c.attrib.pop(side,None);prefix='exit' if side=='source' else 'entry';drop.update(prefix+s for s in ['X','Y','Perimeter','Dx','Dy'])
  c.set('style',';'.join(x for x in parts if x and x.split('=',1)[0] not in drop)+';')
 return E.canonicalize(E.tostring(root,encoding='unicode'))
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);pg=b.new_page();pg.route('**/*',lambda r:r.abort());pg.set_content('<html></html>');pg.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');pg.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'))
 for id in [i for i in review['reviewed_ids'] if not sys.argv[1:] or i in sys.argv[1:]]:
  try:
   audit=json.loads((B/id/'audit.json').read_text());assert audit['state']=='pixel_exact_fully_bound';state,raw,prep=D.execute('select state,output_record,input_manifest from jobs where id=?',(id,)).fetchone();assert state=='rendered';out=json.loads(raw);inp=json.loads(prep);xml=(B/id/'candidate.drawio').read_text();png=(B/id/'candidate.png').read_bytes();before=(R/out['code_file']).read_text();assert sha(before.encode())==audit['previous_code_sha256']==out['code_sha256'];assert sha(xml.encode())==audit['code_sha256'] and sha(png)==audit['image_sha256'];assert out['source_page_count']==1
   assert restricted_canonical(pg.evaluate(canon,before),audit['changes'])==restricted_canonical(pg.evaluate(canon,xml),audit['changes']),'Unrelated native object/style/geometry changed'
   data,code=pair(out['source_record']);original=Image.open(io.BytesIO(data)).convert('RGBA');white=Image.new('RGBA',original.size,'white');white.alpha_composite(original);fresh=native.native_job(xml,inp['width'],inp['height'],90,native.renderer_path(R),8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'];assert fresh['png']==png,'Fresh native PNG differs';pred=Image.open(io.BytesIO(png)).convert('RGB');assert pred.size==white.size and np.array_equal(pred,white.convert('RGB')),'Original pixel comparison failed';root=E.fromstring(xml);parents={c:p for p in root.iter() for c in p};cid=lambda c:c.get('id') or parents.get(c,E.Element('none')).get('id');cells=list(root.iter('mxCell'));ids=[cid(c) for c in cells];verts={cid(c) for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];assert len(ids)==len(set(ids)) and all(ids) and verts;assert all(c.get('source') in verts and c.get('target') in verts for c in edges);assert 'image=' not in xml and 'data:image' not in xml,'Raster resource requires separate asset audit';assert fresh['native_render'].get('blocked_resource_requests')==0;assert not fresh['native_render'].get('content_outside_declared_canvas') or fresh['native_render'].get('selected_image')=='complete_tight_graph';assert all(abs(m['dx']-17)<.05 and abs(m['dy']-11)<.05 for m in audit['moves'])
   proof={'at':now(),'id':id,'source_hashes_verified':True,'fresh_official_drawio_png_identical':True,'original_reference_pixel_identical':True,'only_unique_contour_terminal_constraints_changed':True,'actual_changed_endpoint_moves':audit['moves'],'all_edges_valid_bound':True,'root_visual_review':'conversion/native_contour_repair/root_visual_review.json','accepted':True};(B/id/'acceptance.json').write_text(json.dumps(proof,indent=2));out.update(conversion_method='native_xml_normalization_and_unique_rendered_contour_binding_v2',quality_state='accepted_exact_native_rendered_contours_and_root_review',code_sha256=sha(xml.encode()),image_sha256=sha(png),bound_edges=len(edges),render=fresh['native_render'],binding_repair=audit,accepted_at_utc=now(),validation=proof,root_acceptance=str((B/id/'acceptance.json').relative_to(R)),model=None,model_configuration=None)
   D.execute('begin immediate');assert D.execute('select state,output_record from jobs where id=?',(id,)).fetchone()==(state,raw),'Job changed concurrently'
   for key,blob in [('code_file',xml.encode()),('image_file',png)]:
    path=R/out[key];assert path.resolve().is_relative_to(R/'clean');tmp=path.with_suffix(path.suffix+'.contour.tmp');tmp.write_bytes(blob);tmp.replace(path)
   path=R/out['code_file'];meta=path.parent/'conversion.json';tmp=meta.with_suffix('.tmp');tmp.write_text(json.dumps(out,ensure_ascii=False,indent=2));tmp.replace(meta);D.execute('update jobs set state="accepted",output_record=?,error=NULL,worker_pid=NULL,updated_at=? where id=?',(json.dumps(out,ensure_ascii=False),now(),id));D.execute('update harness_queue_v3 set state="resolved_by_deterministic_acceptance",error=NULL where id=? and state="queued"',(id,));D.commit();row={'id':id,'accepted':True}
  except Exception as e:D.rollback();row={'id':id,'accepted':False,'error':repr(e)}
  results.append(row);print(json.dumps(row),flush=True)
 b.close()
(B/'acceptance_summary.json').write_text(json.dumps({'at':now(),'results':results},indent=2))
