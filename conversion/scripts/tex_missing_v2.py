"""Recognize explicitly named missing bundle dependencies, without guessing fonts."""
import re

EXTENSIONS=('.sty','.cls','.clo','.tex','.fd','.def','.tfm','.otf','.ttf','.map','.enc','.pfb','.vf','.rtx','.ltx','.cfg','.ldf')

def missing_files(text):
    names=set()
    patterns=[
        r"File [`']([^'`\n]+)' not found",
        r'failed to open input file "([^"\n]+)"',
        r'Could not read encoding file:\s*([^\s]+)',
        r'Please check if kpathsea library can find this font:\s*([^\s]+)',
        r'This font is mapped to a physical font "([^"\n]+)"',
    ]
    for pattern in patterns:names.update(re.findall(pattern,text))
    for prefix in ('tikz','pgf','pgfplots'):
        for lib in re.findall(r"did not find the "+prefix+r" library '([A-Za-z0-9_.-]+)'",text):
            names.add(prefix+'library'+lib+'.code.tex')
    for name in re.findall(r'Font\s+[^\n=]+?=([A-Za-z0-9_.-]+)(?:\s+at\s+[^\n]+?)?\s+not loadable:\s*Metric',text):
        names.add(name if name.endswith('.tfm') else name+'.tfm')
    for name in re.findall(r'\[([A-Za-z0-9_.-]+)\]:[^\n]*not loadable',text):
        names.add(name if name.endswith(('.otf','.ttf')) else name+'.otf')
    return sorted(name for name in names if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,179}',name) and name.endswith(EXTENSIONS))
