"""Original native graph plus independently reproved physical-font substitution.

The old bold/italic cell flags may be absorbed by the actual embedded face.
Every such change is checked against font bytes, live PS/glyph observations and
exact before/after native pixels. This is source evidence, never acceptance.
"""
import base64
import collections
import hashlib
import io
import json
import re
import urllib.parse
import uuid
import xml.etree.ElementTree as E
from pathlib import Path

R = Path('/backup/shaoshitong/img2code_20261029')
PROFILE = 'original_native_exact_graph_physical_font_only_v4'
HASH = re.compile(r'^[0-9a-f]{64}$')
FONT_KEYS = {'fontFamily','fontStyle','fontSource'}
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _normalize(source):
    from native_worker import normalize
    return normalize(source)


def _pixels(raw):
    from PIL import Image
    im=Image.open(io.BytesIO(raw)).convert('RGBA')
    return im.size,im.tobytes()


def _read(path, checks):
    raw=path.read_bytes()
    checks[str(path)]=sha(raw)
    return raw


def _clean(root, locator, digest, checks):
    target=(root/locator).resolve()
    if not target.is_relative_to((root/'clean').resolve()):
        raise ValueError('font_source_resource_outside_clean')
    raw=_read(target,checks)
    if sha(raw)!=digest:
        raise ValueError('font_source_resource_hash_changed: '+locator)
    return raw


def _models(xml):
    outer=E.fromstring(xml)
    models=list(outer.iter('mxGraphModel'))
    if len(models)!=1 or outer.tag=='mxfile' and len(outer.findall('diagram'))!=1:
        raise ValueError('font_source_requires_one_uncompressed_page')
    return outer,models[0]


def _cells(outer):
    parents={child:parent for parent in outer.iter() for child in parent}
    result={}
    for cell in outer.iter('mxCell'):
        identifier=cell.get('id') or parents[cell].get('id')
        if not identifier or identifier in result:
            raise ValueError('font_source_ambiguous_cell_identity')
        result[identifier]=cell
    return result


def style_tokens(value):
    # Protect raw data URI headers; normally fontSource is percent encoded.
    value=re.sub(r'((?:image|fontSource)=data:[^,]*,)',lambda m:m[0].replace(';','\x00'),value)
    return [part.replace('\x00',';') for part in value.split(';')]


def style_values(cell):
    return {part.split('=',1)[0]:part.split('=',1)[1] for part in style_tokens(cell.get('style','')) if '=' in part}


def canonical_font_only(xml, changed):
    """Never sort away named styles, resets, topology, text, geometry or other flags."""
    outer,model=_models(xml)
    cells=_cells(outer)
    model.attrib.pop('extFonts',None)
    for identifier in changed:
        cell=cells[identifier]
        value=cell.get('style','')
        tokens=style_tokens(value)
        cell.set('style',json.dumps({'leading_default_reset':value.startswith(';'),
                    'ordered_nonfont_tokens':[part for part in tokens if part and not ('=' in part and part.split('=',1)[0] in FONT_KEYS)]},sort_keys=True))
    def tree(node):
        return [node.tag,sorted(node.attrib.items()),node.text,node.tail,[tree(c) for c in node]]
    return json.dumps(tree(outer),ensure_ascii=False,separators=(',',':'))


def _font_blob(uri):
    decoded=urllib.parse.unquote(uri)
    if not decoded.startswith('data:') or ';base64,' not in decoded:
        raise ValueError('font_source_nonembedded_added_face')
    return base64.b64decode(decoded.split(',',1)[1],validate=True)


def _ext(model):
    result={}
    for entry in (model.get('extFonts') or '').split('|'):
        if not entry:
            continue
        family,separator,uri=entry.partition('^')
        if not family or not separator or family in result:
            raise ValueError('font_source_ambiguous_ext_fonts')
        result[family]=uri
    return result


def _sfnt(raw,index=0):
    from fontTools.ttLib import TTFont
    ft=TTFont(io.BytesIO(raw),fontNumber=index)
    try:
        names=sorted({r.toUnicode() for r in ft['name'].names if r.nameID==6})
        if len(names)!=1 or 'fvar' in ft:
            raise ValueError('font_source_ambiguous_or_variable_physical_face')
        bold=bool(ft['OS/2'].fsSelection&0x20) if 'OS/2' in ft else bool(ft['head'].macStyle&1)
        italic=bool(ft['OS/2'].fsSelection&1) if 'OS/2' in ft else bool(ft['head'].macStyle&2)
        tables={}
        for tag in ft.keys():
            if tag=='GlyphOrder':
                continue
            blob=ft.getTableData(tag)
            if tag=='head':blob=blob[:8]+b'\0'*4+blob[12:] # container checksum adjustment only
            tables[tag]=sha(blob)
        return {'postscript':names[0],'bold':bold,'italic':italic,'table_hashes':tables}
    finally:
        ft.close()


def verify_assets(root, record, before_model, model, checks):
    old=_ext(before_model)
    current=_ext(model)
    if any(current.get(k)!=v for k,v in old.items()):
        raise ValueError('font_source_original_font_payload_removed_or_changed')
    records={}
    for asset in record.get('native_embedded_fonts') or []:
        family=asset.get('family')
        if not family or family in records:
            raise ValueError('font_source_ambiguous_asset_family')
        records[family]=asset
    verified={}
    for family,uri in current.items():
        if family in old:
            continue
        asset=records.get(family)
        if not asset:
            raise ValueError('font_source_added_face_has_no_clean_asset')
        raw=_clean(root,asset['file'],asset['sha256'],checks)
        original=_clean(root,asset['original_file'],asset['original_sha256'],checks)
        if _font_blob(uri)!=raw:
            raise ValueError('font_source_ext_font_bytes_differ_from_clean_asset')
        face=_sfnt(raw)
        source_face=_sfnt(original,int(asset.get('collection_index',0)))
        if face!=source_face:
            raise ValueError('font_source_embedded_face_differs_from_original_physical_font')
        if (face['postscript']!=asset.get('physical_postscript_name') or face['bold'] is not asset.get('physical_bold')
                or face['italic'] is not asset.get('physical_italic')):
            raise ValueError('font_source_asset_physical_flags_or_ps_name_forged')
        verified[family]={**face,'file':asset['file'],'sha256':asset['sha256']}
    return verified


def _counts(fonts, custom=None):
    result=collections.Counter()
    for font in fonts:
        count=font.get('glyphCount')
        if type(count) is not int or count<0:
            raise ValueError('font_source_invalid_glyph_count')
        if count:
            if not font.get('postScriptName') or custom is not None and font.get('isCustomFont') is not custom:
                raise ValueError('font_source_physical_face_or_custom_status_mismatch')
            result[font['postScriptName']]+=count
    return dict(result)


def signature(rows, key='fonts', custom=None):
    result={}
    for row in rows:
        identifier=row.get('cell')
        if not identifier or identifier in result:
            raise ValueError('font_source_ambiguous_physical_observation')
        counts=_counts(row[key],custom)
        if counts:result[identifier]=counts
    return result


def verify_changes(before, xml, details, observations, faces):
    oldroot,_=_models(before)
    root,_=_models(xml)
    oldcells=_cells(oldroot)
    cells=_cells(root)
    changes=details.get('changes')
    if details.get('issues') or not isinstance(changes,list) or not changes:
        raise ValueError('font_source_missing_or_problematic_change_details')
    changed=[item.get('cell') for item in changes]
    if len(set(changed))!=len(changed) or any(k not in cells or k not in oldcells for k in changed):
        raise ValueError('font_source_changed_cell_identity_mismatch')
    if canonical_font_only(before,changed)!=canonical_font_only(xml,changed):
        raise ValueError('font_source_nonfont_graph_text_geometry_or_named_style_changed')
    observed={row['cell']:row for row in observations}
    if len(observed)!=len(observations):
        raise ValueError('font_source_duplicate_stored_observations')
    for change in changes:
        identifier=change['cell']
        row=observed.get(identifier)
        old=style_values(oldcells[identifier])
        current=style_values(cells[identifier])
        family=current.get('fontFamily')
        face=faces.get(family)
        if row is None or face is None or family!=change.get('family'):
            raise ValueError('font_source_unverified_change_family_or_observation')
        before_flags=change.get('before_flags')
        after_flags=change.get('after_flags')
        if type(before_flags) is not int or type(after_flags) is not int or min(before_flags,after_flags)<0:
            raise ValueError('font_source_invalid_style_flags')
        if before_flags!=int(row.get('style',{}).get('fontStyle',0)) or after_flags!=int(current.get('fontStyle','0')):
            raise ValueError('font_source_style_flags_disagree_with_actual_observation_or_xml')
        if change.get('before_family')!=row.get('style',{}).get('fontFamily'):
            raise ValueError('font_source_change_before_family_disagrees_with_observation')
        if 'fontStyle' in old and (int(old['fontStyle'])&~3)!=(before_flags&~3):
            raise ValueError('font_source_non_bold_italic_source_flags_changed')
        expected=before_flags & ~(1 if face['bold'] else 0) & ~(2 if face['italic'] else 0)
        if (before_flags&~3)!=(after_flags&~3) or expected!=after_flags:
            raise ValueError('font_source_style_flags_not_absorbed_by_verified_physical_face')
        actual=[f for f in row['actual_fonts'] if f.get('glyphCount')]
        if len(actual)!=1 or actual[0]!=change.get('actual_font') or actual[0].get('isCustomFont') is not False:
            raise ValueError('font_source_change_does_not_match_stored_system_face')
        if actual[0]['postScriptName']!=face['postscript']:
            raise ValueError('font_source_bold_italic_or_other_physical_face_changed')
        if current.get('fontSource') and _font_blob(current['fontSource'])!=_font_blob(_ext(_models(xml)[1])[family]):
            raise ValueError('font_source_cell_font_bytes_differ_from_verified_face')
    return set(changed)


def _render(xml,width,height,root):
    from native_worker import native
    return native.native_job(xml,width,height,180,root/'conversion/rendering_paintbounds_strict/remote_render.py',
                             8192,root/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')


def check_native_profile(record, xml, source, native_info=None, *, root=None):
    result={'supported':record.get('source_format')=='drawio','ok':False,'profile':PROFILE,'failures':[],
            'evidence':{},'accepted':False}
    if not result['supported']:
        result['failures']=[{'reason':'native_original_drawio_source_required'}]
        return result
    root=Path(root or R).resolve()
    checks={}
    try:
        if sha(Path(__file__).read_bytes())!=IMPLEMENTATION_SHA256:
            raise ValueError('font_source_verifier_module_changed_after_import')
        identity={k:record.get(k) for k in ('id','source_code_sha256','source_image_sha256')}
        if any(not HASH.fullmatch(str(v or '')) for v in identity.values()) or record.get('source_pair_sha256')!=identity['id']:
            raise ValueError('font_source_original_pair_identity_invalid')
        if sha(source.encode())!=identity['source_code_sha256'] or sha(xml.encode())!=record['code_sha256']:
            raise ValueError('font_source_source_or_current_xml_hash_changed')
        if record.get('source_record'):
            if any(record['source_record'].get(a)!=identity[b] for a,b in [('code_sha256','source_code_sha256'),('image_sha256','source_image_sha256')]):
                raise ValueError('font_source_authoritative_source_record_identity_mismatch')
        proof=record.get('native_font_validation') or {}
        digest=proof.get('input_code_sha256')
        if not HASH.fullmatch(str(digest or '')) or proof.get('output_code_sha256')!=record['code_sha256']:
            raise ValueError('font_source_repair_does_not_describe_current_xml')
        folder=root/'conversion/auto_quality_font_repair_v1'/record['id']/digest
        audit=(root/proof['audit']).resolve()
        if audit!=folder/'report.json' or not audit.is_relative_to((root/'conversion/auto_quality_font_repair_v1').resolve()):
            raise ValueError('font_source_unowned_audit')
        stored=json.loads(_read(audit,checks))
        if stored!=proof or stored.get('ok') is not True or stored.get('accepted') is not False:
            raise ValueError('font_source_frozen_report_changed')
        before=_read(folder/'before.drawio',checks).decode()
        previous=json.loads(_read(folder/'before_record.json',checks))
        candidate=_read(folder/'candidate.drawio',checks).decode()
        candidate_record=json.loads(_read(folder/'candidate_record.json',checks))
        frozen_png=_read(folder/'candidate.png',checks)
        details=json.loads(_read(folder/'font_details.json',checks))
        observations=json.loads(_read(folder/'observations.json',checks))
        for r in (previous,candidate_record):
            if any(r.get(k)!=v for k,v in identity.items()) or r.get('source_pair_sha256')!=identity['id']:
                raise ValueError('font_source_frozen_record_source_identity_changed')
        normalized,pages,_=_normalize(source)
        if pages!=1 or normalized!=before or sha(before.encode())!=digest or previous['code_sha256']!=digest:
            raise ValueError('font_source_owned_input_is_not_exact_normalized_original')
        if candidate!=xml or candidate_record['code_sha256']!=record['code_sha256'] or candidate_record.get('native_font_validation')!=proof:
            raise ValueError('font_source_frozen_candidate_xml_or_record_changed')
        if sha(frozen_png)!=proof['output_image_sha256'] or candidate_record['image_sha256']!=proof['output_image_sha256'] or previous['image_sha256']!=proof['input_image_sha256']:
            raise ValueError('font_source_frozen_png_identity_changed')
        _clean(root,record['code_file'],record['code_sha256'],checks)
        current_png=_clean(root,record['image_file'],record['image_sha256'],checks)
        if record.get('original_source_code'):_clean(root,record['original_source_code'],identity['source_code_sha256'],checks)
        if record.get('original_reference'):_clean(root,record['original_reference'],identity['source_image_sha256'],checks)
        archive=root/'conversion/harness_sessions'/('auto_font_'+record['id']+'_'+digest)/'baseline'
        if (root/record['previous_candidate_archive']).resolve()!=archive:
            raise ValueError('font_source_baseline_archive_not_owned_by_this_repair')
        if json.loads(_read(archive/'conversion.json',checks))!=previous or _read(archive/'diagram.drawio',checks).decode()!=before:
            raise ValueError('font_source_frozen_baseline_archive_changed')
        before_png=_read(archive/'image.png',checks)
        if sha(before_png)!=proof['input_image_sha256']:
            raise ValueError('font_source_baseline_png_changed')
        old_model=_models(before)[1]
        model=_models(xml)[1]
        faces=verify_assets(root,record,old_model,model,checks)
        changed=verify_changes(before,xml,details,observations,faces)
        renderer=root/'conversion/rendering_paintbounds_strict/remote_render.py'
        runtime=root/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
        renderer_hash=sha(_read(renderer,checks))
        runtime_hash=sha(_read(runtime,checks))
        width,height=_pixels(before_png)[0]
        baseline=_render(before,width,height,root)
        current=_render(xml,width,height,root)
        if not baseline.get('ok') or not current.get('ok'):
            raise ValueError('font_source_fresh_before_or_current_native_render_failed')
        if not (_pixels(baseline['png'])==_pixels(before_png)==_pixels(current['png'])==_pixels(frozen_png)==_pixels(current_png)):
            raise ValueError('font_source_fresh_before_after_or_frozen_native_pixels_changed')
        observed_signature=signature(observations,'actual_fonts')
        baseline_signature=signature(baseline['native_render']['actual_platform_font_usage'])
        current_signature=signature(current['native_render']['actual_platform_font_usage'],custom=True)
        if not baseline_signature or baseline_signature!=observed_signature or current_signature!=baseline_signature:
            raise ValueError('font_source_fresh_physical_ps_or_glyph_counts_changed')
        if any(identifier not in baseline_signature for identifier in changed):
            raise ValueError('font_source_changed_cell_has_no_fresh_physical_glyph_evidence')
        if native_info is not None and signature(native_info['actual_platform_font_usage'],custom=True)!=current_signature:
            raise ValueError('font_source_caller_fresh_physical_evidence_disagrees')
        # Recheck every proof, source, font and renderer after expensive browser work.
        if any(sha(Path(path).read_bytes())!=digest for path,digest in checks.items()):
            raise ValueError('font_source_evidence_changed_during_validation')
        if sha(Path(__file__).read_bytes())!=IMPLEMENTATION_SHA256:
            raise ValueError('font_source_verifier_module_changed_during_validation')
        work=root/'conversion/native_source_font_profile_v4'/record['id']/record['code_sha256']/uuid.uuid4().hex
        work.mkdir(parents=True,exist_ok=False)
        (work/'before.native.png').write_bytes(baseline['png'])
        (work/'current.native.png').write_bytes(current['png'])
        for name,value in [('before.native.json',baseline['native_render']),('current.native.json',current['native_render'])]:
            (work/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        evidence={'id':record['id'],'source_code_sha256':identity['source_code_sha256'],
                  'source_image_sha256':identity['source_image_sha256'],'normalized_source_sha256':digest,
                  'current_code_sha256':record['code_sha256'],'font_repair_audit':proof['audit'],
                  'changed_cells':sorted(changed),'font_faces':faces,
                  'fresh_physical_ps_glyph_counts':current_signature,
                  'physical_faces_and_glyph_counts_preserved':True,'all_current_actual_glyphs_custom':True,
                  'normalized_original_exactly_equals_frozen_before_xml':True,
                  'font_only_delta_independently_verified':True,'bare_named_styles_and_non_bold_italic_flags_unchanged':True,
                  'fresh_before_after_and_all_frozen_png_pixels_identical':True,
                  'before_native_png_sha256':sha(baseline['png']),'current_native_png_sha256':sha(current['png']),
                  'renderer_module_sha256':renderer_hash,'runtime_manifest_sha256':runtime_hash,
                  'verifier_module_sha256':IMPLEMENTATION_SHA256,
                  'file_checks':{str(Path(path).relative_to(root)):digest for path,digest in checks.items()},
                  'audit':str((work/'proof.json').relative_to(root)),
                  'scope':'Source graph and physically identical portable-font substitution only; fresh full-source, canvas, visual and editability gates remain independent.','accepted':False}
        (work/'proof.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
        result.update(ok=True,evidence=evidence)
    except Exception as exc:
        result['failures']=[{'reason':'native_source_font_only_proof_invalid','type':type(exc).__name__,'error':str(exc)[:2000]}]
    return result
