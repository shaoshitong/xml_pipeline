"""Create a synthetic three-node protocol fixture, never a dataset benchmark."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess


XML = b'''<mxfile host="draw.io"><diagram id="sanity3" name="Protocol sanity fixture"><mxGraphModel background="#ffffff"><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="input" value="Input" style="rounded=0;whiteSpace=wrap;html=0;fillColor=#dae8fc;strokeColor=#6c8ebf;fontFamily=Arial;fontSize=16;fontColor=#1f2937;" vertex="1" parent="1"><mxGeometry x="30" y="30" width="160" height="80" as="geometry"/></mxCell>
<mxCell id="process" value="Process" style="rounded=0;whiteSpace=wrap;html=0;fillColor=#d5e8d4;strokeColor=#82b366;fontFamily=Arial;fontSize=16;fontColor=#1f2937;" vertex="1" parent="1"><mxGeometry x="250" y="30" width="160" height="80" as="geometry"/></mxCell>
<mxCell id="output" value="Output" style="rounded=0;whiteSpace=wrap;html=0;fillColor=#ffe6cc;strokeColor=#d79b00;fontFamily=Arial;fontSize=16;fontColor=#1f2937;" vertex="1" parent="1"><mxGeometry x="470" y="30" width="160" height="80" as="geometry"/></mxCell>
<mxCell id="in_to_process" style="edgeStyle=orthogonalEdgeStyle;endArrow=block;endFill=1;strokeColor=#374151;strokeWidth=2;" edge="1" parent="1" source="input" target="process"><mxGeometry relative="1" as="geometry"/></mxCell>
<mxCell id="process_to_out" style="edgeStyle=orthogonalEdgeStyle;endArrow=block;endFill=1;strokeColor=#374151;strokeWidth=2;" edge="1" parent="1" source="process" target="output"><mxGeometry relative="1" as="geometry"/></mxCell>
</root></mxGraphModel></diagram></mxfile>'''


def prepare(root):
    private = root / "private/sanity3"
    public = root / "inputs/sanity3"
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    public.mkdir(parents=True, exist_ok=True)
    gold = private / "gold.drawio"
    reference = public / "reference.png"
    gold.write_bytes(XML)
    command = [str(root / "renderer/venv/bin/python"),
               str(root / "source/operations/areal_dsh_rollout/render.py"),
               str(gold), str(reference), "--runtime", str(root / "renderer")]
    with (private / "render.json").open("w") as stdout, (private / "render.stderr").open("w") as stderr:
        result = subprocess.run(command, stdout=stdout, stderr=stderr, check=True, timeout=180)
    rendered = json.loads((private / "render.json").read_text())
    record = {"case_id": "sanity3", "source_kind": "synthetic_protocol_fixture",
              "real_collected_dataset_case": False, "quality_benchmark": False,
              "purpose": "Minimum native XML -> official render -> review protocol check",
              "generator_input": "reference.png only; source XML stays host-private",
              "business_nodes": 3, "native_vertices": rendered["vertices"],
              "native_edges": rendered["edges"], "dimensions": rendered["dimensions"],
              "gold_sha256": sha256(XML).hexdigest(),
              "reference_sha256": sha256(reference.read_bytes()).hexdigest(),
              "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "renderer": rendered, "render_exit": result.returncode}
    (private / "source.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
