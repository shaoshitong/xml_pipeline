from pathlib import Path
import os,sys,json,subprocess,signal,shlex,time
root=Path("/DATA/disk1/zbw_tmp4/drawio-agent-qwen38");src=root/"source-snapshots/815df7c/operations/areal_dsh_rollout";sys.path.insert(0,str(src))
from h20_eval import environment,start_server,gpu_inventory
from launch import ready
out=root/"runs/literal-cache-control-815df7c";out.mkdir();env=environment(root);results={}
literal=(root/"runs/qwen38-controls-5db239f-r2/tool-probe/host-private-reference.drawio").read_text()
code="from pathlib import Path;Path('/case/round1.drawio').write_text("+repr(literal)+")"
note="This invocation is ONLY a mechanical tool execution probe, not image reconstruction. Do not inspect the image or renderer source, and do not measure pixels. Use the bash tool to execute exactly this write command: "+shlex.join([str(root/"renderer/venv/bin/python"),"-c",code])+". Then execute the supplied official renderer command below. Return the XML and PNG paths. The XML is a synthetic fixture supplied as input, not an answer to any dataset image."
for mode,extras in (("cache-on",["--disable-overlap-schedule","--mamba-scheduler-strategy","no_buffer"]),("cache-off",["--disable-overlap-schedule","--mamba-scheduler-strategy","no_buffer","--disable-radix-cache"])):
 for _ in range(20):
  if next(x["memory_used_mib"] for x in gpu_inventory() if x["index"]==7)<1024:break
  time.sleep(1)
 assert next(x["memory_used_mib"] for x in gpu_inventory() if x["index"]==7)<1024
 process,log=start_server(root,out/(mode+"-server"),"generator","Qwen3.8-27B","7",32444,262144,0.85,env,yarn=False,sampling="qwen38",extra_args=extras)
 (out/(mode+"-server")/"actual-argv.json").write_text(json.dumps(process.args))
 try:
  ready(process,32444,timeout=900)
  for seed in (42,43):
   case=out/(mode+"-seed"+str(seed));case.mkdir()
   command=[sys.executable,str(src/"rollout.py"),"--runtime",str(root/"runtime"),"--reference",str(root/"runs/qwen38-controls-5db239f-r2/tool-probe/reference.png"),"--out",str(case/"episode"),"--renderer-python",str(root/"renderer/venv/bin/python"),"--render-runtime",str(root/"renderer"),"--python-runtime-root","/DATA/disk1/zbw_tmp4/rdm-sets/envs/rdm","--generator-model","Qwen/Qwen3.8-27B","--generator-url","http://127.0.0.1:32444/v1","--rounds","1","--context-window","262144","--max-tokens","131072","--sampling-preset","qwen38","--preserve-thinking","--skill-mode","minimal","--resume-note",note,"--turn-timeout","300","--seed",str(seed)]
   (case/"invocation.json").write_text(json.dumps({"command":command,"quality_benchmark":False,"provided_synthetic_xml":True,"contains_dataset_gold":False,"backend_extra_args":extras}))
   with (case/"rollout.log").open("wb") as stream:result=subprocess.run(command,env=dict(env,CUDA_VISIBLE_DEVICES="",ROLLOUT_API_WIRE_AUDIT=str(case/"api-wire.jsonl")),stdout=stream,stderr=stream)
   results[case.name]={"exit":result.returncode,"xml":(case/"episode/case/round1.drawio").exists(),"png":(case/"episode/case/round1.png").exists()};(out/"results.json").write_text(json.dumps(results,indent=2));print(json.dumps({case.name:results[case.name]}),flush=True)
 finally:
  if process.poll() is None:
   os.killpg(process.pid,signal.SIGTERM)
   try:process.wait(timeout=30)
   except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
  log.close()
