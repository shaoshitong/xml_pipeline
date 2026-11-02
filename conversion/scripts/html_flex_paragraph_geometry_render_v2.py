"""Persistent, isolated official native renderer with replayable export files."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
def run(xml,size,work):
 from initial_conversion_process_v1 import run as owned_run
 work=Path(work).resolve();assert work.is_relative_to(W.resolve());work.mkdir(parents=True,exist_ok=False)
 renderer=W/'rendering_html_flex_geometry_v2/remote_render.py';bundle=renderer.parent/'assets/viewer-static.min.js';bundle_hash=hashlib.sha256(bundle.read_bytes()).hexdigest();assert bundle_hash==hashlib.sha256((W/'rendering_html_source_paragraph_v9/assets/viewer-static.min.js').read_bytes()).hexdigest(),'geometry_observer_official_bundle_identity_changed';source=work/'input_source.drawio';source.write_text(xml);started=time.monotonic()
 command=[sys.executable,'-B',str(renderer),'--kind','drawio','--source',str(source),'--width',str(size[0]),'--height',str(size[1])]
 process=owned_run(command,work/'owned_process',180,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','HTML_FLEX_GEOMETRY_OBSERVER_ONLY':'1'});(work/'owned_process.json').write_text(json.dumps(process,sort_keys=True))
 if not process.get('cleanup_complete')or process.get('refused'):raise RuntimeError('infrastructure_HTML_source_geometry_observer_ownership_or_cleanup_failed')
 if process.get('deadline_exceeded'):raise TimeoutError('HTML_source_geometry_observer_timeout')
 if not process.get('ok'):raise ValueError('HTML_source_actual_geometry_observer_pending:'+Path(process['stderr_file']).read_text(errors='replace')[-3000:])
 info=json.loads((work/'native_render.json').read_bytes());assert info.get('ok')and info.get('actual_screenshot_count')==0 and not info.get('actual_font_or_glyph_admission'),'geometry_seed_must_not_claim_paint_or_fonts'
 assert info['viewer_bundle_sha256']==bundle_hash==hashlib.sha256(bundle.read_bytes()).hexdigest(),'geometry_observer_runtime_changed'
 assert source.read_text()==xml,'geometry_seed_original_XML_changed'
 return{'ok':True,'native_render':info,'seconds':time.monotonic()-started,'actual_screenshot_count':0,'font_or_glyph_evidence':False,'raw_render_directory':str(work)}
