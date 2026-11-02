"""Revision-owned HTML repair with QA2 missing-object exception admission.

V3 broadens only the selector, retaining the pinned V2 source/paint/font/clip
proposer and all publication gates. Exact terminal V2 revisions are not retried.
The optional verified thin cache avoids repeatedly parsing font-heavy JSON for
stale exceptions; actual claim still compares the complete current snapshot.
Never automatic acceptance.

Default: two workers, watch indefinitely. --limit bounds EACH worker. --publish
is required to publish versioned clean payloads; otherwise only audited proposals
are written and the exact prior job state is restored. Runtime deployment is
separate from importing this module or running its isolated state tests.
"""
import argparse
import collections
import concurrent.futures
import datetime
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import time
import traceback
import uuid
import xml.etree.ElementTree as E
from durable_sqlite import begin, commit

R=Path('/backup/shaoshitong/img2code_20261029')
W=R/'conversion'
STATE='auto_quality_html_source_v3_repairing'
TABLE='auto_quality_html_source_repairs_v3'
PRIOR_TABLE='auto_quality_html_source_repairs_v2'
HISTORY='auto_quality_html_source_repair_history_v3'
IDLE=('rendered','needs_quality_repair','harness_review_pending')
SNAPSHOT_COLUMNS='state,output_record,worker_pid,error,updated_at,input_record,input_manifest'
DEPENDENCIES=('auto_quality_html_repair_batch_v3.py','html_source_repair_v2.py','auto_quality_source_vector_v2.py','html_range_extractor_v2.py','html_dom_clip.js','auto_quality_common.py','native_text_clip.py','native_clip_reference_box.py','native_worker.py','durable_sqlite.py','svg_batch.py','svg_convert_v2.py','harness_context.py')
sha=lambda blob:hashlib.sha256(blob).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path,blob):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+str(os.getpid())+'.htmlqa.tmp')
    tmp.write_bytes(blob);tmp.replace(path)


def implementation():
    directory=Path(__file__).resolve().parent
    paths=[directory/name for name in DEPENDENCIES]
    paths += [R/'scripts/curate_derived.py',R/'scripts/curate_pairs.py',W/'rendering_paintbounds_strict/remote_render.py',W/'rendering_clipbox_strict/remote_render.py',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']
    missing=[str(path) for path in paths if not path.is_file()]
    if missing:raise RuntimeError('Missing pinned repair implementation files: '+repr(missing))
    files={str(path):sha(path.read_bytes()) for path in paths}
    return 'html_wrapped_words_paint_order_candidate_v3:'+sha(json.dumps(files,sort_keys=True).encode())[:20],files


def ensure_implementation(policy,files):
    current,current_files=implementation()
    if (current,current_files)!=(policy,files):raise RuntimeError('Pinned HTML repair implementation changed; deploy a versioned worker')


def exists(db,table):
    return db.execute('select 1 from sqlite_master where type="table" and name=?',(table,)).fetchone() is not None


def init(db):
    begin(db)
    db.execute('create table if not exists '+TABLE+'(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,state TEXT,owner_pid INTEGER,claim_token TEXT,record TEXT,updated_at TEXT,primary key(id,code_hash,image_hash,policy))')
    db.execute('create table if not exists '+HISTORY+'(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,attempt_token TEXT,record TEXT,updated_at TEXT,primary key(id,code_hash,image_hash,policy,attempt_token))')
    commit(db)


def model_running(db,id):
    return exists(db,'harness_queue_v3') and db.execute('select 1 from harness_queue_v3 where id=? and state="running"',(id,)).fetchone() is not None


def snapshot(db,id):
    return db.execute('select '+SNAPSHOT_COLUMNS+' from jobs where id=?',(id,)).fetchone()


# Legacy extractor aliases plus QA2's current proof failures. Admission is not
# acceptance: propose() still requires every added object to be an actually
# measured qaWrappedFragment and rejects extra/nontext/unproven source objects.
EXCEPTION_REASON_SQL="""(e.reason like '%word_spans_multiple_lines%'
 or e.reason like '%overlapping_source_css_paint_order_changed%'
 or (e.reason like '%unsupported_fresh_source_features%' and
     (e.reason like '%css_stacking_order%' or e.reason like '%word_grapheme_range_requires_review%'))
 or e.reason like '%poster_object_coverage_mismatch%'
 or e.reason like '%source_paint_object_missing%')"""


def matches_exception(db,id,code_hash,image_hash):
    if not exists(db,'auto_quality_exceptions_v1'):return False
    sql="""select 1 from auto_quality_exceptions_v1 e where e.id=? and e.code_hash=?
    and e.image_hash=? and e.state='pending' and e.route in
    ('source_geometry_or_harness','source_profile_extension') and """+EXCEPTION_REASON_SQL+' limit 1'
    return db.execute(sql,(id,code_hash,image_hash)).fetchone() is not None


def prior_v2_terminal(db,id,code_hash,image_hash):
    # Helpers and acceptance conditions are unchanged. Repeating a terminal V2
    # attempt on the identical pair would add load without fixing that failure.
    if not exists(db,PRIOR_TABLE):return False
    return db.execute('select 1 from '+PRIOR_TABLE+" where id=? and code_hash=? and image_hash=? and state in ('running','published_candidate','retained_prior_candidate','no_change_required') limit 1",(id,code_hash,image_hash)).fetchone() is not None


def verified_cached_revision(db,id):
    if not exists(db,'auto_quality_inventory_rows_v2') or not exists(db,'auto_quality_dirty_v2'):
        return None
    row=db.execute("""select c.code_hash,c.image_hash from auto_quality_inventory_rows_v2 c
    join auto_quality_dirty_v2 d on d.id=c.id where c.id=? and
    c.seen_version=d.version and c.seen_payload_version=d.payload_version""",(id,)).fetchone()
    return tuple(row) if row else None


def stage_eligible(db,id,code_hash,image_hash,policy,publish):
    # Permit read-only selector inspection before this new worker is deployed.
    if not exists(db,TABLE):return True
    row=db.execute('select state from '+TABLE+' where id=? and code_hash=? and image_hash=? and policy=?',(id,code_hash,image_hash,policy)).fetchone()
    return row is None or row[0]=='deferred_model_running' or publish and row[0]=='validated_dry_run'


def select_candidate(db,policy,publish=False,ids=()):
    if not exists(db,'auto_quality_exceptions_v1'):return None
    model_guard=" and not exists(select 1 from harness_queue_v3 h where h.id=j.id and h.state='running')" if exists(db,'harness_queue_v3') else ''
    identity_guard=' and e.id in ('+','.join('?' for _ in ids)+')' if ids else ''
    # The candidate cursor contains only thin exception metadata and job state.
    # It never selects/JSON-extracts all HTML output_record blobs or sorts them.
    sql="""select distinct e.id,e.code_hash,e.image_hash from auto_quality_exceptions_v1 e
    join jobs j on j.id=e.id where j.format='html' and j.state in
    ('rendered','needs_quality_repair','harness_review_pending') and j.worker_pid is NULL
    and e.state='pending' and e.route in ('source_geometry_or_harness','source_profile_extension')
    and """+EXCEPTION_REASON_SQL+model_guard+identity_guard+' order by e.id,e.code_hash,e.image_hash'
    loaded_id=None;prior=None;record=None
    for id,code_hash,image_hash in db.execute(sql,ids):
        if not stage_eligible(db,id,code_hash,image_hash,policy,publish) or prior_v2_terminal(db,id,code_hash,image_hash):
            continue
        cached=verified_cached_revision(db,id)
        if cached is not None and cached!=(code_hash,image_hash):
            continue
        if loaded_id!=id:
            loaded_id=id;prior=snapshot(db,id)
            if prior is None or prior[0] not in IDLE or prior[2] is not None:
                prior=None;record=None;continue
            try:record=json.loads(prior[1])
            except (TypeError,ValueError):prior=None;record=None;continue
        if prior is None or record.get('source_format')!='html' or record.get('category')!='poster':
            continue
        if (record.get('code_sha256'),record.get('image_sha256'))==(code_hash,image_hash):
            return id,tuple(prior)
    return None


def claim(db,selection,policy,publish=False,pid=None):
    id,prior=selection;pid=pid or os.getpid();old=json.loads(prior[1]);key=(id,old['code_sha256'],old['image_sha256'],policy)
    begin(db)
    try:
        if snapshot(db,id)!=prior or prior[0] not in IDLE or prior[2] is not None or model_running(db,id) or not matches_exception(db,id,*key[1:3]) or not stage_eligible(db,*key,publish) or prior_v2_terminal(db,*key[0:3]):
            db.rollback();return None
        if old.get('source_format')!='html' or old.get('category')!='poster':db.rollback();return None
        previous=db.execute('select record,claim_token from '+TABLE+' where id=? and code_hash=? and image_hash=? and policy=?',key).fetchone()
        if previous:
            db.execute('insert or replace into '+HISTORY+' values(?,?,?,?,?,?,?)',(*key,previous[1] or uuid.uuid4().hex,previous[0],now()))
        token=uuid.uuid4().hex;claimed_at=now();claim_record={'id':id,'key':list(key),'pid':pid,'token':token,'prior_snapshot':list(prior),'claimed_at':claimed_at,'accepted':False}
        db.execute('insert or replace into '+TABLE+' values(?,?,?,?,?,?,?,?,?)',(*key,'running',pid,token,json.dumps(claim_record),claimed_at))
        db.execute('update jobs set state=?,worker_pid=?,updated_at=? where id=?',(STATE,pid,claimed_at,id));commit(db)
        claim_record['owned_snapshot']=[STATE,prior[1],pid,prior[3],claimed_at,prior[5],prior[6]]
        return claim_record
    except Exception:
        db.rollback();raise


def _font_signature(rows):
    result=collections.Counter()
    for font in rows:
        count=int(font.get('glyphCount',0))
        if count:
            name=font.get('postScriptName')
            if not name:raise ValueError('Actual font lacks a physical PostScript identity')
            result[name]+=count
    return dict(sorted(result.items()))


def font_evidence(before,after,old_xml,new_xml,dom,proposal):
    """Current physical faces/counts are recomputed, never inherited by flag alone."""
    old_cells={cell.get('id'):cell for cell in E.fromstring(old_xml).iter('mxCell')}
    new_cells={cell.get('id'):cell for cell in E.fromstring(new_xml).iter('mxCell')}
    old_usage={row['cell']:row.get('fonts',[]) for row in before.get('actual_platform_font_usage',[])}
    new_usage={row['cell']:row.get('fonts',[]) for row in after.get('actual_platform_font_usage',[])}
    all_fonts=[font for fonts in new_usage.values() for font in fonts if font.get('glyphCount',0)]
    if not all_fonts or not all(font.get('isCustomFont') for font in all_fonts):raise ValueError('Actual candidate font glyphs are not all embedded')
    from auto_quality_source_vector_v2 import _plain
    prior_text=[key for key,cell in old_cells.items() if _plain(cell.get('value','')).strip()]
    preserved=[]
    for key in prior_text:
        if not old_usage.get(key) or not new_usage.get(key):raise ValueError('An original text cell lacks actual font evidence: '+str(key))
        a,b=_font_signature(old_usage[key]),_font_signature(new_usage[key])
        if not a or a!=b:raise ValueError('Original cell physical face or glyph count changed: '+str(key))
        preserved.append({'cell':key,'physical_glyph_counts':a})
    source={str(obj['id']+1):obj for obj in dom['objects']}
    actual_text={row['cell']:''.join(char.get('text','') for run in row.get('runs',[]) for char in run.get('chars',[])) for row in after.get('actual_text_positions',[])}
    donors=[]
    for addition in proposal['new_editable_text_fragments']:
        key,donor=addition['cell'],addition['font_donor_cell'];target,original=source[key],source[donor]
        fields=('fontFamilyRaw','bold','italic','underline')
        if any(target.get(field)!=original.get(field) for field in fields):raise ValueError('Added text CSS donor does not match source font style')
        if not target.get('qaWrappedFragment') or actual_text.get(key)!=target['text']:raise ValueError('Added source fragment did not render its exact logical characters')
        from auto_quality_source_vector_v2 import _style
        style=_style(new_cells[key]);donor_style=_style(old_cells[donor])
        if style.get('fontFamily')!=donor_style.get('fontFamily') or style.get('fontStyle','0')!=donor_style.get('fontStyle','0'):raise ValueError('Added text changed the source-style donor physical font stack')
        if abs(float(style['fontSize'])-float(target['fontSize']))>.001:raise ValueError('Added text font size differs from current source CSS')
        names=set(_font_signature(new_usage.get(key,[])));allowed=set(_font_signature(old_usage.get(donor,[])))
        if not names or not names<=allowed:raise ValueError('Added text requires a physical face not proven by its CSS-matched donor')
        donors.append({'cell':key,'donor_cell':donor,'source_css_font_style':{field:target.get(field) for field in fields},'source_font_size':target['fontSize'],'donor_font_size':original['fontSize'],'native_font_stack':style['fontFamily'],'actual_physical_glyph_counts':_font_signature(new_usage[key]),'donor_actual_physical_glyph_counts':_font_signature(old_usage[donor])})
    return {'ok':True,'all_actual_fonts_custom':True,'all_original_cell_physical_faces_and_glyph_counts_preserved':True,'original_text_cell_count':len(prior_text),'original_cells':preserved,'added_fragment_source_css_donors':donors,'actual_custom_glyph_count':sum(int(font['glyphCount']) for font in all_fonts)}


def generate(claim_record,policy,files):
    from PIL import Image
    from native_worker import native
    from html_source_repair_v2 import propose
    import auto_quality_source_vector_v2 as source_profile
    from auto_quality_common import checked,resource_checks,structure_checks,require_rendered_text
    from svg_batch import metric
    ensure_implementation(policy,files)
    id=claim_record['id'];raw=claim_record['prior_snapshot'][1];old=json.loads(raw);digest=old['code_sha256']
    work=W/'auto_quality_html_source_repair_v3'/id/(digest+'_'+old['image_sha256'][:16])/policy.rsplit(':',1)[-1];work.mkdir(parents=True,exist_ok=True)
    xml=checked(R,old['code_file'],digest).decode();old_png=checked(R,old['image_file'],old['image_sha256']);reference=checked(R,old['original_reference'],old['source_image_sha256']);source=checked(R,old['original_source_code'],old['source_code_sha256'])
    atomic(work/'before_record.json',raw.encode());atomic(work/'before.drawio',xml.encode());atomic(work/'before.png',old_png)
    new,proposal=propose(old,xml,work/'proposal_support');new_hash=sha(new.encode())
    if not proposal['new_editable_text_fragments'] and not proposal['paint_order_changed']:
        return work,None,{'id':id,'at':now(),'policy':policy,'state':'no_change_required','accepted':False,'input_code_sha256':digest,'reason':'Current source words and actual browser paint order already match'}
    # Verify all original object bytes/model attributes again outside the helper.
    old_root,new_root=E.fromstring(xml),E.fromstring(new)
    old_model,new_model=old_root.find('.//mxGraphModel'),new_root.find('.//mxGraphModel')
    assert old_model.attrib==new_model.attrib,'Original graph/font-registry attributes changed'
    old_cells={c.get('id'):c for c in old_model.iter('mxCell')};new_cells={c.get('id'):c for c in new_model.iter('mxCell')}
    assert all(E.tostring(cell)==E.tostring(new_cells[key]) for key,cell in old_cells.items()),'Original editable object changed'
    new_record={**old,'code_sha256':new_hash}
    width,height=Image.open(io.BytesIO(reference)).size
    dom,served=source_profile._capture(new_record,source,width,height,'html')
    remaining=[issue for issue in dom['unsupported'] if issue.get('reason')!='css_stacking_order']
    assert not remaining,'Unsupported source features remain: '+repr(remaining[:8])
    coverage=source_profile._html_coverage(dom,new,served);paint=source_profile._html_paint_order(dom,new)
    assert coverage['ok'] and paint['ok'],'Fresh source object/geometry/text/assets/paint coverage failed'
    coverage={**coverage,'source_css_paint_order':paint,'wrapped_word_range_proofs':dom.get('qaWrappedWords',[]),'ok':True}
    structure=structure_checks(new);resources=resource_checks(R,new_record,new,reference)
    renderer=W/'rendering_paintbounds_strict/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
    page_width,page_height=[int(round(float(old_model.get(key,0)))) for key in ('pageWidth','pageHeight')]
    assert 0<page_width<=8192 and 0<page_height<=8192,'Unsupported native canvas'
    baseline=native.native_job(xml,page_width,page_height,180,renderer,8192,runtime)
    fresh=native.native_job(new,page_width,page_height,180,renderer,8192,runtime)
    assert baseline['ok'] and fresh['ok'],'Actual strict native rendering failed'
    before_info,after_info=baseline['native_render'],fresh['native_render']
    require_rendered_text(new,after_info)
    fonts=font_evidence(before_info,after_info,xml,new,dom,proposal)
    before_score,after_score=metric(reference,baseline['png']),metric(reference,fresh['png'])
    assert after_score>=before_score-.02,'Original-reference metric regressed more than .02 under the same strict renderer'
    native_hash=sha(fresh['png']);pending_canvas=after_info.get('selected_image')!='declared_first_page' or after_info.get('content_outside_declared_canvas') or (after_info.get('outside_page_pixel_audit') or {}).get('nonwhite_outside_pixels',0)>0
    proof={'id':id,'at':now(),'policy':policy,'implementation':files,'input_code_sha256':digest,'input_image_sha256':old['image_sha256'],'output_code_sha256':new_hash,'output_image_sha256':native_hash,'source_code_sha256':old['source_code_sha256'],'source_image_sha256':old['source_image_sha256'],'source_coverage':coverage,'structure':structure,'resources':resources,'font_evidence':fonts,'proposal':proposal,'same_strict_renderer_fidelity':{'renderer_sha256':sha(renderer.read_bytes()),'original_reference_ssim_before':before_score,'original_reference_ssim_after':after_score,'maximum_allowed_regression':.02,'passed':True},'baseline_canvas':{'selected_image':before_info.get('selected_image'),'output_size':before_info.get('output_size'),'outside_page_pixel_audit':before_info.get('outside_page_pixel_audit')},'candidate_canvas':{'selected_image':after_info.get('selected_image'),'output_size':after_info.get('output_size'),'outside_page_pixel_audit':after_info.get('outside_page_pixel_audit')},'requires_canvas_repair':bool(pending_canvas),'candidate_checks_passed':True,'accepted':False,'audit':str((work/'report.json').relative_to(R))}
    evidence_blob=(json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    atomic(work/'evidence.json',evidence_blob)
    source_dom_blob=json.dumps(dom,sort_keys=True).encode()
    atomic(work/'source_dom.json',source_dom_blob)
    parent=(R/old['code_file']).parent
    target_code=parent/('diagram.html-source-v3.'+new_hash[:24]+'.drawio')
    target_png=parent/('image.html-source-v3.'+new_hash[:24]+'.'+native_hash[:16]+'.png')
    archive=W/'harness_sessions'/('html_source_v3_'+id+'_'+digest+'_'+old['image_sha256'][:16])/'baseline'
    font_proof={'ok':True,'method':'original_native_physical_faces_glyph_counts_and_css_matched_donor_fonts_v2','output_code_sha256':new_hash,'base_verified_code_sha256':digest,'input_image_sha256':old['image_sha256'],'output_image_sha256':native_hash,'all_actual_fonts_custom':True,'all_original_cell_physical_faces_and_glyph_counts_preserved':True,'original_text_cell_count':fonts['original_text_cell_count'],'added_fragment_source_css_donors':fonts['added_fragment_source_css_donors'],'audit':proof['audit'],'policy':policy,'evidence_file':str((work/'evidence.json').relative_to(R)),'evidence_sha256':sha(evidence_blob)}
    source_proof={'ok':True,'policy':policy,'input_code_sha256':digest,'output_code_sha256':new_hash,'output_image_sha256':native_hash,'source_code_sha256':old['source_code_sha256'],'source_image_sha256':old['source_image_sha256'],'source_dom_file':str((work/'source_dom.json').relative_to(R)),'source_dom_sha256':sha(source_dom_blob),'evidence_file':str((work/'evidence.json').relative_to(R)),'evidence_sha256':sha(evidence_blob),'source_coverage':coverage,'added_text_fragments':len(proposal['new_editable_text_fragments']),'paint_order_changed':proposal['paint_order_changed'],'requires_canvas_repair':bool(pending_canvas),'audit':proof['audit'],'accepted':False}
    out={**old,'code_file':str(target_code.relative_to(R)),'code_sha256':new_hash,'image_file':str(target_png.relative_to(R)),'image_sha256':native_hash,'render':after_info,'source_coverage':coverage,'native_font_validation':font_proof,'html_source_repair_v2':source_proof,'conversion_method':old.get('conversion_method','unknown')+'_wrapped_words_and_browser_paint_order_v2','previous_candidate_archive':str(archive.relative_to(R)),'quality_state':'pending_deterministic_canvas_repair_and_automatic_quality_recheck' if pending_canvas else 'pending_automatic_quality_v2_recheck','converted_at_utc':now(),'metrics':{**old.get('metrics',{}),'original_reference_ssim_512':after_score,'html_source_v2_same_renderer_reference_ssim_before':before_score},'last_repair':{'method':'deterministic_html_source_v2','model':None,'policy':policy}}
    for key in ('accepted_at_utc','automatic_quality_policy','automatic_quality_audit'):
        out.pop(key,None)
    atomic(work/'baseline.strict.png',baseline['png']);atomic(work/'baseline.strict_render.json',(json.dumps(before_info,indent=2)+'\n').encode());atomic(work/'candidate.drawio',new.encode());atomic(work/'candidate.png',fresh['png']);atomic(work/'candidate.strict_render.json',(json.dumps(after_info,indent=2)+'\n').encode());atomic(work/'candidate_record.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode());atomic(work/'report.json',(json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode())
    ensure_implementation(policy,files)
    return work,out,proof


def _checked(path,digest):
    data=Path(path).read_bytes()
    if sha(data)!=digest:raise ValueError('Publication payload hash mismatch: '+str(path))
    return data


def recheck_resource_files(record):
    """Recheck preserved clean dependencies immediately before pointer publication."""
    expected=[]
    for key,digest in [('source_render_svg','source_render_svg_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_png','source_render_png_sha256'),('original_source_data','source_data_sha256')]:
        if record.get(key):expected.append((record[key],record[digest]))
    for asset in record.get('original_vector_assets') or []:
        expected.append((asset['file'],asset['sha256']))
    for asset in record.get('source_assets') or []:
        for key,digest in [('source','source_sha256'),('file','embedded_sha256'),('original_file','original_sha256')]:
            if asset.get(key) and asset.get(digest) and asset[key]!='embedded_original_html_asset':expected.append((asset[key],asset[digest]))
    for font in (record.get('native_embedded_fonts') or [])+(record.get('fonts') or []):
        if font.get('file'):expected.append((font['file'],font['sha256']))
        if font.get('original_file') and font.get('original_sha256'):expected.append((font['original_file'],font['original_sha256']))
    for relative,digest in expected:
        path=(R/relative).resolve()
        assert path.is_relative_to((R/'clean').resolve()),'Preserved dependency moved outside clean'
        _checked(path,digest)
    return len(expected)


def publish_artifacts(claim_record,out,proof,work):
    old=json.loads(claim_record['prior_snapshot'][1])
    assert proof.get('candidate_checks_passed') is True and not proof.get('accepted'),'Only verified non-accepted candidates may publish'
    assert proof['policy']==claim_record['key'][3]
    for key in ('id','source_code_sha256','source_image_sha256','source_pair_sha256'):
        if key in old:assert out.get(key)==old[key],'Original source identity changed'
    assert proof['output_code_sha256']==out['code_sha256'] and proof['output_image_sha256']==out['image_sha256']
    assert out['source_coverage']['ok'] is True and out['native_font_validation']['output_code_sha256']==out['code_sha256']
    assert out['quality_state'].startswith('pending_'),'A repair candidate cannot be accepted'
    for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
        path=(R/old[key]).resolve();assert path.is_relative_to((R/'clean').resolve());_checked(path,old[digest])
    recheck_resource_files(out)
    for proof_key in ('native_font_validation','html_source_repair_v2'):
        source_proof=out.get(proof_key,{})
        if source_proof.get('evidence_file'):
            path=(R/source_proof['evidence_file']).resolve();assert path.is_relative_to(W.resolve()),'Repair evidence outside owned conversion workspace';_checked(path,source_proof['evidence_sha256'])
    new_xml=_checked(work/'candidate.drawio',out['code_sha256']);new_png=_checked(work/'candidate.png',out['image_sha256'])
    assert json.loads((work/'candidate_record.json').read_text())==out
    archive=R/out['previous_candidate_archive'];archive.mkdir(parents=True,exist_ok=True)
    for name,data in [('conversion.json',claim_record['prior_snapshot'][1].encode()),('diagram.drawio',_checked(R/old['code_file'],old['code_sha256'])),('image.png',_checked(R/old['image_file'],old['image_sha256']))]:
        path=archive/name
        if path.exists():assert path.read_bytes()==data,'Immutable prior-pair archive differs'
        else:atomic(path,data)
    for key,data in [('code_file',new_xml),('image_file',new_png)]:
        target=(R/out[key]).resolve();assert target.is_relative_to((R/'clean').resolve()) and out[key]!=old[key],'Repair payload must use a new clean versioned path'
        if target.exists():assert target.read_bytes()==data,'Immutable versioned target has different bytes'
        else:atomic(target,data)
    intent={'id':claim_record['id'],'token':claim_record['token'],'policy':proof['policy'],'old_record_sha256':sha(claim_record['prior_snapshot'][1].encode()),'new_record_sha256':sha(json.dumps(out,ensure_ascii=False).encode()),'out':out,'accepted':False}
    atomic(work/'publish_intent.json',(json.dumps(intent,ensure_ascii=False,indent=2)+'\n').encode())
    atomic((R/old['code_file']).parent/'conversion.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())


def hold_idle_model(db,id):
    if not exists(db,'harness_queue_v3'):return
    assert not model_running(db,id),'Never overwrite a running paid model call'
    db.execute("insert or ignore into harness_queue_v3(id,state,attempts,priority) values(?,'held_for_quality_v2',0,1000)",(id,))
    db.execute("update harness_queue_v3 set state='held_for_quality_v2',worker_pid=NULL,heartbeat=? where id=? and state!='running'",(now(),id))


def finish(db,claim_record,report,out=None,work=None,publish=False,artifact_writer=publish_artifacts):
    id=claim_record['id'];key=tuple(claim_record['key']);prior=tuple(claim_record['prior_snapshot']);owned=tuple(claim_record['owned_snapshot']);published=False
    begin(db)
    try:
        table_owner=db.execute('select state,owner_pid,claim_token from '+TABLE+' where id=? and code_hash=? and image_hash=? and policy=?',key).fetchone()
        if table_owner!=('running',claim_record['pid'],claim_record['token']) or snapshot(db,id)!=owned:
            report.update(state='stale_revision_or_ownership',accepted=False);out=None
        elif model_running(db,id):
            report.update(state='deferred_model_running',accepted=False);out=None
            db.execute('update jobs set state=?,worker_pid=NULL,error=?,updated_at=? where id=?',(prior[0],prior[3],now(),id))
        elif out is not None and publish:
            artifact_writer(claim_record,out,report,work)
            db.execute('update jobs set state="needs_quality_repair",output_record=?,worker_pid=NULL,error=?,updated_at=? where id=?',(json.dumps(out,ensure_ascii=False),'Deterministic HTML source repair candidate; strict QA v2 recheck required'+('; canvas repair required' if report.get('requires_canvas_repair') else ''),now(),id))
            hold_idle_model(db,id);published=True;report.update(state='published_candidate',accepted=False)
        else:
            stage='validated_dry_run' if out is not None else report.get('state','retained_prior_candidate')
            if stage not in ('validated_dry_run','no_change_required'):stage='retained_prior_candidate'
            report.update(state=stage,accepted=False)
            db.execute('update jobs set state=?,worker_pid=NULL,error=?,updated_at=? where id=?',(prior[0],prior[3],now(),id))
        # A stolen/replaced audit-table claim belongs to its new owner and must not be changed.
        if table_owner==('running',claim_record['pid'],claim_record['token']):
            db.execute('update '+TABLE+' set state=?,record=?,updated_at=? where id=? and code_hash=? and image_hash=? and policy=?',(report['state'],json.dumps(report,ensure_ascii=False),now(),*key))
        commit(db)
    except Exception:
        db.rollback()
        # An interrupted FS/SQL boundary can leave only the metadata pointer new;
        # restore it only while we still own this exact prior database revision.
        if snapshot(db,id)==owned:
            old=json.loads(prior[1]);pointer=(R/old['code_file']).parent/'conversion.json'
            if out is not None and pointer.exists():
                try:
                    if json.loads(pointer.read_text())==out:atomic(pointer,prior[1].encode())
                except (OSError,ValueError):pass
        raise
    if work is not None:
        try:
            atomic(Path(work)/'report.json',(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
            if published:atomic(Path(work)/'committed.json',(json.dumps({'at':now(),'code_sha256':out['code_sha256'],'image_sha256':out['image_sha256'],'accepted':False})+'\n').encode())
        except OSError as error:
            # SQL already contains the complete audit report. Never undo a committed
            # candidate merely because the duplicate filesystem receipt failed.
            print(json.dumps({'at':now(),'id':id,'stage':'audit_receipt_write_failed','committed_state':report['state'],'error':repr(error),'audit_saved_in_table':TABLE}),flush=True)
    return report['state']


def worker(index,limit,publish,ids,policy,files):
    db=sqlite3.connect(W/'jobs.sqlite',timeout=2);processed=0;counts=collections.Counter()
    while not limit or processed<limit:
        ensure_implementation(policy,files)
        selection=select_candidate(db,policy,publish,ids)
        if selection is None:
            if limit:break
            time.sleep(15);continue
        current=claim(db,selection,policy,publish)
        if current is None:continue
        started=time.monotonic();out=None;work=None
        try:work,out,report=generate(current,policy,files)
        except Exception as error:
            report={'id':current['id'],'at':now(),'policy':policy,'input_code_sha256':current['key'][1],'input_image_sha256':current['key'][2],'state':'retained_prior_candidate','error':repr(error)[:3000],'accepted':False,'previous_candidate_retained':True}
            work=W/'auto_quality_html_source_repair_v3'/current['id']/(current['key'][1]+'_'+current['key'][2][:16])/policy.rsplit(':',1)[-1];work.mkdir(parents=True,exist_ok=True);atomic(work/'traceback.txt',traceback.format_exc().encode())
        report['seconds']=round(time.monotonic()-started,3)
        try:
            ensure_implementation(policy,files)
            stage=finish(db,current,report,out,work,publish)
        except Exception as error:
            # Keep a fully diagnosed failed revision rather than silently wedging
            # an otherwise-owned job after a reversible publication I/O failure.
            failure={**report,'state':'retained_prior_candidate','error':'Publication failed: '+repr(error),'accepted':False,'previous_candidate_retained':True}
            try:stage=finish(db,current,failure,None,work,False)
            except Exception:
                atomic(work/'owned_job_requires_recovery.json',(json.dumps({'id':current['id'],'pid':os.getpid(),'claim':current,'error':traceback.format_exc(),'accepted':False},indent=2)+'\n').encode());raise
        processed+=1;counts[stage]+=1
        print(json.dumps({'at':now(),'worker':index,'id':current['id'],'stage':stage,'seconds':report['seconds'],'error':report.get('error'),'accepted':False}),flush=True)
    db.close();return {'worker':index,'processed':processed,'counts':dict(counts),'accepted':0}


def main(args):
    from native_worker import R as runtime_root,W as runtime_work
    assert (R,W)==(runtime_root,runtime_work),'Remote runtime root differs'
    lock=(W/'auto_quality_html_source_repair_v3.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    policy,files=implementation();db=sqlite3.connect(W/'jobs.sqlite',timeout=2);init(db);db.close()
    owner={'pid':os.getpid(),'workers':args.workers,'limit_per_worker':args.limit,'publish':args.publish,'at':now(),'policy':policy,'implementation':files,'accepted':0}
    atomic(W/'auto_quality_html_repair_v3_owner.json',(json.dumps(owner,indent=2)+'\n').encode())
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(worker,index,args.limit,args.publish,args.ids,policy,files) for index in range(args.workers)]
        results=[future.result() for future in futures]
    summary={'at':now(),'policy':policy,'workers':results,'accepted':0,'goal_complete':False}
    atomic(W/'auto_quality_html_repair_v3_summary.json',(json.dumps(summary,indent=2)+'\n').encode());print(json.dumps(summary),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=2);parser.add_argument('--limit',type=int,default=0);parser.add_argument('--publish',action='store_true');parser.add_argument('--id',dest='ids',action='append',default=[]);arguments=parser.parse_args()
    if not 1<=arguments.workers<=16 or arguments.limit<0:parser.error('workers must be 1..16 and limit must be >=0')
    main(arguments)
