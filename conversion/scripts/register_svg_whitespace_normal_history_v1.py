"""Preserve both distinct development normals in the immutable once catalog."""
from pathlib import Path
import hashlib,importlib,json,sqlite3,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()))
def main():
    import compiler_source_core_attempts_v3 as history
    parent=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_resolved_geometry_20261102_v13.json';catalog=json.loads(parent.read_bytes());catalog['preserved_parent_whitespace']=asset(parent)
    work=[('compiler_svg_general_guard_v19','conversion/compiler_svg_scene_frontend_v23/normal_development_source_whitespace_v1/2df77d0f3ca34b2d898011733f3039de/02578ea8477157a809457e7a3d2b0514dca01ed9b2ac3fe51537f5b6b79d4024'),('compiler_svg_general_guard_v20','conversion/compiler_svg_scene_frontend_v24/normal_development_source_whitespace_v2/4a604d6e92b940f5bee534d550950d6b/02578ea8477157a809457e7a3d2b0514dca01ed9b2ac3fe51537f5b6b79d4024')]
    destination=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_source_whitespace_20261103_v14.json';assert not destination.exists()
    for i,(module,path)in enumerate(work,1):
        summary=R/path/'summary.json';row=json.loads(summary.read_text());assert row['normal_frontend_calls']==1 and row['canonical_unchanged'];cfg=importlib.import_module(module).configuration();identity=history.core_identity(cfg);assert row['source_core']==identity
        receipt=summary.parent/'manual_normal_receipt_v1.json';assert not receipt.exists();receipt.write_text(json.dumps(dict(cases=[row],normal_frontend_calls=1,model_calls=0),indent=2));receipt.chmod(0o444)
        with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:job=db.execute('select*from jobs where id=?',(row['id'],)).fetchone()
        source=json.loads(job[4]);catalog['entries'].append(dict(id=row['id'],source=source,source_core_key=identity['key'],receipt=asset(receipt),rows_key='cases',row_index=0,normal_count_key='normal_frontend_calls',requires_unchanged_canonical=True,frontend=asset(summary.parent/'frontend_result.json'),admission='Actual immutable development normal of this distinct core. QA-only checks never reset source-core attempt history.'))
        catalog['source_core_configurations']['whitespace_v'+str(i)]=identity;catalog['normal_counts']['whitespace_v'+str(i)]=1
    catalog['producer']=asset(Path(__file__));destination.write_text(json.dumps(catalog,indent=2)+'\n');destination.chmod(0o444)
    for module,path in work:
        cfg=importlib.import_module(module).configuration();events=history.collect(cfg,root=R,catalog=str(destination.relative_to(R)));history.validate(events,cfg,root=R);assert len(events)==1
    print(json.dumps(dict(catalog=asset(destination),preserved_entries=len(catalog['entries'])-2,new_normals_preserved=2,normal_calls=0)))
if __name__=='__main__':main()
