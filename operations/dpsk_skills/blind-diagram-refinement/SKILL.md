---
name: blind-diagram-refinement
description: Finds and verifies editable diagram repairs using a target PNG, a candidate draw.io file, rendered image differences, and re-rendered checkpoints. Use for image-to-draw.io refinement without reference XML.
---

# Blind diagram refinement

Work independently inside this case directory. The target image is the visual specification. `seed.drawio` is your editable starting point. Reference XML, external lookup, and other cases are out of scope. No person will choose a region, explain a discrepancy, or tell you how to repair it.

1. **Survey the entire diagram.** Run `python3 visual_check.py seed.drawio`. Read the returned report and overview as well as the target. Look for several independent, observable discrepancies. Compare the target and candidate at the same scale; differences in the heatmap can be the same feature shifted, not an extra or missing object. Patch MSE proposes where to look. It cannot determine which label, edge or shape is correct.
2. **Decide what you can prove.** Choose the regions and priorities yourself. For each prospective repair, identify a visible feature and the candidate cells it maps to. Use local crops. Read both arrow endpoints and the arrowhead before changing a connection; if a line or label is ambiguous, leave it and record the uncertainty. Check important errors outside the hottest patches too.
3. **Try and measure.** Keep the last accepted XML. Copy it to a new checkpoint ending in `.drawio` and edit only what you can justify. Render each new checkpoint with `python3 visual_check.py checkpoint.drawio --against last_accepted.drawio`. Use the actual target/candidate crops, patch metrics at fixed coordinates, and XML/render validity to decide whether to keep or revert. Compare against the last accepted checkpoint, not an arbitrary later attempt. Inspect neighboring regions for regressions. Avoid global transformations or embedding any screenshot.
4. **Continue over multiple distinct regions.** Do not stop after just one local edit if there are other actionable discrepancies. Spend the tool budget on independently checkable improvements. Stop at convergence or the budget limit; don't claim exact reconstruction when unresolved issues remain. The service allows at most six renders including baseline.
5. **Record the trajectory.** Keep attempted checkpoints and write `decisions.jsonl` with one row per attempt: `from`, `candidate`, target-pixel bbox or patch ID, visual evidence, affected cell IDs, actual measured outcome, and `accept`/`revert` with reason. At the end write `selected.json` with the relative filename of your best already-rendered checkpoint and the unresolved discrepancies.

Use the tool report's file paths to open the PNGs with the image reader. It prints only visual and structural diagnostics; all choices and edits are yours.

To inspect what changed between two already rendered checkpoints, optionally run
`python3 visual_check.py compare before.drawio after.drawio`. Read the revision
report and overlays. The service compares only these two unchanged case-local
checkpoints. A comparison gives native cell IDs, coordinates, and observable
differences for you to interpret alongside the target PNG. Use the target-image
checks to decide whether to keep an edit.
