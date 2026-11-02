"""Persistent, isolated official native renderer with replayable export files."""
from pathlib import Path
import json,os,subprocess,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
def run(xml,size,work):
 from native_worker import native
 work=Path(work).resolve();assert work.is_relative_to(W.resolve());work.mkdir(parents=True,exist_ok=False);renderer=W/'rendering_html_source_paragraph_v9/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json';argv=[sys.executable,str(Path(native.__file__).resolve()),'--render-native-only','--drawio-renderer',str(renderer),'--render-directory',str(work),'--width',str(size[0]),'--height',str(size[1]),'--max-side','8192','--runtime-cache',str(runtime)];started=time.monotonic()
 from initial_conversion_process_v1 import run as owned_run
 source=work/'input_source.drawio';source.write_text(xml)
 shim="import runpy,sys,pathlib;p=sys.argv[1];q=sys.argv[2];sys.path.insert(0,str(pathlib.Path(p).parent));sys.stdin=open(q,'r',encoding='utf-8');sys.argv=[p]+sys.argv[3:];runpy.run_path(p,run_name='__main__')"
 command=[sys.executable,'-B','-c',shim,argv[1],str(source),*argv[2:]]
 result=owned_run(command,work/'owned_process',180,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'});(work/'owned_process.json').write_text(json.dumps(result,sort_keys=True))
 if not result.get('cleanup_complete')or result.get('refused'):raise RuntimeError('infrastructure_HTML_source_private_renderer_ownership_or_cleanup_failed')
 if result.get('deadline_exceeded'):raise TimeoutError('HTML_source_private_native_renderer_timeout')
 if not result.get('ok'):raise ValueError('HTML_source_actual_native_renderer_pending:'+Path(result['stderr_file']).read_text(errors='replace')[-3000:])
 info=json.loads((work/'native_render.json').read_bytes());png=(work/'render.png').read_bytes();proof=work/'source_html_export.proof.json'
 if proof.is_file():
  info['underlying_inspection_selector']=info.get('selected_image');info['selected_image']='original_HTML_source_viewport';info['source_html_export']=json.loads(proof.read_bytes())
 return{'ok':True,'png':png,'native_render':info,'seconds':time.monotonic()-started,'raw_render_directory':str(work),'inspection_png':str(work/'render.inspection.png')if proof.is_file()else str(work/'render.png'),'export_proof':str(proof)if proof.is_file()else None,'svg_export':str(work/'render.svg')}
