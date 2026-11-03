#!/usr/bin/env python3
"""Independent read-only verification of the embedded-XML compiler outputs."""
from pathlib import Path
import collections, json, sqlite3, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedded_xml_compiler_v1 as C
D=C.D; DB=D/'once.sqlite'

def main():
    c=sqlite3.connect(DB)
    rows=c.execute("select id,file,kind,status,record from cases order by ordinal").fetchall()
    pairs_by_case={}
    for line in (D/'verified_candidates.jsonl').read_text().splitlines():
        if line.strip():
            pair=json.loads(line); pairs_by_case[pair['raw_source_pair_id']]=pair
    source_checked=0; source_hash_records=[]; source_mismatch=[]; extraction_mismatch=[]
    for ident,file,kind,status,recraw in rows:
        rec=json.loads(recraw) if recraw else {}
        ex=rec.get('extraction') or {}
        pair=pairs_by_case.get(ident)
        expected=ex.get('source_sha256') or (pair or {}).get('original_container_sha256')
        p=C.R/file
        actual=C.sha(p.read_bytes()); source_hash_records.append({'file':file,'sha256':actual,'bytes':p.stat().st_size})
        if expected:
            source_checked+=1
            if actual!=expected: source_mismatch.append({'id':ident,'file':file,'expected':expected,'actual':actual})
            e=C.extract_candidate(p,kind)
            expected_raw=ex.get('raw_sha256') or (pair or {}).get('original_author_XML_sha256')
            if expected_raw and e['raw_sha256']!=expected_raw: extraction_mismatch.append({'id':ident,'file':file,'expected':expected_raw,'actual':e['raw_sha256']})
    C.put_json(D/'source_hash_manifest.json', {'schema':'embedded_xml_compiler_source_hash_manifest_v1','at_utc':None,'files':source_hash_records})
    manifest=D/'verified_candidates.jsonl'
    pairs=[json.loads(x) for x in manifest.read_text().splitlines() if x.strip()]
    errors=[]; member_rows=0; proof_files=0
    for p in pairs:
        try:
            code=C.R/p['code_file']; image=C.R/p['image_file']
            if C.sha(code.read_bytes())!=p['code_sha256']: errors.append({'pair':p['id'],'error':'code_hash'})
            if C.sha(image.read_bytes())!=p['image_sha256']: errors.append({'pair':p['id'],'error':'image_hash'})
            source=C.R/p['original_container_file']; e=C.extract_candidate(source, 'PNG_native_XML_marker' if p['source_origin_kind'].startswith('png') else 'SVG_native_XML_marker')
            if e['raw_sha256']!=p['original_author_XML_sha256']: errors.append({'pair':p['id'],'error':'extracted_author_hash'})
            if C.sha(source.read_bytes())!=p['original_container_sha256']: errors.append({'pair':p['id'],'error':'container_hash'})
            for key in ('official_decoder_agreement','native_replay_proof','archive_membership_proof'):
                f=C.R/p[key]
                if C.sha(f.read_bytes())!=p[key+'_sha256']: errors.append({'pair':p['id'],'error':key+'_hash'})
                proof_files+=1
            proof=json.loads((C.R/p['native_replay_proof']).read_text())
            if not proof.get('ok'): errors.append({'pair':p['id'],'error':'replay_proof_not_ok'})
            for k in ('normalized_model_exact_restore','mutation_actual_RGBA_changed','restored_actual_RGBA_exact','restored_PNG_bytes_exact','restored_SVG_namespace_canonical_exact'):
                if proof.get(k) is not True: errors.append({'pair':p['id'],'error':'proof_'+k})
            for f in p.get('font_dependencies',[]):
                q=C.R/f['file']
                if not q.is_file() or C.sha(q.read_bytes())!=f['sha256']: errors.append({'pair':p['id'],'error':'font_hash'})
            member=json.loads((C.R/p['archive_membership_proof']).read_text())
            if not member.get('all_members_exact_and_safe'): errors.append({'pair':p['id'],'error':'archive_membership'})
            member_rows+=len(member.get('members',[]))
            ident=p['raw_source_pair_id']; actual=c.execute('select status from cases where id=?',(ident,)).fetchone()
            if not actual or actual[0]!='verified': errors.append({'pair':p['id'],'error':'case_not_verified'})
        except Exception as e:
            errors.append({'pair':p.get('id'),'error':type(e).__name__+':'+str(e)[:300]})
    summary={
        'schema':'embedded_xml_compiler_independent_verification_v1','at_utc':None,
        'inventory_cases':len(rows),'source_hashes_checked':source_checked,'source_hashes_recorded':len(source_hash_records),'source_hash_manifest':str((D/'source_hash_manifest.json').relative_to(C.R)),'source_hash_mismatches':source_mismatch,
        'extraction_hash_mismatches':extraction_mismatch,'verified_candidate_pairs':len(pairs),
        'proof_files_checked':proof_files,'archive_member_proofs_checked':member_rows,'errors':errors,
        'ok':not source_mismatch and not extraction_mismatch and not errors,
        'sources_modified':bool(source_mismatch or extraction_mismatch),'authoritative_index_modified':False,
        'baseline3759_modified':False,'new_model_calls':0,'new_PDF_import_calls':0,'new_source_downloads':0,
    }
    import datetime
    summary['at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    C.put_json(D/'independent_verification.json', summary)
    print(json.dumps({k:summary[k] for k in ('ok','inventory_cases','source_hashes_checked','verified_candidate_pairs','errors')},ensure_ascii=False))
    return 0 if summary['ok'] else 1
if __name__=='__main__': sys.exit(main())
