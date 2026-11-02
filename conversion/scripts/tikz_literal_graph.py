"""Parse complete, explicit named-node TikZ graphs; unsupported statements are never skipped."""
import re
from tikz_connectivity import Unsupported,balanced,norm

def split_options(s):
 out=[];start=0;stack=[]
 for i,c in enumerate(s):
  if i and s[i-1]=='\\':continue
  if c in '{[':stack.append(c)
  elif c in '}]':
   if not stack or stack.pop()!=('{' if c=='}' else '['):raise Unsupported('unbalanced options')
  elif c==',' and not stack:out.append(s[start:i].strip());start=i+1
 if stack:raise Unsupported('unclosed option group')
 return [x for x in out+[s[start:].strip()] if x]

def literal(s):
 s=s.replace(r'\%', '%').replace(r'\&','&').replace(r'\_','_')
 if any(c in s for c in '\\{}$#'):raise Unsupported('nonliteral node or edge text requires TeX-aware matching')
 return s.strip()

def options_at(s,pos):
 while pos<len(s) and s[pos].isspace():pos+=1
 if pos<len(s) and s[pos]=='[':
  opts,end=balanced(s,pos,'[',']');return opts,end
 return '',pos

def parse_literal(code):
 code=re.sub(r'(?<!\\)%[^\n]*','',code)
 if re.search(r'\\(?:foreach|def|newcommand|renewcommand|input|include|tikzset|tikzstyle)\b',code):raise Unsupported('macros or external style definitions require TeX-aware extraction')
 starts=list(re.finditer(r'\\begin\{tikzpicture\}',code));ends=list(re.finditer(r'\\end\{tikzpicture\}',code))
 if len(starts)!=1 or len(ends)!=1:raise Unsupported('requires one complete TikZ picture')
 opts,pos=options_at(code,starts[0].end());body=code[pos:ends[0].start()].strip();styles={};globalopts=[]
 for token in split_options(opts):
  m=re.fullmatch(r'([\w /-]+)\s*/\.style\s*=\s*\{(.*)\}',token,re.S)
  if m:
   name=m[1].strip()
   if name in styles:raise Unsupported('duplicate style definition')
   styles[name]=split_options(m[2])
  else:globalopts.append(token)
 def expand(tokens,seen=()):
  result=[]
  for token in tokens:
   if token in styles:
    if token in seen:raise Unsupported('style cycle')
    result+=expand(styles[token],seen+(token,))
   else:result.append(token)
  return result
 def arrows(edgeopts):
  start=end=False
  for token in expand(globalopts+styles.get('every path',[])+split_options(edgeopts)):
   if token in ('->','<-','<->','-'):
    start='<' in token;end='>' in token;continue
   m=re.fullmatch(r'(?:\{)?(Stealth|Latex|Triangle)?(?:\})?-(?:\{)?(Stealth|Latex|Triangle)?(?:\})?',token)
   if m:start=bool(m[1]);end=bool(m[2]);continue
   if token.split('=',1)[0].strip() in ('node distance','>','<','shorten >','shorten <','line width','draw','color','opacity','rounded corners','minimum width','minimum height','minimum size','font','align','inner sep','outer sep','text width'):continue
   if token in ('thick','very thick','ultra thick','thin','very thin','ultra thin','semithick','densely dashed','dashed','dotted','solid'):continue
   if re.fullmatch(r'(?:black|white|red|green|blue|yellow|orange|gray|grey|purple|cyan|magenta|brown|teal)(?:!\d+(?:![a-z]+)?)*',token):continue
   raise Unsupported('unresolved edge/global style: '+token)
  return start,end
 # Require full top-level statement consumption, so loops/path commands cannot disappear.
 statements=[];i=0
 while i<len(body):
  while i<len(body) and body[i].isspace():i+=1
  if i==len(body):break
  m=re.match(r'\\(node|draw)\b',body[i:])
  if not m:raise Unsupported('unsupported picture statement: '+body[i:i+50])
  kind=m[1];begin=i+m.end();j=begin
  while j<len(body):
   if body[j] in '{[':
    _,j=balanced(body,j,body[j],'}' if body[j]=='{' else ']');continue
   if body[j]==';':break
   j+=1
  if j==len(body):raise Unsupported('missing statement semicolon')
  statements.append((kind,body[begin:j].strip()));i=j+1
 nodes={};decorative=[];rawedges=[]
 for kind,s in statements:
  if kind=='draw':rawedges.append(s);continue
  pos=0;name=None
  while pos<len(s):
   while pos<len(s) and s[pos].isspace():pos+=1
   if pos==len(s):raise Unsupported('missing node text')
   if s[pos]=='[':_,pos=balanced(s,pos,'[',']');continue
   if s[pos]=='(':
    value,pos=balanced(s,pos,'(',')')
    if name is not None or not re.fullmatch(r'[-\w]+',value):raise Unsupported('invalid node name')
    name=value;continue
   if s.startswith('at',pos) and (pos+2==len(s) or s[pos+2].isspace()):
    pos+=2
    while pos<len(s) and s[pos].isspace():pos+=1
    _,pos=balanced(s,pos,'(',')');continue
   if s[pos]=='{':
    value,end=balanced(s,pos);assert end<=len(s)
    if s[end:].strip():raise Unsupported('trailing node constructs')
    label=literal(value)
    if name:
     if name in nodes:raise Unsupported('duplicate node name')
     nodes[name]=label
    else:decorative.append(label)
    break
   raise Unsupported('unsupported node header')
 if not nodes or len(set(map(norm,nodes.values())))!=len(nodes):raise Unsupported('ambiguous or empty node labels')
 edges=[]
 terminal=r'\(([-\w]+)(?:\.([\w ]+))?\)'
 for s in rawedges:
  options,pos=options_at(s,0);s=s[pos:].strip();a=re.match(terminal,s)
  if not a:raise Unsupported('connection must start at a named node')
  left,anchor1=a.groups();s=s[a.end():].lstrip()
  route=next((t for t in ('--','|-','-|') if s.startswith(t)),None)
  if not route:raise Unsupported('requires explicit straight/orthogonal connection')
  s=s[len(route):].lstrip();label=''
  def label_at(text):
   opts,pos=options_at(text,4)
   while pos<len(text) and text[pos].isspace():pos+=1
   value,end=balanced(text,pos);return literal(value),text[end:].lstrip(),opts
  if s.startswith('node'):
   label,s,labelopts=label_at(s)
  b=re.match(terminal,s)
  if not b:raise Unsupported('connection must end at a named node')
  right,anchor2=b.groups();s=s[b.end():].lstrip()
  if s.startswith('node') and not label:label,s,labelopts=label_at(s)
  if s:raise Unsupported('additional path segments or constructs')
  if left not in nodes or right not in nodes or left==right:raise Unsupported('unknown/self terminal')
  start,end=arrows(options)
  edges.append({'source':left,'target':right,'source_anchor':anchor1,'target_anchor':anchor2,'label':label,'route':route,'start_arrow':start,'end_arrow':end})
 if not edges:raise Unsupported('no explicit connections')
 return {'nodes':nodes,'edges':edges,'decorative_labels':decorative,'parser':'literal_named_nodes_explicit_paths_v1','complete_statement_coverage':len(statements)}
