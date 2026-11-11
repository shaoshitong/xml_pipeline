"""Reuse the offline pipeline editor and export a common page coordinate frame."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from math import ceil, floor, isfinite
from pathlib import Path

from PIL import Image

from arxiv_bulk_official_xml_png_math_v1 import CHROME, WAR, OfficialXmlPng


WAR_SHA = "44dd56958c8408963457dc98f04d2228408ac145c7aa1d8e6895d9c88d5e42aa"
NATIVE = Path(__file__).with_name("native.js").read_text()


def digest(blob):
    return sha256(blob).hexdigest()


def shared_frame(*snapshots):
    boxes = [s["bounds"] for s in snapshots if s is not None and s.get("bounds")]
    if not boxes:
        boxes = [[0, 0, 0, 0]]
    if any(not all(isfinite(v) for v in box) for box in boxes):
        raise ValueError("non-finite native page bounds")
    x0 = floor(min(b[0] for b in boxes)) - 12
    y0 = floor(min(b[1] for b in boxes)) - 12
    x1 = ceil(max(b[0] + b[2] for b in boxes)) + 12
    y1 = ceil(max(b[1] + b[3] for b in boxes)) + 12
    width, height = x1 - x0, y1 - y0
    scale = min(1, 2400 / max(width, height))
    return {"bounds": [x0, y0, width, height], "scale": scale,
            "dimensions": [ceil(width * scale), ceil(height * scale)]}


def project_box(box, transform):
    if box is None:
        return None
    x, y, w, h = box
    sx, sy = transform["offset"]
    scale = transform["scale"]
    return [round(x * scale + sx, 3), round(y * scale + sy, 3),
            round(w * scale, 3), round(h * scale, 3)]


@dataclass
class Render:
    image: Image.Image
    transform: dict
    unresolved: list

    @property
    def pixel_sha256(self):
        return digest(self.image.tobytes())


class Runtime:
    def __enter__(self):
        if digest(WAR.read_bytes()) != WAR_SHA:
            raise ValueError(f"draw.io WAR checksum differs from the pinned runtime: {WAR}")
        self.renderer = OfficialXmlPng()
        self.metadata = {"drawio_version": "32.6.1", "war_sha256": WAR_SHA,
                         "chromium": self.renderer.browser.version, "chromium_path": CHROME,
                         "device_scale_factor": 1}
        return self

    def __exit__(self, *args):
        self.renderer.close()

    def call(self, operation, xml, **options):
        page = self.renderer.page
        page.bring_to_front()
        return page.evaluate(NATIVE, {"operation": operation, "xml": xml, **options})

    def render(self, xml, frame, page_number=1):
        renderer = self.renderer
        renderer.blocked.clear()
        renderer.missing.clear()
        exported = self.call("render", xml, frame=frame, pageNumber=page_number)
        transform = exported["transform"]
        if (transform["pixel_ratio"], transform["view_scale"], transform["view_translate"]) != (1, 1, [0, 0]):
            raise ValueError("unexpected draw.io view scale, translation or browser pixel ratio")
        page = renderer.render_page
        page.bring_to_front()
        w, h = frame["dimensions"]
        page.set_viewport_size({"width": w + 2, "height": h + 2})
        page.set_content(
            '<html><head><meta http-equiv="Content-Security-Policy" content="'
            "default-src 'none'; style-src 'unsafe-inline'; "
            f"img-src data: {renderer.origin}; font-src data: {renderer.origin}; "
            f'base-uri {renderer.origin}"><base href="{renderer.origin}/"></head>'
            '<body style="margin:0;background:white">' + exported["svg"] + "</body></html>",
            wait_until="load", timeout=20000,
        )
        failed = page.evaluate("""async () => {
            const nodes = [...document.querySelectorAll("svg image, svg img")];
            const urls = [...new Set(nodes.map(node => node.getAttribute("href") ||
                node.getAttribute("xlink:href") || node.getAttribute("src")).filter(Boolean))];
            const failures = await Promise.all(urls.map(async url => {
                try {
                    const image = new Image();
                    image.src = url;
                    await image.decode();
                    return null;
                } catch {
                    return url.startsWith("data:") ? "embedded data asset" : url.split("?")[0];
                }
            }));
            await document.fonts.ready;
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            return failures.filter(Boolean);
        }""")
        png = page.locator("body > svg").first.screenshot(animations="disabled", timeout=20000)
        with Image.open(BytesIO(png)) as source:
            image = source.convert("RGB")
        if list(image.size) != frame["dimensions"]:
            raise ValueError(f"export dimensions {image.size} do not match shared frame {frame['dimensions']}")
        unresolved = sorted(set(failed + renderer.blocked + renderer.missing))
        return Render(image, transform, unresolved)
