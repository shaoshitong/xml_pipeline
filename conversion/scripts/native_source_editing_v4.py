"""Native original graph editability under actual fixed/floating edge routing.

This is limited to an independently verified original-native source graph. It
never weakens converted SVG/TikZ marker/relationship or original-fidelity gates.
"""
import hashlib,json,math
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029')
SCRIPT_PATH=Path(__file__).with_suffix('.js')
IMPLEMENTATION_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
SCRIPT_SHA256=hashlib.sha256(SCRIPT_PATH.read_bytes()).hexdigest()
PROFILE='original_native_live_constraint_perimeter_intervention_v4'


def require_source_proof(record,source_profile,xml):
    if record.get('source_format')!='drawio' or record.get('code_sha256')!=hashlib.sha256(xml.encode()).hexdigest():
        raise ValueError('native_editing_requires_hash_bound_original_drawio_source')
    if source_profile.get('supported') is not True or source_profile.get('ok') is not True:
        raise ValueError('native_editing_requires_successful_original_source_profile')
    proof=source_profile.get('evidence') or {}
    if source_profile.get('profile')=='original_native_xml':
        if proof.get('unchanged_source_objects_except_portable_font_styles') is not True or proof.get('source_pages')!=1:
            raise ValueError('native_editing_original_graph_identity_not_proven')
    elif source_profile.get('profile')=='original_native_exact_graph_physical_font_only_v4':
        fields=('normalized_original_exactly_equals_frozen_before_xml','font_only_delta_independently_verified',
                'fresh_before_after_and_all_frozen_png_pixels_identical','physical_faces_and_glyph_counts_preserved')
        if any(proof.get(key) is not True for key in fields) or proof.get('current_code_sha256')!=record['code_sha256']:
            raise ValueError('native_editing_exact_physical_font_only_source_not_proven')
    else:
        raise ValueError('native_editing_source_profile_not_an_exact_original_native_graph')
    if record.get('auto_quality_canvas_repair') and proof.get('canvas_only_transformation_independently_verified') is not True:
        raise ValueError('native_editing_canvas_delta_not_independently_proven')


def validate_report(result):
    if result.get('ok') is not True or result.get('model_and_all_live_states_restored') is not True:
        raise ValueError('native_editing_incomplete_live_intervention_proof')
    moves=result.get('moves');edges=result.get('edge_count')
    if isinstance(edges,bool) or not isinstance(edges,int) or edges<0 or not isinstance(moves,list) or len(moves)!=2*edges:
        raise ValueError('native_editing_incomplete_endpoint_coverage')
    seen=set();edge_sides={}
    def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
    def close(a,b):return finite(a) and finite(b) and abs(a-b)<=1e-6
    for move in moves:
        key=(move.get('edge'),move.get('side'))
        if key in seen or key[1] not in ('source','target') or move.get('ok') is not True:
            raise ValueError('native_editing_duplicate_or_invalid_terminal_proof')
        seen.add(key);edge_sides.setdefault(key[0],set()).add(key[1])
        if not move.get('terminal') or not move.get('moved_vertex') or move.get('mode') not in ('fixed_constraint','floating_native_perimeter'):
            raise ValueError('native_editing_terminal_or_constraint_evidence_missing')
        interventions=move.get('interventions')
        if not isinstance(interventions,list) or len(interventions)!=2:
            raise ValueError('native_editing_requires_two_controlled_interventions')
        changed=False
        for index,intervention in enumerate(interventions):
            offset=intervention.get('offset') or {}
            expected_offset=({'x':17,'y':11},{'x':-13,'y':19})[index]
            if offset!=expected_offset:raise ValueError('native_editing_wrong_controlled_intervention')
            if intervention.get('model_and_all_live_states_restored') is not True:
                raise ValueError('native_editing_restore_proof_missing')
            for stage in ('before','after'):
                proof=intervention[stage]
                for key in ('expected','painted'):
                    if any(not close(proof['actual'][axis],proof[key][axis]) for axis in ('x','y')):
                        raise ValueError('native_editing_endpoint_expected_or_painted_mismatch')
            actual_delta={axis:intervention['after']['actual'][axis]-intervention['before']['actual'][axis] for axis in ('x','y')}
            if any(not close(actual_delta[axis],intervention['delta'][axis]) for axis in ('x','y')):
                raise ValueError('native_editing_endpoint_delta_evidence_disagrees')
            changed=changed or any(abs(v)>1e-6 for v in actual_delta.values())
            for child in intervention.get('child_deltas') or []:
                if any(not close(child[axis],offset[axis]) for axis in ('x','y')):
                    raise ValueError('native_editing_child_did_not_follow_vertex')
            for group in intervention.get('label_member_deltas') or []:
                members=group.get('members') or []
                if not members or any(not close(member[axis],members[0][axis]) for member in members for axis in ('x','y')):
                    raise ValueError('native_editing_compound_label_did_not_move_together')
        if not changed:raise ValueError('native_editing_endpoint_unaffected_by_both_interventions')
    if len(edge_sides)!=edges or any(sides!={'source','target'} for sides in edge_sides.values()):
        raise ValueError('native_editing_both_sides_of_every_edge_not_proven')
    return result


def audit(xml, *, record,source_profile):
    require_source_proof(record,source_profile,xml)
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=IMPLEMENTATION_SHA256 or hashlib.sha256(SCRIPT_PATH.read_bytes()).hexdigest()!=SCRIPT_SHA256:
        raise ValueError('native_editing_implementation_changed_after_import')
    from native_worker import native
    from playwright.sync_api import sync_playwright
    viewer=native.renderer_path(R).parent/'assets/viewer-static.min.js'
    viewer_sha=hashlib.sha256(viewer.read_bytes()).hexdigest()
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
        try:
            page=browser.new_page();page.route('**/*',lambda route:route.abort());page.set_content('<html></html>')
            page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}')
            page.add_script_tag(path=str(viewer));result=page.evaluate(SCRIPT_PATH.read_text(),xml)
        finally:browser.close()
    validate_report(result)
    if hashlib.sha256(viewer.read_bytes()).hexdigest()!=viewer_sha or hashlib.sha256(SCRIPT_PATH.read_bytes()).hexdigest()!=SCRIPT_SHA256:
        raise ValueError('native_editing_runtime_or_script_changed_during_proof')
    result.update(profile=PROFILE,source_code_sha256=record.get('source_code_sha256'),current_code_sha256=record['code_sha256'],source_profile=source_profile['profile'],viewer_sha256=viewer_sha,script_sha256=SCRIPT_SHA256,verifier_sha256=IMPLEMENTATION_SHA256)
    return result
