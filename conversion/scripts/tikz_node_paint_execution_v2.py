"""Original bytes plus nonpainting PGF hooks in private pinned pdfLaTeX2025.

Actual Poppler100dpi equality proves that instrumentation did not change any
page. Opened runtime files are individually hashed from pdfTeX recorder output.
No source rewrite, reference fitting, network access or canonical state writes.
"""
from pathlib import Path
import hashlib,json,math,os,sys
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
RUNTIME=W/'runtime/texlive2025_source_v1';BIN=RUNTIME/'texlive/bin/x86_64-linux'
sha=lambda b:hashlib.sha256(b).hexdigest()

def actual_pdf_text_positions(page,scale):
 rows=[]
 for n,trace in enumerate(page.get_texttrace()):
  if trace['type']==3:continue
  chars=[]
  for unicode,gid,origin,bbox in trace['chars']:
   x0,y0,x1,y1=bbox
   chars.append({'text':chr(unicode) if 0<=unicode<=0x10ffff else '\ufffd','x':x0*scale,'y':y0*scale,'width':(x1-x0)*scale,'height':(y1-y0)*scale})
  rows.append({'cell':'actual_pdf_display_list_text_'+str(n),'runs':[{'chars':chars}]})
 return rows

def density(reference):
 from PIL import Image
 import io
 info=Image.open(io.BytesIO(reference)).info;d=info.get('dpi')
 if not d or len(d)!=2 or not all(math.isfinite(x) and abs(x-100)<.001 for x in d):
  raise ValueError('source_PNG_does_not_declare_supported_100dpi_profile')
 return 100.

def raster_pdf(pdf,directory,dpi=100):
 from sandbox_runner import run
 from PIL import Image
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
 (directory/'source.pdf').write_bytes(Path(pdf).read_bytes())
 argv=['/usr/bin/pdftoppm','-png','-r',str(int(dpi)),'-singlefile','/work/source.pdf','/work/source']
 proc=run(directory,argv,timeout=120)
 (directory/'render.stdout').write_text(proc.stdout);(directory/'render.stderr').write_text(proc.stderr)
 if proc.returncode:raise ValueError('actual_source_Poppler_render_failed:'+proc.stderr[-1800:])
 p=directory/'source.png';data=p.read_bytes();im=Image.open(p).convert('RGB')
 return {'png':data,'pixels_sha256':sha(im.tobytes()),'canvas':list(im.size),'renderer':'Poppler_pdftoppm_default_100dpi','argv':argv,'density_dpi':dpi}

def runtime_configuration():
 receipt=json.loads((RUNTIME/'receipt.json').read_bytes())
 if receipt.get('stage')!='complete' or 'TeX Live 2025' not in receipt['pdflatex_version']:
  raise RuntimeError('infrastructure_private_pdfLaTeX2025_not_ready')
 if sha((RUNTIME/'runtime_manifest.json').read_bytes())!=receipt['runtime_manifest_sha256']:
  raise RuntimeError('infrastructure_private_pdfLaTeX2025_manifest_changed')
 names=[RUNTIME/'receipt.json',RUNTIME/'runtime_manifest.json',BIN/'pdftex',Path('/usr/bin/pdftoppm')]
 for n in ('tikz.code.tex','pgfmoduleshapes.code.tex','pgfcorearrows.code.tex','latex.ltx','pdflatex.fmt','pdftex.map'):
  candidates=list((RUNTIME/'texlive').rglob(n))
  if len(candidates)!=1:raise RuntimeError('infrastructure_pdfLaTeX2025_runtime_core_missing_or_ambiguous:'+n)
  names.append(candidates[0])
 return {'policy':'private_historic_final_TeXLive2025_pdfLaTeX_Poppler100dpi_v1',
         'repository':receipt['repository'],'runtime_manifest_sha256':receipt['runtime_manifest_sha256'],
         'pins':{str(p):sha(p.read_bytes()) for p in names},'shell_escape':False,'source_rewriting':False}

def recorder_inputs(directory):
 directory=Path(directory).resolve(strict=True);out={}
 for line in (directory/'source.fls').read_text(errors='strict').splitlines():
  if not line.startswith('INPUT '):continue
  name=line[6:];p=Path(name)
  if str(p).startswith('/work/'):p=directory/str(p)[6:]
  elif not p.is_absolute():p=directory/p
  p=p.resolve(strict=True)
  if not (p.is_relative_to(RUNTIME.resolve()) or p.is_relative_to(directory.resolve())):
   raise ValueError('source_opened_unpinned_nonruntime_input:'+str(p))
  key=('runtime/'+str(p.relative_to(RUNTIME.resolve()))) if p.is_relative_to(RUNTIME.resolve()) else ('case/'+str(p.relative_to(directory)))
  if p.is_file():out[key]={'file':str(p),'sha256':sha(p.read_bytes())}
 return out

def compile_execution_graph(data,directory,dpi=100):
 from sandbox_runner import run
 from tikz_node_paint_events_v2 import parse_events,legacy_events,ownership
 from tikz_execution_graph import graph_from_events
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
 configuration=runtime_configuration();hook=(W/'scripts/tikz_node_paint_hooks_v2.tex').read_bytes()
 wrappers={'baseline':b'\\input{original_source.tex}\n','instrumented':b'\\AtBeginDocument{\\input{tikz_execution_graph_hooks.tex}}\n\\input{original_source.tex}\n'}
 result={'version':'actual_pdfLaTeX2025_PGF_node_driver_paint_ownership_v2',
         'source_sha256':sha(data),'source_bytes_unchanged':True,'hook_sha256':sha(hook),
         'configuration':configuration,'runs':{},'published':False,'density_dpi':dpi}
 try:
  renders={}
  for mode,wrapper in wrappers.items():
   work=directory/mode;work.mkdir();(work/'original_source.tex').write_bytes(data);(work/'source.tex').write_bytes(wrapper)
   for n in ('texmf-var','texmf-config','texmf-home'):(work/n).mkdir()
   if mode=='instrumented':(work/'tikz_execution_graph_hooks.tex').write_bytes(hook)
   env={'PATH':str(BIN)+':/usr/bin:/bin','TEXMFVAR':'/work/texmf-var','TEXMFCONFIG':'/work/texmf-config','TEXMFHOME':'/work/texmf-home',
        'openin_any':'p','openout_any':'p','shell_escape':'0','MKTEXFMT':'0','MKTEXPK':'0','MKTEXTFM':'0'}
   argv=[str(BIN/'pdflatex'),'-no-shell-escape','-interaction=nonstopmode','-halt-on-error','-file-line-error','-recorder','-output-directory=/work','/work/source.tex']
   proc=run(work,argv,timeout=150,extra_ro=[(RUNTIME,RUNTIME)],extra_env=env)
   (work/'stdout.log').write_text(proc.stdout);(work/'stderr.log').write_text(proc.stderr)
   result['runs'][mode]={'returncode':proc.returncode,'wrapper_sha256':sha(wrapper),'argv':argv}
   if (work/'original_source.tex').read_bytes()!=data:raise ValueError('original_source_bytes_changed')
   if proc.returncode:raise ValueError('original_pdfLaTeX_compilation_failed:'+mode+':'+proc.stdout[-2800:]+proc.stderr[-500:])
   opened=recorder_inputs(work);result['runs'][mode].update(pdf_sha256=sha((work/'source.pdf').read_bytes()),opened_inputs=opened)
   renders[mode]=raster_pdf(work/'source.pdf',work/'actual_Poppler100dpi',dpi)
  if (renders['baseline']['canvas'],renders['baseline']['pixels_sha256'])!=(renders['instrumented']['canvas'],renders['instrumented']['pixels_sha256']):
   raise ValueError('instrumentation_changed_actual_Poppler_PDF_pixels')
  sys.path.append(str(W/'runtime/python_packages'));import pymupdf
  with pymupdf.open(directory/'baseline/source.pdf') as a,pymupdf.open(directory/'instrumented/source.pdf') as b:
   if len(a)!=1 or len(b)!=1 or a[0].rotation or b[0].rotation:raise ValueError('source_requires_single_unrotated_page')
  trace=(directory/'instrumented/source.iic').read_bytes();result['execution_trace_sha256']=sha(trace)
  result['instrumentation_pdf_pixel_equivalence']=[{'page':0,'pixel_identical':True,'baseline_pixel_sha256':renders['baseline']['pixels_sha256'],'instrumented_pixel_sha256':renders['instrumented']['pixels_sha256'],'size':renders['baseline']['canvas'],'actual_renderer':'Poppler100dpi'}]
  events=parse_events(trace.decode());result['graph']=graph_from_events(legacy_events(events));result['node_paint_ownership']=ownership(events);result['ok']=result['graph']['ok']
 except Exception as error:result.update(ok=False,error_type=type(error).__name__,error=str(error))
 (directory/'execution_graph.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 return result
