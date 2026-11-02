import json
from tex_xcolor_forwarding import plan,Unsupported
base='\\documentclass[tikz]{standalone}\n%s\n\\begin{document}X\\end{document}'
cases=[('\\usepackage[dvipsnames]{xcolor}',['dvipsnames']),('\\usepackage[table, dvipsnames]{xcolor}\n\\usepackage[dvipsnames]{xcolor}',['table','dvipsnames']),('%%\\usepackage[pdftex]{xcolor}\n\\usepackage[table]{xcolor,colortbl}',['table'])]
for pre,options in cases:
    data=(base%pre).encode();p=plan(data);assert p['options']==options and p['source_content_changed'] is False
negative=['\\usepackage[pdftex,dvipsnames]{xcolor}','\\usepackage[\\variable]{xcolor}','\\newcommand{\\foo}{\\usepackage[table]{xcolor}}','\\iftrue\\usepackage[table]{xcolor}\\fi','\\input{config}\n\\usepackage[table]{xcolor}','%\\usepackage[table]{xcolor}','\\usepackage{xcolor}','\\PassOptionsToPackage{table}{xcolor}\\usepackage[table]{xcolor}']
for pre in negative:
    try:plan((base%pre).encode())
    except Unsupported:continue
    raise AssertionError(pre)
print(json.dumps({'ok':True,'positive':len(cases),'negative':len(negative)}))
