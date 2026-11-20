#!/usr/bin/env bash
cd /DATA/disk1/zbw_tmp4/drawio-agent-qwen38
while [[ ! -f logs/qwen38-controls-5db239f-r2.exit ]]; do sleep 5; done
if [[ $(cat logs/qwen38-controls-5db239f-r2.exit) == 0 ]]; then
  echo 0 > logs/qwen38-controls-09298e7-r3.exit
  exit 0
fi
sleep 5
bash source-snapshots/09298e7/operations/areal_dsh_rollout/h20_compare.sh /DATA/disk1/zbw_tmp4/drawio-agent-qwen38 /DATA/disk1/zbw_tmp4/drawio-agent-qwen38/runs/qwen38-controls-09298e7-r3 09298e7f00fd920e71b7bb406d7cf9e4c2cf4031 /DATA/disk1/zbw_tmp4/rdm-sets/envs/rdm --resume-from /DATA/disk1/zbw_tmp4/drawio-agent-qwen38/runs/qwen38-controls-5db239f-r2 --turn-timeout 21600
echo $? > logs/qwen38-controls-09298e7-r3.exit
