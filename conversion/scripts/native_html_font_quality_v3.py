"""Independent HTML font-revision QA, never source/reference acceptance.

The caller passes the frozen font revision itself. Later canvas/glyph/layout
successors must independently replay their complete lineage and full source,
original-reference, clipping, rendering and editing gates afterward.
"""
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import uuid
import xml.etree.ElementTree as E

R=Path('/backup/shaoshitong/img2code_20261029')
SCHEMA='independent_html_observed_font_delta_v3'
PRODUCER_SCHEMA='native_html_observed_font_delta_v3'
ORDER_SCHEMA='original_CSS_grapheme_physical_fallback_precedence_v3'
LOADED_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'


def sha(blob):return hashlib.sha256(blob).hexdigest()
def require(ok,reason):
    if not ok:raise ValueError(reason)


def _counts(fonts, custom=None):
    result={}
    for font in fonts:
        count=font.get('glyphCount')
        require(type(count) is int and count>=0,'html_font_invalid_glyph_count')
        if not count:continue
        require(bool(font.get('postScriptName')),'html_font_missing_physical_face')
        if custom is not None:require(font.get('isCustomFont') is custom,'html_font_unexpected_font_origin')
        name=font['postScriptName'];result[name]=result.get(name,0)+count
    return result


class _IndependentCssProbe:
    """Fresh CSS/grapheme probes; does not import the producer's probe helper."""
    def __init__(self,browser):
        self.page=browser.new_page();self.page.route('**/*',lambda request:request.abort())
        self.page.set_content('<html><body><span id="independent-font-probe"></span></body></html>')
        self.cdp=self.page.context.new_cdp_session(self.page)
        self.cdp.send('DOM.enable');self.cdp.send('CSS.enable');self.cache={}
    def close(self):
        self.cdp.detach();self.page.close()
    def graphemes(self,text):
        return self.page.evaluate('s=>Array.from(new Intl.Segmenter(undefined,{granularity:"grapheme"}).segment(s),g=>g.segment)',text)
    def fonts(self,family,flags,size,text):
        key=(family,flags,size,text)
        if key not in self.cache:
            self.page.evaluate('''async a=>{const s=document.querySelector('#independent-font-probe');s.textContent=a.text;s.style.cssText='';s.style.fontFamily=a.family;s.style.fontSize=a.size+'px';s.style.fontWeight=(a.flags&1)?'bold':'normal';s.style.fontStyle=(a.flags&2)?'italic':'normal';s.style.whiteSpace='pre';await document.fonts.ready;s.getBoundingClientRect();}''',{'family':family,'flags':flags,'size':size,'text':text})
            root=self.cdp.send('DOM.getDocument',{'depth':1})['root']['nodeId']
            node=self.cdp.send('DOM.querySelector',{'nodeId':root,'selector':'#independent-font-probe'})['nodeId']
            self.cache[key]=self.cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
        return self.cache[key]


def verify_changes(before,xml,details,observations,faces,probe,cmaps):
    """Pure replay once fresh original observations, SFNT faces and probe exist."""
    from native_source_font_profile_v4 import _models,_cells,canonical_font_only,style_values,_font_blob,_ext
    from html_actual_text_alignment import _plain
    changes=details.get('changes')
    require(isinstance(changes,list) and changes and not details.get('issues'),'html_font_invalid_change_details')
    changed={c['cell'] for c in changes};require(len(changed)==len(changes),'html_font_duplicate_changed_cell')
    require(canonical_font_only(before,changed)==canonical_font_only(xml,changed),'html_font_nonfont_graph_or_markup_changed')
    oldcells=_cells(_models(before)[0]);cells=_cells(_models(xml)[0])
    rows={r['cell']:r for r in observations};require(len(rows)==len(observations),'html_font_duplicate_original_observation')
    whole_graph=set()
    for row in observations:
        flags=int(row['style'].get('fontStyle',0))
        for f in row.get('actual_fonts',[]):
            if f.get('glyphCount',0)>0 and f.get('isCustomFont') is False:whole_graph.add((f['postScriptName'],flags))
    primary_checks=[];order_checks=[]
    for change in changes:
        cid=change['cell'];require(cid in rows and cid in cells and cid in oldcells,'html_font_unknown_changed_cell')
        row=rows[cid];current=style_values(cells[cid]);old=style_values(oldcells[cid])
        actual=_counts(row['actual_fonts'],False);require(actual,'html_font_changed_cell_has_no_original_system_glyphs')
        require(_counts(change.get('actual_fonts',[]),False)==actual,'html_font_change_original_physical_inventory_changed')
        flags=change.get('before_flags');after=change.get('after_flags')
        require(type(flags) is int and type(after) is int and flags>=0 and after>=0,'html_font_invalid_style_flags')
        require(flags==int(row['style'].get('fontStyle',0)) and after==int(current.get('fontStyle',0)),'html_font_observed_style_flags_changed')
        family=str(row['style'].get('fontFamily','Arial'));size=float(row['style'].get('fontSize',12))
        require(change.get('before_family')==row['style'].get('fontFamily'),'html_font_observed_original_family_changed')
        require(0<size<=8192,'html_font_unsupported_probe_size')
        families=current.get('fontFamily','').split(',')
        require(families==change.get('families') and len(set(families))==len(families) and all(f in faces for f in families),'html_font_unverified_family_stack')
        selected=[faces[f] for f in families];postscript=[f['postscript'] for f in selected]
        require(len(set(postscript))==len(postscript),'html_font_duplicate_physical_stack_face')
        require(len({(f['bold'],f['italic']) for f in selected})==1,'html_font_mixed_physical_styles_require_independent_runs')
        expected=flags & ~(1 if selected[0]['bold'] else 0) & ~(2 if selected[0]['italic'] else 0)
        require(after==expected,'html_font_synthetic_style_not_absorbed_by_physical_face')
        if 'fontStyle' in old:require((int(old['fontStyle'])&~3)==(flags&~3),'html_font_nonfont_text_flags_changed')
        extra=set(postscript)-set(actual);strut=change.get('primary_strut')
        if strut is not None:
            require(isinstance(strut,dict) and set(strut)=={'postscript','family','basis'} and strut['basis']=='same_original_graph_observed_requested_primary_face','html_font_invalid_primary_strut_proof')
            primary=_counts(probe.fonts(family,flags,size,'M'),False)
            require(len(primary)==1 and strut['postscript']==next(iter(primary)),'html_font_requested_primary_not_reproduced_by_fresh_M')
            require((strut['postscript'],flags) in whole_graph,'html_font_primary_not_observed_in_same_original_graph')
            require(strut['family'] in faces and faces[strut['family']]['postscript']==strut['postscript'],'html_font_primary_asset_mismatch')
            require(families[0]==strut['family'],'html_font_claimed_primary_strut_is_not_first')
            require(extra<=set(primary),'html_font_unobserved_extra_stack_face')
            primary_checks.append({'cell':cid,'postscript':strut['postscript'],'fresh_M_probe':primary,'same_graph_original_flags':flags})
        else:require(not extra,'html_font_extra_stack_face_without_primary_proof')
        require(set(postscript)==set(actual)|extra,'html_font_original_physical_face_removed')
        require(set(actual)<=set(postscript),'html_font_original_physical_face_removed')
        if current.get('fontSource'):
            require(len(families)==1 and _font_blob(current['fontSource'])==_font_blob(_ext(_models(xml)[1])[families[0]]),'html_font_cell_source_mismatch')
        declared=change.get('physical_fallback_precedence')
        require(isinstance(declared,dict) and declared.get('schema')==ORDER_SCHEMA,'html_font_missing_grapheme_precedence_proof')
        digest=declared.get('sha256');body={k:v for k,v in declared.items() if k!='sha256'}
        require(digest==sha(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()),'html_font_precedence_proof_hash_mismatch')
        require((declared.get('family'),declared.get('flags'),declared.get('size'))==(family,flags,size),'html_font_precedence_original_css_mismatch')
        require(declared.get('no_target_image_score_used') is True,'html_font_precedence_score_fitting_not_allowed')
        constraints=set();observed=[]
        for text in sorted(set(probe.graphemes(_plain(row['label'])))):
            if text.isspace():continue
            chars=set(map(ord,text));covering=[name for name in actual if chars<=cmaps[name]]
            if len(covering)==1:
                wanted=covering[0];livefonts=[];basis='unique_original_observed_cmap_face'
            else:
                livefonts=probe.fonts(family,flags,size,text);live=_counts(livefonts,False)
                require(len(live)==1 and set(live)<=set(actual),'html_font_ambiguous_or_context_sensitive_grapheme')
                wanted=next(iter(live));basis='isolated_original_CSS_physical_font_probe'
            require(chars<=cmaps[wanted],'html_font_original_grapheme_not_in_verified_cmap')
            observed.append({'text':text,'fonts':livefonts,'wanted_postscript':wanted,'basis':basis})
            for other in postscript:
                if other!=wanted and chars<=cmaps[other]:constraints.add((wanted,other))
        supplied=declared.get('observations')
        require(isinstance(supplied,list) and [r.get('text') for r in supplied]==[r['text'] for r in observed],'html_font_grapheme_membership_changed')
        for stored,live in zip(supplied,observed):
            require(stored.get('wanted_postscript')==live['wanted_postscript'] and stored.get('basis')==live['basis'],'html_font_grapheme_wanted_or_inventory_basis_changed')
            require(_counts(stored['fonts'],False)==_counts(live['fonts'],False),'html_font_grapheme_physical_face_or_count_changed')
        require(declared.get('constraints')==[list(pair) for pair in sorted(constraints)],'html_font_precedence_constraints_changed')
        require(declared.get('ordered_postscript')==postscript,'html_font_precedence_order_differs_from_actual_stack')
        positions={name:i for i,name in enumerate(postscript)}
        require(all(positions[a]<positions[b] for a,b in constraints),'html_font_stack_violates_original_grapheme_precedence')
        order_checks.append({'cell':cid,'grapheme_count':len(observed),'constraints':len(constraints),'ordered_postscript':postscript})
    return {'changed_cells':sorted(changed),'primary_strut_checks':primary_checks,'grapheme_order_checks':order_checks}


def verify(record,work=None):
    """Independently verify the frozen HTML font revision; no qualification."""
    result={'ok':False,'schema':SCHEMA,'accepted':False,'model_calls':0,'canonical_db_written':False}
    checks={}
    def read(path,owner=None):
        path=Path(path).resolve(strict=True);require(path.is_relative_to(Path(owner or R).resolve()),'html_font_unowned_evidence')
        blob=path.read_bytes();checks[str(path)]=sha(blob);return blob
    def clean(locator,digest):
        path=(R/locator).resolve(strict=True);blob=read(path,R/'clean');require(sha(blob)==digest,'html_font_clean_payload_hash_changed');return blob
    try:
        if isinstance(record,(str,Path)):
            record_path=Path(record).resolve(strict=True)
            record=json.loads(read(record_path,R/'conversion'))
        require(sha(Path(__file__).read_bytes())==LOADED_SHA,'html_font_verifier_changed_after_import')
        require(record.get('source_format')=='html' and record.get('format')=='drawio','html_font_only_html_native_revisions_supported')
        require(re.fullmatch(r'[0-9a-f]{64}',str(record.get('id',''))) and record['id']==record.get('source_pair_sha256'),'html_font_invalid_original_pair_identity')
        proof=record.get('round2_font_repair');require(isinstance(proof,dict) and proof.get('ok') is True and proof.get('accepted') is False,'html_font_missing_unaccepted_font_revision')
        require(proof.get('version')=='observed_physical_font_only_round2_v1','html_font_wrong_proof_version')
        require(proof.get('output_code_sha256')==record.get('code_sha256') and proof.get('output_image_sha256')==record.get('image_sha256'),'html_font_pass_frozen_font_revision_not_later_successor')
        for k in ('source_code_sha256','source_image_sha256'):require(proof.get(k)==record.get(k),'html_font_source_identity_mismatch')
        owner=R/'conversion/auto_quality_font_repair_v1/round2_v1'/record['id'];audit=(R/proof['audit']).resolve(strict=True)
        require(audit.is_relative_to(owner.resolve()) and audit.name=='report.json','html_font_unowned_proof')
        require(json.loads(read(audit,owner))==proof,'html_font_frozen_proof_changed');folder=audit.parent
        before=read(folder/'before.drawio',folder).decode();xml=read(folder/'candidate.drawio',folder).decode()
        previous=json.loads(read(folder/'before_record.json',folder));frozen=json.loads(read(folder/'candidate_record.json',folder))
        details=json.loads(read(folder/'font_details.json',folder));stored=json.loads(read(folder/'observations.json',folder))
        require(frozen==record,'html_font_frozen_candidate_record_changed')
        for obj in [previous,frozen]:require(all(obj.get(k)==record.get(k) for k in ('id','source_pair_sha256','source_code_sha256','source_image_sha256','source_format','category','source','original_source_code','original_reference')),'html_font_original_identity_or_paths_changed')
        require(sha(before.encode())==proof['input_code_sha256']==previous['code_sha256'] and sha(xml.encode())==record['code_sha256'],'html_font_frozen_revision_hash_changed')
        require(sha(read(folder/'before.png',folder))==proof['input_image_sha256']==previous['image_sha256'],'html_font_frozen_baseline_png_changed')
        clean(previous['code_file'],previous['code_sha256']);clean(previous['image_file'],previous['image_sha256'])
        require(clean(record['code_file'],record['code_sha256']).decode()==xml,'html_font_current_code_differs_from_frozen')
        currentpng=clean(record['image_file'],record['image_sha256']);require(read(folder/'candidate.png',folder)==currentpng,'html_font_frozen_current_png_changed')
        clean(record['original_source_code'],record['source_code_sha256']);clean(record['original_reference'],record['source_image_sha256'])
        compiler=proof.get('font_compiler');require(isinstance(compiler,dict) and compiler.get('schema')==PRODUCER_SCHEMA,'html_font_missing_new_compiler_proof')
        producer_path=(R/compiler.get('file','')).resolve();require(producer_path==R/'conversion/scripts/native_html_font_compiler_v3.py','html_font_unowned_compiler')
        producer=read(producer_path,R/'conversion/scripts');require(sha(producer)==compiler.get('sha256'),'html_font_compiler_hash_changed')
        constants={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(producer).body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='COMPILER_VERSION'}
        require(compiler.get('version')==details.get('compiler_version')==constants.get('COMPILER_VERSION'),'html_font_compiler_version_mismatch')
        pins=compiler.get('pins');require(isinstance(pins,dict) and pins,'html_font_missing_compiler_pins')
        required=[R/'conversion/scripts'/n for n in ('native_html_font_compiler_v3.py','native_font_order_probe_v3.py','portable_native_fonts.py','auto_quality_font_repair.py')]+[R/'conversion/rendering_paintbounds_strict/remote_render.py',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']
        normalized_pins={str((R/p).resolve()):h for p,h in pins.items()}
        require(all(str(p.resolve()) in normalized_pins for p in required),'html_font_incomplete_compiler_pin_set')
        for path,digest in normalized_pins.items():require(sha(read(path))==digest,'html_font_compiler_dependency_changed')
        from native_source_font_profile_v4 import verify_assets,_models,_pixels,signature
        from native_worker import native
        from portable_native_fonts import capture,ready_page
        from playwright.sync_api import sync_playwright
        from fontTools.ttLib import TTFont
        faces=verify_assets(R,record,_models(before)[1],_models(xml)[1],checks)
        cmaps={}
        for f in faces.values():
            ft=TTFont(io.BytesIO(read(R/f['file'],R/'clean')))
            try:cmaps[f['postscript']]=set(ft.getBestCmap() or {})
            finally:ft.close()
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
            try:
                observations=capture(ready_page(browser),before)
                require(signature(observations,'actual_fonts')==signature(stored,'actual_fonts'),'html_font_fresh_original_glyph_signature_changed')
                original={r['cell']:r for r in observations};require(len(original)==len(observations) and set(original)=={r['cell'] for r in stored},'html_font_original_text_membership_changed')
                for r in stored:
                    live=original[r['cell']];require(r['label']==live['label'],'html_font_original_label_observation_changed')
                    require(all(r['style'].get(k)==live['style'].get(k) for k in ('fontFamily','fontStyle','fontSize')),'html_font_original_css_observation_changed')
                probe=_IndependentCssProbe(browser)
                try:delta=verify_changes(before,xml,details,observations,faces,probe,cmaps)
                finally:probe.close()
            finally:browser.close()
        model=_models(xml)[1];size=[int(round(float(model.get(k,0)))) for k in ('pageWidth','pageHeight')]
        require(all(0<s<=8192 for s in size),'html_font_unsupported_page')
        renderer=R/'conversion/rendering_paintbounds_strict/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
        baseline=native.native_job(before,*size,180,renderer,8192,runtime);fresh=native.native_job(xml,*size,180,renderer,8192,runtime)
        require(baseline.get('ok') is True and fresh.get('ok') is True,'html_font_fresh_native_render_failed')
        require(_pixels(baseline['png'])==_pixels(fresh['png'])==_pixels(currentpng),'html_font_fresh_before_after_pixels_changed')
        old=signature(baseline['native_render']['actual_platform_font_usage']);new=signature(fresh['native_render']['actual_platform_font_usage'],custom=True)
        require(old and old==new==signature(observations,'actual_fonts'),'html_font_fresh_physical_faces_or_glyph_counts_changed')
        require(all(sha(Path(path).read_bytes())==digest for path,digest in checks.items()),'html_font_evidence_changed_during_verification')
        result.update(ok=True,evidence={**delta,'source_pair_sha256':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'font_revision_code_sha256':record['code_sha256'],'font_revision_png_sha256':record['image_sha256'],'font_asset_count':len(faces),'complete_original_graph_text_nonfont_styles_unchanged':True,'fresh_original_graph_observed_faces':True,'fresh_grapheme_physical_fallback_constraints_recomputed':True,'fresh_before_after_and_stored_png_pixels_exact':True,'fresh_physical_ps_and_glyph_counts_exact':True,'all_fresh_current_glyphs_custom':True,'compiler':compiler,'verifier_sha256':LOADED_SHA,'evidence_checks':checks,'scope':'Font revision only; complete source, current successor lineage, original-reference fidelity, clipping, actual native rendering and editing remain mandatory.'})
    except Exception as exc:result.update(reason=str(exc),exception_type=type(exc).__name__)
    # All proof renders remain remote in a dedicated immutable report folder.
    # Pure unit tests with no attached data root perform no filesystem writes.
    if (R/'conversion').is_dir():
        try:
            if work is None:out=R/'conversion/independent_html_font_quality_v3'/str(record.get('id','unsupported'))/uuid.uuid4().hex
            else:
                base=Path(work).resolve();require(base.is_relative_to((R/'conversion').resolve()),'html_font_quality_work_outside_conversion');out=base/uuid.uuid4().hex
            out.mkdir(parents=True,exist_ok=False)
            for name,obj in [('baseline.png',locals().get('baseline',{}).get('png')),('current.png',locals().get('fresh',{}).get('png'))]:
                if isinstance(obj,bytes):(out/name).write_bytes(obj)
            for name,obj in [('original_observations.json',locals().get('observations')),('baseline.native_info.json',locals().get('baseline',{}).get('native_render')),('current.native_info.json',locals().get('fresh',{}).get('native_render'))]:
                if obj is not None:(out/name).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
            result['report_file']=str(out/'report.json')
            payload=(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode();(out/'report.json').write_bytes(payload);result['report_sha256']=sha(payload)
        except Exception as exc:result={'ok':False,'schema':SCHEMA,'accepted':False,'reason':'html_font_quality_report_failure:'+str(exc),'exception_type':type(exc).__name__}
    return result
