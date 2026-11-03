#!/usr/bin/env python3
"""Independent read-only verification of the complete-page compiler outputs."""
from pathlib import Path
import collections,hashlib,json,sqlite3,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import embedded_xml_compiler_v1 as C
import embedded_xml_page_core_v1 as P
D=P.D;DB=D/'once.sqlite';OLD=C.Path(__file__).resolve().parents[1]/'results'/'embedded_XML_compiler_dpsk_v1'

def main():
    c=sqlite3.connect(DB)
    parents={r[0]:json.loads(r[1]) for r in c.execute('select id,record from parent_jobs')}
    pages=c.execute('select id,parent_job_id,file,page_index,page_id,page_name,page_graph_sha256,page_xml_sha256,state,record from page_cases order by parent_job_id,page_index').fetchall()
    errors=[];source_manifest=[];parent_checked=0;sidecars_checked=0
    for pid,rec in parents.items():
        try:
            ex=rec.get('extraction',{})
            # parent record stores file in extraction
            file=ex.get('file') or rec.get('file')
            if not file: raise ValueError('parent_file_missing')
            src=C.R/file;actual=C.sha(src.read_bytes());source_manifest.append({'file':file,'sha256':actual,'bytes':src.stat().st_size})
            if ex.get('source_sha256') and actual!=ex.get('source_sha256'):errors.append({'parent':pid,'error':'source_hash_mismatch','file':file})
            if ex.get('full_embedded_XML_file'):
                full=C.R/ex['full_embedded_XML_file'];fb=full.read_bytes()
                if C.sha(fb)!=ex.get('full_embedded_XML_sha256'):errors.append({'parent':pid,'error':'full_embedded_XML_hash'})
            ident=C.candidate_source_identity(src)
            if C.sha((C.R/ident['source_archive_file']).read_bytes())!=ident['source_archive_sha256']:errors.append({'parent':pid,'error':'archive_hash'})
            if C.sha((C.R/ident['source_receipt_file']).read_bytes())!=ident['source_receipt_sha256']:errors.append({'parent':pid,'error':'receipt_hash'})
            parent_checked+=1
        except Exception as e:errors.append({'parent':pid,'error':type(e).__name__+':'+str(e)[:300]})
    pair_by_page={}
    for ident,pid,file,idx,pageid,pagename,graph,xmlsha,state,recraw in pages:
        try:
            r=json.loads(recraw) if isinstance(recraw,str) else recraw
            v=r.get('verified') or {};p=v.get('pair')
            pg=r.get('page',{})
            if p:
                sidefile=C.R/p['original_page_author_XML']
            elif pg.get('page_sidecar_file'):
                sidefile=C.R/pg['page_sidecar_file']
            else:
                pex=parents[pid]['extraction']
                pg=next(x for x in pex['pages'] if x['page_index']==idx)
                sidefile=C.R/pg['page_sidecar_file']
            side=sidefile.read_bytes();sidecars_checked+=1
            if C.sha(side)!=xmlsha:errors.append({'page':ident,'error':'sidecar_hash'})
            if C.page_graph_hash(P.safe_xml(side))!=graph:errors.append({'page':ident,'error':'page_graph_hash'})
            if p:
                if p.get('selected_page_id')!=pageid or p.get('selected_page_name')!=pagename:errors.append({'page':ident,'error':'page_identity'})
            elif pg.get('page_id')!=pageid or pg.get('page_name')!=pagename:errors.append({'page':ident,'error':'page_identity'})
            if state=='verified':
                if not p:errors.append({'page':ident,'error':'verified_without_pair'});continue
                pair_by_page[ident]=p
                code=C.R/p['code_file'];image=C.R/p['image_file']
                if C.sha(code.read_bytes())!=p['code_sha256']:errors.append({'page':ident,'error':'code_hash'})
                if C.sha(image.read_bytes())!=p['image_sha256']:errors.append({'page':ident,'error':'image_hash'})
                if p.get('source_origin_kind')!='embedded_native_complete_page':errors.append({'page':ident,'error':'wrong_origin_kind'})
                if p.get('paired_code_XML_bytes_equal_selected_page_XML') is not True:errors.append({'page':ident,'error':'sidecar_not_equal_claimed'})
                if C.sha(side)!=p.get('selected_page_XML_sha256'):errors.append({'page':ident,'error':'selected_page_sha'})
                if C.sha((C.R/p['original_author_XML']).read_bytes())!=p['original_author_XML_sha256']:errors.append({'page':ident,'error':'full_parent_sha'})
                for key in ('page_selection_proof','official_full_decoder_agreement','official_page_decoder_comparison','native_replay_proof','archive_membership_proof'):
                    f=C.R/p[key]
                    if C.sha(f.read_bytes())!=p[key+'_sha256']:errors.append({'page':ident,'error':key+'_hash'})
                sel=json.loads((C.R/p['page_selection_proof']).read_text());dec=json.loads((C.R/p['official_page_decoder_comparison']).read_text());full=json.loads((C.R/p['official_full_decoder_agreement']).read_text());rep=json.loads((C.R/p['native_replay_proof']).read_text())
                if not sel.get('complete_selected_mxGraphModel') or sel.get('fragment_crop_or_subgraph_selection')!=False:errors.append({'page':ident,'error':'selection_proof'})
                if sel.get('selected_page_index')!=idx or sel.get('selected_page_XML_sha256')!=C.sha(side):errors.append({'page':ident,'error':'selection_identity'})
                if not (full.get('exact_bytes_equal') or full.get('canonical_XML_equal')):errors.append({'page':ident,'error':'full_decoder'})
                if not (dec.get('exact_bytes_equal') or dec.get('canonical_model_equal')):errors.append({'page':ident,'error':'page_decoder'})
                if not rep.get('ok'):errors.append({'page':ident,'error':'replay_not_ok'})
                for k in ('normalized_model_exact_restore','mutation_actual_RGBA_changed','restored_actual_RGBA_exact','restored_PNG_bytes_exact','restored_SVG_namespace_canonical_exact'):
                    if rep.get(k) is not True:errors.append({'page':ident,'error':'replay_'+k})
                for f in p.get('font_dependencies',[]):
                    if not C.R/f['file'] or C.sha((C.R/f['file']).read_bytes())!=f['sha256']:errors.append({'page':ident,'error':'font_hash'})
                member=json.loads((C.R/p['archive_membership_proof']).read_text())
                if not member.get('all_members_exact_and_safe'):errors.append({'page':ident,'error':'archive_membership'})
        except Exception as e:errors.append({'page':ident,'error':type(e).__name__+':'+str(e)[:300]})
    old_manifest=OLD/'verified_candidates.jsonl';old_status=OLD/'status.json'
    old_ok=(not old_manifest.exists() or C.sha(old_manifest.read_bytes())=='35eacfa76dcd18a54c012d58f47317abbeddde38ebc7339298da2ab6adfac9f2')
    if not old_ok:errors.append({'old_compiler':'manifest_changed'})
    auto=C.P/'goal500_automatic_admission_v2/accepted_new_pairs.jsonl';auto_sha=C.sha(auto.read_bytes()) if auto.exists() else None
    current=C.P/'goal500_automatic_admission_v2/current.json';current_obj=json.loads(current.read_text()) if current.exists() else {}
    if auto.exists() and current_obj.get('accepted_new_pairs',{}).get('sha256') and auto_sha!=current_obj['accepted_new_pairs']['sha256']:errors.append({'authoritative_414':'accepted_manifest_changed'})
    summary={'schema':'embedded_native_page_compiler_independent_verification_v1','at_utc':None,
        'inventory_candidates':c.execute('select count(*) from cumulative_cases').fetchone()[0],'parents_checked':parent_checked,
        'pages_checked':len(pages),'page_sidecars_checked':sidecars_checked,'verified_page_pairs':len(pair_by_page),
        'source_hashes_recorded':len(source_manifest),'errors':errors,'ok':not errors,
        'old_compiler_manifest_sha256':C.sha(old_manifest.read_bytes()) if old_manifest.exists() else None,
        'old_compiler_manifest_expected_unchanged':old_ok,
        'authoritative_414_manifest_sha256':auto_sha,'authoritative_414_unchanged':not any('authoritative_414' in str(e) for e in errors),
        'sources_modified':any(e.get('error')=='source_hash_mismatch' for e in errors),
        'new_model_calls':0,'new_PDF_import_calls':0,'new_source_downloads':0}
    import datetime
    summary['at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    P.put_json(D/'source_hash_manifest.json',{'schema':'embedded_native_page_source_hash_manifest_v1','files':source_manifest,'at_utc':summary['at_utc']})
    P.put_json(D/'independent_verification.json',summary)
    print(json.dumps({k:summary[k] for k in ('ok','parents_checked','pages_checked','verified_page_pairs','source_hashes_recorded','errors')},ensure_ascii=False))
    return 0 if summary['ok'] else 1
if __name__=='__main__':sys.exit(main())
