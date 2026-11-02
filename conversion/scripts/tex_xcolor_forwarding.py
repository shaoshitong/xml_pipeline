"""Forward literal source-requested xcolor options before class/package loading."""
import hashlib,re

class Unsupported(ValueError):pass
ALLOWED={'dvipsnames','svgnames','x11names','table','usenames','xcdraw','rgb','prologue','hyperref'}

def without_comments(text):
    out=[]
    for line in text.splitlines(keepends=True):
        for i,ch in enumerate(line):
            if ch!='%':continue
            n=0;j=i-1
            while j>=0 and line[j]=='\\':n+=1;j-=1
            if n%2==0:
                line=line[:i]+ ('\n' if line.endswith('\n') else '');break
        out.append(line)
    return ''.join(out)

def plan(data):
    text=data.decode('utf-8');clean=without_comments(text)
    if clean.count('\\begin{document}')!=1:raise Unsupported('requires one literal document boundary')
    pre=clean.split('\\begin{document}')[0]
    if len(re.findall(r'\\documentclass\b',pre))!=1:raise Unsupported('requires one document class')
    if re.search(r'\\(?:input|include|catcode|csname|PassOptionsToPackage|if\w*)\b',pre):raise Unsupported('conditional or indirect preamble requires TeX-aware inspection')
    options=[];declarations=[]
    pat=re.compile(r'\\(?:usepackage|RequirePackage)\s*(?:\[([^\[\]]*)\])?\s*\{([^{}]*)\}')
    for match in pat.finditer(pre):
        packages=[v.strip() for v in match[2].split(',')]
        if 'xcolor' not in packages:continue
        prefix=pre[:match.start()];depth=len(re.findall(r'(?<!\\)\{',prefix))-len(re.findall(r'(?<!\\)\}',prefix))
        if depth:raise Unsupported('package declaration inside macro/group')
        values=[v.strip() for v in (match[1] or '').split(',') if v.strip()]
        if not set(values)<=ALLOWED:raise Unsupported('unsupported xcolor option or explicit engine driver: '+repr(values))
        for value in values:
            if value not in options:options.append(value)
        declarations.append(match[0])
    if not options:raise Unsupported('no literal source-requested xcolor options')
    wrapper='\\PassOptionsToPackage{'+','.join(options)+'}{xcolor}\n\\input{original_source.tex}\n'
    return {'version':'literal_xcolor_option_forwarding_v1','options':options,'source_declarations':declarations,'wrapper':wrapper,'original_code_sha256':hashlib.sha256(data).hexdigest(),'wrapper_sha256':hashlib.sha256(wrapper.encode()).hexdigest(),'source_content_changed':False,'jobname_preserved':'source'}
