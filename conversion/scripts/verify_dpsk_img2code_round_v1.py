"""Offline round verifier for the five-case image-to-native-draw.io pilot."""
from collections import Counter
from html.parser import HTMLParser
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

import numpy as np
from PIL import Image, ImageOps
from skimage.metrics import structural_similarity

from arxiv_author_native_assets_v1 import inventory, models
from arxiv_bulk_official_xml_png_math_v1 import OfficialXmlPng, R


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Label(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)


def label(value):
    parser = Label()
    parser.feed(value or '')
    parser.close()
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', ' '.join(parser.text))).strip().casefold()


def graph(model):
    cells = {}
    for outer in model.find('root'):
        c = outer if outer.tag == 'mxCell' else outer.find('mxCell')
        if c is None:
            continue
        cid = outer.get('id') or c.get('id')
        if not cid or cid in cells:
            raise ValueError('missing_or_duplicate_cell_id')
        cells[cid] = (c, label(outer.get('label') or c.get('value')))
    if '0' not in cells or '1' not in cells:
        raise ValueError('missing_graph_root_or_default_layer')
    counts = Counter()
    labels, edges = Counter(), Counter()
    for cid, (c, text) in cells.items():
        vertex, edge = c.get('vertex') == '1', c.get('edge') == '1'
        if text and (vertex or edge):
            labels[text] += 1
        counts['vertices'] += int(vertex)
        counts['edges'] += int(edge)
        if vertex or edge:
            visited, parent = {cid}, c.get('parent')
            if parent is None:
                counts['invalid_parent_chain'] += 1
            while parent:
                if parent in visited or parent not in cells:
                    counts['invalid_parent_chain'] += 1
                    break
                visited.add(parent)
                parent = cells[parent][0].get('parent')
        if vertex:
            g = c.find('mxGeometry')
            if g is None or any(not math.isfinite(float(g.get(k, '0'))) for k in ('x', 'y', 'width', 'height')):
                counts['invalid_vertex_geometry'] += 1
        if edge:
            src, dst = c.get('source'), c.get('target')
            if src in cells and dst in cells and all(cells[n][0].get('vertex') == '1' for n in (src,dst)):
                counts['bound_edges'] += 1
                if cells[src][1] and cells[dst][1]:
                    edges[(cells[src][1], cells[dst][1])] += 1
            elif src is not None and src not in cells or dst is not None and dst not in cells:
                counts['dangling_edge_references'] += 1
            else:
                counts['unbound_or_partially_bound_edges'] += 1
    counts['labels'] = sum(labels.values())
    counts['labelled_endpoint_edges'] = sum(edges.values())
    return counts, labels, edges


def visual(reference, candidate):
    def on_white(im):
        im = im.convert('RGBA')
        bg = Image.new('RGBA', im.size, 'white')
        bg.alpha_composite(im)
        return bg.convert('RGB')

    a, b = [on_white(x) for x in (reference, candidate)]
    # Scale uniformly by target width (or height for a portrait target). The
    # origin stays top-left; no stretch or similarity-maximizing registration.
    axis = int(a.height > a.width)
    def scaled(im):
        factor = 768 / im.size[axis]
        size = tuple(max(1, min(4096, round(n*factor))) for n in im.size)
        if any(n*factor > 4096 for n in im.size):
            raise ValueError('candidate_aspect_ratio_exceeds_metric_canvas')
        return im.resize(size, Image.Resampling.LANCZOS)
    sa, sb = scaled(a), scaled(b)
    w, h = max(sa.width, sb.width, 7), max(sa.height, sb.height, 7)
    def canvas(im):
        frame = Image.new('RGB', (w,h), 'white')
        frame.paste(im,(0,0))
        return np.array(frame)
    x,y = canvas(sa),canvas(sb)
    fa,fb = np.any(x < 225,axis=2),np.any(y < 225,axis=2)
    union = fa|fb
    local = []
    for r in range(3):
        for c in range(3):
            sl = (slice(r*h//3,(r+1)*h//3),slice(c*w//3,(c+1)*w//3))
            n = int(union[sl].sum())
            if n:
                local.append({'row':r+1,'col':c+1,'foreground_iou':round(float((fa[sl]&fb[sl]).sum()/n),4)})
    return dict(target_dimensions=a.size, candidate_dimensions=b.size,
                relative_aspect_error=abs((b.width/b.height)/(a.width/a.height)-1),
                ssim=structural_similarity(x,y,channel_axis=2,data_range=255),
                foreground_iou=float((fa&fb).sum()/max(1,union.sum())),
                foreground_rgb_mae_255=float(np.abs(x.astype('int16')-y)[union].mean()) if union.any() else 0,
                worst_tiles=sorted(local,key=lambda d:d['foreground_iou'])[:3],
                registration='one uniform scale per tight export along target dominant axis; top-left aligned; white padding')


def overlap(expected, actual):
    gold, pred, match = sum(expected.values()), sum(actual.values()), sum((expected&actual).values())
    return dict(gold=gold, predicted=pred, matched=match,
                precision=match/pred if pred else None, recall=match/gold if gold else None,
                f1=2*match/(gold+pred) if gold+pred else None)


def run(args):
    candidate = args.code.read_bytes()
    ref = args.reference.read_bytes()
    if digest(ref) != args.image_sha256:
        raise ValueError('target_hash_mismatch')
    _, pages, refs, *_ = inventory(candidate)
    if len(pages)!=1 or refs:
        raise ValueError('requires_single_page_and_no_image_or_external_assets')
    for node in pages[0].iter():
        for value in node.attrib.values():
            if re.search(r'data\s*:|<\s*(?:img|iframe|script|object)\b|shape\s*=\s*image', value, re.I):
                raise ValueError('image_or_active_content_disallowed_in_this_pilot')
    counts, labels, edges = graph(pages[0])
    fail = ['invalid_parent_chain','invalid_vertex_geometry','dangling_edge_references']
    if not counts['vertices'] or any(counts[k] for k in fail):
        raise ValueError('invalid_native_graph:'+str(dict(counts)))
    if not args.compare_only:
        renderer = OfficialXmlPng()
        try:
            render = renderer.render(candidate.decode('utf-8-sig'), args.out)
        finally:
            renderer.close()
        with Image.open(args.reference) as a, Image.open(args.out/'official.png') as b:
            metrics = visual(a,b)
        return dict(native_gate=True, visual_diagnostic_only=True, code_sha256=digest(candidate),
                    target_sha256=digest(ref), graph=dict(counts), render=render, visual=metrics)
    gold = args.gold.read_bytes()
    if digest(gold) != args.gold_sha256:
        raise ValueError('gold_code_hash_mismatch')
    gold_pages = models(gold)[1]
    if len(gold_pages)!=1:
        raise ValueError('multi_page_gold_unsupported')
    gc, gl, ge = graph(gold_pages[0])
    return dict(byte_equal=candidate==gold, gold_graph=dict(gc), candidate_graph=dict(counts),
                normalized_exact_label_multiset=overlap(gl,labels),
                explicit_labelled_directed_edge_multiset=overlap(ge,edges),
                caveat='XML comparison uses native labels and explicit edges only; free endpoints, graphic text and grouping differ across implementations. Not a graph-equivalence proof.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--code', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--image-sha256', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--gold', type=Path)
    p.add_argument('--gold-sha256')
    p.add_argument('--compare-only', action='store_true')
    args = p.parse_args()
    try:
        result = run(args)
    except Exception as e:
        result = dict(native_gate=False,error_type=type(e).__name__,error=str(e)[:1500])
    args.out.mkdir(parents=True,exist_ok=True)
    name = 'gold_diagnostic.json' if args.compare_only else 'feedback.json'
    (args.out/name).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='render'},ensure_ascii=False),flush=True)
