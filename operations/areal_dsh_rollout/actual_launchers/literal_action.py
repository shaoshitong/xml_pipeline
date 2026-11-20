from pathlib import Path
import os,sys,json,subprocess,signal
root=Path("/DATA/disk1/zbw_tmp4/drawio-agent-qwen38")
src=root/"source-snapshots/09298e7/operations/areal_dsh_rollout"
sys.path.insert(0,str(src))
from h20_eval import environment,start_server,gpu_inventory
from launch import ready
out=root/"runs/literal-action-probe-09298e7";out.mkdir()
assert next(r["memory_used_mib"] for r in gpu_inventory() if r["index"]==7)<1024
env=environment(root)
process,log=start_server(root,out/"server","generator","Qwen3.8-27B","7",32444,262144,0.85,env,yarn=False,sampling="qwen38")
try:
 ready(process,32444,timeout=900)
 literal=(root/"runs/qwen38-controls-5db239f-r2/tool-probe/host-private-reference.drawio").read_text()
 import shlex
 code="from pathlib import Path;Path('/case/round1.drawio').write_text("+repr(literal)+")"
 note="This invocation is ONLY a mechanical tool execution probe, not image reconstruction. Do not inspect the image or renderer source, and do not measure pixels. Use the bash tool to execute exactly this write command: "+shlex.join([str(root/"renderer/venv/bin/python"),"-c",code])+". Then execute the supplied official renderer command below. Return the XML and PNG paths. The XML is a synthetic fixture supplied as input, not an answer to any dataset image."
 command=[sys.executable,str(src/"rollout.py"),"--runtime",str(root/"runtime"),"--reference",str(root/"runs/qwen38-controls-5db239f-r2/tool-probe/reference.png"),"--out",str(out/"episode"),"--renderer-python",str(root/"renderer/venv/bin/python"),"--render-runtime",str(root/"renderer"),"--python-runtime-root","/DATA/disk1/zbw_tmp4/rdm-sets/envs/rdm","--generator-model","Qwen/Qwen3.8-27B","--generator-url","http://127.0.0.1:32444/v1","--rounds","1","--context-window","262144","--max-tokens","131072","--sampling-preset","qwen38","--preserve-thinking","--skill-mode","minimal","--resume-note",note,"--turn-timeout","300"]
 (out/"invocation.json").write_text(json.dumps({"command":command,"quality_benchmark":False,"provided_synthetic_xml":True,"contains_dataset_gold":False,"purpose":"Isolate DSH tool execution/rendering from visual planning"},indent=2))
 with (out/"rollout.log").open("wb") as stdout:
  result=subprocess.run(command,env=dict(env,CUDA_VISIBLE_DEVICES=""),stdout=stdout,stderr=stdout)
 (out/"result.json").write_text(json.dumps({"exit":result.returncode,"quality_benchmark":False,"provided_synthetic_xml":True}))
finally:
 if process.poll() is None:
  os.killpg(process.pid,signal.SIGTERM)
  try:process.wait(timeout=30)
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
 log.close()
