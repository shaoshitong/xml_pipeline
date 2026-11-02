"""Portable Unicode fonts from actual embedded pdfTeX Type1/CFF glyphs.

For Type1, the actual FreeType glyph-index/name table independently resolves
every PDF text-trace GID before copying its original CharString outline. Font
metrics and per-glyph source identity are retained; no system font substitute.
"""
import base64,collections,hashlib,io,re
from pathlib import Path
from fontTools.cffLib import CFFFontSet
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from pdf_fonts import clusters
TX_ROOT=Path('/backup/shaoshitong/img2code_20261029/conversion/runtime/afdko_tx_v1')

def type1_transport(data):
 """PFB framing only; preserve both original Type1 program segments exactly."""
 if not data.startswith(b'%!'):return data
 boundary=re.search(rb'currentfile\s+eexec[ \t]*\r?\n',data)
 if boundary is None:raise ValueError('actual_PDF_Type1_eexec_boundary_missing')
 clear,encrypted=data[:boundary.end()],data[boundary.end():]
 trailer=b'\n'+b'0'*512+b'\ncleartomark\n'
 def segment(kind,body):return bytes([128,kind])+len(body).to_bytes(4,'little')+body
 return segment(1,clear)+segment(2,encrypted)+segment(1,trailer)+bytes([128,3])

def source_glyphs(info,directory):
 ext=info['ext'];data=info['data']
 if ext in ('cff','cid'):
  c=CFFFontSet();c.decompile(io.BytesIO(data),None);top=c.topDictIndex[0];matrix=top.FontMatrix
  order=list(top.charset);glyphs=top.CharStrings;cid=hasattr(top,'ROS');preserved_cff=c
  def name(gid):return ('cid'+str(gid).zfill(5)) if cid and gid else order[gid] if not cid else '.notdef'
 elif ext in ('pfb','pfa'):
  from fontTools.t1Lib import T1Font
  from matplotlib.ft2font import FT2Font
  p=directory/('original_'+hashlib.sha256(data).hexdigest()+'.'+ext);p.write_bytes(data)
  # PDF FontFile streams may legally omit the 512-zero PFA transport trailer
  # (Length3=0). Feed the unchanged raw Type1 program to the PostScript parser;
  # the public file reader's trailer scan is not a requirement on PDF fonts.
  if data.startswith(b'%!'):
   font=T1Font.__new__(T1Font);font.data=data;font.encoding='ascii'
  else:font=T1Font(str(p))
  glyphs=font.getGlyphSet();matrix=font['FontMatrix'];order=list(glyphs)
  face=FT2Font(io.BytesIO(type1_transport(data)))
  def name(gid):
   if not 0<=gid<face.num_glyphs:raise ValueError('PDF_glyph_id_outside_actual_Type1_font')
   value=face.get_glyph_name(gid)
   if isinstance(value,bytes):value=value.decode('ascii')
   if value not in glyphs:raise ValueError('actual_FreeType_Type1_glyph_name_missing_from_original_CharStrings')
   return value
  # Preserve original Type1 stem/zone hints through Adobe's mature converter.
  # -T disables bitmap-affecting charstring optimizations; no autohinting or
  # glyph-overlap removal is performed. Original source outlines are checked.
  from sandbox_runner import run
  txwork=directory/('tx_'+hashlib.sha256(data).hexdigest());txwork.mkdir(exist_ok=False)
  (txwork/'source.pfb').write_bytes(type1_transport(data))
  proc=run(txwork,[str(TX_ROOT/'tx'),'-cff','-T','+b','/work/source.pfb','/work/source.cff'],timeout=60,extra_ro=[(TX_ROOT,TX_ROOT)])
  (txwork/'stdout.log').write_text(proc.stdout);(txwork/'stderr.log').write_text(proc.stderr)
  if proc.returncode:raise ValueError('actual_Type1_hint_preserving_CFF_conversion_failed:'+proc.stderr[-1500:])
  preserved_cff=CFFFontSet();preserved_cff.decompile(io.BytesIO((txwork/'source.cff').read_bytes()),None)
  if set(preserved_cff.topDictIndex[0].charset)!=set(order):raise ValueError('hint_preserving_converter_changed_source_glyph_inventory')
 else:raise ValueError('unsupported_embedded_pdf_font:'+str(ext))
 if list(matrix[1:4])!=[0,0,matrix[0]] or list(matrix[4:])!=[0,0]:raise ValueError('nonstandard_source_font_matrix')
 upem=round(1/matrix[0])
 if not 16<=upem<=16384 or '.notdef' not in order:raise ValueError('invalid_source_font_units_or_notdef')
 order=['.notdef']+[n for n in order if n!='.notdef']
 charstrings={};metrics={};outlines={};boundsall=[]
 for n in order:
  glyph=glyphs[n];recording=DecomposingRecordingPen(glyphs);glyph.draw(recording);width=glyph.width
  pen=T2CharStringPen(width,None);recording.replay(pen);charstrings[n]=pen.getCharString()
  bounds=BoundsPen(None);recording.replay(bounds)
  metrics[n]=(round(width),round(bounds.bounds[0]) if bounds.bounds else 0)
  outlines[n]=hashlib.sha256(repr(recording.value).encode()).hexdigest()
  if bounds.bounds:boundsall.append(bounds.bounds)
 hinted=preserved_cff.topDictIndex[0];hint_counts=collections.Counter()
 for n in order:
  pen=DecomposingRecordingPen(hinted.CharStrings);hinted.CharStrings[n].draw(pen)
  # Equivalent closing operators may be encoded differently; the source and
  # converted contour records must nevertheless preserve all path coordinates.
  sourcepen=DecomposingRecordingPen(glyphs);glyphs[n].draw(sourcepen)
  if pen.value!=sourcepen.value:raise ValueError('hint_preserving_converter_changed_original_glyph_contours:'+n)
  hinted.CharStrings[n].decompile()
  hint_counts.update(x for x in hinted.CharStrings[n].program if isinstance(x,str) and x in ('hstem','vstem','hstemhm','vstemhm','hintmask','cntrmask'))
 order=list(hinted.charset)
 return order,name,upem,charstrings,metrics,outlines,boundsall,preserved_cff,dict(hint_counts)

def build_fonts(doc,page,directory):
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);traces=page.get_texttrace();by=collections.defaultdict(list)
 for trace in traces:
  trace['clusters']=clusters(trace)
  if trace['type']!=3:by[trace['font']].append(trace)
 infos={}
 for f in page.get_fonts(full=True):
  name,ext,typ,data=doc.extract_font(f[0]);base=re.sub(r'^[A-Z]{6}\+','',name).removesuffix('-Identity-H')
  if base in infos and infos[base]['data']!=data:raise ValueError('ambiguous_actual_embedded_pdf_font:'+base)
  infos[base]={'xref':f[0],'data':data,'ext':ext,'pdf_name':name,'type':typ}
 result={}
 for fontname,rows in by.items():
  info=infos[fontname];order,lookup,upem,charstrings,metrics,outlines,bounds,preserved_cff,hint_counts=source_glyphs(info,directory)
  cmap={};advances={};source_ids={};used=[]
  for trace in rows:
   for cluster in trace['clusters']:
    gid=cluster['gid'];name=lookup(gid);u=ord(cluster['text'])
    if name not in charstrings:raise ValueError('actual_embedded_PDF_glyph_outline_missing')
    if u in cmap and cmap[u]!=name:raise ValueError('Unicode_maps_to_different_source_glyphs')
    cmap[u]=name;advances[gid]=metrics[name][0]/upem;source_ids[gid]={'glyph_name':name,'outline_sha256':outlines[name]};used.append(gid)
  family='PDF_'+hashlib.sha256(info['data']+str(sorted(cmap.items())).encode()).hexdigest()[:16]
  fb=FontBuilder(upem,isTTF=False);fb.setupGlyphOrder(order);fb.setupCharacterMap(cmap)
  fb.setupCFF(family,{'FullName':family,'FamilyName':family,'Weight':'Regular'},charstrings,{})
  preserved_cff.fontNames=[family];preserved_cff.topDictIndex[0].FullName=family;preserved_cff.topDictIndex[0].FamilyName=family
  fb.font['CFF '].cff=preserved_cff
  fb.setupHorizontalMetrics(metrics);fb.setupHorizontalHeader(ascent=round(upem*.8),descent=-round(upem*.2))
  fb.setupNameTable({'familyName':family,'styleName':'Regular','uniqueFontIdentifier':family,'fullName':family,'psName':family})
  fb.setupOS2(sTypoAscender=round(upem*.8),sTypoDescender=-round(upem*.2),usWinAscent=max([round(upem*.8)]+[round(b[3]) for b in bounds]),usWinDescent=max([round(upem*.2)]+[round(-b[1]) for b in bounds]))
  fb.setupPost();fb.font['head'].created=2082844800;fb.font['head'].modified=2082844800;fb.font.recalcTimestamp=False
  path=directory/(family+'.otf');fb.save(path);data=path.read_bytes()
  result[fontname]={'mapping_version':'actual_Type1_FreeType_GID_or_CFF_to_original_outline_Unicode_v1','family':family,'file':str(path),'sha256':hashlib.sha256(data).hexdigest(),'uri':'data:font/otf;base64,'+base64.b64encode(data).decode(),'glyph_advances':advances,'glyphs':len(cmap),'pdf_font':info['pdf_name'],'source_font_sha256':hashlib.sha256(info['data']).hexdigest(),'source_type':info['type'],'source_glyph_identities':source_ids,'source_glyph_uses':dict(collections.Counter(used)),'original_hints_preserved':True,'native_hint_operators':hint_counts,'original_contours_preserved':True}
 return result,traces
