"""Fresh two-generation, one-review skill ablations using the unchanged core runner.

Pass core input/runtime/model/endpoint options after --. No model is contacted by
--dry-run. Compare against corrected-full with the same effective sampling.
"""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
SKILL_SENTENCE = "Follow the supplied drawio-reconstruction skill. "
MEANING = {
    "no-skill": "Remove only the supplied skill file and its explicit prompt cue; preserve other core instructions.",
    "minimal": "Remove the skill and simplify instructions; this is an instruction-complexity comparison, not a pure skill-file effect.",
}
MANAGED = {"--out", "--rounds", "--skill-mode", "--context-window", "--max-tokens",
           "--reasoning-effort", "--turn-timeout", "--sampling-preset", "--resume",
           "--seeded", "--generator-session-id", "--resume-note"}


def prompt_for_mode(mode, role, number, rounds, original):
    """Explicit core hook; full is byte-identical and no-skill removes one cue."""
    if mode == "full":
        return original
    if mode == "no-skill":
        if original.count(SKILL_SENTENCE) != 1:
            raise ValueError("Expected exactly one explicit supplied-skill cue")
        return original.replace(SKILL_SENTENCE, "", 1)
    if mode != "minimal" or role not in ("generator", "reviewer"):
        raise ValueError("Unknown skill mode or role")
    if role == "generator":
        previous = (
            f"Use your own round{number - 1}.drawio and review{number - 1}.json to revise the candidate."
            if number > 1 else "Read reference.png and directly reconstruct its diagram."
        )
        return f"""You are the Generator, round {number} of {rounds}. {previous}
Write round{number}.drawio with native editable Draw.io cells. Match the visible
text, layout, shapes, colors, and connectors. Render round{number}.png with the
supplied official renderer and visually inspect it against reference.png.
Fix clear defects, then finish this round even if imperfections remain; the
independent Reviewer handles the next review. No exhaustive inventory is needed.
Do not alter reference.png or earlier rounds, embed images, or flatten the diagram.
Use only the reference and your own outputs/reviews. No other answers, gold,
gold-aware tools, diff/score feedback, external models, or extra agents.
End with the XML and PNG paths and brief remaining limitations.
"""
    return f"""You are the independent frozen Reviewer for round {number}.
Compare reference.png with round{number}.png and the Generator's own round{number}.drawio.
Do not edit files or render. Briefly prioritize visible mismatches in content,
layout, colors, and connectors; do not invent details you cannot see.
Use only these inputs: no other answers, gold, gold-aware tools, diffs/scores,
external models, or extra agents.
Return only JSON with round={number}, candidate="round{number}.drawio",
render="round{number}.png", status (PASS/FIX/UNCERTAIN), summary, issues, limitations.
Each issue has id, severity (blocking/major/minor), category
(missing/extra/text/geometry/color/connector/layering/editability), reference_bbox,
candidate_bbox, cell_ids, observed, expected, suggested_fix. Use null boxes or
empty cell_ids when uncertain, and an empty issues list when none are found.
"""


def build_command(args):
    forwarded = args.rollout_args[1:] if args.rollout_args[:1] == ["--"] else args.rollout_args
    if any(value.split("=", 1)[0] in MANAGED for value in forwarded):
        raise ValueError("Use wrapper options for budgets/mode; ablations require fresh sessions")
    return [sys.executable, str(HERE / "rollout.py"), *forwarded,
            "--out", str(args.out.resolve()), "--rounds", "2", "--skill-mode", args.mode,
            "--context-window", str(args.context_window), "--max-tokens", str(args.max_tokens),
            "--reasoning-effort", args.reasoning_effort, "--turn-timeout", str(args.turn_timeout),
            "--sampling-preset", args.sampling_preset]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=tuple(MEANING))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--context-window", type=int, default=65536)
    parser.add_argument("--max-tokens", type=int, default=32768)
    parser.add_argument("--turn-timeout", type=int, default=900)
    parser.add_argument("--reasoning-effort", choices=("off", "high"), default="off")
    parser.add_argument("--sampling-preset", default="instruct")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("rollout_args", nargs=argparse.REMAINDER,
                        help="Core --runtime/--reference/renderer/model/endpoint options after --")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must be a new independent directory")
    try:
        command = build_command(args)
    except ValueError as error:
        parser.error(str(error))
    manifest = {
        "mode": args.mode, "interpretation": MEANING[args.mode],
        "generations": 2, "independent_reviews": 1, "skill_file": False,
        "gold_feedback": False, "fresh_sessions": True,
        "context_window": args.context_window, "max_tokens": args.max_tokens,
        "turn_timeout": args.turn_timeout, "reasoning_effort": args.reasoning_effort,
        "sampling_preset": args.sampling_preset,
        "matched_control": "corrected-full with the same effective request sampling; legacy full is not a control",
        "command": command,
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("ablate_skill.py", "rollout.py", "prompts.py", "dsh_profiles.py",
                                       "sandbox_gateway.py", "trace_proxy.py")},
    }
    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return
    args.out.mkdir(parents=True)
    (args.out / "ablation.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    os.execv(sys.executable, command)


if __name__ == "__main__":
    main()

