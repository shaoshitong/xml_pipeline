import collections
import hashlib
import html
import json
import pathlib
import random
import shutil
import zipfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = pathlib.Path('/backup/shaoshitong/img2code_20261029')
INDEX = 'clean/research_pairs_catalog/snapshot_20261103T050123984464Z_v5_ce4384b8de20/pairs.jsonl'
INDEX_SHA = 'ff8be5a09c73f63b35c5e10fdf45c99101fb0b10ce128caf78fe1b2304e3bf43'
SEED = 20261102100
OUT = ROOT / 'clean/review_samples/random100_catalog3759_seed20261102100_v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    raw = (ROOT / INDEX).read_bytes()
    assert sha(raw) == INDEX_SHA
    population = [json.loads(line) for line in raw.splitlines()]
    assert len(population) == 3759
    selected = random.Random(SEED).sample(population, 100)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'pairs').mkdir(exist_ok=True)
    cards, records, thumbs = [], [], []
    groups = collections.Counter()
    for number, record in enumerate(selected, 1):
        folder = OUT / 'pairs' / f'{number:03d}'
        folder.mkdir(exist_ok=True)
        for key, filename, digest_key in [('image_file', 'image.png', 'image_sha256'), ('code_file', 'editable.drawio', 'code_sha256')]:
            source = ROOT / record[key]
            assert source.is_relative_to(ROOT)
            data = source.read_bytes()
            assert sha(data) == record[digest_key], (number, key)
            (folder / filename).write_bytes(data)
        with Image.open(folder / 'image.png') as source:
            rgba = source.convert('RGBA')
            white = Image.new('RGBA', rgba.size, 'white')
            white.alpha_composite(rgba)
            thumb = ImageOps.contain(white.convert('RGB'), (310, 210))
            thumbs.append(thumb)
        views = record['quality_views']
        group = 'arXiv' if any(v.startswith('arxiv') for v in views) else 'Scientific chart' if any(v.startswith('scientific_chart') for v in views) else 'Diagram / poster'
        groups[group] += 1
        sources = sorted(set(s.get('source') for s in record['source_records'] if s.get('source')))
        papers = sorted(set(s.get('paper') for s in record['source_records'] if s.get('paper')))
        records.append(dict(number=number, local_image=f'pairs/{number:03d}/image.png', local_code=f'pairs/{number:03d}/editable.drawio', **record))
        esc = html.escape
        cards.append(f'''<article data-group="{esc(group)}"><header>#{number:03d} · {esc(group)}</header><a href="pairs/{number:03d}/image.png" target="_blank"><img loading="lazy" src="pairs/{number:03d}/image.png"></a><footer>{esc(', '.join(sources + papers))}<details><summary>核验等级</summary>{esc(', '.join(views))}</details><a href="pairs/{number:03d}/image.png" target="_blank">查看原图</a> · <a href="pairs/{number:03d}/editable.drawio" download>下载可编辑文件</a></footer></article>''')
        if number % 25 == 0:
            print(json.dumps({'copied_pairs': number}, ensure_ascii=False), flush=True)
    manifest = dict(population=3759, sampled=100, sampling='uniform random without replacement; no visual filtering', seed=SEED, index=INDEX, index_sha256=INDEX_SHA, counts=dict(groups), records=records)
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17)
    except OSError:
        font = ImageFont.load_default()
    for page in range(4):
        sheet = Image.new('RGB', (1600, 1250), '#e9edf2')
        draw = ImageDraw.Draw(sheet)
        for cell, thumb in enumerate(thumbs[page * 25:(page + 1) * 25]):
            x, y = (cell % 5) * 320, (cell // 5) * 250
            draw.rectangle((x + 3, y + 3, x + 317, y + 247), fill='white')
            sheet.paste(thumb, (x + (320 - thumb.width) // 2, y + 5 + (210 - thumb.height) // 2))
            n = page * 25 + cell + 1
            vs = selected[n - 1]['quality_views']
            group = 'arXiv' if any(v.startswith('arxiv') for v in vs) else 'Chart' if any(v.startswith('scientific_chart') for v in vs) else 'Diagram/poster'
            draw.text((x + 10, y + 224), f'#{n:03d}  {group}', font=font, fill='#142333')
        sheet.save(OUT / f'overview_{page + 1}.jpg', quality=90)
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>100 对成品随机抽样</title><style>body{margin:0;background:#edf1f6;color:#172333;font:16px system-ui}main{max-width:1600px;margin:auto;padding:24px}h1{margin:0 0 12px}nav{position:sticky;top:0;background:#edf1f6ee;padding:12px 0;z-index:1}button{padding:9px 16px;margin-right:8px;border:1px solid #bcc8d5;border-radius:8px;background:white;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px}article{background:white;border-radius:12px;overflow:hidden}header,footer{padding:12px}header{font-weight:700}img{width:100%;height:330px;object-fit:contain;background:white}footer{font-size:13px;overflow-wrap:anywhere}details{margin:8px 0}a{color:#135fb3}p{line-height:1.6}</style><main><h1>100 对成品随机抽样</h1><p>从已冻结的 3759 对总库均匀无放回抽取；随机种子 20261102100；未按效果挑选或替换。点击图片查看原始分辨率，下载对应 drawio 文件可在 diagrams.net 打开。不同核验等级分别保留，作者源码重放不等于原始 PDF 保真。</p><p>COUNTS</p><nav><button onclick="filter('')">全部 100 对</button><button onclick="filter('Diagram / poster')">框图与海报</button><button onclick="filter('Scientific chart')">科学图表</button><button onclick="filter('arXiv')">arXiv</button><a href="manifest.json">抽样记录</a></nav><section class="grid">CARDS</section></main><script>function filter(g){document.querySelectorAll('article').forEach(e=>e.hidden=!!g&&e.dataset.group!==g)}</script></html>'''
    page = page.replace('COUNTS', html.escape(' · '.join(f'{k}: {v}' for k, v in groups.items()))).replace('CARDS', '\n'.join(cards))
    (OUT / 'index.html').write_text(page)
    archive = OUT.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for path in sorted(OUT.rglob('*')):
            if path.is_file():
                z.write(path, arcname=str(path.relative_to(OUT.parent)))
    receipt = dict(root=str(OUT), archive=str(archive), archive_bytes=archive.stat().st_size, archive_sha256=sha(archive.read_bytes()), counts=dict(groups), sampled=100, population=3759, seed=SEED)
    OUT.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
