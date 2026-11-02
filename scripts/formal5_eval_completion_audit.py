"""Read-only audit of five existing img2code results and three gold calibrations.

No model, renderer, plotting program, raw session payload or credentials are
opened/executed. Only selected artifact bytes are hashed; transcript/log files
receive existence/size checks. SDK tar headers are listed without extraction.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import time
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True

SPECS = {
 'line_chart': {'directory': 'baseline_native_20261029/line_chart/pass2', 'ext': 'py', 'kind': 'python', 'budget': 20000, 'reasoning': 'max', 'workflow': 'two_turns_one_feedback', 'report_index': 1, 'report_label': '曲线图'},
 'scatter_chart': {'directory': 'scatter_rescue_20261029/scatter_chart/pass2', 'ext': 'py', 'kind': 'python', 'budget': 32768, 'reasoning': 'max', 'workflow': 'two_turns_one_feedback', 'report_index': 2, 'report_label': '散点图'},
 'framework_simple': {'directory': 'baseline_xml_20261029/framework_simple/pass2', 'ext': 'drawio', 'kind': 'drawio', 'budget': 32768, 'reasoning': 'max', 'workflow': 'two_turns_one_feedback', 'report_index': 3, 'report_label': '简单论文框图'},
 'framework_complex': {'directory': 'toolloop_high_20261029/framework_complex/final', 'ext': 'drawio', 'kind': 'drawio', 'budget': 65536, 'reasoning': 'high', 'workflow': 'file_and_render_tool_loop', 'report_index': 4, 'report_label': '复杂论文框图'},
 'academic_poster': {'directory': 'academic_poster_high_20261029/academic_poster/pass2', 'ext': 'html', 'kind': 'html', 'budget': 65536, 'reasoning': 'high', 'workflow': 'two_turns_one_feedback', 'report_index': 5, 'report_label': '学术海报'}}
METRIC_KEYS = ('ssim_resized', 'mae_resized_0_1', 'foreground_iou_resized', 'reference_size', 'render_size')


def rounded_equal(literal, actual):
    try:
        value = float(literal); actual = float(actual)
        if not math.isfinite(value) or not math.isfinite(actual): return False
        digits = len(str(literal).partition('.')[2])
        return abs(value - actual) <= .5 * 10 ** (-digits) + 1e-12
    except (ValueError, TypeError): return False


def metric_equal(left, right):
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isfinite(float(left)) and math.isfinite(float(right)) and abs(float(left) - float(right)) <= 1e-11
    return left == right


def numeric_fields(value, prefix=''):
    output = {}
    if isinstance(value, dict):
        for key, child in value.items():
            name = prefix + '.' + key if prefix else key
            if isinstance(child, (int, float)) and not isinstance(child, bool): output[name] = child
            elif isinstance(child, dict): output.update(numeric_fields(child, name))
    return output


class Audit:
    def __init__(self, root):
        self.root = root.resolve(); self.issues = []; self.unknown = []; self.checks = collections.Counter()
        self.hash_cache = {}; self.hashed_bytes = 0; self.expected_hash_checks = 0

    def issue(self, code, context, **metadata):
        self.issues.append({'code': code, 'context': context, **metadata})

    def require(self, condition, code, context, **metadata):
        self.checks['passed' if condition else 'failed'] += 1
        if not condition: self.issue(code, context, **metadata)
        return bool(condition)

    def path(self, value, base=None):
        try:
            path = Path(value)
            path = path if path.is_absolute() else (base or self.root) / path
            resolved = path.resolve()
            if not resolved.is_relative_to(self.root): raise ValueError('outside_root')
            return resolved
        except (OSError, ValueError, TypeError):
            self.issue('path_outside_or_invalid_task_scope', 'artifact_path'); return None

    def rel(self, path):
        return str(path.relative_to(self.root))

    def json(self, path, required=True):
        path = self.path(path)
        if path is None: return {}
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 ** 2: raise ValueError('invalid_json_file')
            result = json.loads(path.read_text())
            if not isinstance(result, dict): raise ValueError('expected_object')
            return result
        except (OSError, ValueError):
            if required: self.issue('metadata_missing_or_invalid', self.rel(path))
            return {}

    def file(self, path, expected_sha=None, expected_bytes=None, hash_bytes=True, required=True):
        path = self.path(path)
        if path is None: return {'present': False}
        record = {'path': self.rel(path), 'present': False}
        try:
            if path.is_symlink() or not path.is_file(): raise OSError('not_regular_file')
            before = path.stat(); record.update(present=True, bytes=before.st_size)
            if required: self.require(before.st_size > 0, 'empty_required_artifact', self.rel(path))
            if expected_bytes is not None: self.require(before.st_size == expected_bytes, 'artifact_size_mismatch', self.rel(path), expected=expected_bytes, observed=before.st_size)
            if hash_bytes or expected_sha:
                key = (str(path), before.st_size, before.st_mtime_ns)
                if key not in self.hash_cache:
                    digest = hashlib.sha256()
                    with path.open('rb') as stream:
                        for block in iter(lambda: stream.read(1024 ** 2), b''): digest.update(block)
                    self.hash_cache[key] = digest.hexdigest(); self.hashed_bytes += before.st_size
                record['sha256'] = self.hash_cache[key]
                after = path.stat()
                self.require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'artifact_changed_during_hash', self.rel(path))
            if expected_sha:
                self.expected_hash_checks += 1
                record['historical_expected_sha256_available'] = True
                record['matches_expected_sha256'] = self.require(record.get('sha256') == expected_sha, 'artifact_hash_mismatch', self.rel(path), expected=expected_sha, observed=record.get('sha256'))
            else: record['historical_expected_sha256_available'] = False
        except (OSError, ValueError):
            if required: self.issue('artifact_missing_or_unreadable', self.rel(path))
        return record

    def png(self, path, expected_size=None):
        from PIL import Image
        record = self.file(path)
        if not record.get('present'): return record
        try:
            with Image.open(self.path(path)) as image:
                size = list(image.size); image.verify()
            record['image_dimensions'] = size
            if expected_size is not None: self.require(size == expected_size, 'image_dimensions_mismatch', record['path'], expected=expected_size, observed=size)
        except (OSError, ValueError, SyntaxError): self.issue('image_decode_or_crc_failed', record['path'])
        return record

    def archive(self, path, expected=None, generated_files=None):
        expected = expected or {}; record = self.file(path, expected.get('sha256'), expected.get('bytes'))
        if not record.get('present'): return record
        if expected.get('path'): self.require(self.path(expected['path']) == self.path(path), 'archive_manifest_path_mismatch', record['path'])
        record.update(session_payload_headers=0, session_payload_header_bytes=0, regular_members=0, symlink_headers_not_followed=0, extracted=False, session_payload_opened=False)
        try:
            with tarfile.open(self.path(path), 'r:*') as package:
                regular = {}
                for index, member in enumerate(package):
                    if index >= 50000: raise ValueError('archive_header_limit')
                    if member.issym() or member.islnk(): record['symlink_headers_not_followed'] += 1
                    if not member.isfile(): continue
                    record['regular_members'] += 1
                    parts = tuple(part for part in PurePosixPath(member.name).parts if part != '.')
                    if '..' in parts or PurePosixPath(member.name).is_absolute(): raise ValueError('archive_path_escape')
                    regular['/'.join(parts)] = member
                    if 'sessions' in parts and parts[-1].startswith('session.') and '.jsonl' in parts[-1] and member.size > 0:
                        record['session_payload_headers'] += 1; record['session_payload_header_bytes'] += member.size
                for name, current in (generated_files or {}).items():
                    member = regular.get(name)
                    if not self.require(member is not None, 'generated_archive_member_missing', record['path'], artifact_name=name): continue
                    digest = hashlib.sha256()
                    # These are selected generated source/image artifacts, never
                    # a session member, response or transcript body.
                    with package.extractfile(member) as stream:
                        for chunk in iter(lambda: stream.read(1024 ** 2), b''): digest.update(chunk)
                    self.require(digest.hexdigest() == current.get('sha256'), 'generated_archive_artifact_mismatch', record['path'], artifact_name=name)
            record['tar_headers_valid'] = True
        except (OSError, ValueError, tarfile.TarError):
            record['tar_headers_valid'] = False; self.issue('archive_headers_invalid', record['path'])
        if generated_files is None: self.require(record['session_payload_headers'] > 0, 'raw_session_payload_header_missing', record['path'])
        return record

    def metrics(self, actual, recorded, context):
        for key in METRIC_KEYS:
            value = actual.get(key)
            valid = (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)) if key not in {'reference_size', 'render_size'} else (isinstance(value, list) and len(value) == 2 and all(isinstance(n, int) and n > 0 for n in value))
            self.require(valid and key in recorded and metric_equal(value, recorded.get(key)), 'metric_metadata_mismatch', context + '.' + key)


def xml_editability(path):
    data = path.read_bytes()
    if len(data) > 2 * 1024 ** 2 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper(): raise ValueError('unsupported_xml_document')
    tree = ET.fromstring(data)
    cells = [node for node in tree.iter() if node.tag.rsplit('}', 1)[-1] == 'mxCell']
    edges = [node for node in cells if node.get('edge') == '1']
    return {'editable_vertices': sum(node.get('vertex') == '1' for node in cells),
            'xml_edges': len(edges), 'edges_missing_source_or_target': sum(not node.get('source') or not node.get('target') for node in edges)}


def audit_cases(audit, semantic, report):
    root = audit.root; evaluation = root / 'evaluation'; results = {}
    audit.require(semantic.get('mode') == 'formal5', 'wrong_semantic_summary_mode', 'formal5_semantic_summary')
    audit.require(set(semantic.get('cases', {})) == set(SPECS), 'formal_case_set_mismatch', 'formal5_semantic_summary')
    for case, spec in SPECS.items():
        final = evaluation / spec['directory']; parent = final.parent; context = 'case.' + case
        summary = audit.json(parent / 'summary.json'); render = audit.json(final / 'render.json')
        sem = semantic.get('cases', {}).get(case, {}); outputs = sem.get('outputs', [])
        selected = outputs[-1] if outputs and isinstance(outputs[-1], dict) else {}
        final_semantic = selected.get('semantic', {}) or {}
        prediction = final / ('prediction.' + spec['ext'])
        result = {'directory': audit.rel(final), 'prediction': audit.file(prediction),
                  'render_metadata': audit.file(final / 'render.json'), 'render_ok': render.get('ok'),
                  'metrics': {key: render.get('metrics', {}).get(key) for key in METRIC_KEYS},
                  'controller_gold_source_accessed': summary.get('gold_source_accessed')}
        audit.require(render.get('ok') is True, 'final_render_not_successful', context)
        audit.require(render.get('kind') == spec['kind'], 'final_render_kind_mismatch', context)
        audit.require(summary.get('id') == case, 'run_case_id_mismatch', context)
        audit.require(summary.get('provider') == 'deepseek-account', 'provider_mismatch', context)
        audit.require(summary.get('gold_source_accessed') is False, 'controller_gold_access_declaration_missing', context)
        audit.require(audit.path(sem.get('selected_final_directory', '')) == final, 'selected_final_path_mismatch', context)
        audit.require(audit.path(selected.get('source_directory', '')) == final, 'semantic_output_path_mismatch', context)
        audit.require(audit.path(selected.get('prediction_code', '')) == prediction and selected.get('prediction_present') is True, 'semantic_prediction_binding_mismatch', context)
        gold_code = root / 'cases' / case / ('ground_truth.' + spec['ext'])
        result['gold_code'] = audit.file(gold_code)
        audit.require(audit.path(sem.get('gold_code', '')) == gold_code and sem.get('format') == spec['ext'], 'semantic_gold_or_format_binding_mismatch', context)
        audit.require(selected.get('render', {}).get('ok') is True, 'stored_semantic_render_not_successful', context)
        audit.require(audit.path(render.get('source', '')) == prediction and audit.path(render.get('output', '')) == final / 'render.png', 'render_source_or_output_binding_mismatch', context)
        audit.metrics(render.get('metrics', {}), selected.get('render', {}).get('metrics', {}), context + '.formal_render')
        result['render_image'] = audit.png(final / 'render.png', render.get('metrics', {}).get('render_size'))
        if render.get('viewer_bundle_sha256'): result['viewer_bundle'] = audit.file(evaluation / 'assets/viewer-static.min.js', render['viewer_bundle_sha256'])
        reference = audit.path(summary.get('reference_image', ''))
        expected_reference = root / 'cases' / case
        if audit.require(reference is not None and reference.parent == expected_reference, 'reference_outside_frozen_case', context):
            case_meta = audit.json(parent / 'case.json', required=case != 'framework_complex')
            expected_ref_sha = case_meta.get('reference_sha256')
            if not expected_ref_sha and case in {'framework_simple', 'framework_complex', 'academic_poster'}:
                manifest = audit.json(evaluation / 'dataset_gold_validation' / case / 'input_manifest.json')
                expected_ref_sha = next((item.get('sha256') for item in manifest.get('files', []) if item.get('role') == 'reference'), None)
            audit.require(bool(expected_ref_sha), 'reference_expected_hash_missing', context)
            result['reference'] = audit.file(reference, expected_ref_sha)
            result['reference_image'] = audit.png(reference, render.get('metrics', {}).get('reference_size'))
            if case_meta:
                audit.require(audit.path(case_meta.get('image_path', '')) == reference, 'case_reference_binding_mismatch', context)
        configuration = sem.get('configuration', {})
        observed_effort = summary.get('reasoning_effort', summary.get('reasoning'))
        for key, expected in [('reasoning', spec['reasoning']), ('per_call_output_budget', spec['budget']), ('workflow', spec['workflow'])]:
            audit.require(configuration.get(key) == expected, 'recorded_configuration_mismatch', context + '.' + key, expected=expected, observed=configuration.get(key))
        audit.require(observed_effort == spec['reasoning'], 'run_reasoning_mismatch', context, expected=spec['reasoning'], observed=observed_effort)
        config_match = re.search(re.escape(spec['report_label']) + r'\s+(Max|High)/(\d+)', report)
        audit.require(config_match is not None and config_match.group(1).lower() == spec['reasoning'] and int(config_match.group(2)) == spec['budget'], 'report_configuration_mismatch', context)
        result['configuration'] = {'recorded': configuration, 'run_effort': observed_effort,
                                  'report_matches_recorded_configuration': bool(config_match and int(config_match.group(2)) == spec['budget']),
                                  'runtime_budget_echo': None, 'runtime_budget_enforcement_status': 'unverified_not_echoed_in_saved_initialize_ack'}
        audit.unknown.append({'code': 'runtime_budget_echo_not_recorded', 'context': context,
                              'note': 'The saved initialize acknowledgment contains serverInfo, not maxTokens. Recorded formal test settings are consistent; independent SDK/API enforcement is not inferred.'})
        metrics = render.get('metrics', {})
        paragraph_match = re.search(r'(?m)^' + str(spec['report_index']) + r'\.\s*([^\n]+)', report)
        paragraph = paragraph_match.group(1) if paragraph_match else ''
        score_match = re.search(r'最终 SSIM\s*([0-9.]+)', paragraph)
        audit.require(score_match is not None and rounded_equal(score_match.group(1), metrics.get('ssim_resized')), 'report_model_ssim_mismatch', context)
        if case != 'framework_complex':
            pass_summary = audit.json(final / 'summary.json'); audit.metrics(metrics, pass_summary.get('render', {}).get('metrics', {}), context + '.pass_summary')
            passes = summary.get('passes', [])
            audit.require(len(passes) == 2, 'two_turn_workflow_record_mismatch', context)
            if passes: audit.metrics(metrics, passes[-1].get('render', {}).get('metrics', {}), context + '.run_final_pass')
            result['historical_first_pass'] = {'render_ok': passes[0].get('render', {}).get('ok') if passes else None,
                                               'token_limit_reached': passes[0].get('token_limit_reached') if passes else None}
            result['raw_log_presence'] = {name: audit.file(path, hash_bytes=False) for name, path in [('final_events', final / 'events.jsonl'), ('final_response', final / 'response.txt'), ('all_events', parent / 'all_events.jsonl')]}
        else:
            audit.metrics(metrics, summary.get('final_render', {}).get('metrics', {}), context + '.run_final_render')
            audit.require(summary.get('artifact_exists') is True, 'fulltool_artifact_not_recorded', context)
            result['agent_loop'] = {'tool_call_count': summary.get('tool_call_count'), 'wall_seconds': summary.get('wall_seconds'),
                                    'render_tool_call_count': sum('render_drawio_on_hkust' in str(name) for name in summary.get('observed_tool_calls', [])),
                                    'environment_failure': summary.get('environment_failure'), 'token_limit_reached': summary.get('token_limit_reached')}
            audit.require(summary.get('tool_call_count') == 23 and result['agent_loop']['render_tool_call_count'] == 3, 'reported_tool_loop_count_mismatch', context)
            reported_duration = re.search(r'High 工具迭代约\s*(\d+)\s*分\s*(\d+)\s*秒', report)
            reported_seconds = (int(reported_duration.group(1)) * 60 + int(reported_duration.group(2))) if reported_duration else None
            result['agent_loop']['report_rounded_seconds'] = reported_seconds
            audit.require(isinstance(summary.get('wall_seconds'), (int, float)) and reported_seconds is not None and abs(summary['wall_seconds'] - reported_seconds) <= .5, 'reported_tool_loop_duration_mismatch', context)
            result['raw_log_presence'] = {name: audit.file(parent / name, hash_bytes=False) for name in ('events.jsonl', 'response.txt')}
        archives = summary.get('verified_remote_archives', {})
        sdk_expected = archives.get('sdk_session', {})
        result['session_archive'] = audit.archive(parent / 'sdk_session.tar.gz', sdk_expected)
        if not sdk_expected: audit.unknown.append({'code': 'historical_sdk_archive_digest_not_persisted', 'context': context, 'note': 'A current archive hash and nonempty raw-session TAR header are checked. No historical expected archive SHA is invented.'})
        if case == 'framework_complex':
            audit.require(bool(sdk_expected.get('sha256')) and bool(archives.get('generated_workspace', {}).get('sha256')), 'persisted_archive_hashes_missing', context)
            uploaded = {name: audit.file(final / name) for name in summary.get('uploaded_generated_files', []) if name in {'prediction.drawio', 'render_01.png', 'render_02.png', 'render_03.png'}}
            result['generated_workspace_archive'] = audit.archive(parent / 'generated_workspace.tar.gz', archives.get('generated_workspace'), uploaded)
        if spec['ext'] == 'drawio':
            try:
                editability = xml_editability(prediction); result['independent_xml_structure'] = editability
                for key, actual in editability.items(): audit.require(final_semantic.get('prediction', {}).get(key) == actual, 'stored_xml_structure_mismatch', context + '.' + key)
                expected_edges = 9 if case == 'framework_simple' else 12
                audit.require(editability['xml_edges'] == expected_edges and editability['edges_missing_source_or_target'] == expected_edges, 'reported_unbound_edge_count_mismatch', context)
                if case == 'framework_simple':
                    labels = final_semantic.get('text_labels', {})
                    audit.require(labels.get('matched') == 10 and labels.get('gold_count') == 10, 'reported_simple_label_count_mismatch', context)
                else: audit.require(editability['editable_vertices'] == 56, 'reported_complex_vertex_count_mismatch', context)
            except (OSError, ValueError, ET.ParseError): audit.issue('selected_xml_structure_unreadable', context)
        elif case == 'line_chart':
            aggregate = final_semantic.get('aggregate', {})
            result['numeric_diagnostics'] = {'mean_matched_line_normalized_rmse': aggregate.get('mean_matched_line_normalized_rmse')}
            audit.require(metric_equal(aggregate.get('mean_matched_line_normalized_rmse'), 0.), 'reported_line_rmse_mismatch', context)
        elif case == 'scatter_chart':
            aggregate = final_semantic.get('aggregate', {})
            result['numeric_diagnostics'] = {key: aggregate.get(key) for key in ('gold_scatter_points', 'prediction_scatter_points')}
            audit.require(aggregate.get('gold_scatter_points') == 2250 and aggregate.get('prediction_scatter_points') == 3000, 'reported_scatter_point_count_mismatch', context)
        elif case == 'academic_poster':
            for label, key in [('MAE', 'mae_resized_0_1'), ('前景 IoU', 'foreground_iou_resized')]:
                match = re.search(re.escape(label) + r'\s*([0-9.]+)', paragraph)
                audit.require(match is not None and rounded_equal(match.group(1), metrics.get(key)), 'report_poster_metric_mismatch', context + '.' + key)
            elements = render.get('native_editable_elements', {})
            result['poster_structure'] = {key: elements.get(key) for key in ('htmlTextElements', 'svgTextElements', 'svgVectorElements')}
            audit.require(all(elements.get(key) == expected for key, expected in [('htmlTextElements', 48), ('svgTextElements', 108), ('svgVectorElements', 584)]), 'reported_poster_element_count_mismatch', context)
            dom_path = root / 'evaluation/academic_poster_high_20261029/text_diagnostics.json'
            dom = audit.json(dom_path)
            result['poster_dom_diagnostic_file'] = audit.file(dom_path)
            result['poster_dom_word_f1_evidence'] = {key: dom.get(key) for key in ('provided_html_text_words', 'prediction_html_text_words', 'word_f1')}
            f1_match = re.search(r'词级 F1\s*([0-9.]+)', paragraph)
            count_match = re.search(r'标准 DOM\s*(\d+)\s*词、生成 DOM\s*(\d+)\s*词', paragraph)
            audit.require(f1_match is not None and rounded_equal(f1_match.group(1), dom.get('word_f1')), 'reported_poster_dom_f1_mismatch', context)
            audit.require(count_match is not None and [int(count_match.group(1)), int(count_match.group(2))] == [dom.get('provided_html_text_words'), dom.get('prediction_html_text_words')], 'reported_poster_dom_word_count_mismatch', context)
        results[case] = result
    return results


def audit_gold(audit, report, model_results):
    root = audit.root; base = root / 'evaluation/dataset_gold_validation'; summary = audit.json(base / 'summary.json')
    audit.require(summary.get('ok') is True and summary.get('no_model_calls') is True and summary.get('original_inputs_modified') is False, 'gold_summary_status_mismatch', 'gold_calibration')
    cases = {item.get('case'): item for item in summary.get('cases', []) if isinstance(item, dict)}
    expected_cases = {'framework_simple', 'framework_complex', 'academic_poster'}
    audit.require(set(cases) == expected_cases, 'gold_case_set_mismatch', 'gold_calibration')
    result = {}
    for case in sorted(expected_cases):
        directory = base / case; manifest = audit.json(directory / 'input_manifest.json'); render = audit.json(directory / 'render.json'); item = cases.get(case, {}); context = 'gold.' + case
        audit.require(manifest.get('case') == case and manifest.get('no_model_calls') is True, 'gold_manifest_status_mismatch', context)
        audit.require(item.get('ok') is True and render.get('ok') is True and item.get('originals_unchanged') is True, 'gold_render_status_mismatch', context)
        process = item.get('process', {})
        audit.require(process.get('timed_out') is False and process.get('returncode') == 0, 'gold_render_process_status_mismatch', context)
        files = manifest.get('files', []); role_counts = collections.Counter(entry.get('role') for entry in files)
        audit.require(role_counts.get('source') == 1 and role_counts.get('reference') == 1 and role_counts.get('asset', 0) == (19 if case == 'academic_poster' else 0), 'gold_input_role_count_mismatch', context)
        file_checks = []
        for entry in files:
            original = audit.path(entry.get('original', '')); copy = audit.path(entry.get('copy', ''), directory)
            if not audit.require(original is not None and original.is_relative_to(root / 'cases' / case) and copy is not None and copy.is_relative_to(directory), 'gold_input_path_scope_mismatch', context): continue
            expected = entry.get('sha256'); audit.require(isinstance(expected, str) and bool(re.fullmatch('[0-9a-f]{64}', expected)), 'gold_input_hash_missing', context)
            file_checks.append({'role': entry.get('role'), 'original': audit.file(original, expected, entry.get('bytes')), 'frozen_copy': audit.file(copy, expected, entry.get('bytes'))})
        renderer = audit.path(manifest.get('existing_renderer', ''))
        renderer_check = audit.file(renderer, manifest.get('existing_renderer_sha256')) if renderer is not None else None
        viewer_check = audit.file(root / 'evaluation/assets/viewer-static.min.js', render['viewer_bundle_sha256']) if render.get('viewer_bundle_sha256') else None
        audit.metrics(render.get('metrics', {}), item.get('metrics', {}), context + '.summary_render')
        audit.require(metric_equal(item.get('baseline_ssim'), render.get('metrics', {}).get('ssim_resized')), 'gold_baseline_ssim_mismatch', context)
        audit.require(item.get('blocked_resource_request_count') == 0 and not render.get('blocked_resource_requests'), 'gold_blocked_resources_present', context)
        audit.require(not item.get('content_outside_declared_canvas') and not item.get('content_outside_viewport'), 'gold_capture_clipping_present', context)
        record = {'inputs': file_checks, 'renderer': renderer_check, 'viewer_bundle': viewer_check, 'reference_size': manifest.get('reference_size'),
                  'baseline_ssim': item.get('baseline_ssim'), 'render_image': audit.png(directory / 'render.png', render.get('metrics', {}).get('render_size')),
                  'asset_count': role_counts.get('asset', 0), 'blocked_resource_request_count': item.get('blocked_resource_request_count')}
        row_label = {'framework_simple': '简单框图', 'framework_complex': '复杂框图', 'academic_poster': '学术海报'}[case]
        row_match = re.search(r'(?m)^\s*\|?\s*' + row_label + r'\s*\|\s*([0-9.]+)\s*\|\s*([^|\n]+)\|\s*([0-9.]+)', report)
        audit.require(row_match is not None and rounded_equal(row_match.group(1), item.get('baseline_ssim')) and rounded_equal(row_match.group(3), model_results.get(case, {}).get('metrics', {}).get('ssim_resized')), 'report_calibration_table_mismatch', context)
        if case != 'academic_poster':
            crop = render.get('graph_bounds_content_crop_diagnostic') or {}; summary_crop = item.get('graph_bounds_content_crop_diagnostic') or {}
            audit.require(crop.get('ok') is True and metric_equal(crop.get('declared_page_bounds_coverage'), 1.), 'gold_crop_coverage_mismatch', context)
            audit.require(metric_equal(crop.get('baseline_ssim'), summary_crop.get('baseline_ssim')), 'gold_crop_summary_mismatch', context)
            crop_path = audit.path(crop.get('output', ''))
            record['crop'] = {'baseline_ssim': crop.get('baseline_ssim'), 'coverage': crop.get('declared_page_bounds_coverage'),
                              'image': audit.png(crop_path, crop.get('metrics', {}).get('render_size')) if crop_path is not None else None}
            audit.require(row_match is not None and rounded_equal(row_match.group(2).strip(), crop.get('baseline_ssim')), 'report_crop_ssim_mismatch', context)
        else: audit.require(item.get('missing_image_count') == 0, 'gold_poster_missing_images', context)
        result[case] = record
    return result


def main(args):
    started = time.monotonic(); audit = Audit(args.root); root = audit.root
    report_path = audit.path(args.report or root / 'reports/img2code_evaluation_zh.txt')
    report_info = audit.file(report_path, args.expected_report_sha256) if report_path else {'present': False}
    try: report = report_path.read_text() if report_path else ''
    except (OSError, ValueError): report = ''
    semantic = audit.json(root / 'evaluation/formal5_semantic_summary.json')
    cases = audit_cases(audit, semantic, report)
    gold = audit_gold(audit, report, cases)
    markers = {'heterogeneous_not_uniform': '不同预算' in report and '不构成统一' in report,
               'gold_xml_error_not_all_model': '不能全部归因于模型' in report or '不能把模型的全部像素误差归因于模型' in report,
               'unbound_edges_not_all_visual_arrows_wrong': '不能直接解释为所有视觉箭头均画错' in report,
               'binding_editability_limitation': '可编辑性缺陷' in report and '未绑定节点' in report,
               'ssim_not_semantic_acceptance': '不能替代文字、数值和图拓扑验收' in report,
               'poster_dom_not_full_ocr': '不能把它称为完整 OCR 准确率' in report,
               'budgets_not_native_model_caps': '并非模型原生上限' in report}
    for name, present in markers.items(): audit.require(present, 'report_scope_caveat_missing', name)
    out = {'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'read_only': True,
           'audit_scope': 'Five fixed selected DeepSeek final results, their known task archives, formal5 stored semantic metadata and three frozen gold calibrations. No dataset/model/renderer execution or transcript/credential content access.',
           'ok': not audit.issues, 'ok_definition': 'Required selected artifacts, stored render/semantic/report consistency and all available expected hashes pass. Explicit unknown checks below are not marked verified.',
           'checks': dict(audit.checks), 'mismatches': audit.issues, 'unverified_checks': audit.unknown,
           'report': report_info, 'report_scope_markers': markers, 'cases': cases, 'gold_calibration': gold,
           'hash_verification': {'unique_file_versions_hashed': len(audit.hash_cache), 'bytes_hashed': audit.hashed_bytes,
                                 'comparisons_with_persisted_expected_sha256': audit.expected_hash_checks,
                                 'note': 'Unmanifested output digests are current snapshots, not historical immutability proofs. Raw transcript and response files are only checked for presence/size; SDK session payloads are not opened.'},
           'limitations': ['Output budgets are recorded test settings; saved initialize acknowledgments do not independently echo maxTokens, so SDK/API budget enforcement is unverified.',
                          'Persisted image/semantic metrics are checked for consistency, not recomputed. No extra model, plotting capture or render is run.',
                          'Different budgets/workflows are not a uniform benchmark. Supplied XML/HTML references may be reconstructions or templates rather than original-author gold.',
                          'Low reference-XML SSIM limits attribution of model pixel error. Similar gold/model SSIM does not prove equivalent meaning or topology.',
                          'Missing source/target bindings support an editability limitation; floating edges can be intentional and do not by themselves prove visually wrong arrows.',
                          'Poster DOM word F1 excludes text embedded in raster assets and is not full-image OCR accuracy.',
                          'Harness global defaults/account model limits and unrelated ~/.dsh workspaces are outside this artifact audit.'],
           'seconds': round(time.monotonic() - started, 3)}
    print(json.dumps(out, ensure_ascii=False, allow_nan=False), flush=True)
    return 0 if not audit.issues else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--report', type=Path); parser.add_argument('--expected-report-sha256')
    raise SystemExit(main(parser.parse_args()))
