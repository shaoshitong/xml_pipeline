# drawio-compare

On HKUST3, from the repository root:

```sh
PATH=/home/shaoshitong/anaconda3/bin:$PATH \
  conversion/scripts/drawio-compare A.drawio B.drawio \
    --mode reference --out /backup/shaoshitong/img2code_20261029/evaluation/compare-example
```

Use the default `--mode revision` for two checkpoints. It reports before and after values.
Reference mode labels the same evidence as expected and actual. Both modes keep the
inputs intact and require a new output directory. Exit 0 means comparison completed.
Consult the report for differences. Exit 2 means an input or rendering check failed.

## Compilation

Each input independently becomes an uncompressed `mxfile` in `A_hat.xml` or
`B_hat.xml`. This unpacks compressed pages and wraps a bare `mxGraphModel`, orders
XML attributes, removes whitespace used to indent draw.io model containers, and
omits redundant native cell defaults such as `visible="1"` and `collapsed="0"`.
Cell and page IDs, sibling order, styles, geometry, and labels are retained.
Equivalent compression/wrapping can therefore collapse to the same output bytes.
Drawings with different IDs can still have equivalent pixels and logical objects.

The compiler verifies byte idempotence, exact native cell state and codec output, and exact RGB pixels
between each source and its own normalized output at a fixed viewport. For compressed
inputs, the source render uses draw.io's independent `Graph.decompress`. Unresolved
assets fail the render proof. The official XSD provides advisory diagnostics because
some editor-authored XML features extend the generated XML schema.

`--official-repairs` also runs the editor's `Graph.normalizeModel()`. Its optional
`*_official_repair.xml` and JSON record identify reparented edges, inserted edge
geometries, and expanded containers. The repair check records pixel equality and
keeps both renders when they differ. These candidates are separate from the checked
outputs and are never fed back into the comparison.

## Reports

- `A_cell_ids.json`, `B_cell_ids.json` map normalized IDs back to original XML and pages.
- `A_coordinates.json`, `B_coordinates.json` contain the native page and PNG positions,
  including routed edge points, painted shape and label bounds, and the shared
  page-to-PNG transform. Bounding boxes are `[x, y, width, height]`; crop regions are
  `[left, top, right, bottom]`. Hidden objects can lack visible coordinates.
- `diff.json` and `diff.txt` record normalization receipts, matches, and discrepancies.
  A confirmed match has distinctive evidence in this comparison. Suspected matches
  have competing correspondences. Unmatched means no supported match was found.
  Unknown means the requested observation was unavailable.
- `page_*_A.png`, `page_*_B.png`, `page_*_overlay.png`, and `crops/` show where
  differences occur. Both renders use one origin and scale, so a diagram shift is
  visible. Patch MSE identifies regions of pixel change. It does not select repairs.

Matching uses page order, normalized label text, object kind, panel membership,
neighbor labels, and geometry. A single centered text object can match the label
of a rectangle while its original cell and drag behavior remain observable.
Native editable tables, simple HTML tables, and regular grids of adjacent rectangles
inside one group are supported. Complex spans and ambiguous repeated objects can
require review.
The edge probe moves an actual vertex in draw.io and measures the endpoint before
and after restoring the original model. The report includes both binding attributes
and observed motion.

The existing pipeline provides the pinned draw.io 32.6.1 WAR, Chromium executable,
MathJax and font environment on HKUST3. The implementation uses Pillow and NumPy for
pixels, SciPy for assignment, NetworkX for adjacency, and lxml for the advisory schema.
The vendored XSD is from
[jgraph/drawio-mcp at cfc1b916](https://github.com/jgraph/drawio-mcp/blob/cfc1b916b9deaa7c78d23d719d4124bd76d2d0bf/shared/mxfile.xsd).
See `LICENSE.drawio-mcp` for its license.

## Acceptance

```sh
PYTHONPATH=conversion/scripts /home/shaoshitong/anaconda3/bin/python -u \
  conversion/drawio_compare/acceptance.py --out /backup/shaoshitong/img2code_20261029/evaluation/compare-acceptance
```

The suite checks representation changes, actual edit behavior, structural
differences, render-safe normalization, and coordinate projection. To also run
the five recorded img2code cases, pass `--fixtures` with a directory containing
the staged `outputs/random100_new540_final_seed20261103100_v1/pairs/*/author.drawio`
and `outputs/dpsk_img2code_max_pilot_20261111/*/round1.drawio` inputs.

The blind DPSK service can call this CLI through
`python3 visual_check.py compare before.drawio after.drawio`. It checks the hashes
of both previously rendered case checkpoints, then invokes revision mode on
HKUST3. It returns the revision report and overlays to the case directory. The
full artifact folder stays on HKUST3. The bridge's `--drawio-compare` argument
selects the installed CLI if the deployment path changes.
