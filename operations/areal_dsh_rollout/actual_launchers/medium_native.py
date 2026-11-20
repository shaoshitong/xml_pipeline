from pathlib import Path
from types import SimpleNamespace
import os,sys,json,subprocess,signal
root=Path("/DATA/disk1/zbw_tmp4/drawio-agent-qwen38");src=root/"source-snapshots/c983558/operations/areal_dsh_rollout";sys.path.insert(0,str(src))
from h20_eval import environment,start_server,gpu_inventory
from h20_compare import evaluate
from launch import ready
from matched_eval import verify_server
out=root/"runs/qwen38-medium-c983558";out.mkdir();env=environment(root)
assert next(x["memory_used_mib"] for x in gpu_inventory() if x["index"]==7)<1024
contract={"source_commit":"c983558462e400a55ae5369313134360ea18880a","model":"Qwen/Qwen3.8-27B","qwen38_effort":"medium","temperature":1.0,"preserve_thinking":True,"context":262144,"max_output":131072,"stage_limit_seconds":21600,"completion_retries":3,"native_goal":False,"gold_feedback":False,"full_skill":True,"generator_gpu":7,"tp":1,"reviewer":"Qwen/Qwen3.5-4B","reviewer_gpu":6,"reviewer_frozen":True,"reviewer_owner":"qwen38-controls-09298e7-r3","training":False,"fresh_from_image":True,"provided_synthetic_xml":False}
(out/"contract.json").write_text(json.dumps(contract,indent=2))
process,log=start_server(root,out/"server","generator","Qwen3.8-27B","7",32444,262144,0.85,env,yarn=False,sampling="qwen38")
try:
 ready(process,32444,timeout=900)
 contract["backend"]=verify_server(32444,262144,out/"server/backend.json");contract["server_pid"]=process.pid;(out/"contract.json").write_text(json.dumps(contract,indent=2));print(json.dumps({"ready":"medium","pid":process.pid}),flush=True)
 args=SimpleNamespace(root=root,out=out,python_runtime_root=Path("/DATA/disk1/zbw_tmp4/rdm-sets/envs/rdm"),turn_timeout=21600,resume_from=None,qwen38_effort="medium",completion_retries=3)
 result=evaluate(args,"medium-native",32444,262144,env);(out/"result.json").write_text(json.dumps(result,indent=2))
finally:
 if process.poll() is None:
  os.killpg(process.pid,signal.SIGTERM)
  try:process.wait(timeout=30)
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
 log.close()
