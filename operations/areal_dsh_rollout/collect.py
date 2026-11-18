"""Collect an unscored DSH episode through native AReaL, without an optimizer."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import shlex
import sys
from urllib.request import urlopen

os.environ["CUDA_VISIBLE_DEVICES"] = ""

import torch

from areal.api import LocalInfServerInfo
from areal.api.cli_args import AgentConfig, InferenceEngineConfig, SchedulingSpec
from areal.engine.sglang_remote import RemoteSGLangEngine
from areal.infra.controller.rollout_controller import RolloutController
from areal.infra.rpc.rtensor import RTensor
from areal.infra.scheduler.local import LocalScheduler

from workflow import SAMPLING


HERE = Path(__file__).resolve().parent
AREAL_COMMIT = "64a7fcca3936ddf2ab16bb1dd3e776d66ced31ff"


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def audit_tensors(trajectory, merge_size):
    ids, mask = trajectory["input_ids"], trajectory["loss_mask"]
    attention = trajectory["attention_mask"].bool()
    logprobs = trajectory["logprobs"]
    assert ids.ndim == 2 and ids.numel() and ids.dtype == torch.int64
    assert mask.shape == attention.shape == logprobs.shape == ids.shape
    assert ((mask == 0) | (mask == 1)).all() and not mask[~attention].any()
    policy = mask.bool() & attention
    assert policy.any() and (ids[attention] >= 0).all()
    assert torch.isfinite(logprobs[policy]).all() and (logprobs[policy] <= 0.001).all()
    modalities = trajectory["mm_token_type_ids"]
    inputs = trajectory["multi_modal_input"]
    assert modalities.shape == ids.shape and len(inputs) == ids.shape[0]
    assert not policy[modalities == 1].any()
    rows = []
    image_rows = 0
    for number, (active, loss, modality, multimodal) in enumerate(
            zip(attention, policy, modalities, inputs, strict=True)):
        positions = loss.nonzero().flatten()
        assert len(positions) and positions[0] > 0
        assert loss[positions[0]:][active[positions[0]:]].all()
        images = int((modality == 1).sum())
        item = {"row": number, "prompt_tokens": int(positions[0]),
                "policy_tokens": int(loss.sum()), "image_tokens": images}
        if images:
            pixels, grid = multimodal["pixel_values"], multimodal["image_grid_thw"]
            expected = int(grid.prod(dim=-1).sum()) // (merge_size * merge_size)
            assert images == expected and torch.isfinite(pixels).all()
            item.update(pixel_values_shape=list(pixels.shape), image_grid_thw=grid.tolist())
            image_rows += 1
        rows.append(item)
    assert image_rows, "No real image tensor appeared in the collected episode"
    group = trajectory["rollout_group"].validate_rows(len(rows))
    assert len(group.row_counts) == 1
    return {"rows": rows, "logical_rollout": asdict(group), "image_rows": image_rows,
            "policy_tokens": int(policy.sum()),
            "policy_logprob_min": float(logprobs[policy].min()),
            "policy_logprob_max": float(logprobs[policy].max()),
            "native_reward_values": trajectory["rewards"].tolist(),
            "image_grid_token_count_matches": True, "mrope_forward_checked": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "runtime", "reference", "tokenizer", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--generator-host", default="127.0.0.1")
    parser.add_argument("--generator-port", type=int, default=30000)
    parser.add_argument("--generator-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--reviewer-url", default="http://127.0.0.1:30102/v1")
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=7200)
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(mode=0o700, parents=True)
    source = Path(sys.modules["areal"].__file__).resolve().parents[1]
    assert source == args.root.resolve() / "controller/source" / ("AReaL-" + AREAL_COMMIT)
    expected_defaults = {"min_p": 0.0, "presence_penalty": 1.5, "repetition_penalty": 1.0}
    origin = f"http://{args.generator_host}:{args.generator_port}"
    with urlopen(origin + "/model_info", timeout=10) as response:
        model_info = json.load(response)
    preferred = model_info.get("preferred_sampling_params") or {}
    if any(preferred.get(key) != value for key, value in expected_defaults.items()):
        raise ValueError("Existing Generator must explicitly serve the instruct sampling defaults")
    assert model_info.get("has_image_understanding"), "Generator has no vision support"
    env = {"CUDA_VISIBLE_DEVICES": "", "PYTHONPATH": str(HERE),
           "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
           "PYTHONDONTWRITEBYTECODE": "1", "LITELLM_LOCAL_MODEL_COST_MAP": "True"}
    trial = "capture-" + secrets.token_hex(6)
    config = InferenceEngineConfig(
        experiment_name="drawio-unscored-wire", trial_name=trial,
        backend="sglang:d1", tokenizer_path=str(args.tokenizer.resolve()),
        fileroot=str(args.out), max_concurrent_rollouts=1, consumer_batch_size=1,
        request_retries=1, dump_to_file=True,
        scheduling_spec=(SchedulingSpec(cpu=1, gpu=0, mem=8, env_vars=env,
                                       cmd=shlex.quote(sys.executable) + " -m areal.infra.rpc.rpc_server"),),
        agent=AgentConfig(mode="inline", export_style="individual", chat_template_type="hf",
                          tool_call_parser="qwen3_coder", reasoning_parser="qwen3",
                          engine_max_tokens=65536, turn_discount=1.0,
                          admin_api_key=secrets.token_urlsafe(32),
                          chat_template_kwargs={"enable_thinking": False, "preserve_thinking": False}),
    )
    scheduler = LocalScheduler(gpu_devices=[0], log_dir=str(args.out / "worker-logs"),
                               experiment_name=config.experiment_name, trial_name=trial,
                               fileroot=str(args.out), enable_tms_offload=False,
                               nfs_record_root=str(args.out / "name-resolve"))
    collector = RolloutController(inf_engine=RemoteSGLangEngine, config=config, scheduler=scheduler)
    audit = {"kind": "native_areal_unscored_capture", "areal_commit": AREAL_COMMIT,
             "areal_source": str(source),
             "reward_status": "unscored_native_zero_placeholders", "training_eligible": False,
             "optimizer_started": False, "registered_policy_servers": [origin],
             "reviewer_url": args.reviewer_url, "reviewer_frozen": True,
             "sampling": {**SAMPLING, **expected_defaults},
             "reference_sha256": sha256(args.reference.read_bytes()).hexdigest(),
             "reviewer_cache_check": "separate direct upstream; no policy auth supplied to reviewer"}
    save(args.out / "capture-contract.json", audit)
    try:
        collector.initialize(role="eval-rollout", server_infos=[
            LocalInfServerInfo(process=None, host=args.generator_host, port=args.generator_port)])
        collector.start_proxy()
        collector.submit(
            data={"reference": str(args.reference.resolve())}, workflow="workflow.DSHAgent",
            workflow_kwargs={"root": str(args.root.resolve()), "runtime": str(args.runtime.resolve()),
                             "out": str(args.out / "dsh"), "generator_model": args.generator_model,
                             "reviewer_url": args.reviewer_url, "rounds": args.rounds,
                             "episode_timeout": args.timeout},
            is_eval=True, group_size=1, reward_normalization=False)
        results = collector.wait(count=1, timeout=args.timeout)
        trajectory = results[0]
        assert trajectory is not None and isinstance(trajectory["input_ids"], RTensor)
        local = RTensor.localize(trajectory, preserve_tensor_aliases=True)
        preprocessing = json.loads((args.tokenizer / "preprocessor_config.json").read_text())
        audit.update(audit_tensors(local, preprocessing["merge_size"]))
        torch.save({"trajectory": local, "native_rtensors": trajectory, "audit": audit},
                   args.out / "unscored-capture.pt")
        audit.update(completed=True, capture_bytes=(args.out / "unscored-capture.pt").stat().st_size)
        save(args.out / "capture-audit.json", audit)
        print(json.dumps({"completed": True, "training_eligible": False,
                          "image_rows": audit["image_rows"], "policy_tokens": audit["policy_tokens"]}))
    finally:
        collector.destroy()


if __name__ == "__main__":
    main()
