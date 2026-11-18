def generation_prompt(n: int, rounds: int = 4) -> str:
    previous = (
        f"Start from your own round{n - 1}.drawio and read review{n - 1}.json. "
        "Check its findings against reference.png, repair the candidate, and preserve correct regions."
        if n > 1
        else "Inspect reference.png and make a complete visible-element inventory before constructing the candidate."
    )
    return f"""You are the Generator for round {n} of {rounds}.
Follow the supplied drawio-reconstruction skill. {previous}

Write round{n}.drawio using native editable Draw.io cells, text, geometry, and
connectors. Match all visible content, positions, dimensions, typography, colors,
line styles, edge endpoints, and arrow directions. Do not change reference.png
or earlier round files. Do not embed screenshots, reference crops, images, data
URIs, external image assets, or flattened SVGs; crops are for observation only.

Use the supplied official Draw.io renderer to export round{n}.png from the actual
XML. Inspect that render globally and locally against the reference and repair
visible defects within this round's budget. Rendering success is not fidelity.

Use only the reference and your own earlier candidates/reviews. Do not access
other Draw.io answers, gold XML, gold-aware MCP tools, compiler diffs, comparison
scores, external models, or additional agents. Do not create a review verdict.
End with the two output paths and concise remaining limitations. This is a
bounded rollout; stop after completing this round, even if defects remain.
"""


def review_prompt(n: int) -> str:
    return f"""You are the independent, frozen Reviewer for round {n}.
Follow the supplied drawio-reconstruction skill. Read only reference.png,
round{n}.png, and the Generator's own round{n}.drawio. You have no gold XML,
gold-aware MCP, compiler diff, comparison score, other answers, or external model.
Do not edit XML, render images, or modify any file. The host saves your final
JSON as review{n}.json and gives it to the Generator for the next round.

Compare the whole page and readable local regions. Check every visible element,
exact readable wording, geometry, typography, colors, strokes, containment,
layering, clipping, and connectors: source, target, anchors, direction, arrowhead,
and route. Inspect candidate XML for editable cells rather than embedded images.
Report evidence-based differences; use null bounding boxes and empty cell_ids
when uncertain. Boxes use [x, y, width, height] in each image's own pixels.
PASS is only an advisory visual assessment, never host acceptance or a reward.

Return one JSON object, with no markdown or surrounding prose, in this format:
{{
  "round": {n},
  "candidate": "round{n}.drawio",
  "render": "round{n}.png",
  "status": "PASS or FIX or UNCERTAIN",
  "summary": "Brief evidence-based assessment",
  "issues": [
    {{
      "id": "R{n}-I1",
      "severity": "blocking or major or minor",
      "category": "missing or extra or text or geometry or color or connector or layering or editability",
      "reference_bbox": [0, 0, 10, 10],
      "candidate_bbox": [0, 0, 10, 10],
      "cell_ids": [],
      "observed": "What the candidate visibly does",
      "expected": "What the reference visibly shows",
      "suggested_fix": "Concrete correction based only on these visible inputs"
    }}
  ],
  "limitations": []
}}
Use actual boxes, unique issue IDs, and one allowed value per status/severity/
category field. Use an empty issues list when no issue is found; do not copy
the example issue. Record illegible or unverifiable details in limitations.
"""
