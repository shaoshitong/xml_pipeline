"""Source-only exhaustive native XML inventory and fresh operational-family cohort.

No conversion, rendering, target quality scores, or model calls. Same-family
invariant collisions are conservatively merged; no independence beyond observed
source structure/provenance is claimed. All remaining supported rows form the
future native bulk population, including families excluded from heldout validation.
"""
import argparse
import collections
import hashlib
import importlib
import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
sys.path.insert(0, str(W / 'scripts'))
SEED = 'hkust-original-native-export-unseen-20261101-round4'


def raw(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def family(code):
    import compiler_types_source_ir_v1 as ir
    import compiler_validation_dot_ir_v2 as iso
    from native_worker import normalize
    from types import SimpleNamespace
    normalized,pages,_=normalize(code)
    if pages!=1:raise ValueError('native_multpage_source')
    root=ET.fromstring(normalized)
    for geometry in root.iter('mxGeometry'):
        for name in ('x','y','width','height'):
            if name in geometry.attrib:geometry.set(name,'N')
        for point in geometry.iter('mxPoint'):
            for name in ('x','y'):
                if name in point.attrib:point.set(name,'N')
    _,graph,evidence=ir.native(ET.tostring(root,encoding='unicode'),SimpleNamespace(expanded_xml=ET.fromstring))
    return 'native_observed_template_graph_v2:'+iso.invariant(graph),evidence



def rows(path):
    with path.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def prepare(output, inventory, frontend):
    if frontend != 'compiler_native_source_frontend_v1':
        raise ValueError('invalid_native_source_frontend')
    compiler = importlib.import_module(frontend)
    import compiler_validation_cluster_audit_v1 as provenance
    output.mkdir(parents=True, exist_ok=False)
    scope_path = R / 'release/fixed_batch_v1/initial_screen_20261031_1717/input_order.jsonl'
    scope = {x['id']: x for x in rows(scope_path) if x['format'] == 'drawio'}
    if len(scope) != 1539:
        raise ValueError('native_scope_changed')
    accepted = {x['id'] for x in rows(inventory / 'qualified.jsonl')}
    dev_path = R / 'release/compiler_types_audit_v1/source_only_20261101_v1/compiler_types_development_audit.jsonl'
    development = {x['id'] for x in rows(dev_path) if x['format'] == 'drawio'}
    registry = R / 'release/compiler_v1/validation_registry.sqlite'
    with sqlite3.connect('file:' + str(registry) + '?mode=ro', uri=True) as db:
        registry_keys = set(db.execute('select kind,value from reservation_keys'))
    development.update(identifier for kind, identifier in registry_keys if kind == 'id' and identifier in scope)
    excluded_codes = {value for kind, value in registry_keys if kind == 'code'}
    excluded_images = {value for kind, value in registry_keys if kind == 'image'}
    families, doc_keys, counters = set(), set(), collections.Counter()
    columns = ('id', 'category', 'format', 'source', 'input_record', 'input_manifest')
    db = sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True, timeout=30)
    def load(identifier):
        found = db.execute('select ' + ','.join(columns) + ' from jobs where id=?', (identifier,)).fetchone()
        if not found:
            raise ValueError('source_job_missing')
        job = dict(zip(columns, found))
        source = json.loads(job['input_record'])
        manifest = json.loads(job['input_manifest'])
        data = (R / manifest['source_code']).read_bytes()
        if sha(data) != source['code_sha256']:
            raise ValueError('original_source_hash_changed')
        return job, source, data.decode('utf-8-sig')
    try:
        for identifier in sorted(development):
            try:
                job, source, code = load(identifier)
                excluded_codes.add(source['code_sha256'])
                excluded_images.add(source['image_sha256'])
                f, _ = family(code)
                families.add(f)
                doc_keys.update(provenance.provenance(source, source['source']))
                counters['development_parsed'] += 1
            except Exception as error:
                counters['development_source_not_in_graph_grammar:' + type(error).__name__] += 1
        eligible = []
        seen_codes, seen_images, chosen_families, chosen_provenance = set(), set(), set(), set()
        # Frozen ordering depends on original ID only, before any target outcome.
        ordered = sorted((x for x in scope if x not in accepted), key=lambda x: sha(raw([SEED, x])))
        with (output / 'supported_population.jsonl').open('wb') as population, (output / 'source_audit.jsonl').open('wb') as audit:
            for identifier in ordered:
                item = dict(id=identifier, source_format='drawio')
                try:
                    job, source, code = load(identifier)
                    support = compiler.static_support(job)
                    if not support['supported']:
                        item.update(disposition='pending_unsupported_in_this_version', reason=support['reasons'])
                    else:
                        population.write(raw(dict(id=identifier, source=source, compiler_unit=compiler.UNIT)))
                        counters['supported_remaining_population'] += 1
                        f, evidence = family(code)
                        keys = set(provenance.provenance(source, source['source']))
                        item.update(family=f, source_evidence=evidence)
                        if identifier in development or source['code_sha256'] in excluded_codes or source['image_sha256'] in excluded_images:
                            item['disposition'] = 'development_or_reserved_identity_overlap'
                        elif f in families or keys & doc_keys:
                            item['disposition'] = 'development_or_reserved_family_provenance_overlap'
                        elif f in chosen_families or keys & chosen_provenance or source['code_sha256'] in seen_codes or source['image_sha256'] in seen_images:
                            item['disposition'] = 'duplicate_validation_family_provenance_or_identity'
                        else:
                            item['disposition'] = 'eligible_unseen_observed_family'
                            chosen_families.add(f)
                            chosen_provenance.update(keys)
                            seen_codes.add(source['code_sha256'])
                            seen_images.add(source['image_sha256'])
                            eligible.append(dict(id=identifier, source=source, compiler_unit=compiler.UNIT,
                                                 audit_cluster=f, cluster=f, cluster_keys=sorted({f} | keys)))
                except Exception as error:
                    item.update(disposition='pending_source_inventory_diagnosis', reason=str(error)[:600])
                counters[item['disposition']] += 1
                audit.write(raw(item))
        selected = eligible[:100]
        for seq, item in enumerate(selected, 1):
            item['seq'] = seq
            # Source and original baseline are bound without using its QA score.
            row = db.execute('select output_record from jobs where id=?', (item['id'],)).fetchone()
            item['source_record_sha256'] = sha((row[0] or '').encode())
            record = json.loads(row[0]) if row[0] else {}
            item.update(baseline_code_sha256=record.get('code_sha256'), baseline_image_sha256=record.get('image_sha256'))
        (output / 'selected.jsonl').write_bytes(b''.join(raw(x) for x in selected))
        config = compiler.configuration()
        method_files = [Path(__file__).resolve(), W/'scripts/compiler_types_source_ir_v1.py',
                        W/'scripts/compiler_validation_dot_ir_v2.py', W/'scripts/compiler_validation_cluster_audit_v1.py']
        summary = dict(schema='compiler_iteration_native_source_pool_v1', seed=SEED, compiler_unit=compiler.UNIT,
                       frontend_module=frontend, method_pins={str(p): sha(p.read_bytes()) for p in method_files},
                       source_only=True, conversion_or_rendering=False, model_calls=0, scope=1539,
                       excluded_accepted=len(accepted & set(scope)), counters=dict(counters),
                       development_ids=len(development), development_families=len(families),
                       eligible_observed_families=len(eligible), selected=len(selected),
                       all_remaining_observed_families_selected=len(selected) == len(eligible),
                       minimum100_met=len(selected) >= 100,
                       frozen_implementation=config, registry_modified=False,
                       limitations=['Observed source families do not prove hidden generator independence.',
                                    'Invariant collisions conservatively merge families.',
                                    'Source support is version-specific; rejected source remains pending.'],
                       files={name: dict(sha256=sha((output/name).read_bytes()), bytes=(output/name).stat().st_size)
                              for name in ('source_audit.jsonl', 'selected.jsonl', 'supported_population.jsonl')})
        (output / 'summary.json').write_bytes(raw(summary))
        print(json.dumps({k: v for k, v in summary.items() if k != 'frozen_implementation'}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--frontend', default='compiler_native_source_frontend_v1')
    a = p.parse_args()
    prepare(a.output, a.inventory, a.frontend)
