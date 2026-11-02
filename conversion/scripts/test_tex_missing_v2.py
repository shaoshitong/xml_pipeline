import json
from tex_missing_v2 import missing_files
cases=[
 ('caused by: failed to open input file "pgfmodulebending.code.tex"',['pgfmodulebending.code.tex']),
 ('warning: Could not read encoding file: cm-super-t1.enc\nwarning: >> This font is mapped to a physical font "sfrm0800.pfb".\nwarning: >> Please check if kpathsea library can find this font: sfrm0800.pfb',['cm-super-t1.enc','sfrm0800.pfb']),
 ("error: revtex4-2.cls:7659: ! LaTeX Error: File `aps4-2.rtx' not found.",['aps4-2.rtx']),
 ('error: soul.sty:54: Font \\SOUL@tt=ectt1000 not loadable: Metric (TFM) file or installed font not found',['ectt1000.tfm']),
 ('Font \\foo=cmr10 at 10.0pt not loadable: Metric (TFM) file not found',['cmr10.tfm']),
 ("did not find the pgfplots library 'fillbetween'",['pgfplotslibraryfillbetween.code.tex']),
 ('error: source.tex:32: Undefined control sequence',[]),
 ('failed to open input file "../../private.tex"',[]),
 ('failed to open input file "/etc/passwd"',[]),
 ('failed to open input file "https://example.org/foo.tex"',[]),
 ('failed to open input file "$(bad).sty"',[]),
 ("File `figure.png' not found",[]),
 ('Please check if kpathsea library can find this font: wrong.exe',[]),
 ('File `cmr10.tfm\nmalicious.sty\' not found',[]),
]
for text,expected in cases:assert missing_files(text)==expected,(text,missing_files(text),expected)
print(json.dumps({'passed':len(cases),'ok':True}))
