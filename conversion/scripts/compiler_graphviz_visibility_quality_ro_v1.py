"""Independent full QA of native Graphviz and conserved nonpainting source IR."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='independent_graphviz_visible_and_nonpainting_source_quality_v1'
sha=lambda data:hashlib.sha256(data).hexdigest()


def require(condition,reason):
    if not condition:raise ValueError(reason)


def verify(identifier,record_file,data_root,plugin_file,work,database=W/'jobs.sqlite'):
    from fixed_batch_case_v1 import checked,save,raw
    import compiler_graphviz_visibility_frontend_v1 as frontend
    import compiler_graphviz_visibility_quality_v1 as quality
    record_file=Path(record_file).resolve(strict=True);work=Path(work).resolve()
    require(Path(data_root).resolve()==R.resolve(),'visibility_wrong_data_root')
    require(work.is_relative_to((W/'prototype/candidate_quality_ro_v1').resolve()) and not work.exists(),'visibility_unowned_QA_work')
    work.mkdir(parents=True)
    blob=record_file.read_bytes();record=json.loads(blob);config=frontend.configuration()
    report=dict(id=identifier,version=VERSION,quality_policy=config['policy'],implementation_pins=config['pins'],
                input_record_sha256=sha(blob),checks={},failures=[],ok=False,accepted=False,canonical_mutations=0,model_calls=0)
    try:
        require(Path(plugin_file).resolve()==Path(frontend.__file__).resolve(),'visibility_wrong_source_plugin')
        require(all(sha(Path(p).read_bytes())==h for p,h in config['pins'].items()),'infrastructure_visibility_pin_changed')
        with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=30) as db:
            job=db.execute('select * from jobs where id=?',(identifier,)).fetchone()
        require(job is not None and job[12] is None,'visibility_missing_or_owned_original_job')
        source=json.loads(job[4])
        require((record['id'],record['source_pair_sha256'],record['source_format'],record['source_code_sha256'],record['source_image_sha256'])==
                (identifier,identifier,'python',source['code_sha256'],source['image_sha256']),'visibility_source_identity_changed')
        checked(record['code_file'],record['code_sha256']);checked(record['image_file'],record['image_sha256'])
        underlying,out,directory=quality.verify(record,job,W/'compiler_graphviz_visibility_v1/independent'/work.name,0)
        report['checks']=copy.deepcopy(underlying.get('checks',{}));report['failures']=copy.deepcopy(underlying.get('failures',[]))
        report['underlying_quality_report']=dict(file=str((directory/'audit.json').relative_to(R)),sha256=sha((directory/'audit.json').read_bytes()))
        require(out and underlying.get('state')=='qualified' and not report['failures'],'visibility_underlying_full_quality_failed')
        source_check=report['checks']['source'];require(source_check.get('ok') is True,'visibility_source_profile_not_complete')
        domain=report['checks']['compiler_render_domain'];checks=domain['evidence']['checks']
        require(domain.get('ok') is True and all(c.get('ok') is True for c in checks.values()),'visibility_independent_full_domain_not_complete')
        nonpaint=checks['source_semantics']['source_json_endpoints']['nonpainting_layout_constraints']
        require(nonpaint.get('ok') is True and nonpaint.get('all_original_source_edge_ids_and_relationships_preserved') is True,
                'visibility_nonpainting_source_constraints_not_conserved')
        report['checks']['source'].setdefault('evidence',{}).update(complete_source_coverage=True,nonpainting_constraints=nonpaint,
                complete_visible_scene_and_nonpainting_relationships_independently_reconstructed=True)
        png=(directory/'fresh.png').read_bytes();require(sha(png)==record['image_sha256'],'visibility_stored_png_not_exact_fresh_native')
        save(work/'fresh.png',png)
        report.update(ok=True,accepted=True)
    except Exception as exc:
        report['failures'].append(dict(type=type(exc).__name__,reason=str(exc)[:7000]))
        report['infrastructure_failure']=isinstance(exc,(ImportError,ModuleNotFoundError)) or str(exc).startswith('infrastructure_')
    save(work/'report.json',raw(report))
    return report
