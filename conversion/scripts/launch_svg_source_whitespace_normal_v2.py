"""Launch one source/core attempt, recording its immutable identity before work."""
from pathlib import Path
import hashlib, json, os, subprocess, sys, uuid

R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
sys.path.insert(0,str(S))

def main():
    identifier=sys.argv[1]
    assert len(identifier)==64 and all(c in '0123456789abcdef' for c in identifier)
    names=['svg_source_whitespace_native_v2.py','svg_resolved_geometry_v1.js','svg_dom_v11.js','svg_dom_source_scene_v6.js','svg_source_endpoint_bridge_v5.py','svg_source_compound_linear_paths_v1.py','compiler_svg_explicit_coordinates_v8.py','compiler_svg_explicit_coordinates_v8.js','svg_source_stroke_support_v3.py','svg_source_edge_layers_v17.py',
           'compiler_svg_scene_backend_v16.py','compiler_svg_scene_frontend_v24.py',
           'compiler_svg_general_guard_v20.py','compiler_svg_general_quality_adapter_v27.py',
           'compiler_svg_scene_quality_ro_v31.py','svg_rotated_source_visual_scope_v7.py',
           'svg_source_whitespace_normal_dev_v2.py']
    owned={}
    for name in names:
        path=S/name;owned[name]=hashlib.sha256(path.read_bytes()).hexdigest();path.chmod(0o444)
    import compiler_svg_general_guard_v20 as compiler
    from compiler_source_core_attempts_v3 import core_identity
    configuration=compiler.configuration();core=core_identity(configuration)
    claim=R/'conversion'/compiler.VERSION/'normal_once'/core['key']/(identifier+'.json')
    assert not claim.exists(),'Consumed source/core attempt must never be restarted'
    parent=R/'conversion'/compiler.VERSION/'normal_development_source_whitespace_v2'/uuid.uuid4().hex
    parent.mkdir(parents=True);work=parent/identifier;freeze=parent/'freeze.json'
    freeze.write_text(json.dumps(dict(configuration=configuration,owned=owned),indent=2));freeze.chmod(0o444)
    command=[sys.executable,str(S/'svg_source_whitespace_normal_dev_v2.py'),identifier,str(work),str(freeze)]
    wrapper=parent/'run.py'
    wrapper.write_text('import subprocess,time,json\nfrom pathlib import Path\nt=time.monotonic()\nr=subprocess.run('+repr(command)+')\nPath('+repr(str(parent/'timing.json'))+').write_text(json.dumps(dict(elapsed_seconds=time.monotonic()-t,exit_code=r.returncode)))\n')
    log=(parent/'output.log').open('wb')
    process=subprocess.Popen([sys.executable,str(wrapper)],stdout=log,stderr=subprocess.STDOUT,
                             start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
    birth=Path('/proc',str(process.pid),'stat').read_text().rsplit(') ',1)[1].split()[19]
    receipt=dict(pid=process.pid,birth_ticks=birth,parent=str(parent),work=str(work),source_core=core,
                 policy=configuration['policy'],normal_calls_planned=1,model_calls=0,goal_complete=False)
    (parent/'launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))

if __name__=='__main__':main()
