"""Conservative source-only declaration domain; no HTML or CSS is executed.

This is an admission subset, not a success/quality predictor. Runtime computed
source geometry, fonts, paint, asset completeness and all eight QA remain final.
"""
import hashlib,json,re
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')
POLICY='static_original_HTML_block_flex_uniform_opaque_CSS_paint_no_external_rounded_clip_v2'
BLOCK=set('html body div p h1 h2 h3 h4 h5 h6 ul ol li section header footer main article aside nav figure figcaption pre blockquote'.split())
SEMANTIC=set('div p h1 h2 h3 h4 h5 h6 li span b strong i em u s sub sup br a'.split())
INLINE=set('span b strong i em u s sub sup br a'.split())
def sha(b):return hashlib.sha256(b).hexdigest()
def inspect(code):
 from lxml import html
 from lxml.cssselect import CSSSelector
 import cssselect,tinycss2
 from compiler_types_source_ir_v1 import html_ir
 html_ir(code)
 if len(code.encode())>2_000_000:raise ValueError('source_size_outside_frozen_domain')
 for reason,pattern in [('source_background_paint_pending',r'(?:linear|radial|conic)-gradient\s*\('),('source_font_face_pending',r'@font-face')]:
  if re.search(pattern,code,re.I):raise ValueError(reason)
 for prop in (r'background-image',r'transform|filter|clip-path|mask(?:-image)?|text-shadow'):
  if any(v.strip().lower()!='none'for v in re.findall(r'(?:'+prop+r')\s*:([^;}]+)',code,re.I)):raise ValueError('source_css_effect_or_background_image_pending')
 doc=html.document_fromstring(code);elements=list(doc.iter());styles={e:{}for e in elements};priorities={e:{}for e in elements};order=0
 def expand_border(key,value):
  # Expand declarative shorthand before cascade, preserving specificity/order.
  from tinycss2.color3 import parse_color
  sides=('top','right','bottom','left');stylenames={'none','hidden','dotted','dashed','solid','double','groove','ridge','inset','outset'}
  def color(v):return v.lower()=='currentcolor'or parse_color(v)is not None
  def four(v):
   tokens=[tinycss2.serialize([t]).strip()for t in tinycss2.parse_component_value_list(v)if t.type!='whitespace']
   if not 1<=len(tokens)<=4:raise ValueError('source_CSS_border_shorthand_pending')
   return(tokens*4 if len(tokens)==1 else[tokens[0],tokens[1],tokens[0],tokens[1]]if len(tokens)==2 else[tokens[0],tokens[1],tokens[2],tokens[1]]if len(tokens)==3 else tokens)
  if key in('border-width','border-style','border-color'):return[('border-'+side+'-'+key.split('-')[-1],v)for side,v in zip(sides,four(value))]
  if key=='border'or key in('border-top','border-right','border-bottom','border-left'):
   vals=[tinycss2.serialize([t]).strip()for t in tinycss2.parse_component_value_list(value)if t.type!='whitespace'];out={'width':'medium','style':'none','color':'currentColor'};seen=set()
   for v in vals:
    kind='style'if v in stylenames else'width'if re.fullmatch(r'(?:0|[0-9.]+px|thin|medium|thick)',v)else'color'if color(v)else None
    if kind is None or kind in seen:raise ValueError('source_CSS_border_shorthand_pending')
    out[kind]=v;seen.add(kind)
   return[('border-'+side+'-'+kind,v)for side in(sides if key=='border'else[key[7:]])for kind,v in out.items()]
  if key=='border-radius':
   if '/'in value:raise ValueError('source_elliptical_CSS_radius_pending')
   return[('border-'+corner+'-radius',v)for corner,v in zip(('top-left','top-right','bottom-right','bottom-left'),four(value))]
  return[(key,value)]
 def declarations(tokens):
  out=[]
  for d in tinycss2.parse_declaration_list(tokens,skip_whitespace=True,skip_comments=True):
   if d.type!='declaration':raise ValueError('source_CSS_declaration_unknown')
   value=tinycss2.serialize(d.value).strip()
   if 'var('in value or 'calc('in value:raise ValueError('source_dynamic_numeric_CSS_pending')
   out.extend((k,v,d.important)for k,v in expand_border(d.lower_name,value))
  return out
 def apply(e,decls,specificity,ordinal):
  for key,value,important in decls:
   priority=(important,*specificity,ordinal)
   if priority>=priorities[e].get(key,(-1,)):
    styles[e][key]=value;priorities[e][key]=priority
 for e in elements:
  if not isinstance(e.tag,str):continue
  if e.tag=='link'and e.get('rel','').lower()=='stylesheet':raise ValueError('source_external_stylesheet_pending')
  if e.tag!='style':continue
  for rule in tinycss2.parse_stylesheet(e.text or'',skip_comments=True,skip_whitespace=True):
   if rule.type!='qualified-rule':raise ValueError('source_CSS_at_rule_or_error_pending')
   selector=tinycss2.serialize(rule.prelude).strip();decls=declarations(rule.content);order+=1
   for part in selector.split(','):
    # A universal box-sizing reset does not instantiate pseudo-element paint.
    # Any declaration that could create/style a pseudo paint remains pending.
    if '::'in part:
     if re.fullmatch(r'\s*\*::(?:before|after)\s*',part)and all(k=='box-sizing'and v in('border-box','content-box')for k,v,_ in decls):continue
     raise ValueError('source_CSS_pseudo_paint_pending')
    if re.search(r':(?:hover|active|focus|visited|link|checked|target|enabled|disabled)\b',part):raise ValueError('source_CSS_dynamic_state_pending')
    parsed=cssselect.parse(part);assert len(parsed)==1
    for target in CSSSelector(part)(doc):apply(target,decls,parsed[0].specificity(),order)
 for e in elements:
  if isinstance(e.tag,str)and e.get('style'):order+=1;apply(e,declarations(e.get('style')),(1000000,0,0),order)
 def display(e):return styles[e].get('display','block'if e.tag in BLOCK else'inline')
 def clipped(e):return any(styles[e].get(k,styles[e].get('overflow','visible')).lower()in('hidden','clip','scroll','auto')for k in('overflow-x','overflow-y'))
 def nonzero(value):return value.lower()not in('0','0px','0%','0 0','0px 0px','0px 0px 0px 0px','none','normal','')
 def rounded(e):return any(nonzero(styles[e].get(k,'0'))for k in('border-radius','border-top-left-radius','border-top-right-radius','border-bottom-left-radius','border-bottom-right-radius'))
 def bordered(e):
  d=styles[e]
  for k,v in d.items():
   if k.startswith('border')and k.endswith('width')and nonzero(v):return True
   if k in('border','border-left','border-right','border-top','border-bottom')and re.search(r'(?:^|\s)(?!0(?:px)?(?:\s|$))\d+(?:\.\d+)?px(?:\s|$)',v):return True
  return False
 # Original renderer supports only uniform solid opaque CSS rectangles.
 # This admission is source declarations only; full runtime observations still
 # independently bind geometry, physical fonts, image paint and every QA guard.
 from tinycss2.color3 import parse_color
 for e in elements:
  if not isinstance(e.tag,str):continue
  d=styles[e]
  if any(d.get(k,'none').lower()not in('none','0s','0','normal')for k in('animation','animation-name','transition','transition-property')):raise ValueError('source_time_dependent_CSS_pending')
  if d.get('box-shadow','none')!='none':raise ValueError('source_CSS_box_shadow_pending')
  if d.get('background-clip','border-box')!='border-box':raise ValueError('source_nondefault_CSS_background_clip_pending')
  widths=[];colors=[];kinds=[]
  for side in('top','right','bottom','left'):
   kind=d.get('border-'+side+'-style','none');literal=d.get('border-'+side+'-width','medium')
   if kind in('none','hidden'):width=0.
   else:
    if not re.fullmatch(r'(?:0|[0-9.]+px)',literal):raise ValueError('source_relative_or_keyword_CSS_border_pending')
    width=float(literal.removesuffix('px'))
   widths.append(width);kinds.append(kind)
   raw=d.get('border-'+side+'-color','currentColor')
   if raw.lower()=='currentcolor':
    raw=next((styles[a]['color']for a in[e,*e.iterancestors()]if styles[a].get('color','').lower()not in('','inherit','initial','unset','currentcolor')),'black')
   c=parse_color(raw)
   if c is None:raise ValueError('source_CSS_border_color_unresolved_pending')
   colors.append(c)
  if len(set(widths))!=1 or max(widths)>0 and(len(set(kinds))!=1 or kinds[0]!='solid'or len(set(colors))!=1 or colors[0].alpha!=1):raise ValueError('source_nonuniform_or_translucent_CSS_border_pending')
  radii=[d.get('border-'+corner+'-radius','0')for corner in('top-left','top-right','bottom-right','bottom-left')]
  if any(not re.fullmatch(r'(?:0|[0-9.]+px)',v)for v in radii)or len({float(v.removesuffix('px'))for v in radii})!=1:raise ValueError('source_nonuniform_or_relative_CSS_radius_pending')
 roots=set()
 for e in elements:
  if not isinstance(e.tag,str)or e.tag in('style','script','title','head'):continue
  owners=[]
  if(e.text or'').strip():owners.append(e)
  if(e.tail or'').strip()and e.getparent()is not None:owners.append(e.getparent())
  for owner in owners:
   if any(display(a)=='none'for a in [owner,*owner.iterancestors()]):continue
   host=owner
   while host is not None and display(host)in('inline','contents'):host=host.getparent()
   if host is None or host.tag in('html','body')or display(host)not in('block','inline-block','list-item','flex','inline-flex'):raise ValueError('source_paragraph_original_host_outside_domain')
   roots.add(host)
 for host in roots:
  for e in host.iter():
   if not isinstance(e.tag,str)or e.tag not in SEMANTIC:raise ValueError('source_paragraph_nonsemantic_descendant_pending')
   d=styles[e]
   if e is not host:
    if display(e)not in('inline','contents','none')and not(display(e.getparent())in('flex','inline-flex')and e.tag in INLINE):raise ValueError('source_paragraph_nested_block_pending')
    if d.get('position','static')!='static':raise ValueError('source_paragraph_positioned_descendant_pending')
    if bordered(e):raise ValueError('source_paragraph_nested_border_pending')
    if d.get('background-color','transparent')not in('transparent','rgba(0, 0, 0, 0)')or d.get('background','transparent')not in('transparent','none'):raise ValueError('source_paragraph_nested_background_pending')
  for a in host.iterancestors():
   if clipped(a)and rounded(a):raise ValueError('source_paragraph_external_rounded_clip_pending')
   if clipped(a)and bordered(a):raise ValueError('source_paragraph_external_bordered_clip_pending')
  for a in [host,*host.iterancestors()]:
   if styles[a].get('opacity','1')not in('1','1.0')or styles[a].get('mix-blend-mode','normal')!='normal':raise ValueError('source_paragraph_group_compositing_pending')
 if not roots:raise ValueError('source_no_visible_paragraph_hosts')
 images=[e for e in elements if isinstance(e.tag,str)and e.tag=='img'];urls=[e.get('src','')for e in images]
 if any(not u or re.match(r'(?:https?:|//|javascript:)',u,re.I)for u in urls):raise ValueError('source_external_or_missing_image_pending')
 return {'supported':True,'policy':POLICY,'source_only':True,'HTML_executed':False,'paragraph_host_count_not_complexity':len(roots),'image_objects':len(images),'source_image_URIs':urls,'formatting_hosts':dict(__import__('collections').Counter(display(e)for e in roots))}
def support(row,manifest):
 try:
  path=(R/manifest['source_code']).resolve(strict=True);assert path.is_relative_to((R/'clean').resolve()),'source_not_clean';body=path.read_bytes();assert sha(body)==row['code_sha256'],'source_code_hash_changed'
  out=inspect(body.decode('utf-8'));info=row['image_info'];assert 0<info['width']<=8128 and 0<info['height']<=8128,'source_canvas_pending';assets=(R/manifest['asset_root']).resolve(strict=True);assert assets.is_relative_to((R/'clean').resolve())and assets.is_dir(),'source_asset_root_pending'
  import urllib.parse
  for uri in out.pop('source_image_URIs'):
   if uri.startswith('data:'):continue
   u=urllib.parse.urlparse(uri);assert not u.scheme and not u.netloc,'source_external_asset_pending';p=(assets/urllib.parse.unquote(u.path)).resolve();assert p.is_relative_to(assets)and p.is_file(),'source_local_asset_missing'
  return out
 except Exception as error:return {'supported':False,'policy':POLICY,'source_only':True,'HTML_executed':False,'reason':str(error)[:1200],'error_type':type(error).__name__}
