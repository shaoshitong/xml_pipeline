import collections,datetime,hashlib,json,os
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029'); D=R/'release'; D.mkdir(exist_ok=True)
load=lambda p:json.loads(p.read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
S=load(R/'reports/visual_audit_final/sample_locators.json'); V=load(R/'reports/visual_audit_final/summary.json'); A=load(R/'reports/content_audit.json')
assert V['ok'] and A['ok'] and len(S)==139 and V['stratum_count']==71
reject={19:'decorative_logo_not_target_diagram',30:'collapsed_plot_and_overlapping_axes',42:'severe_title_axis_overlap',56:'clipped_and_overlapping_diagram_labels',72:'severe_instrument_label_overlap',73:'severe_plot_and_diagram_label_overlap',79:'severe_edge_label_overlap',81:'collapsed_data_trace_and_overlapping_labels',88:'severe_axis_label_overlap',95:'decorative_album_layout_not_target',102:'generic_shape_demonstration',119:'placeholder_Text_nodes'}
recategorize={i:'scientific_diagram' for i in [0,1,4,5,8,9,12,13,20,23,50,105,130,133,134]}
recategorize.update({i:'chart' for i in [43,55,101]})
reject_hash={S[i]['locator']['image_sha256']:{'sample_id':i,'reason':reason} for i,reason in reject.items()}
category_hash={S[i]['locator']['image_sha256']:{'sample_id':i,'category':category} for i,category in recategorize.items()}
review={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'root_assistant_visual_inspection','sheets_reviewed':V['sheets'],'samples_reviewed':139,'strata_reviewed':71,'sample_inventory_sha256':sha((R/'reports/visual_audit_final/sample_locators.json').read_bytes()),'base_manifest_sha256':A['input_manifest_sha256'],'rejected_image_hashes':reject_hash,'category_corrections_by_image_hash':category_hash,'findings':['All twelve contact sheets were visually inspected, including RealChart samples 137 and 138.','No sampled web UI remains; several source chart/diagram labels were inaccurate.','Confirmed decorative/placeholder/severely illegible examples are excluded by image hash, including other catalog occurrences.','Remaining examples include minor overlaps, low-resolution template previews, and variable source quality. This stratified review is not exhaustive visual or semantic verification.','Existing full-content audit covers every retained image/code byte; release adds only exclusions, category corrections and review annotations.']}
(R/'reports/visual_audit_final/root_visual_review.json').write_text(json.dumps(review,indent=2)+'\n')
summary={'created_at_utc':review['created_at_utc'],'status':'final_reviewed_release','base_catalog_summary':str(R/'reports/catalog_summary.json'),'base_content_audit':str(R/'reports/content_audit.json'),'base_manifest_sha256':A['input_manifest_sha256'],'visual_review':'reports/visual_audit_final/root_visual_review.json','groups':{},'exclusions':[],'corrections':[]}
allimages=set();allpairs=set()
for kind,folder,label in [('provided','clean','clean'),('derived','derived','derived')]:
 src=R/folder/'manifest.jsonl'; h=hashlib.sha256();out=D/(kind+'.jsonl');tmp=out.with_suffix('.tmp'); images=set();pairs=set();stats={key:collections.Counter() for key in ['formats','categories','sources']};count=0;excluded=0;corrections=0
 with src.open('rb') as stream,tmp.open('wb') as target:
  for line in stream:
   h.update(line);row=json.loads(line);im=row['image_sha256']
   if im in reject_hash:
    summary['exclusions'].append({'kind':kind,'pair_sha256':row['pair_sha256'],'image_sha256':im,**reject_hash[im]});excluded+=1;continue
   if im in category_hash and row['category']!=category_hash[im]['category']:
    correction={'kind':kind,'pair_sha256':row['pair_sha256'],'previous_category':row['category'],**category_hash[im]};summary['corrections'].append(correction);row['category']=correction['category'];row['visual_review_category_correction']=correction;corrections+=1
   target.write((json.dumps(row,ensure_ascii=False)+'\n').encode());count+=1;images.add(im);pairs.add(row['pair_sha256']);allimages.add(im);allpairs.add(row['pair_sha256'])
   for k,f in [('formats','format'),('categories','category'),('sources','source')]:stats[k][row[f]]+=1
 assert h.hexdigest()==A['input_manifest_sha256'][label]
 os.replace(tmp,out)
 summary['groups'][kind]={'pairs':count,'unique_images':len(images),'unique_pairs':len(pairs),'excluded_pairs':excluded,'category_corrected_pairs':corrections,'manifest':str(out),'sha256':sha(out.read_bytes()),**{k:dict(v) for k,v in stats.items()}}
summary.update(total_pairs=sum(g['pairs'] for g in summary['groups'].values()),unique_images=len(allimages),unique_pairs=len(allpairs),finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(D/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['exclusions','corrections']},ensure_ascii=False))
