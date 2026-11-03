"""Publish baseline-relative complex pairs and measured throughput, no new QA.

Only accepts existing successful official native source-replay proofs, verifies
payload hashes and original editable structure, and deduplicates exact code +
decoded RGBA. A root visual-policy approval is required before publication;
unreviewed candidates are reported separately and never inflate accepted counts.
"""
from pathlib import Path
import argparse
import collections
import datetime
import fcntl
import hashlib
import io
import json
import os
import signal
import sqlite3
import struct
import sys
import time

from PIL import Image

R = Path('/backup/shaoshitong/img2code_20261029')
P = R / 'clean/arxiv_research_figures_v1'
D = P / 'goal500_progress_v1'
BASELINE = R / 'clean/accepted_3759_v1/pairs.jsonl'
BASELINE_SHA = '913624deb45c1f9b0e72bc25ba0c7b643700e7566e00ac27237f11ed7eb639f2'
S = R / 'conversion/scripts'
sys.path.insert(0, str(S))
from priority_source_complexity_filter_v1 import native, classify

STOP = False
VALUE_POLICY = dict(version='method_framework_and_dense_scientific_composite_v1', native_graph_rules='unchanged_priority_source_complexity_filter_v1', composite_min_vertices=60, composite_min_distinct_labels=20, composite_min_label_characters=400, composite_min_images=4, dialogue_only_and_story_example_panels_not_method_frameworks=True, native_pages=1, reference_or_QA_thresholds_changed=False)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def put(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n')
    os.replace(tmp, path)


def key(row):
    image = row['image_pixels']
    return (row['code_sha256'], image['width'], image['height'], image['rgba_sha256'])


def pixels(blob):
    with Image.open(io.BytesIO(blob)) as im:
        rgba = im.convert('RGBA')
        return dict(width=rgba.width, height=rgba.height, rgba_sha256=sha(struct.pack('>QQ', rgba.width, rgba.height) + rgba.tobytes()))


def snapshot():
    D.mkdir(exist_ok=True)
    value_policy = D / 'value_policy.json'
    if not value_policy.exists():
        put(value_policy, VALUE_POLICY)
    assert json.loads(value_policy.read_text()) == VALUE_POLICY
    b = BASELINE.read_bytes()
    assert sha(b) == BASELINE_SHA
    baseline = [json.loads(line) for line in b.splitlines()]
    assert len(baseline) == len({key(row) for row in baseline}) == 3759
    baseline_keys = {key(row) for row in baseline}
    baseline_exact_bytes = {(row['code_sha256'], row['image_sha256']) for row in baseline}
    cachefile = D / 'verified_pair_cache.json'
    cache = json.loads(cachefile.read_text()) if cachefile.exists() else {}
    sources = [P / 'author_native_source_replay_v1/published_source_replay_v2/source_replay_aligned.jsonl', P / 'author_native_source_replay_incremental_v1/author_native_source_replay.jsonl', P / 'math_source_replay_v1/author_native_math_source_replay.jsonl', P / 'math_viewport_source_replay_v1/author_native_math_source_replay.jsonl', P / 'stable_export_source_replay_v1/author_native_math_source_replay.jsonl', P / 'direct_author_XML_source_replay_v1/author_native_source_replay.jsonl']
    rows = [json.loads(line) for path in sources if path.exists() for line in path.read_text().splitlines()]
    selected, all_new = {}, {}
    errors, statuses = [], collections.Counter()
    held_composites = 0
    pdf_registry = P / 'original_PDF_reference_audit_v2/paired_registered_original_PDF.jsonl'
    pdf_matches = {(r['code_sha256'], r['image_sha256']): r for r in map(json.loads, pdf_registry.read_text().splitlines())} if pdf_registry.exists() else {}
    for row in rows:
        if (row['code_sha256'], row['image_sha256']) in baseline_exact_bytes:
            continue  # Already frozen and fully hashed in the retained baseline.
        cache_key = 'dimensions_prefixed_RGBA_v1:' + row['code_sha256'] + ':' + row['image_sha256']
        try:
            code, image = R / row['code_file'], R / row['image_file']
            assert code.resolve().is_relative_to(R / 'clean') and image.resolve().is_relative_to(R / 'clean')
            ids = [list((p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns)) for p in [code, image]]
            cached = cache.get(cache_key)
            if cached is None or cached['file_identities'] != ids:
                code_bytes, image_bytes = code.read_bytes(), image.read_bytes()
                assert sha(code_bytes) == row['code_sha256'] and sha(image_bytes) == row['image_sha256']
                observed = pixels(image_bytes)
                features = native(code_bytes.decode('utf-8-sig'))
                status, reasons = classify(features, 'drawio', {})
                if features['native_pages'] != 1:
                    status, reasons = 'structure_review', ['multi_page_source']
                cached = dict(file_identities=ids, image_pixels=observed, features=features, status=status, reasons=reasons)
                cache[cache_key] = cached
            current = dict(row, image_pixels=cached['image_pixels'])
            k = key(current)
            if k in baseline_keys:
                continue
            all_new[k] = current
            statuses[cached['status']] += 1
            if cached['status'] != 'complex_candidate':
                continue
            proof_file = row.get('native_replay_proof')
            if proof_file:
                proof = (R / proof_file).read_bytes()
                assert sha(proof) == row['native_replay_proof_sha256']
                actual = json.loads(proof)
                assert actual['ok'] and actual['source_official_PNG_sha256'] == row['image_sha256']
            else:
                # Frozen earlier products are already part of the preserved baseline.
                raise ValueError('missing_incremental_official_replay_proof')
            f = cached['features']
            graph = (f['source_backed_logical_nodes'] >= 20 and f['connected_edges'] >= 15 and f['label_characters'] >= 200 and not f['directed_chain_only']) or (f['source_backed_logical_nodes'] >= 30 and f['label_characters'] >= 200) or (f['source_backed_logical_nodes'] >= 12 and f['connected_edges'] >= 12 and f['native_connected_groups'] >= 2 and f['label_characters'] >= 250)
            if not graph and not (f['native_vertices'] >= 60 and f['distinct_owner_labels'] >= 20 and f['label_characters'] >= 400 and f['image_objects'] >= 4):
                held_composites += 1
                continue
            current.update(goal500_pair_id=sha(json.dumps(k).encode()), curation_view='complex_native_framework' if graph else 'labeled_source_image_composite', curation_features=f, quality_views=['arxiv_author_native_source_replay'], original_PDF_fidelity=row.get('original_PDF_fidelity', 'review_not_certified'), scientific_value_individually_certified=False)
            matched_pdf = pdf_matches.get((row['code_sha256'], row.get('auxiliary_preexisting_native_PNG_sha256')))
            if matched_pdf and row.get('fresh_RGBA_equals_preexisting_native_PNG') is True:
                raw_ids = set(row.get('raw_source_pair_ids', [row.get('raw_source_pair_id')]))
                if raw_ids & {a.get('source_PDF_sha256') for a in matched_pdf.get('source_aliases', [])}:
                    current['quality_views'].append('arxiv_registered_original_PDF_visual_v2')
                    current['original_PDF_fidelity'] = 'qualified_registered_original_PDF_visual_v2'
                    current['original_PDF_reference_record'] = matched_pdf
            current['official_validated_image_mtime_epoch'] = image.stat().st_mtime
            selected[k] = current
        except Exception as error:
            errors.append(dict(id=row.get('id'), reason=type(error).__name__ + ':' + str(error)))
    put(cachefile, cache)
    ordered = sorted(selected.values(), key=lambda r: r['goal500_pair_id'])
    (D / 'selected_pending_visual_policy_review.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in ordered))
    approval_path = D / 'value_policy_approval.json'
    approval = json.loads(approval_path.read_text()) if approval_path.exists() else {}
    accepted = ordered if approval.get('approved') and approval.get('source_filter_sha256') == sha((S / 'priority_source_complexity_filter_v1.py').read_bytes()) and approval.get('value_policy_sha256') == sha(value_policy.read_bytes()) else []
    if accepted:
        excluded = set(approval.get('excluded_goal500_ids', []))
        accepted = [r for r in accepted if r['goal500_pair_id'] not in excluded]
        # Scientific value is reviewed per figure, never inferred for future rows
        # merely because a structural policy passed on an earlier contact sheet.
        reviewed = set(approval.get('reviewed_accepted_goal500_ids', []))
        accepted = [r for r in accepted if r['goal500_pair_id'] in reviewed]
        accepted = [dict(r, scientific_value_individually_certified=True,
                         scientific_value_review=approval.get('review_evidence')) for r in accepted]
    manifest = D / 'accepted_new_pairs.jsonl'
    manifest.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in accepted))
    unified = D / 'baseline_plus_accepted_new.jsonl'
    unified.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in baseline + accepted))
    connection = sqlite3.connect((P / 'recent_ai_source_expansion_v2/once.sqlite').as_uri() + '?mode=ro', uri=True, timeout=10)
    paper_states = dict(connection.execute("select status,count(*) from papers where json_extract(record,'$.metadata.discovery')='official_OAI_PMH_arXivRaw' group by status"))
    connection.close()
    guard = json.loads((P / 'transport_performance_v3/resource_guard_v1/state.json').read_text())
    policy = json.loads((P / 'oai_direct_pipeline_v1/policy.json').read_text())
    measurement = dict(epoch=time.time(), at_utc=now(), baseline=3759, new_complex_accepted=len(accepted), new_complex_selected_pending_review=len(ordered) - len(accepted), new_technical_pairs=len(all_new), curation_states=dict(statuses), new_paper_states=paper_states, phase_source_network_bytes=max(0, guard['observed_payload_bytes'] - policy['initial_cumulative_network_bytes']), cumulative_source_budget_used_bytes=guard['observed_payload_bytes'], cumulative_source_budget_limit_bytes=guard['network_payload_limit_bytes'], source_errors=len(errors), goal_target=500, goal_complete=False)
    cluster = P / 'cluster_direct_v1'
    if (cluster / 'transition.json').exists() and (cluster / 'progress.json').exists():
        transition = json.loads((cluster / 'transition.json').read_text())
        progress = json.loads((cluster / 'progress.json').read_text())
        measurement['phase_network_budget_charged_bytes'] = measurement['phase_source_network_bytes']
        measurement['phase_source_network_bytes'] = max(0, transition['budget_used_before'] - policy['initial_cumulative_network_bytes']) + progress['source_bytes_actually_received']
        measurement['network_measurement_protocol'] = 'old_single_node_body_counter_plus_cluster_actual_body_counter_v1'
        measurement['cluster_network_budget_is_conservative_reservation'] = True
        measurement['cluster_jobs'] = progress['jobs']
    measurement.update(held_dialogue_or_nondense_composites=held_composites, accepted_by_quality_view=dict(collections.Counter(v for r in accepted for v in r['quality_views'])), quality_views_overlap=True)
    origin_file = D / 'measurement_origin.json'
    if not origin_file.exists():
        launch = json.loads((P / 'oai_direct_pipeline_v1/launch.json').read_text())
        put(origin_file, dict(at_utc=launch['at_utc'], epoch=datetime.datetime.fromisoformat(launch['at_utc']).timestamp(), note='First sustained DIRECT launch. Predating this launch is baseline-relative backlog, excluded from production rate.'))
    origin = json.loads(origin_file.read_text())['epoch']
    window_start = max(origin, measurement['epoch'] - 1800)
    produced = sum(window_start <= r['official_validated_image_mtime_epoch'] <= measurement['epoch'] for r in accepted)
    elapsed = measurement['epoch'] - window_start
    measurement.update(production_window_seconds=elapsed, accepted_products_generated_in_window=produced, measured_production_pairs_per_hour=produced * 3600 / elapsed if elapsed > 0 else None, measured_production_seconds_per_pair=elapsed / produced if produced else None, accepted_preexisting_since_frozen_baseline=sum(r['official_validated_image_mtime_epoch'] < origin for r in accepted))
    history = D / 'speed_measurements.jsonl'
    previous = [json.loads(line) for line in history.read_text().splitlines()] if history.exists() else []
    candidates = [m for m in previous if m['epoch'] >= measurement['epoch'] - 1800 and m.get('network_measurement_protocol') == measurement.get('network_measurement_protocol')]
    if candidates:
        first = candidates[0]
        delta = measurement['new_complex_accepted'] - first['new_complex_accepted']
        elapsed = measurement['epoch'] - first['epoch']
        measurement.update(speed_window_seconds=elapsed, accepted_pairs_gained_in_window=delta, accepted_pairs_per_hour=delta * 3600 / elapsed if elapsed > 0 else None, measured_seconds_per_accepted_pair=elapsed / delta if delta > 0 else None, measured_source_bytes_per_second=(measurement['phase_source_network_bytes'] - first['phase_source_network_bytes']) / elapsed if elapsed > 0 else None)
    with history.open('a') as output:
        output.write(json.dumps(measurement, sort_keys=True) + '\n')
    put(D / 'errors.json', errors)
    put(D / 'current.json', dict(accepted_new_pairs=dict(file=str(manifest.relative_to(R)), rows=len(accepted), sha256=sha(manifest.read_bytes())), unified_pairs=dict(file=str(unified.relative_to(R)), rows=3759 + len(accepted), sha256=sha(unified.read_bytes())), measurement=measurement, approval_required_before_counting=True, random100_preview_required_for_final_goal_acceptance=True))
    put(D / 'speed.json', measurement)
    print(json.dumps(measurement), flush=True)
    return measurement


def main(watch):
    global STOP
    D.mkdir(exist_ok=True)
    lock = (D / 'publisher.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda *_: globals().__setitem__('STOP', True))
    while True:
        snapshot()
        if not watch or STOP:
            break
        for _ in range(60):
            if STOP:
                break
            time.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true')
    main(parser.parse_args().watch)
