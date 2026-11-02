"""QA-only session ownership adapter; the frozen generation core is unchanged."""
import copy,hashlib
from pathlib import Path
import compiler_svg_general_guard_v14 as core
from compiler_source_core_attempts_v3 import core_identity

R,W,VERSION,UNIT,UNITS=core.R,core.W,core.VERSION,core.UNIT,core.UNITS
structure_checks=core.structure_checks


def generation_configuration(data_root=R):return core.configuration(data_root)


def configuration(data_root=R):
    generation=generation_configuration(data_root);config=copy.deepcopy(generation)
    path=Path(__file__).resolve();digest=hashlib.sha256(path.read_bytes()).hexdigest()
    config['pins'][str(path)]=digest
    config['generation_source_core']=core_identity(generation)
    for name in ('svg_leaf_opacity_proof_v1.py','svg_source_use_instance_proof_v5.py','compiler_svg_explicit_coordinates_v7.py','svg_rotated_source_visual_scope_v1.py','compiler_svg_explicit_coordinates_v7.js'):
        dependency=Path(__file__).with_name(name);config['pins'][str(dependency)]=hashlib.sha256(dependency.read_bytes()).hexdigest()
    config['policy']=generation['policy']+':QA_source_edge_layers_interleaving_background_rotation_local_anchor_painter_frame_rotated_visual_scope_edit_runtime_leaf_opacity_v20:'+hashlib.sha256(core.raw(config['pins'])).hexdigest()[:12]
    return config


def _close_source_sessions():
    # The reused native edit/offset probes own their sessions in v1, whereas
    # the analytic source observer is v2. Closing v2 alone leaves v1's sync
    # manager active and prevents a later independent sync observation.
    import svg_source_scene_dom_v1 as v1
    import svg_source_scene_dom_v2 as v2
    v1.close_worker_runtime();v2.close_worker_runtime()


def check_source(record,xml,source,data_root,native_info=None):
    try:result=core.frontend.check_source(record,xml,source,data_root,native_info=native_info)
    finally:_close_source_sessions()
    if not result.get('ok'):return result
    try:
        prepared=core.frontend.prepare_source(record)
        from svg_leaf_opacity_proof_v1 import source_features
        guard=source_features(core,prepared['capture']['dom'],prepared['size'],xml)
        coordinates=core.frontend._semantics(prepared['capture']['dom'],xml)
        result['evidence']['checks']['current_source_rotation_and_membership']=coordinates
        result['failures']+=coordinates['errors']
        order=core.paint_order(prepared['capture']['dom'],xml,prepared['size'])if guard['ok']else dict(ok=False,failures=[])
        result['evidence']['checks']['complete_source_compositing_guard']={k:v for k,v in guard.items()if k not in('semantic','binding')}
        result['evidence']['checks']['actual_source_overlap_paint_order']=order
        result['failures']+=guard['failures']+order['failures'];result['ok']=not result['failures']
        result['evidence']['complete_source_coverage']=result['ok'];result['profile']=UNIT
        result['evidence']['QA_source_session_owners_closed_before_next_observation']=True
    except Exception as error:
        result['failures'].append(dict(reason='complete_source_order_or_compositing_guard_failed',detail=str(error)[:1600]))
        result['ok']=False;result['evidence']['complete_source_coverage']=False
    finally:_close_source_sessions()
    return result


def source_reproduction(*args,**kwargs):
    try:return core.source_reproduction(*args,**kwargs)
    finally:_close_source_sessions()


def quality_visual(*args,**kwargs):
    try:
        from svg_rotated_source_visual_scope_v1 import quality_visual as actual
        return actual(*args,**kwargs)
    finally:_close_source_sessions()


def audit_editing(*args,**kwargs):
    try:return core.audit_editing(*args,**kwargs)
    finally:_close_source_sessions()
