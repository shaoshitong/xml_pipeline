"""Pure metadata-only source component closure and deterministic fresh selection.

All records, including unsupported, accepted, live and foreign-format bridges,
participate. Store only components touching the target scope, but retain every
foreign member and key of each such component. Unknown members forbid an
independence claim. Requests are supplied separately as full canonical records.
"""
import copy
import hashlib
import json
from compiler_validation_identity_alias_v1 import normalize_keys, request_keys

POLICY = 'full_scope_sealed_metadata_components_fresh_exclusions_v1'


def raw(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def build_components(records, target_ids):
    targets=set(target_ids);parent=[];seen={};items=[];identifiers=set()
    def find(index):
        while parent[index] != index:
            parent[index]=parent[parent[index]];index=parent[index]
        return index
    for record in records:
        request=record.get('request') or {};identifier=record.get('id') or request.get('id')
        if not identifier or identifier in identifiers:
            raise ValueError('sealed_source_record_missing_or_duplicate_ID')
        identifiers.add(identifier)
        pairs=[('hard_cluster',key)for key in record['keys']]
        pairs.append(('id',identifier))
        source=request.get('source') or record.get('source')
        if source:
            pairs.extend([('code',source['code_sha256']),('image',source['image_sha256'])])
        keys=normalize_keys(pairs);index=len(parent);parent.append(index)
        for key in keys:
            if key in seen:
                a,b=find(index),find(seen[key]);parent[max(a,b)]=min(a,b)
            else:
                seen[key]=index
        items.append((identifier,keys,record.get('known') is True))
    if not targets <= identifiers:
        raise ValueError('sealed_full_source_scope_missing_target_ids')
    grouped={}
    for index,(identifier,keys,known)in enumerate(items):
        group=grouped.setdefault(find(index),dict(ids=[],keys=set(),known=True))
        group['ids'].append(identifier);group['keys'].update(keys);group['known'] &= known
    components=[]
    for group in grouped.values():
        own=sorted(targets & set(group['ids']))
        if not own:continue
        keys=sorted(group['keys']);component='sealed_source_component_v1:'+sha(raw(keys))
        components.append(dict(component=component,component_all_ids=sorted(group['ids']),
                               target_ids=own,keys=[list(key)for key in keys],known=group['known']))
    return dict(schema=POLICY,full_scope_records=len(items),target_records=len(targets),
                full_components=len(grouped),components=sorted(components,key=lambda x:x['component']))


def select(components, requests, exclusion_keys, *, seed, limit=100):
    """Select once per known component; no pixels, scores or failure reasons."""
    blocked=set(tuple(key)for key in exclusion_keys);by_id={r['id']:r for r in requests}
    if len(by_id) != len(requests):raise ValueError('sealed_candidate_request_duplicate_ID')
    covered=set();eligible=[];excluded=unknown=0
    for component in components:
        ids=set(component['component_all_ids']);covered.update(ids)
        keys={tuple(key)for key in component['keys']}
        if keys & blocked:
            excluded+=1;continue
        if component.get('known')is not True:
            unknown+=1;continue
        candidates=[by_id[i]for i in component['target_ids']if i in by_id]
        if not candidates:continue
        row=copy.deepcopy(min(candidates,key=lambda r:sha(raw([seed,r['id']]))))
        # The complete canonical key union is kept, including foreign bridges.
        storage=[]
        for kind,value in sorted(keys):
            if kind not in ('id','code','image','cluster'):
                raise ValueError('sealed_component_unknown_canonical_identity_kind')
            storage.append((kind+':'+value)if kind in('id','code','image')else value)
        row.update(audit_cluster=component['component'],cluster=component['component'],
                   cluster_keys=sorted(set(storage+[component['component']])))
        if request_keys(row) & blocked:raise ValueError('sealed_selection_alias_conflict')
        eligible.append(row)
    if not set(by_id) <= covered:
        raise ValueError('sealed_candidate_request_missing_complete_component')
    eligible.sort(key=lambda r:sha(raw([seed,r['id']])))
    selected=eligible[:limit]
    for seq,row in enumerate(selected,1):row['seq']=seq
    return dict(selected=selected,eligible_observed_families=len(eligible),
                all_remaining_observed_families_selected=len(selected)==len(eligible),
                requested=limit,excluded_components=excluded,unknown_components=unknown,
                selection_policy=POLICY,seed=seed)
