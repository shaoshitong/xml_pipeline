"""Publish the individually reviewed original-scale Mermaid pilot, with fresh proof."""
import hashlib,json,sqlite3,shutil,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,native,now
from durable_sqlite import begin,commit
from mermaid_native_v1 import build
from mermaid_semantic_v4 import check as semantic
from mermaid_geometry_coverage import check as geometry
from svg_source_coverage_v2 import audit as coverage
from harness_context_v4 import structure
from native_move_audit import audit as move_audit
from strict_canvas_gate import require_declared_page
from svg_batch import metric
ID='0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641'
OLD='322d7b6d2ac9b624af53c680aabf0a8852269508dad499e8dbf5393a9161115d'
NEW='157d21f034a5bc9c31e1fa986f88d9a737dfdeccec60d64a893b15ff1a549935'
sha=lambda b:hashlib.sha256(b).hexdigest()
D=sqlite3.connect(W/'jobs.sqlite',timeout=2)
state,raw=D.execute('select state,output_record from jobs where id=?',(ID,)).fetchone()
r=json.loads(raw);assert state=='harness_review_pending' and r['code_sha256']==OLD
B=W/'mermaid_reference_fit'/ID
assert json.loads((B/'before_record.json').read_text())==r
for key,hkey in [('code_file','code_sha256'),('image_file','image_sha256'),('original_reference','source_image_sha256'),('original_source_code','source_code_sha256'),('source_render_svg','source_render_svg_sha256')]:
 p=R/r[key];assert p.resolve().is_relative_to(R/'clean') and sha(p.read_bytes())==r[hkey],key
xml=(B/'candidate.drawio').read_text();png=(B/'candidate.png').read_bytes();assert sha(xml.encode())==NEW
w,h=Image.open(R/r['original_reference']).size
dom=json.loads((B/'source_dom.json').read_text());ast=json.loads((B/'source_ast.json').read_text());md=json.loads((B/'source_geometry.json').read_text())
unembedded,stats,processed=build(dom,w,h,md)
assert unembedded==(B/'unembedded.drawio').read_text()
cov=coverage(processed,xml,stats);geo=geometry(ast,xml,md);sem=semantic(ast,xml);struct=structure(xml,{})
assert cov['ok'] and geo['ok'] and sem['status']=='node_edge_text_match' and struct['ok']
assert geo['source_nodes']==7 and geo['source_edges']==geo['native_markers']==10
assert not dom['issues'] and struct['edges']==struct['bound_edges']==10 and not struct['source_asset_image_cells']
before=native.native_job(unembedded,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
after=native.native_job(xml,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
assert before['ok'] and after['ok'] and before['png']==after['png']==png
require_declared_page(after['native_render'],w,h)
moves=move_audit(xml);assert len(moves['moves'])==20
for m in moves['moves']:
 assert abs(m['delta']['x']-17)<1e-6 and abs(m['delta']['y']-11)<1e-6
 for c in m['child_deltas']:assert abs(c['x']-17)<1e-6 and abs(c['y']-11)<1e-6
fonts=json.loads((B/'fonts.json').read_text());fp=json.loads((B/'font_proof.json').read_text());assert not fp['issues'] and fp['text_cells_observed']==7
assert {x['physical_postscript_name'] for x in fonts.values()}=={'TrebuchetMS'}
usage=after['native_render']['actual_platform_font_usage'];assert usage
for row in usage:
 for f in row.get('fonts',row.get('actual_fonts',[])):
  if f.get('glyphCount'):assert f['isCustomFont'] and f['postScriptName']=='TrebuchetMS',f
fit=json.loads((W/'mermaid_variant_source_probe'/ID/'reference_scale_fit.json').read_text())
assert len(fit['pairs'])==7 and max(x['max_abs_residual'] for x in fit['fits'].values())<1
proof={'at':now(),'id':ID,'input_code_sha256':OLD,'output_code_sha256':NEW,'output_image_sha256':sha(png),'source_coverage':cov,'source_geometry':geo,'source_semantic':sem,'actual_endpoint_moves':20,'strict_canvas_pass':True,'fresh_native_png_byte_identical':True,'embedded_fonts_preserve_exact_pixels':True,'physical_fonts':['TrebuchetMS'],'source_dom_issues':[], 'global_source_fit':{'svg_width':1552,'svg_height':396,'left':0,'top':0,'reference_size':[w,h],'node_fill_boundary_fit':fit,'scope':'One affine transform of entire source SVG; no per-node/content/label/topology edits'},'reference_ssim_before':r['metrics']['original_reference_ssim_512'],'reference_ssim_after':metric((R/r['original_reference']).read_bytes(),png),'source_native_ssim':metric((B/'source_fit.png').read_bytes(),png),'root_visual_review':{'reviewer':'root','pass':True,'evidence':'Compared original, fitted source, and actual native PNG side by side. All seven named nodes, four fill classes, ten directed connections, endpoint positions and Trebuchet letterforms retained. Earlier Arial candidate with model score99 rejected. Native triangular markers and sampled curves differ slightly in contour/antialiasing; no material omitted content, displaced group or clipping observed.','exact_pixels':False,'case_specific':True},'accepted':True}
(B/'root_acceptance.json').write_text(json.dumps(proof,indent=2))
# Versioned source files keep all older frozen provenance hashes intact.
clean=(R/r['code_file']).parent/'source_fit_v1';clean.mkdir(exist_ok=True)
files={}
for name in ['source_fit.svg','source_fit.png','source_dom.json','source_ast.json','source_geometry.json','source_stats.json']:
 dest=clean/name;data=(B/name).read_bytes()
 if dest.exists():assert dest.read_bytes()==data
 else:dest.write_bytes(data)
 files[name]={'file':str(dest.relative_to(R)),'sha256':sha(data)}
for f in fonts.values():
 data=open(f['file'],'rb').read();assert sha(data)==f['sha256']==f['original_sha256']
 dest=R/'clean/font_assets'/('native_'+f['sha256']+'.ttf')
 if dest.exists():assert dest.read_bytes()==data
 else:dest.write_bytes(data)
 f['file']=f['original_file']=str(dest.relative_to(R))
archive=B/'previous_candidate';archive.mkdir(exist_ok=True)
for key,name in [('code_file','diagram.drawio'),('image_file','image.png')]:
 dest=archive/name;data=(R/r[key]).read_bytes()
 if dest.exists():assert dest.read_bytes()==data
 else:dest.write_bytes(data)
(archive/'conversion.json').write_text(raw)
keep=['id','source_pair_sha256','source','category','source_format','source_record','source_image_sha256','source_code_sha256','original_reference','original_source_code','image_file','code_file','format','original_asset_root','original_vector_assets','source_assets','used_assets']
out={k:r[k] for k in keep if k in r};out.update(code_sha256=NEW,image_sha256=sha(png),conversion_method='mermaid_10_9_1_source_global_reference_fit_native_editable_v1',model=None,model_configuration=None,previous_candidate_archive=str(archive.relative_to(R)),vertices=struct['vertices'],edges=struct['edges'],bound_edges=struct['bound_edges'],source_editability=geo,source_coverage=cov,svg_conversion=stats,native_embedded_fonts=list(fonts.values()),native_font_validation={'method':'actual_physical_font_embedding_and_byte_identical_native_render','output_code_sha256':NEW,'native_pixels_unchanged':True,'audit':str((B/'root_acceptance.json').relative_to(R))},native_source_geometry_repair={'method':'whole_source_affine_from_original_fill_boundaries','files':files,'audit':str((B/'root_acceptance.json').relative_to(R))},source_render_svg=files['source_fit.svg']['file'],source_render_svg_sha256=files['source_fit.svg']['sha256'],render={k:v for k,v in after['native_render'].items() if k!='actual_text_positions'},metrics={'original_reference_ssim_512':proof['reference_ssim_after'],'source_render_vs_drawio_ssim_512':proof['source_native_ssim']},quality_state='accepted_source_geometry_fonts_and_root_visual_review',accepted_at_utc=now(),root_acceptance=str((B/'root_acceptance.json').relative_to(R)),root_review=proof['root_visual_review'])
(B/'candidate_record.json').write_text(json.dumps(out,indent=2));(B/'after_render.json').write_text(json.dumps(after['native_render'],indent=2))
begin(D);assert D.execute('select state,output_record from jobs where id=?',(ID,)).fetchone()==(state,raw)
assert sha((R/r['code_file']).read_bytes())==OLD and sha((R/r['image_file']).read_bytes())==r['image_sha256']
for src,dst in [(B/'candidate.drawio',R/out['code_file']),(B/'candidate.png',R/out['image_file']),(B/'candidate_record.json',(R/out['code_file']).parent/'conversion.json')]:
 tmp=dst.with_suffix(dst.suffix+'.referencefit.tmp');shutil.copyfile(src,tmp);tmp.replace(dst)
D.execute('update jobs set state="accepted",output_record=?,worker_pid=NULL,error=NULL,updated_at=? where id=?',(json.dumps(out),now(),ID))
D.execute('update harness_queue_v3 set state="resolved_by_deterministic_acceptance",error=NULL where id=? and state!="running"',(ID,));commit(D)
(B/'committed.json').write_text(json.dumps({'at':now(),'code_sha256':NEW,'image_sha256':sha(png),'accepted':True}));print(json.dumps(proof))
