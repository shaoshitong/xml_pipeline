"""Validate a frozen full-source audit's exhaustive shortage exception.

This changes cohort size only. The 20% / +5 / zero-regression quality gate
remains fixed, even when fewer than five independent families remain.
"""

def validate(info, selected):
    count=len(selected)
    if count<1 or count>100 or info.get('selected')!=count:
        raise ValueError('empty_or_inconsistent_source_cohort')
    if len({row['id'] for row in selected})!=count:
        raise ValueError('duplicate_source_cohort_original')
    if len({row['cluster'] for row in selected})!=count:
        raise ValueError('duplicate_source_cohort_component')
    if [row.get('seq') for row in selected]!=list(range(1,count+1)):
        raise ValueError('source_cohort_order_changed')
    if count<100:
        scope=info.get('full_scope_manifest') or {}
        if not (info.get('source_only') is True and info.get('scope')==26754
                and scope.get('unique_scope')==131904 and scope.get('duplicate_scope_rows')==0
                and scope.get('manifest_sha256')=='361bce924762d14481da9b541cfbcf0f6879f97618fbc750922ac1c918a70a85'
                and info.get('eligible_observed_families')==count
                and info.get('all_remaining_observed_families_selected') is True
                and info.get('unknown_families_retained_in_bulk') is True):
            raise ValueError('short_source_cohort_not_proven_exhaustive')
    elif info.get('minimum100_met') is not True:
        raise ValueError('full_source_cohort_not_declared_complete')
    return dict(actual_samples=count,shortage_exhaustive_exception=count<100,
                eligible_observed_families=info.get('eligible_observed_families'),
                all_remaining_observed_families_selected=info.get('all_remaining_observed_families_selected'),
                independent_source_components=count,
                fixed_minimum_qualified_fraction=.20,fixed_minimum_new_qualified=5,
                no_gate_change=True)
