---
name: drawio-reconstruction
description: Reconstruct or refine an editable draw.io diagram from its target PNG using compiler diagnostics and checkpoint renders. Use for image-to-draw.io reconstruction.
---

# Reconstruct editable draw.io

Open the target PNG with the image reader. Identify panels, labels, shapes and directed connections from the image. Create an uncompressed draw.io file with editable shapes and text. Use bound edge terminals where the image shows a connection. Keep each checkpoint in a separate `.drawio` file. Do not embed a screenshot, flattened vector or external asset.

When available, call `mcp__drawio__check` with your checkpoint's filename. Open the returned candidate PNG as an image. Diagnostics point to candidate cells and approximate regions in target-image pixels. Confirm each issue in the target PNG. For ambiguous matches, missing objects or suspected edges, inspect the region yourself before editing.

Prioritize visible omissions, labels, arrow directions and major layout discrepancies. Treat coordinates as approximate, and keep correct regions intact. Make a new checkpoint, check it, and review the same regions plus neighboring regions for regressions. Image metrics help compare checkpoints. A lower error can still conceal an incorrect connection or label.

Choose the best verified checkpoint and report the filename, observed fixes and remaining uncertainties. Stop at convergence or the stated check budget.
