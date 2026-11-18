"""Render a candidate with the pinned official offline Draw.io editor."""

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree


def render(source: Path, output: Path, resources: Path, source_root: Path | None = None) -> dict:
    # The DSH bash sandbox keeps its session home read-only. Chrome crashpad
    # needs a writable config home even when browser crash reporting is off.
    keys = ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "TMPDIR")
    previous = {key: os.environ.get(key) for key in keys}
    # Chrome uses Unix sockets: a shared-storage TMPDIR may exceed sun_path.
    with tempfile.TemporaryDirectory(prefix="drawio-chrome-", dir="/tmp") as home:
        os.environ.update({key: home for key in keys})
        try:
            return render_editor(source, output, resources, source_root)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def render_editor(source: Path, output: Path, resources: Path, source_root: Path | None = None) -> dict:
    os.environ["FONTCONFIG_FILE"] = str(resources / "fonts.conf")
    os.environ["LD_LIBRARY_PATH"] = str(resources / "lib") + ":" + os.environ.get("LD_LIBRARY_PATH", "")
    conversion = (source_root or resources / "source") / "conversion"
    sys.path[:0] = [str(conversion / "drawio_compare"), str(conversion / "scripts")]
    import arxiv_bulk_official_xml_png_math_v1 as official
    import runtime

    war = resources / "draw.war"
    chrome = resources / "chrome-linux64" / "chrome"
    official.WAR = runtime.WAR = war
    official.CHROME = runtime.CHROME = str(chrome)
    xml = source.read_text()
    document = ElementTree.fromstring(xml)
    models = [document] if document.tag == "mxGraphModel" else document.iter("mxGraphModel")
    for model in models:
        counts = Counter(cell.get("id") for cell in model.iter("mxCell") if cell.get("id"))
        duplicates = [name for name, count in counts.items() if count > 1]
        if duplicates:
            raise ValueError("Duplicate mxCell IDs: " + ", ".join(duplicates[:10]))
    with runtime.Runtime() as editor:
        snapshot = editor.call("snapshot", xml, pageNumber=1)
        rendered = editor.render(xml, runtime.shared_frame(snapshot))
        if rendered.unresolved:
            raise ValueError(f"Unresolved Draw.io resources: {rendered.unresolved}")
        output.parent.mkdir(parents=True, exist_ok=True)
        rendered.image.save(output)
        return {
            **editor.metadata,
            "renderer": "official_drawio_Graph.getSvg",
            "fontconfig": str(resources / "fonts.conf"),
            "source_sha256": sha256(source.read_bytes()).hexdigest(),
            "png_sha256": sha256(output.read_bytes()).hexdigest(),
            "pixel_sha256": rendered.pixel_sha256,
            "dimensions": list(rendered.image.size),
            "vertices": sum(cell["kind"] == "vertex" for cell in snapshot["cells"]),
            "edges": sum(cell["kind"] == "edge" for cell in snapshot["cells"]),
            "unresolved": rendered.unresolved,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.source, args.output, args.runtime, args.source_root), sort_keys=True))


if __name__ == "__main__":
    main()
