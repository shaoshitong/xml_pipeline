#!/usr/bin/env python3
"""HKUST3 CPU-only QA and triplet materialization for local draw.io sources.

Input sources are staged from Mac but all rendering, PDF compilation and QA run
on HKUST3. Original source files are copied byte-for-byte into each accepted
pair; failures remain in the audit area and never enter the dataset index.
"""
from __future__ import annotations
import argparse, concurrent.futures, datetime, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image

R = Path('/backup/shaoshitong/img2code_20261029')
RENDER = R / 'evaluation' / 'remote_render.py'

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b): return hashlib.sha256(b).hexdigest()
def jwrite(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp.' + str(os.getpid()))
    t.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
    os.replace(t, p)

def pdf_from_svg(svg: Path, out: Path):
    from playwright.sync_api import sync_playwright
    text = svg.read_text()
    with sync_playwright() as p:
        opts = {'headless': True, 'args': ['--disable-dev-shm-usage']}
        exes = sorted(Path.home().joinpath('.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'))
        if exes: opts['executable_path'] = str(exes[-1])
        b = p.chromium.launch(**opts)
        page = b.new_page(viewport={'width': 8192, 'height': 8192})
        page.set_content('<!doctype html><html><head><style>html,body{margin:0;padding:0;background:white;-webkit-print-color-adjust:exact;print-color-adjust:exact}body>svg{display:block}</style></head><body>'+text+'</body></html>', wait_until='load')
        page.evaluate('document.fonts.ready')
        box = page.locator('body>svg').bounding_box()
        if not box or box['width'] <= 0 or box['height'] <= 0: raise ValueError('empty_svg')
        page.set_viewport_size({'width': int(box['width']) + 2, 'height': int(box['height']) + 2})
        page.add_style_tag(content=f'@page{{size:{box["width"]}px {box["height"]}px;margin:0}}')
        page.pdf(path=str(out), width=f'{box["width"]}px', height=f'{box["height"]}px',
                 prefer_css_page_size=True, margin={'top':'0','right':'0','bottom':'0','left':'0'},
                 print_background=True, display_header_footer=False, scale=1)
        b.close()
    return {'width': box['width'], 'height': box['height']}

def pdf_check(pdf: Path, png: Path):
    info = subprocess.check_output(['pdfinfo', str(pdf)], text=True, timeout=30)
    if 'Pages:           1' not in info and 'Pages:          1' not in info:
        raise ValueError('pdf_not_single_page')
    stem = pdf.parent / (pdf.stem + '.pdfcheck')
    subprocess.run(['pdftoppm','-singlefile','-r','96','-png',str(pdf),str(stem)],
                   check=True, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    with Image.open(png) as a, Image.open(stem.with_suffix('.png')) as b:
        if a.width <= 0 or a.height <= 0 or b.width <= 0 or b.height <= 0:
            raise ValueError('empty_image')
        # PDF rasterization may differ in font antialiasing, but dimensions must
        # remain the same page and foreground must not disappear.
        if abs(a.width - b.width) > 4 or abs(a.height - b.height) > 4:
            raise ValueError(f'pdf_page_size_mismatch:{a.size}:{b.size}')
    (stem.parent / (stem.name + '.png')).unlink(missing_ok=True)
    return {'pdfinfo_pages': 1, 'pdf_raster_dimensions_match': True}

def process(row, source_root: Path, audit: Path, delivery: Path):
    rel = Path(row['relative_to_documents'])
    src = source_root / rel
    code_sha = row['code_sha256']
    pid = 'local-' + code_sha[:32]
    work = audit / 'work' / pid
    out = delivery / pid
    proof_path = audit / 'proofs' / (pid + '.json')
    if proof_path.exists():
        old = json.loads(proof_path.read_text())
        if old.get('accepted') and all((out / k).is_file() for k in ('diagram.drawio','diagram.png','diagram.pdf')):
            return old
    rec = {'id': pid, 'source_relative_to_documents': str(rel), 'code_sha256': code_sha,
           'prefilter_score': row.get('prefilter_score'), 'CPU_host': 'HKUST3', 'accepted': False,
           'started_utc': now()}
    try:
        raw = src.read_bytes()
        if sha(raw) != code_sha: raise ValueError('source_sha256_mismatch')
        root = ET.fromstring(raw.decode('utf-8-sig'))
        if root.tag not in ('mxfile','mxGraphModel'): raise ValueError('not_drawio_root')
        if len(root.findall('.//diagram')) != 1: raise ValueError('requires_one_page')
        if row.get('prefilter_score', -999) < 25: raise ValueError('prefilter_below_quality_floor')
        work.mkdir(parents=True, exist_ok=True)
        source = work / 'source.drawio'; source.write_bytes(raw)
        cmd = [sys.executable, str(RENDER), '--kind','drawio','--source',str(source),
               '--width','8192','--height','8192','--allow-embedded-raster']
        run = subprocess.run(cmd, text=True, capture_output=True, timeout=240)
        render_json = work / 'render.json'
        if run.returncode != 0 or not render_json.is_file():
            raise ValueError('renderer_failed:' + run.stderr[-1000:])
        render = json.loads(render_json.read_text())
        rec['render'] = render
        if not render.get('ok'): raise ValueError('render_not_ok')
        if render.get('browser_trace'): raise ValueError('browser_trace:' + json.dumps(render['browser_trace'])[:1000])
        outside = bool(render.get('content_outside_declared_canvas'))
        png = work / ('render.tight.png' if outside else 'render.png')
        svg = work / 'render.svg'
        if not png.is_file() or not svg.is_file(): raise ValueError('render_artifact_missing')
        with Image.open(png) as im:
            im.verify()
            rec['image_pixels'] = {'width': im.width, 'height': im.height, 'sha256': sha(png.read_bytes())}
        pdf = work / 'diagram.pdf'
        if outside:
            # The official viewer provides a tight diagnostic when author page
            # bounds are stale. Preserve all pixels in a lossless one-page PDF;
            # the editable source remains the original drawio XML.
            im = Image.open(png).convert('RGB'); rawpix = im.tobytes(); import zlib
            data = zlib.compress(rawpix, 3); w, h = im.size; pw, ph = w*72/96, h*72/96
            content = f'q {pw:.4f} 0 0 {ph:.4f} 0 0 cm /I Do Q\n'.encode()
            objs = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                    f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw:.4f} {ph:.4f}] /Resources << /XObject << /I 4 0 R >> >> /Contents 5 0 R >>'.encode(),
                    f'<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} >>\nstream\n'.encode()+data+b'\nendstream',
                    f'<< /Length {len(content)} >>\nstream\n'.encode()+content+b'endstream']
            buf=bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'); offs=[0]
            for i,obj in enumerate(objs,1): offs.append(len(buf)); buf.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
            xref=len(buf); buf.extend(f'xref\n0 {len(objs)+1}\n0000000000 65535 f \n'.encode())
            for pos in offs[1:]: buf.extend(f'{pos:010d} 00000 n \n'.encode())
            buf.extend(f'trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()); pdf.write_bytes(buf)
            rec['pdf']={'renderer':'lossless_tight_viewer_raster_fallback','width':w,'height':h}
        else:
            rec['pdf'] = pdf_from_svg(svg, pdf)
        rec['pdf'].update(pdf_check(pdf, png)); rec['tight_view_used'] = outside
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, out / 'diagram.drawio')
        shutil.copyfile(png, out / 'diagram.png')
        shutil.copyfile(pdf, out / 'diagram.pdf')
        rec.update({'accepted': True, 'finished_utc': now(),
                    'artifacts': {k: {'sha256': sha((out/k).read_bytes()), 'bytes': (out/k).stat().st_size}
                                  for k in ('diagram.drawio','diagram.png','diagram.pdf')}})
    except Exception as exc:
        rec.update({'finished_utc': now(), 'error': type(exc).__name__ + ':' + str(exc)[:3000]})
    jwrite(proof_path, rec)
    return rec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--source-root', type=Path, required=True)
    ap.add_argument('--output-root', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=8)
    args = ap.parse_args()
    audit = args.output_root / 'audit'; delivery = args.output_root / 'pairs'
    rows = [json.loads(x) for x in args.manifest.read_text().splitlines() if x.strip()]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = [ex.submit(process, r, args.source_root, audit, delivery) for r in rows]
        for i, f in enumerate(concurrent.futures.as_completed(futs), 1):
            try: rec = f.result()
            except Exception as exc: rec = {'accepted': False, 'error': type(exc).__name__+':'+str(exc)}
            results.append(rec)
            print(json.dumps({'completed': i, 'total': len(rows), 'id': rec.get('id'),
                              'accepted': rec.get('accepted'), 'error': rec.get('error')}, ensure_ascii=False), flush=True)
    results.sort(key=lambda r: r.get('id',''))
    accepted = [r for r in results if r.get('accepted')]
    index = args.output_root / 'accepted_local_pairs.jsonl'
    index.write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True)+'\n' for r in accepted))
    summary = {'at_utc': now(), 'CPU_host': 'HKUST3', 'candidates': len(rows),
               'accepted': len(accepted), 'rejected': len(rows)-len(accepted),
               'accepted_pairs_file': str(index), 'delivery_root': str(delivery),
               'triplet_contract': ['diagram.drawio','diagram.pdf','diagram.png']}
    jwrite(args.output_root / 'current.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)

if __name__ == '__main__': main()
