import json,os,subprocess
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');D=W/'runtime/tectonic/warmup';D.mkdir(parents=True,exist_ok=True);source=r'''\documentclass{standalone}
\usepackage{tikz,pgfplots,amsmath,amssymb,xcolor}
\pgfplotsset{compat=1.18}
\usetikzlibrary{calc,positioning,shapes.geometric,arrows.meta,matrix,shadows,decorations.pathmorphing,fit,backgrounds}
\begin{document}
\begin{tikzpicture}\node[draw,fill=blue!10] (a) {Input $x_1$};\node[draw,right=of a] (b) {Output $\alpha$};\draw[->] (a)--(b);\end{tikzpicture}
\end{document}''';(D/'warmup.tex').write_text(source);env=dict(os.environ,XDG_CACHE_HOME=str(W/'runtime/tectonic/cache'),TECTONIC_CACHE_DIR=str(W/'runtime/tectonic/cache'));r=subprocess.run([str(W/'runtime/tectonic/tectonic'),'--untrusted','--keep-logs','--keep-intermediates',str(D/'warmup.tex')],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600);(D/'compile.stdout').write_text(r.stdout);(D/'compile.stderr').write_text(r.stderr);out={'returncode':r.returncode,'pdf_exists':(D/'warmup.pdf').exists(),'stdout_tail':r.stdout[-2000:],'stderr_tail':r.stderr[-2000:]};(W/'tex_warmup.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
