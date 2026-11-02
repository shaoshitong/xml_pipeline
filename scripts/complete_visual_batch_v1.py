"""Publish recorded actual-PNG review decisions and update the review ledger."""
from pathlib import Path
import argparse,json,subprocess
def main():
 p=argparse.ArgumentParser();p.add_argument('--review-root',required=True);p.add_argument('--decisions',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 notes=json.loads(a.decisions.read_text());assert notes and all(len(x)==3 and isinstance(x[1],bool)and x[2].strip()for x in notes)
 code='''from pathlib import Path
import json,subprocess,sys,sqlite3
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
'''+ 'root=Path('+repr(a.review_root)+');notes='+repr(notes)+'''
assert root.resolve().is_relative_to(R/'clean/complexity_curation_20261102T054553Z_v1/value_reviews')
rows=[json.loads(x)for x in(root/'reviewed_pairs.jsonl').read_text().splitlines()];assert len(rows)==len(notes);decisions={}
for r,(prefix,approved,note)in zip(rows,notes):
 assert r['id'].startswith(prefix);decisions[r['id']]=dict(approved=approved,note=note,actual_native_PNG_inspected=True)
p=root.parent/(root.name+'_decisions.json');body=json.dumps(decisions,indent=2)
if p.exists():assert p.read_text()==body
else:p.write_text(body);p.chmod(0o444)
r=subprocess.run([sys.executable,str(S/'finalize_incremental_visual_review_v1.py'),'--input',str(root),'--decisions',str(p)],capture_output=True,text=True);assert r.returncode==0,r.stderr;review=json.loads(r.stdout)
r=subprocess.run([sys.executable,str(S/'publish_content_reviewed_complex_v2.py'),'--review-summary',review['root']+'/summary.json'],capture_output=True,text=True);assert r.returncode==0,r.stderr;publication=json.loads(r.stdout)
with sqlite3.connect(R/'clean/complexity_curation_20261102T054553Z_v1/value_review_registry_v1/status.sqlite')as db:
 for r in rows:db.execute('update reviews set review_root=?,status=? where id=? and code_sha256=? and image_sha256=?',(review['root'],'published'if decisions[r['id']]['approved']else'held',r['id'],r['pair']['code_sha256'],r['pair']['image_sha256']))
print(json.dumps(dict(review=review,publication=publication)))
'''
 r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=30);assert r.returncode==0,r.stderr
 result=json.loads(r.stdout);a.output.write_text(json.dumps(result,indent=2));print(json.dumps(result['publication']))
if __name__=='__main__':main()
