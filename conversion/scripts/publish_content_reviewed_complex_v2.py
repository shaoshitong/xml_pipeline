"""Publish source-selected full-QA pairs after content and layout review."""
from pathlib import Path
import collections,datetime,hashlib,json,os,uuid
R=Path('/backup/shaoshitong/img2code_20261029');C=R/'clean/complexity_curation_20261102T054553Z_v1'
VALUE=None
OCCLUSION=None
SPOT=[]

def sha(data):return hashlib.sha256(data).hexdigest()
def raw(value):return(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
def asset(path):return dict(file=str(path.relative_to(R)),sha256=sha(path.read_bytes()),bytes=path.stat().st_size)
def checked(ref):
    path=(R/ref['file']).resolve(strict=True);assert path.is_relative_to((R/'clean').resolve());assert sha(path.read_bytes())==ref['sha256'];return path


def main():
    import argparse
    global VALUE,OCCLUSION,SPOT
    parser=argparse.ArgumentParser();parser.add_argument('--review-summary',type=Path,required=True);args=parser.parse_args();assert args.review_summary.resolve().is_relative_to((R/'clean').resolve())
    input_summary=json.loads(args.review_summary.read_bytes());VALUE=checked(input_summary['pairs']);OCCLUSION=checked(input_summary['occlusion']);SPOT=input_summary['approved_ids']
    before=(C/'current.json').read_bytes();pointer=json.loads(before);old_body=checked(pointer['views']['paired_priority_complex']).read_bytes();old=[json.loads(line)for line in old_body.splitlines()if line];existing={row['id']for row in old}
    candidates=[json.loads(line)for line in VALUE.read_bytes().splitlines()if line];occlusion={row['id']:row for row in[json.loads(line)for line in OCCLUSION.read_bytes().splitlines()if line]};assert candidates
    approved=[];decisions=[]
    for row in candidates:
        pair=row['pair'];review=occlusion[pair['id']];assert review['source_sha256']==pair['source_code_sha256'];assert row['full_eight_quality_reverified']and row['direct_native_PNG_visual_inspection']
        for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('metadata_file','metadata_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:checked(dict(file=pair[field],sha256=pair[digest]))
        if not row['approved_for_strict_main']:decisions.append(dict(id=pair['id'],approved=False,reason=row['visual_note']));continue
        assert review['potential_occluded_labels']==0
        if pair['id']in existing:continue
        approved.append(pair);decisions.append(dict(id=pair['id'],approved=True,selection_rules=row['dense_source_rules'],source_features=row['dense_source_features'],source_text_occlusion_labels=0,direct_native_PNG_visual_inspection=pair['id']in SPOT,selection_method='Frozen rich scientific source preselection plus complete recorded full8 and source-visibility evidence, with actual PNG spot inspection.'))
    if not approved:
        print(json.dumps(dict(before=len(old),after=len(old),added_ids=[],already_published=True)));return
    output=C/('published_current_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_review_batch_v8');output.mkdir()
    review=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),producer=asset(Path(__file__)),input_value_review=asset(VALUE),source_visibility_review=asset(OCCLUSION),direct_visual_sample_ids=SPOT,direct_visual_observations={row['id']:row['visual_note']for row in candidates},decisions=decisions,scientific_correctness_of_source_not_claimed=True,full_source_or_QA_thresholds_changed=False,new_normal_conversions=0,new_QA_calls=0,new_model_calls=0)
    review_path=output/'value_review.json';review_path.write_bytes(raw(review));added=[]
    for pair in approved:added.append({**pair,'curation':dict(selection='rich_scientific_source_full8_content_review_v8',review=asset(review_path),source_content_visibility_review=asset(OCCLUSION),original_source_and_qualification_unchanged=True)})
    main_path=output/'paired_priority_complex.jsonl';rows=sorted(old+added,key=lambda row:row['id']);main_path.write_bytes(b''.join((json.dumps(row,sort_keys=True)+'\n').encode()for row in rows));main_ref={**asset(main_path),'rows':len(rows)}
    parent_summary=json.loads(checked(pointer['summary']).read_text());now=datetime.datetime.now(datetime.timezone.utc).isoformat();summary={**parent_summary,'schema':'content_reviewed_complex_batch_summary_v8','at_utc':now,'root':str(output),'paired_priority_complex':len(rows),'paired_priority_by_source':dict(collections.Counter(row['source']for row in rows)),'paired_priority_by_format':dict(collections.Counter(row['source_format']for row in rows)),'reviewed_complex_additions':[row['id']for row in added],'reviewed_complex_addition_count':len(added),'held_layout_review_ids':[r['id']for r in candidates if not r['approved_for_strict_main']],'value_review':asset(review_path),'files':{**parent_summary.get('files',{}),**pointer['views'],'paired_priority_complex':main_ref},'files_new_in_this_snapshot':{'paired_priority_complex':main_ref,'value_review':asset(review_path)},'producer_sha256':sha(Path(__file__).read_bytes()),'new_conversions':0,'new_QA_calls':0,'goal_complete':False};(output/'summary.json').write_bytes(raw(summary));(output/'previous_current_snapshot.json').write_bytes(before);(output/'hash_inventory.json').write_bytes(raw(dict(main=main_ref,summary=asset(output/'summary.json'),value_review=asset(review_path),parent_pointer=asset(output/'previous_current_snapshot.json'),inherited_views=pointer['views'])))
    updated={**pointer,'schema':'curated_current_pointer_v8','at_utc':now,'snapshot':str(output.relative_to(R)),'summary':asset(output/'summary.json'),'hash_inventory':asset(output/'hash_inventory.json'),'previous_current_snapshot':asset(output/'previous_current_snapshot.json'),'views':{**pointer['views'],'paired_priority_complex':main_ref},'paired_priority_complex':len(rows)}
    assert(C/'current.json').read_bytes()==before,'concurrent_curation_change'
    temporary=C/('current.'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(raw(updated));os.replace(temporary,C/'current.json')
    for path in output.iterdir():path.chmod(0o444)
    print(json.dumps(dict(before=len(old),after=len(rows),added_ids=[row['id']for row in added],held_ids=[r['id']for r in candidates if not r['approved_for_strict_main']],main=main_ref,review=asset(review_path),pointer=asset(C/'current.json'))),flush=True)

if __name__=='__main__':main()
