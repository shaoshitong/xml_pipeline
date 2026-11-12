---
name: drawio-reconstruction
description: Reconstruct or refine an editable draw.io diagram from its target PNG using compiler diagnostics and checkpoint renders. Use for image-to-draw.io reconstruction.
---

# Reconstruct editable draw.io

Open the target PNG with the image reader. Identify panels, labels, shapes and directed connections from the image. Create an uncompressed draw.io file with editable shapes and text. Use bound edge terminals where the image shows a connection. Keep each checkpoint in a separate `.drawio` file. Do not embed a screenshot, flattened vector or external asset.

Call `mcp__drawio__check` with your checkpoint's filename when available. If it returns a `diagnostics_file`, read its relevant ranges for object-level findings. Use `field_diagnostics_file` for individual XML fields and bindings. Check node and label content, directed connectivity and bound endpoints first. Confirm unmatched objects, unresolved references and ambiguous matches against the target before editing.

Check layout and color with the same report. Bounding boxes and routes are in target-image pixels. For color, compare the reported fill, stroke or text field with the target region. Open the rendered candidate to confirm changes and spot regressions in nearby objects.

Choose the checkpoint that preserves the target's objects, labels and connections and has the fewest visually confirmed remaining discrepancies in layout and appearance. Report corrected cell IDs or regions, unresolved findings and the selected file. Stop at convergence or the stated check budget.
