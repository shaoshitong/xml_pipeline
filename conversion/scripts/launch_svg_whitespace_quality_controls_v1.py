"""Reuse the full8 repair and run one regression plus two real negative cases."""
from pathlib import Path
import json,os,subprocess,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
def main():
    root=R/'conversion/svg_whitespace_quality_controls_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
    normal=R/'conversion/compiler_svg_scene_frontend_v24/normal_development_source_whitespace_v2/4a604d6e92b940f5bee534d550950d6b/02578ea8477157a809457e7a3d2b0514dca01ed9b2ac3fe51537f5b6b79d4024/summary.json';n=json.loads(normal.read_text());assert n['quality_ok']and n['canonical_unchanged'];candidate=Path(n['candidate_file'])
    prior=json.loads((R/'release/compiler_iterations/controls/svg_resolved_geometry_20261102_v1/proof.json').read_text());historical=R/prior['positive_cases'][0]['candidate']['file']
    cases=[('positive',historical),('negative_whitespace',candidate),('negative_text',candidate)]
    plan=dict(reused_full8_normal_summary=str(normal),cases=[dict(role=role,candidate=str(record))for role,record in cases],normal_conversion_calls=0,QA_calls_planned=3)
    (root/'plan.json').write_text(json.dumps(plan,indent=2));(root/'plan.json').chmod(0o444)
    handles=[]
    for role,record in cases:
        with(root/(role+'.log')).open('wb')as log:
            process=subprocess.Popen([sys.executable,str(S/'svg_source_whitespace_quality_control_v1.py'),'--record',str(record),'--work',str(root/role),'--role',role],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
        birth=Path('/proc',str(process.pid),'stat').read_text().rsplit(') ',1)[1].split()[19];handles.append(dict(role=role,pid=process.pid,birth_ticks=birth))
    receipt=dict(root=str(root),handles=handles,reused_full8_normal_summary=str(normal),normal_conversion_calls=0,QA_calls_planned=3,goal_complete=False);(root/'launch.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
if __name__=='__main__':main()
