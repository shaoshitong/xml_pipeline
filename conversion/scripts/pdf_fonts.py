"""Rebuild PDF-embedded CFF subsets as portable OpenType with Unicode mappings."""
import base64,collections,hashlib,io,re,unicodedata
from fontTools.cffLib import CFFFontSet
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
LIGATURES={'ff':'\ufb00','fi':'\ufb01','fl':'\ufb02','ffi':'\ufb03','ffl':'\ufb04','st':'\ufb06'}
def clusters(trace):
 out=[]
 for uni,gid,origin,bbox in trace['chars']:
  if gid<0:
   if not out:raise ValueError('orphan continuation glyph')
   out[-1]['source_text']+=chr(uni);continue
  out.append({'source_text':chr(uni),'gid':gid,'origin':origin,'bbox':bbox})
 for c in out:
  text=c['source_text'];plain=unicodedata.normalize('NFKC',text);c['text']=LIGATURES.get(plain,text)
  if len(c['text'])!=1 or ord(c['text'])==0xfffd:raise ValueError('unresolved multi-Unicode glyph mapping '+repr(text))
 return out

def build_fonts(doc,page,directory):
 directory.mkdir(parents=True,exist_ok=True);traces=page.get_texttrace();by=collections.defaultdict(list)
 for t in traces:
  t['clusters']=clusters(t);by[t['font']].append(t)
 infos={}
 for f in page.get_fonts(full=True):
  name,ext,typ,data=doc.extract_font(f[0]);base=re.sub(r'^[A-Z]{6}\+','',name).removesuffix('-Identity-H')
  if base in infos and infos[base]['data']!=data:raise ValueError('ambiguous embedded font '+base)
  infos[base]={'xref':f[0],'data':data,'ext':ext,'pdf_name':name}
 result={}
 for name,ts in by.items():
  info=infos[name];c=CFFFontSet();c.decompile(io.BytesIO(info['data']),None);top=c.topDictIndex[0];matrix=top.FontMatrix;assert matrix[1:4]==[0,0,matrix[0]] and matrix[4:]==[0,0],'nonstandard CFF font matrix';upem=round(1/matrix[0]);assert 16<=upem<=16384
  cid=hasattr(top,'ROS');cmap={};gidnames={};advances={};charstrings={};metrics={};boundsall=[]
  for glyph in top.charset:
   old=top.CharStrings[glyph];recording=RecordingPen();old.draw(recording);width=old.width;pen=T2CharStringPen(width,None);recording.replay(pen);charstrings[glyph]=pen.getCharString();bounds=BoundsPen(None);recording.replay(bounds);metrics[glyph]=(round(width),round(bounds.bounds[0]) if bounds.bounds else 0)
   if bounds.bounds:boundsall.append(bounds.bounds)
  for t in ts:
   for cluster in t['clusters']:
    gid=cluster['gid'];glyph=('cid'+str(gid).zfill(5)) if cid and gid else top.charset[gid] if not cid else '.notdef';assert glyph in charstrings,(name,gid,glyph);u=ord(cluster['text'])
    if u in cmap and cmap[u]!=glyph:raise ValueError('Unicode maps to different source glyphs '+name+' '+str(u))
    cmap[u]=glyph;gidnames[gid]=glyph;advances[gid]=metrics[glyph][0]/upem
  family='PDF_'+hashlib.sha256(info['data']+str(sorted(cmap.items())).encode()).hexdigest()[:16];fb=FontBuilder(upem,isTTF=False);fb.setupGlyphOrder(top.charset);fb.setupCharacterMap(cmap);fb.setupCFF(family,{'FullName':family,'FamilyName':family,'Weight':'Regular'},charstrings,{});fb.setupHorizontalMetrics(metrics);fb.setupHorizontalHeader(ascent=round(upem*.8),descent=-round(upem*.2));fb.setupNameTable({'familyName':family,'styleName':'Regular','uniqueFontIdentifier':family,'fullName':family,'psName':family});fb.setupOS2(sTypoAscender=round(upem*.8),sTypoDescender=-round(upem*.2),usWinAscent=round(upem*.8),usWinDescent=round(upem*.2));fb.setupPost();fb.font['head'].created=2082844800;fb.font['head'].modified=2082844800;fb.font.recalcTimestamp=False;path=directory/(family+'.otf');fb.save(path);data=path.read_bytes();result[name]={'mapping_version':'cff_unicode_nfkc_ligatures_v2','family':family,'file':str(path),'sha256':hashlib.sha256(data).hexdigest(),'uri':'data:font/otf;base64,'+base64.b64encode(data).decode(),'glyph_advances':advances,'glyphs':len(cmap),'pdf_font':info['pdf_name'],'source_font_sha256':hashlib.sha256(info['data']).hexdigest()}
 return result,traces
