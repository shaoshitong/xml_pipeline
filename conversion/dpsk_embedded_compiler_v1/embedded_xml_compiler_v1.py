"""Deterministic extraction/validation core for SVG/PNG embedded draw.io XML.

Read-only with respect to original sources.  This module contains bounded,
safe container decoders and the strict static/render diagnostics used by the
durable batch runner.  It never rewrites or synthesises author geometry.
"""
from pathlib import Path
import base64, collections, hashlib, io, json, math, os, re, struct, tarfile, urllib.parse, zlib
import xml.etree.ElementTree as ET

R = Path('/backup/shaoshitong/img2code_20261029')
P = R / 'clean/arxiv_research_figures_v1'
S = R / 'conversion/scripts'
D = Path(__file__).resolve().parents[1] / 'results' / 'embedded_XML_compiler_dpsk_v1'
WAR = R / 'evaluation/assets/drawio-runtime-v32.6.1/draw.war'
LIMIT = 64 * 1024 * 1024
SOURCE_LIMIT = 128 * 1024 * 1024
TARGET_KEYS = ('mxfile', 'mxGraphModel')
UI_ATTRS = {'dx','dy','grid','gridSize','guides','tooltips','connect','arrows','fold','page','pageScale','pageWidth','pageHeight'}
TARGET_TEXT_TYPES = {'tEXt', 'zTXt', 'iTXt'}

def sha(b):
    if isinstance(b, Path): b = b.read_bytes()
    elif isinstance(b, str): b = b.encode()
    elif hasattr(b, 'read'): b = b.read()
    return hashlib.sha256(b).hexdigest()

def dumps(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def raw(x):
    return (dumps(x) + '\n').encode()

def finite_number(v):
    try:
        x = float(v)
        return math.isfinite(x)
    except (TypeError, ValueError):
        return False

def tag(e):
    return e.tag.rsplit('}', 1)[-1]

def local_attrs(d):
    return {k.rsplit('}', 1)[-1]: v for k, v in d.items()}

def atomic_put(path, data, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists():
        raise FileExistsError(str(path))
    tmp = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    if isinstance(data, str): data = data.encode()
    if exclusive:
        with tmp.open('xb') as f: f.write(data)
        os.link(tmp, path)
        tmp.unlink()
    else:
        with tmp.open('wb') as f: f.write(data)
        os.replace(tmp, path)
    return {'file': str(path), 'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size}

def put_json(path, obj, exclusive=False):
    return atomic_put(path, raw(obj), exclusive=exclusive)

# ---------------------------------------------------------------------------
# PNG metadata decoder.  Mirrors the official Editor.extractGraphModelFromPng
# contract: tEXt/zTXt only, keys mxfile/mxGraphModel, before IDAT, zTXt inflate
# and official '+' -> ' ' normalisation, then up to two leading-% URI decodes.
# iTXt is parsed for diagnosis but refused because the official decoder ignores it.
# ---------------------------------------------------------------------------
def _png_chunk(blob, off):
    if off + 12 > len(blob): raise ValueError('truncated_PNG_chunk_header')
    n = struct.unpack('>I', blob[off:off+4])[0]
    end = off + 12 + n
    if n > SOURCE_LIMIT or end > len(blob): raise ValueError('truncated_or_oversized_PNG_chunk')
    kind = blob[off+4:off+8]
    data = blob[off+8:off+8+n]
    crc = struct.unpack('>I', blob[off+8+n:end])[0]
    if (zlib.crc32(kind + data) & 0xffffffff) != crc:
        raise ValueError('PNG_chunk_CRC_changed')
    return kind, data, end

def _inflate_bounded(data):
    obj = zlib.decompressobj()
    out = obj.decompress(data, LIMIT + 1)
    if len(out) > LIMIT or obj.unconsumed_tail:
        raise ValueError('compressed_text_above_bound')
    out += obj.flush()
    if len(out) > LIMIT or not obj.eof or obj.unused_data:
        raise ValueError('compressed_text_incomplete_or_trailing')
    return out

def png_target_texts(blob):
    if len(blob) > SOURCE_LIMIT: raise ValueError('PNG_above_source_bound')
    if blob[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError('not_PNG')
    off = 8; rows = []; before_idat = True; iend = False; header = None
    while off < len(blob):
        kind, data, end = _png_chunk(blob, off)
        if kind == b'IHDR':
            if header is not None: raise ValueError('duplicate_IHDR')
            header = dict(zip(('width','height','bit_depth','color_type','compression','filtering','interlace'), struct.unpack('>IIBBBBB', data)))
        if kind == b'IDAT': before_idat = False
        if kind in (b'tEXt', b'zTXt', b'iTXt'):
            key, rest = data.split(b'\x00', 1)
            key = key.decode('latin-1')
            if key in TARGET_KEYS:
                chunk_type = kind.decode('ascii')
                text = None; steps = []
                if kind == b'tEXt':
                    text = rest.decode('latin-1')
                elif kind == b'zTXt':
                    if not rest or rest[0] != 0: raise ValueError('unsupported_zTXt_compression_method')
                    text = _inflate_bounded(rest[1:]).decode('latin-1')
                    steps.append('zlib_text_inflate')
                else:
                    compressed, method = rest[:2]
                    rest2 = rest[2:]
                    language, rest2 = rest2.split(b'\x00', 1)
                    translated, payload = rest2.split(b'\x00', 1)
                    if compressed:
                        if method != 0: raise ValueError('unsupported_iTXt_compression_method')
                        payload = _inflate_bounded(payload); steps.append('zlib_iTXt_inflate')
                    text = payload.decode('utf-8'); steps.append('iTXt_utf8')
                rows.append({
                    'chunk_type': chunk_type, 'key': key, 'before_IDAT': before_idat,
                    'text_latin1': text, 'text_sha256': sha(text.encode('latin-1', errors='strict')),
                    'text_bytes': len(text.encode('latin-1', errors='strict')),
                    'chunk_sha256': sha(blob[off:end]), 'chunk_bytes': blob[off:end],
                    'steps': steps,
                })
        off = end
        if kind == b'IEND': iend = True; break
    if header is None or not iend or off != len(blob):
        raise ValueError('PNG_structure_incomplete_or_trailing')
    return header, rows

def decode_png_metadata(blob):
    header, rows = png_target_texts(blob)
    if len(rows) != 1:
        raise ValueError('target_PNG_text_chunk_count_%d' % len(rows))
    row = rows[0]
    if not row['before_IDAT']:
        raise ValueError('official_PNG_decoder_stops_at_IDAT')
    if row['chunk_type'] == 'iTXt':
        raise ValueError('official_PNG_decoder_does_not_support_iTXt')
    text = row['text_latin1']
    if row['chunk_type'] == 'zTXt':
        normalised = text.replace('+', ' ')
        plus_changed = normalised != text
        row['steps'].append('official_zTXt_plus_to_space')
    else:
        normalised = text; plus_changed = False
    if plus_changed:
        raise ValueError('official_zTXt_plus_to_space_changes_author_bytes')
    b = normalised.encode('latin-1')
    for _ in range(2):
        if b[:1] == b'%':
            b = urllib.parse.unquote_to_bytes(b.decode('latin-1'))
            row['steps'].append('leading_percent_URI_decode')
        else:
            break
    if len(b) > LIMIT: raise ValueError('decoded_XML_above_bound')
    row.update(raw=b, raw_sha256=sha(b), raw_bytes=len(b), source_container_sha256=sha(blob),
               png_header=header, official_decoder='Editor.extractGraphModelFromPng')
    return row

# ---------------------------------------------------------------------------
# SVG embedded XML decoder.  A standard external SVG 1.1 DOCTYPE is accepted;
# internal subsets/ENTITY declarations are refused.  The content attribute rules
# follow Editor.extractGraphModel(node, true): raw XML, one leading-% URI decode,
# or legacy base64 for non-'<'/non-'%' values.
# ---------------------------------------------------------------------------
DOCTYPES = {
    b'-//W3C//DTD SVG 1.1//EN',
    b'-//W3C//DTD SVG 1.0//EN',
    b'-//W3C//DTD SVG 1.1 Basic//EN',
}

def _safe_svg_root(blob):
    if len(blob) > SOURCE_LIMIT: raise ValueError('SVG_above_source_bound')
    text = blob.decode('utf-8-sig')
    if '<!ENTITY' in text.upper(): raise ValueError('unsafe_SVG_ENTITY_declaration')
    # Remove only an external standard SVG doctype; never accept an internal subset.
    while True:
        m = re.search(r'<!DOCTYPE\s+[^>]*>', text, re.S | re.I)
        if not m: break
        dt = m.group(0)
        upper = dt.upper()
        if '[' in dt or '<!ENTITY' in upper: raise ValueError('unsafe_SVG_doctype_internal_subset')
        ident = re.search(r'PUBLIC\s+["\']([^"\']+)["\']', dt, re.I)
        if not ident or ident.group(1).encode().upper() not in DOCTYPES:
            raise ValueError('unsupported_SVG_doctype')
        text = text[:m.start()] + text[m.end():]
    if len(text.encode()) > LIMIT: raise ValueError('SVG_XML_above_bound')
    return ET.fromstring(text)

def decode_svg_metadata(blob):
    root = _safe_svg_root(blob)
    rt = tag(root)
    if rt in TARGET_KEYS:
        rawb = blob[3:] if blob.startswith(b'\xef\xbb\xbf') else blob
        return {'chunk_type': 'native_root', 'key': rt, 'steps': ['native_root_XML'],
                'raw': rawb, 'raw_sha256': sha(rawb), 'raw_bytes': len(rawb),
                'source_container_sha256': sha(blob), 'official_decoder': 'Editor.extractGraphModel(node,true)',
                'svg_root': rt, 'content_sha256': None, 'content_steps': []}
    if rt != 'svg': raise ValueError('SVG_root_not_svg_or_native')
    content = root.get('content')
    if content is None: raise ValueError('SVG_content_attribute_missing')
    steps = []; b = content.encode('utf-8')
    if not content.startswith('<') and not content.startswith('%'):
        try: b = base64.b64decode(content, validate=True)
        except Exception as e: raise ValueError('SVG_legacy_base64_invalid:' + type(e).__name__)
        steps.append('legacy_base64')
    if b[:1] == b'%':
        b = urllib.parse.unquote_to_bytes(b.decode('utf-8'))
        steps.append('leading_percent_URI_decode')
    if len(b) > LIMIT: raise ValueError('decoded_XML_above_bound')
    return {'chunk_type': 'svg_content', 'key': 'content', 'steps': steps,
            'raw': b, 'raw_sha256': sha(b), 'raw_bytes': len(b),
            'source_container_sha256': sha(blob), 'official_decoder': 'Editor.extractGraphModel(node,true)',
            'svg_root': rt, 'content_sha256': sha(content.encode('utf-8')), 'content_steps': steps}

def extract_candidate(path, kind):
    path = Path(path)
    if not path.is_file(): raise FileNotFoundError(str(path))
    if path.stat().st_size > SOURCE_LIMIT: raise ValueError('source_file_above_bound')
    blob = path.read_bytes()
    return decode_png_metadata(blob) if kind.startswith('PNG') else decode_svg_metadata(blob)

# ---------------------------------------------------------------------------
# Native models, value policy, graph fingerprints
# ---------------------------------------------------------------------------
def import_native_modules():
    import sys
    if str(S) not in sys.path: sys.path.insert(0, str(S))
    from arxiv_author_native_assets_v1 import models, dependencies
    from arxiv_math_source_repair_v1 import native, classify, valuable
    from inventory_arxiv_direct_author_XML_v1 import graphhash
    return models, dependencies, native, classify, valuable, graphhash

def node_tree(n):
    return [n.tag, sorted(n.attrib.items()), (n.text or '').strip(), [node_tree(c) for c in n]]

def page_graph_hash(model):
    root = model.find('root')
    if root is None: raise ValueError('native_model_root_missing')
    return sha(raw(node_tree(root)))

def document_graphs(rawb):
    models, _, _, _, _, _ = import_native_modules()
    root, ms = models(rawb)
    hashes = [page_graph_hash(m) for m in ms]
    return root, ms, hashes, sha(raw(json.dumps(hashes, ensure_ascii=True)))

def value_snapshot(rawb):
    models, _, native, classify, valuable, _ = import_native_modules()
    root, ms = models(rawb)
    features = native(rawb.decode('utf-8-sig'))
    kind, reasons = classify(features, 'drawio', {})
    is_valuable = bool(kind == 'complex_candidate' and len(ms) == 1 and valuable(features))
    return features, kind, reasons, is_valuable, len(ms)

# ---------------------------------------------------------------------------
# Source archive, receipt, metadata identity (read-only)
# ---------------------------------------------------------------------------
def candidate_source_identity(path):
    path = Path(path).resolve()
    base = (P / 'recent_ai_source_expansion_v2/papers').resolve()
    try:
        rel = path.relative_to(base)
    except ValueError:
        raise ValueError('candidate_outside_completed_source_papers')
    paper = rel.parts[0]
    folder = base / paper
    source_root = folder / 'source'
    try:
        rel_source = path.relative_to(source_root)
    except ValueError:
        raise ValueError('candidate_outside_paper_source_tree')
    archive = folder / 'source.archive'; receipt = folder / 'source_receipt.json'
    if not archive.is_file() or not receipt.is_file():
        raise ValueError('source_archive_or_receipt_missing')
    receipt_obj = json.loads(receipt.read_text())
    if receipt_obj.get('url') != 'https://arxiv.org/src/' + paper:
        raise ValueError('source_receipt_url_mismatch')
    if sha(archive) != receipt_obj.get('sha256') or archive.stat().st_size != receipt_obj.get('bytes'):
        raise ValueError('source_archive_receipt_hash_or_size_mismatch')
    import sqlite3
    once = P / 'recent_ai_source_expansion_v2/once.sqlite'
    with sqlite3.connect(once.as_uri() + '?mode=ro', uri=True) as c:
        c.execute('pragma query_only=ON')
        row = c.execute('select status,record from papers where id=?', (paper,)).fetchone()
    if not row or row[0] != 'source_completed':
        raise ValueError('paper_not_source_completed')
    rec = json.loads(row[1]); meta = rec.get('metadata', {})
    if meta.get('versioned_id') != paper: raise ValueError('paper_metadata_versioned_id_mismatch')
    import datetime
    try:
        pd = str(meta['publication_date']).replace('Z', '+00:00').replace('/', '-')
        day = datetime.datetime.fromisoformat(pd).date()
    except Exception:
        raise ValueError('paper_publication_date_unverified')
    if not datetime.date(2023, 1, 1) <= day <= datetime.date(2026, 11, 2):
        raise ValueError('paper_publication_date_outside_frozen_window')
    cats = set(meta.get('categories', []))
    if not cats & {'cs.AI', 'cs.CL', 'cs.CV', 'cs.LG'}:
        raise ValueError('paper_categories_outside_AI_CL_CV_LG')
    return {
        'paper': paper, 'paper_folder': str(folder.relative_to(R)),
        'source_root': str(source_root.relative_to(R)),
        'candidate_archive_relative': rel_source.as_posix(),
        'source_archive_file': str(archive.relative_to(R)), 'source_archive_sha256': sha(archive),
        'source_archive_bytes': archive.stat().st_size,
        'source_receipt_file': str(receipt.relative_to(R)), 'source_receipt_sha256': sha(receipt),
        'source_receipt': receipt_obj,
        'original_paper_record_SHA256': sha(row[1].encode()),
        'paper_metadata': meta,
    }

def archive_file(t, source, root):
    source = Path(source).resolve(); root = Path(root).resolve()
    relative = source.relative_to(root).as_posix()
    import posixpath
    members = []
    for m in t.getmembers():
        name = m.name
        parts = [p for p in name.replace('\\', '/').split('/') if p not in ('', '.')]
        if m.isfile() and not name.startswith('/') and '..' not in parts and '/'.join(parts) == relative:
            members.append(m)
    if len(members) != 1: raise ValueError('archive_member_missing_or_ambiguous:' + relative)
    m = members[0]
    if m.size > SOURCE_LIMIT: raise ValueError('archive_member_above_bound')
    with t.extractfile(m) as f: b = f.read(m.size + 1)
    if len(b) != m.size or sha(b) != sha(source) or b != source.read_bytes():
        raise ValueError('archive_member_bytes_mismatch:' + relative)
    return {'member': m.name, 'sha256': sha(b), 'bytes': len(b), 'relative': relative}

def verify_source_archive_members(identity, source_file, asset_files=()):
    archive = R / identity['source_archive_file']
    root = R / identity['source_root']
    proof = {'archive': identity['source_archive_file'], 'archive_sha256': identity['source_archive_sha256'], 'members': []}
    with tarfile.open(archive) as t:
        proof['members'].append(archive_file(t, source_file, root))
        for p in sorted({str(Path(x).resolve()) for x in asset_files}):
            proof['members'].append(archive_file(t, Path(p), root))
    proof['all_members_exact_and_safe'] = True
    return proof

# ---------------------------------------------------------------------------
# Static diagnostics
# ---------------------------------------------------------------------------
def _style_tokens(style):
    out = {}
    for part in (style or '').split(';'):
        if '=' in part:
            k, v = part.split('=', 1); out[k.strip()] = v.strip()
    return out

def _model_cells(ms):
    return [c for m in ms for c in m.iter('mxCell')]

def static_diagnostics(rawb, features, ms):
    cells = _model_cells(ms)
    vertices = [c for c in cells if c.get('vertex') in ('1', 'true')]
    edges = [c for c in cells if c.get('edge') in ('1', 'true')]
    images = [c for c in vertices if 'image=' in (c.get('style') or '') or 'shape=image' in (c.get('style') or '')]
    fails = []; warnings = []; detail = {}
    detail.update(vertices=len(vertices), edges=len(edges), images=len(images),
                  labels=int(features.get('distinct_owner_labels', 0)),
                  label_characters=int(features.get('label_characters', 0)))
    # Wrapper / whole-raster tests.
    if not vertices:
        fails.append('native_graph_has_no_editable_vertices')
    if len(vertices) <= 1 and images:
        fails.append('whole_raster_wrapper_without_independent_structure')
    if features.get('all_single_image_wrapper'):
        fails.append('wrapper_or_single_image_source')
    # Bounds / geometry.
    xs=[]; ys=[]; bad=[]
    for c in vertices:
        g = c.find('mxGeometry')
        if g is None: bad.append(c.get('id')); continue
        for k in ('x','y'):
            if g.get(k) is not None:
                if not finite_number(g.get(k)): bad.append(c.get('id')); break
        if g.get('x') is not None and finite_number(g.get('x')): xs.append(float(g.get('x')))
        if g.get('y') is not None and finite_number(g.get('y')): ys.append(float(g.get('y')))
    if bad: fails.append('non_finite_vertex_geometry')
    if xs or ys:
        width = (max(xs) - min(xs)) if xs else 0; height = (max(ys) - min(ys)) if ys else 0
        detail['coordinate_span'] = [min(xs) if xs else None, min(ys) if ys else None, width, height]
        if max(abs(v) for v in xs + ys) > 1_000_000:
            fails.append('vertex_coordinates_above_1e6')
        if width > 100_000 or height > 100_000:
            fails.append('huge_canvas_bounds_above_100000')
        elif width > 30_000 or height > 30_000:
            warnings.append('large_canvas_bounds_above_30000')
    for m in ms:
        pw = m.get('pageWidth'); ph = m.get('pageHeight')
        if finite_number(pw) and finite_number(ph):
            pw = float(pw); ph = float(ph); detail['page_canvas'] = [pw, ph]
            if pw <= 0 or ph <= 0: fails.append('nonpositive_page_canvas')
            elif pw > 1_000_000 or ph > 1_000_000: fails.append('page_canvas_above_1e6')
            elif pw > 20_000 or ph > 20_000: warnings.append('large_page_canvas_above_20000')
            if xs and ys and pw * ph > 0:
                used = max(width, 1) * max(height, 1)
                if used / (pw * ph) < 1e-5:
                    warnings.append('sparse_page_canvas_used_area_below_1e-5')
    # Repeated draft subgraph signature (only for real labelled cells).
    sig = collections.Counter()
    for c in vertices:
        v = (c.get('value') or '').strip()
        if not v: continue
        g = c.find('mxGeometry')
        geo = tuple(round(float(g.get(k) or 0), 3) for k in ('x','y','width','height')) if g is not None and all(finite_number(g.get(k) or 0) for k in ('x','y','width','height')) else ()
        sig[(v, c.get('style') or '', geo)] += 1
    if sig:
        val, count = sig.most_common(1)[0]
        detail['max_identical_labelled_cell_signature'] = count
        detail['distinct_labelled_cell_signatures'] = len(sig)
        if count >= 8 and len(vertices) >= 20 and count / len(vertices) >= 0.4:
            fails.append('repeated_draft_subgraph_signature')
        elif count >= 5:
            warnings.append('repeated_identical_labelled_cells')
    # Asset static diagnostics.
    dep = detail.get('assets')
    return {'ok': not fails, 'failures': sorted(set(fails)), 'warnings': sorted(set(warnings)), 'detail': detail}

def asset_diagnostics(dep, packaged_manifest=None):
    fails=[]; warnings=[]; rows=[]
    for a in dep.get('assets', []):
        st = a.get('status'); uri = a.get('uri', '')[:120]
        row = {k: a.get(k) for k in ('role','cell','status','uri_sha256','mime','bytes','sha256','dimensions','file','reason') if a.get(k) is not None}
        row['uri_prefix'] = a.get('uri_prefix') or uri.split(',',1)[0][:80]
        if st and st.startswith(('pending_', 'unsupported_')):
            fails.append('unclosed_asset:' + st)
        if st == 'inline_verified' and a.get('dimensions'):
            w,h = a['dimensions']
            row['dimensions'] = [w,h]
            if w < 8 or h < 8 or w*h < 64: fails.append('low_resolution_inline_image')
            elif w < 32 or h < 32: warnings.append('small_inline_image')
        if st == 'author_adjacent_file':
            p = Path(a.get('file', ''))
            if not p.is_file(): fails.append('adjacent_asset_missing_after_inventory')
            else:
                from PIL import Image
                try:
                    with Image.open(p) as im:
                        w,h = im.size; im.verify()
                    row['dimensions'] = [w,h]
                    if w < 8 or h < 8: fails.append('low_resolution_adjacent_image')
                    elif w < 32 or h < 32: warnings.append('small_adjacent_image')
                except Exception as e:
                    fails.append('adjacent_asset_decode_failed:' + type(e).__name__)
        rows.append(row)
    if packaged_manifest:
        for r in packaged_manifest.get('resource_dependencies', []):
            from PIL import Image
            p = R / r['portable_asset_file'] if not Path(r['portable_asset_file']).is_absolute() else Path(r['portable_asset_file'])
            if not p.is_file() or sha(p.read_bytes()) != r['sha256']:
                fails.append('packaged_asset_hash_or_existence_failed')
                continue
            try:
                with Image.open(p) as im:
                    w,h=im.size; im.verify()
                if w < 8 or h < 8: fails.append('low_resolution_packaged_image')
            except Exception:
                # Non-image inline dependencies are legal; only image MIME is decoded upstream.
                pass
    return {'ok': not fails, 'failures': sorted(set(fails)), 'warnings': sorted(set(warnings)), 'assets': rows}

def render_diagnostics(proof, png_path, dep, packaged_manifest=None):
    from PIL import Image, ImageChops
    fails=[]; warnings=[]; detail={}
    if not proof.get('ok'):
        fails.append('strict_render_edit_restore_proof_not_ok')
    for key in ('normalized_model_exact_restore','mutation_normalized_model_changed',
                'mutation_actual_RGBA_changed','restored_actual_RGBA_exact',
                'restored_PNG_bytes_exact','restored_SVG_namespace_canonical_exact'):
        if proof.get(key) is not True: fails.append('strict_check_failed:' + key)
    fonts = proof.get('font_observations', {})
    if not fonts.get('all_physical_font_bytes_pinned'):
        fails.append('font_bytes_not_pinned')
    for f in fonts.get('font_assets', []):
        p = R / f['file']
        if not p.is_file() or sha(p.read_bytes()) != f.get('sha256'):
            fails.append('font_file_hash_changed')
    closure = proof.get('resource_closure', {})
    if closure.get('failed'): fails.append('render_resource_closure_failed')
    bounds = proof.get('source_initial_state', {}).get('bounds', {})
    detail['bounds'] = bounds
    for k in ('x','y','width','height'):
        if not finite_number(bounds.get(k)): fails.append('render_bounds_non_finite')
    if finite_number(bounds.get('width')) and finite_number(bounds.get('height')):
        w=float(bounds['width']); h=float(bounds['height'])
        if w <= 0 or h <= 0: fails.append('render_bounds_empty')
        if w > 100_000 or h > 100_000: fails.append('render_bounds_above_100000')
        elif w > 30_000 or h > 30_000: warnings.append('render_bounds_large')
    png_path = Path(png_path)
    if not png_path.is_file(): fails.append('official_png_missing')
    else:
        try:
            with Image.open(png_path) as im:
                rgba = im.convert('RGBA'); detail['png_size'] = list(im.size)
                bbox = ImageChops.difference(im.convert('RGB'), Image.new('RGB', im.size, 'white')).getbbox()
                if bbox is None:
                    fails.append('blank_official_png')
                else:
                    area = max(1, (bbox[2]-bbox[0])*(bbox[3]-bbox[1]))
                    ratio = area / (im.size[0]*im.size[1])
                    detail['nonwhite_bbox'] = list(bbox); detail['nonwhite_bbox_area_ratio'] = round(ratio, 8)
                    if im.size[0] > 8192 or im.size[1] > 8192: fails.append('official_png_above_8192')
                    if im.size[0] < 2 or im.size[1] < 2: fails.append('official_png_too_small')
                    if ratio < 1e-6: fails.append('huge_blank_official_canvas')
                    elif ratio < 1e-4: warnings.append('sparse_official_canvas')
        except Exception as e:
            fails.append('official_png_decode_failed:' + type(e).__name__)
    a = asset_diagnostics(dep, packaged_manifest)
    detail['asset_diagnostics'] = a
    if not a['ok']: fails.extend(a['failures'])
    else: warnings.extend(a['warnings'])
    return {'ok': not fails, 'failures': sorted(set(fails)), 'warnings': sorted(set(warnings)), 'detail': detail}

def static_diagnostics_with_assets(rawb, features, ms, dep):
    s = static_diagnostics(rawb, features, ms)
    a = asset_diagnostics(dep)
    s['failures'] = sorted(set(s['failures'] + a['failures'])); s['warnings'] = sorted(set(s['warnings'] + a['warnings']))
    s['ok'] = not s['failures']; s['detail']['asset_diagnostics'] = a
    return s

# ---------------------------------------------------------------------------
# Official decoder agreement
# ---------------------------------------------------------------------------
PNG_DECODE_JS = r'''b64=>{try{return Editor.extractGraphModelFromPng('data:image/png;base64,'+b64);}catch(e){return {__error:String(e&&e.message||e)}}}'''
SVG_DECODE_JS = r'''svg=>{try{const root=mxUtils.parseXml(svg).documentElement;const node=Editor.extractGraphModel(root,true);if(!node)return null;return {nodeName:node.nodeName,xml:mxUtils.getXml(node)};}catch(e){return {__error:String(e&&e.message||e)}}}'''

def canonical_xml_bytes(blob):
    root = ET.fromstring(blob)
    return ET.canonicalize(ET.tostring(root, encoding='unicode'), strip_text=True).encode()

def official_decode_agreement(renderer, source_blob, kind, rawb):
    page = renderer.r.page if hasattr(renderer, 'r') else renderer.page
    if kind.startswith('PNG'):
        got = page.evaluate(PNG_DECODE_JS, base64.b64encode(source_blob).decode())
        if isinstance(got, dict) and got.get('__error'): raise ValueError('official_PNG_decoder_exception:' + got['__error'][:300])
        if got is None: raise ValueError('official_PNG_decoder_returned_null')
        gotb = got.encode('utf-8')
        exact = gotb == rawb
        canonical = None
        if not exact:
            try: canonical = canonical_xml_bytes(gotb) == canonical_xml_bytes(rawb)
            except Exception: canonical = False
        if not (exact or canonical):
            raise ValueError('official_PNG_decoder_disagrees_with_bounded_decoder')
        return {'official_function':'Editor.extractGraphModelFromPng','official_xml_sha256':sha(gotb),
                'python_xml_sha256':sha(rawb),'exact_bytes_equal':exact,
                'canonical_XML_equal':bool(canonical if not exact else True),
                'iTXt_or_after_IDAT_used':False,'official_WAR_sha256':sha(WAR.read_bytes())}
    got = page.evaluate(SVG_DECODE_JS, source_blob.decode('utf-8'))
    if isinstance(got, dict) and got.get('__error'): raise ValueError('official_SVG_decoder_exception:' + got['__error'][:300])
    if not got: raise ValueError('official_SVG_decoder_returned_null')
    gotb = got['xml'].encode('utf-8')
    exact = gotb == rawb
    canonical = False
    try: canonical = canonical_xml_bytes(gotb) == canonical_xml_bytes(rawb)
    except Exception: pass
    if not (exact or canonical): raise ValueError('official_SVG_decoder_disagrees_with_bounded_decoder')
    return {'official_function':'Editor.extractGraphModel(mxUtils.parseXml(svg).documentElement,true)',
            'official_root_node':got.get('nodeName'),'official_xml_sha256':sha(gotb),
            'python_xml_sha256':sha(rawb),'exact_bytes_equal':exact,'canonical_XML_equal':canonical,
            'official_WAR_sha256':sha(WAR.read_bytes())}

def source_hashes_for_manifest(paths):
    rows=[]
    for p in sorted({Path(x) for x in paths}):
        rows.append({'file': str(p.relative_to(R)) if p.is_relative_to(R) else str(p),
                     'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size})
    return rows
