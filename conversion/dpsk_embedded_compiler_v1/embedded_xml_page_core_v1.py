"""Versioned decoder + complete native-page isolation for embedded draw.io XML.

This module is read-only with respect to sources and does not modify the
frozen v1 compiler core.  It adds:
  * bounded PNG zTXt zlib-then-raw-deflate fallback (official contract)
  * exact complete mxGraphModel page extraction for inline and compressed pages
  * official page-decoding comparison helpers
"""
from pathlib import Path
import base64, hashlib, json, re, struct, urllib.parse, zlib
import xml.etree.ElementTree as ET
import embedded_xml_compiler_v1 as C
import sys
if str(C.S) not in sys.path: sys.path.insert(0, str(C.S))

R=C.R
D=C.Path(__file__).resolve().parents[1] / 'results' / 'embedded_XML_page_compiler_v1'
LIMIT=C.LIMIT
SOURCE_LIMIT=C.SOURCE_LIMIT
TARGET_KEYS=('mxfile','mxGraphModel')
sha=C.sha
raw_json=C.raw
dumps=C.dumps
put_json=C.put_json
atomic_put=C.atomic_put

def local(e): return e.tag.rsplit('}',1)[-1]

def _inflate_text_bounded(data):
    """Official PNG zTXt contract: try zlib wrapper, then raw deflate."""
    attempts=[]
    for mode,name in ((zlib.MAX_WBITS,'zlib_wrapper'),(-15,'raw_deflate')):
        try:
            d=zlib.decompressobj(mode)
            out=d.decompress(data,LIMIT+1)
            if len(out)>LIMIT or d.unconsumed_tail: raise ValueError('compressed_text_above_bound')
            out+=d.flush()
            if len(out)>LIMIT or not d.eof or d.unused_data: raise ValueError('compressed_text_incomplete_or_trailing')
            attempts.append({'mode':name,'ok':True,'output_bytes':len(out),'output_sha256':sha(out)})
            return out,name,attempts
        except Exception as e:
            attempts.append({'mode':name,'ok':False,'error':type(e).__name__+':'+str(e)[:200]})
    raise ValueError('zTXt_inflate_failed_after_zlib_and_raw:'+json.dumps(attempts)[:600])

def _uri_decode_bytes(text, max_times=2):
    steps=[]
    b=text.encode('latin-1')
    for _ in range(max_times):
        if b[:1]!=b'%': break
        s=b.decode('latin-1')
        if re.search(r'%(?![0-9A-Fa-f]{2})',s): raise ValueError('malformed_URI_percent_escape')
        b=urllib.parse.unquote_to_bytes(s);steps.append('percent_URI_decode')
    return b,steps

def _png_chunk(blob,off):
    if off+12>len(blob): raise ValueError('truncated_PNG_chunk_header')
    n=struct.unpack('>I',blob[off:off+4])[0];end=off+12+n
    if n>SOURCE_LIMIT or end>len(blob): raise ValueError('truncated_or_oversized_PNG_chunk')
    kind=blob[off+4:off+8];data=blob[off+8:off+8+n]
    crc=struct.unpack('>I',blob[off+8+n:end])[0]
    if (zlib.crc32(kind+data)&0xffffffff)!=crc: raise ValueError('PNG_chunk_CRC_changed')
    return kind,data,end

def decode_png_metadata_v2(blob):
    """Bounded official-compatible PNG decoder with raw-deflate zTXt repair."""
    if len(blob)>SOURCE_LIMIT: raise ValueError('PNG_above_source_bound')
    if blob[:8]!=b'\x89PNG\r\n\x1a\n': raise ValueError('not_PNG')
    off=8;rows=[];before_idat=True;iend=False;header=None
    while off<len(blob):
        kind,data,end=_png_chunk(blob,off)
        if kind==b'IHDR':
            if header is not None: raise ValueError('duplicate_IHDR')
            header=dict(zip(('width','height','bit_depth','color_type','compression','filtering','interlace'),struct.unpack('>IIBBBBB',data)))
        if kind==b'IDAT': before_idat=False
        if kind in (b'tEXt',b'zTXt',b'iTXt'):
            key,rest=data.split(b'\x00',1);key=key.decode('latin-1')
            if key in TARGET_KEYS:
                chunk_type=kind.decode('ascii');steps=[]
                if kind==b'tEXt':
                    text=rest.decode('latin-1');charset='latin-1';mode=None;attempts=[]
                elif kind==b'zTXt':
                    if not rest or rest[0]!=0: raise ValueError('unsupported_zTXt_compression_method')
                    payload,mode,attempts=_inflate_text_bounded(rest[1:])
                    try: text=payload.decode('utf-8');charset='utf-8'
                    except UnicodeDecodeError: text=payload.decode('latin-1');charset='latin-1'
                    normalised=text.replace('+',' ')
                    steps.append('official_zTXt_plus_to_space')
                    if normalised!=text: steps.append('official_zTXt_plus_normalisation_changed_text')
                    text=normalised
                else:
                    raise ValueError('official_PNG_decoder_does_not_support_iTXt')
                b,uri_steps=_uri_decode_bytes(text,2);steps.extend(uri_steps)
                rows.append({'chunk_type':chunk_type,'key':key,'before_IDAT':before_idat,
                    'text_sha256':sha(text.encode('utf-8')),
                    'text_charset':charset,'compression_mode':mode,'inflate_attempts':attempts,
                    'steps':steps,'chunk_sha256':sha(blob[off:end]),'chunk_bytes':blob[off:end],
                    'raw':b,'raw_bytes':len(b),'raw_sha256':sha(b),
                    'source_container_sha256':sha(blob),'png_header':header,
                    'official_decoder':'Editor.extractGraphModelFromPng',
                    'decoder_adapter':'embedded_xml_page_decoder_v2_zlib_then_raw_fallback'})
        off=end
        if kind==b'IEND': iend=True;break
    if header is None or not iend or off!=len(blob): raise ValueError('PNG_structure_incomplete_or_trailing')
    target=[r for r in rows if r['before_IDAT']]
    if len(target)!=1:
        if rows and not target: raise ValueError('official_PNG_decoder_stops_at_IDAT')
        raise ValueError('target_PNG_text_chunk_count_%d'%len(target))
    return target[0]

def extract_full_v2(path,kind):
    path=Path(path)
    if path.stat().st_size>SOURCE_LIMIT: raise ValueError('source_file_above_bound')
    blob=path.read_bytes()
    if kind.startswith('PNG'):
        e=decode_png_metadata_v2(blob)
    else:
        e=C.decode_svg_metadata(blob)
    e['source_file']=str(path.relative_to(R));e['source_bytes']=len(blob);e['source_sha256']=sha(blob)
    return e

# ---------------------------------------------------------------------------
# Exact complete-page extraction
# ---------------------------------------------------------------------------
def safe_xml(rawb):
    if len(rawb)>LIMIT: raise ValueError('XML_above_bound')
    up=rawb.upper()
    if b'<!DOCTYPE' in up or b'<!ENTITY' in up: raise ValueError('native_XML_DTD_or_ENTITY_not_supported')
    try: text=rawb.decode('utf-8-sig')
    except UnicodeDecodeError: raise ValueError('native_XML_not_UTF8')
    return ET.fromstring(text)

def canonical_model(model):
    return ET.canonicalize(ET.tostring(model,encoding='unicode'),strip_text=True)

def _canon_equal(a,b):
    try: return canonical_model(a)==canonical_model(b)
    except Exception: return False

def _lexical_inline_models(rawb):
    starts=[m.start() for m in re.finditer(rb'<mxGraphModel(?=[\s/>])',rawb)]
    out=[]
    for start in starts:
        gt=rawb.find(b'>',start)
        if gt<0: return []
        if rawb[gt-1:gt]==b'/': end=gt+1
        else:
            close=re.search(rb'</mxGraphModel\s*>',rawb[gt:])
            if not close: return []
            end=gt+close.end()
        out.append((start,end,rawb[start:end]))
    return out

def _page_record(index,pid,name,model,sidecar,kind,rawb,details=None):
    try: parsed=safe_xml(sidecar)
    except Exception as e: raise ValueError('page_sidecar_parse_failed:'+str(e)[:200])
    if local(parsed)!='mxGraphModel': raise ValueError('page_sidecar_root_not_mxGraphModel')
    if not _canon_equal(parsed,model): raise ValueError('page_sidecar_canonical_model_changed')
    cells=[c for c in parsed.iter('mxCell')]
    rec={'page_index':index,'page_id':pid,'page_name':name,'page_sidecar_XML':sidecar,
         'page_sidecar_sha256':sha(sidecar),'page_sidecar_bytes':len(sidecar),
         'page_extraction_kind':kind,'full_embedded_XML_sha256':sha(rawb),
         'page_model_canonical_sha256':sha(canonical_model(parsed).encode()),
         'page_graph_sha256':C.page_graph_hash(parsed),
         'cell_count':len(cells),'vertex_count':sum(c.get('vertex')=='1' for c in cells),
         'edge_count':sum(c.get('edge')=='1' for c in cells),
         'diagram_attributes':{k:v for k,v in (details or {}).items() if k in ('id','name','pageWidth','pageHeight','background')},
         'model_attributes':dict(parsed.attrib),'sidecar_is_full_embedded_XML':sidecar==rawb,
         'fragment_crop_or_geometry_rewrite':False}
    rec.update({k:v for k,v in (details or {}).items() if k not in rec})
    return rec

def parse_full_pages(rawb):
    """Return the complete mxGraphModel sidecar for every page in document order."""
    root=safe_xml(rawb);t=local(root)
    if t=='mxGraphModel':
        page=_page_record(0,None,None,root,rawb,'native_root_mxGraphModel_exact',rawb)
        return {'root_kind':'mxGraphModel','pages':[page],'full_XML_sha256':sha(rawb)}
    if t!='mxfile': raise ValueError('native_root_not_mxfile_or_mxGraphModel')
    diagrams=[d for d in list(root) if local(d)=='diagram']
    if not diagrams: raise ValueError('mxfile_has_no_diagrams')
    inline=[]
    for d in diagrams:
        m=[e for e in list(d) if local(e)=='mxGraphModel']
        if len(m)>1: raise ValueError('multiple_inline_models_one_page')
        inline.append(m[0] if m else None)
    lexical=_lexical_inline_models(rawb) if any(m is not None for m in inline) else []
    lexical_ok=len(lexical)==sum(m is not None for m in inline)
    pages=[];inline_ordinal=0
    for i,(d,m) in enumerate(zip(diagrams,inline)):
        attrs={k:v for k,v in d.attrib.items()}
        if m is not None:
            if lexical_ok:
                sidecar=lexical[inline_ordinal][2];kind='inline_lexical_exact_mxGraphModel'
                # Re-validate that lexical candidate is the same inline model.
                if not _canon_equal(safe_xml(sidecar),m):
                    sidecar=ET.tostring(m,encoding='utf-8');kind='inline_canonical_reserialization'
                    attrs['lexical_fallback_reason']='lexical_candidate_model_mismatch'
            else:
                sidecar=ET.tostring(m,encoding='utf-8');kind='inline_canonical_reserialization'
                attrs['lexical_fallback_reason']='inline_model_lexical_count_mismatch'
            details=attrs;inline_ordinal+=1
        else:
            text=(d.text or '').strip()
            if not text: raise ValueError('empty_compressed_diagram_page')
            try: compressed=base64.b64decode(''.join(text.split()),validate=True)
            except Exception as e: raise ValueError('compressed_page_base64_invalid:'+type(e).__name__)
            # Must be raw deflate for official Graph.decompress; a zlib-wrapped
            # payload is retained for diagnosis but will not match official page decode.
            try:
                dec=zlib.decompressobj(-15);inflated=dec.decompress(compressed,LIMIT+1)
                if len(inflated)>LIMIT or dec.unconsumed_tail or not dec.eof or dec.unused_data: raise ValueError('compressed_page_bound_or_trailing')
                compression='raw_deflate'
            except Exception as raw_error:
                try:
                    dec=zlib.decompressobj(zlib.MAX_WBITS);inflated=dec.decompress(compressed,LIMIT+1)
                    if len(inflated)>LIMIT or dec.unconsumed_tail or not dec.eof or dec.unused_data: raise ValueError('compressed_page_bound_or_trailing')
                    compression='zlib_wrapper_diagnostic_only'
                except Exception:
                    raise ValueError('compressed_page_raw_deflate_failed:'+str(raw_error)[:200])
            try: inflated_text=inflated.decode('utf-8')
            except UnicodeDecodeError: inflated_text=inflated.decode('latin-1')
            if re.search(r'%(?![0-9A-Fa-f]{2})',inflated_text): raise ValueError('compressed_page_malformed_URI_escape')
            sidecar=urllib.parse.unquote_to_bytes(inflated_text)
            if len(sidecar)>LIMIT: raise ValueError('compressed_page_XML_above_bound')
            kind='compressed_raw_deflate_URI_decoded' if compression=='raw_deflate' else 'compressed_zlib_wrapper_URI_decoded_not_official'
            details=attrs|{'compressed_payload_sha256':sha(compressed),'inflated_sha256':sha(inflated),
                           'compressed_inflated_bytes':len(inflated),'compression_mode':compression,
                           'page_text_sha256':sha(text.encode('utf-8'))}
            m=safe_xml(sidecar)
        pages.append(_page_record(i,d.get('id'),d.get('name'),m,sidecar,kind,rawb,details))
    return {'root_kind':'mxfile','pages':pages,'full_XML_sha256':sha(rawb),'diagram_count':len(diagrams)}

# ---------------------------------------------------------------------------
# Official page decoder comparison
# ---------------------------------------------------------------------------
PAGE_DECODE_JS=r'''args=>{try{
 const root=mxUtils.parseXml(args.xml).documentElement;
 if(root.nodeName==='mxGraphModel'){
  if(args.index!==0)return {__error:'page_index_out_of_range'};
  return {nodeName:'mxGraphModel',xml:mxUtils.getXml(root),method:'native_root_mxGraphModel',page_id:null,page_name:null};
 }
 let ds=root.getElementsByTagName('diagram');
 if(args.index<0||args.index>=ds.length)return {__error:'page_index_out_of_range'};
 let d=ds[args.index],m=d.getElementsByTagName('mxGraphModel')[0],method='inline_mxGraphModel',decoded=null;
 if(!m){decoded=Graph.decompress(mxUtils.getTextContent(d));m=mxUtils.parseXml(decoded).documentElement;method='Graph.decompress_compressed_page';}
 if(m.nodeName!=='mxGraphModel')return {__error:'selected_page_not_mxGraphModel'};
 return {nodeName:m.nodeName,xml:mxUtils.getXml(m),method:method,page_id:d.getAttribute('id'),page_name:d.getAttribute('name'),decoded_chars:decoded?decoded.length:null};
}catch(e){return {__error:String(e&&e.message||e)}}}'''

def official_page_decode_agreement(renderer,full_rawb,page_meta):
    page=renderer.r.page if hasattr(renderer,'r') else renderer.page
    got=page.evaluate(PAGE_DECODE_JS,{'xml':full_rawb.decode('utf-8'),'index':page_meta['page_index']})
    if isinstance(got,dict) and got.get('__error'): raise ValueError('official_page_decoder_exception:'+got['__error'][:300])
    if not got: raise ValueError('official_page_decoder_returned_null')
    official_xml=got['xml'].encode('utf-8')
    sidecar=page_meta['page_sidecar_XML']
    exact=official_xml==sidecar
    try:
        canonical=canonical_model(safe_xml(official_xml))==canonical_model(safe_xml(sidecar))
    except Exception: canonical=False
    if not (exact or canonical): raise ValueError('official_page_decoder_disagrees_with_selected_page_model')
    if page_meta.get('page_id') is not None and got.get('page_id')!=page_meta.get('page_id'):
        raise ValueError('official_page_decoder_page_id_mismatch')
    if page_meta.get('page_name') is not None and got.get('page_name')!=page_meta.get('page_name'):
        raise ValueError('official_page_decoder_page_name_mismatch')
    return {'schema':'embedded_native_page_official_decoder_comparison_v1',
            'official_function':'Editor page decode via mxUtils.parseXml/Graph.decompress',
            'official_method':got.get('method'),'official_page_id':got.get('page_id'),
            'official_page_name':got.get('page_name'),'selected_page_index':page_meta['page_index'],
            'selected_page_id':page_meta.get('page_id'),'selected_page_name':page_meta.get('page_name'),
            'full_embedded_XML_sha256':sha(full_rawb),'selected_page_XML_sha256':sha(sidecar),
            'official_page_XML_sha256':sha(official_xml),'exact_bytes_equal':exact,
            'canonical_model_equal':bool(canonical),'official_WAR_sha256':sha(C.WAR.read_bytes())}

def page_selection_proof(parent,page,page_file_sha=None):
    side=page['page_sidecar_XML']
    return {'schema':'embedded_native_complete_page_selection_v1',
        'source_origin_kind':'embedded_native_complete_page',
        'parent_full_embedded_XML_file':parent['full_embedded_XML_file'],
        'parent_full_embedded_XML_sha256':parent['full_embedded_XML_sha256'],
        'full_original_embedded_XML_bytes_preserved':True,
        'selected_page_index':page['page_index'],'selected_page_id':page.get('page_id'),
        'selected_page_name':page.get('page_name'),'selected_page_XML_file':page['page_sidecar_file'],
        'selected_page_XML_sha256':sha(side),'selected_page_XML_bytes':len(side),
        'selected_page_extraction_kind':page['page_extraction_kind'],
        'selected_page_model_canonical_sha256':page['page_model_canonical_sha256'],
        'selected_page_graph_sha256':page['page_graph_sha256'],
        'cell_count':page['cell_count'],'vertex_count':page['vertex_count'],'edge_count':page['edge_count'],
        'complete_selected_mxGraphModel':True,'every_original_cell_edge_group_style_geometry_label_preserved':True,
        'fragment_crop_or_subgraph_selection':False,'geometry_or_scientific_content_rewritten':False,
        'sidecar_is_full_embedded_XML':bool(page.get('sidecar_is_full_embedded_XML')),
        'sidecar_XML_equals_full_embedded_XML':sha(side)==sha(parent['full_embedded_XML']),
        'sidecar_bytes_claimed_equal_when_not':False,
        'page_selection_proof_sha256':None}
