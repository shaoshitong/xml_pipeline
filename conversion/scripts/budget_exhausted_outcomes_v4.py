"""Full historical-budget pass excluding validator/runtime faults as verdicts."""
import argparse, collections, json, sqlite3
from budget_exhausted_outcomes_v2 import ROOT, prepare as prior_prepare, apply, now
from budget_exhausted_outcomes_v3 import candidates


def validator_fault(failures):
    for failure in failures:
        if not isinstance(failure, str):
            continue
        if failure.startswith('source_coverage_failure: '):
            try:
                issues = json.loads(failure[len('source_coverage_failure: '):])
            except (ValueError, TypeError):
                return True
            if not isinstance(issues, list):
                return True
            if any(isinstance(issue, dict) and issue.get('reason') == 'source_profile_validation_error' for issue in issues):
                return True
        if any(token in failure for token in ('KeyError(', 'AttributeError(', 'NameError(', 'outside_page_pixel_audit')):
            return True
    return False


def prepare(db, identifier, policy):
    plan, reason = prior_prepare(db, identifier, policy)
    if plan is not None and validator_fault(plan['evidence']['failed_qa_reasons']):
        return None, 'validator_interface_error_requires_program_recovery'
    return plan, reason


def main(publish=False):
    work = ROOT / 'conversion'
    db = sqlite3.connect(work / 'jobs.sqlite', timeout=60)
    owner_bytes = (work / 'auto_quality_owner.json').read_bytes()
    policy = json.loads(owner_bytes)['policy']
    ids = candidates(work / 'model_history_ledger_v1/at_least_two_unqualified.json')
    rows = []
    for identifier in ids:
        assert (work / 'auto_quality_owner.json').read_bytes() == owner_bytes, 'Quality coordinator changed; re-plan.'
        plan, reason = prepare(db, identifier, policy)
        state = apply(db, plan, publish) if plan else 'pending_or_previously_recorded'
        rows.append({'id': identifier, 'state': state, 'reason': reason, 'evidence': plan['evidence'] if plan else None})
    result = {'at': now(), 'policy': policy, 'publish': publish, 'history_ids_examined': len(ids), 'model_calls': 0, 'jobs_queues_source_files_or_history_modified': False, 'records': rows, 'counts': dict(collections.Counter(row['state'] for row in rows)), 'goal_complete': False}
    (work / 'budget_exhausted_outcomes_v4_latest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true')
    main(parser.parse_args().publish)
