"""Curate existing pairs using actual source panels and data; no conversion or QA."""
from pathlib import Path
import collections,hashlib,json,re,sys,time,uuid,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');BASE=R/'clean/matplotlib_plot_pipeline_20261102_v1/vector_backend_rollout_v6'
TERMS=set('error accuracy precision recall f1 auc loss training inference neural model algorithm parameter regression classification correlation covariance variance matrix eigen entropy frequency amplitude spectrum temperature pressure voltage current power energy efficiency battery stress strain velocity distance concentration gene protein cell dna rna mutation particle quantum wavelength absorbance validation baseline benchmark experiment simulation sample dataset attention embedding transformer bleu rouge psnr ssim lpips mse rmse mae features latent trait openness neuroticism extraversion agreeableness conscientiousness uncertainty confidence probability density distribution'.split())
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def source_features(row):
 scene_path=R/row['source_data_scene'];svg_path=R/row['frozen_raw_source_SVG_file'];scene_bytes=scene_path.read_bytes();svg_bytes=svg_path.read_bytes();assert sha(scene_bytes)==row['source_data_scene_sha256']and sha(svg_bytes)==row['frozen_raw_source_SVG_sha256']
 scene=json.loads(scene_bytes);observations=scene['actual_source_export_settings']['backend_export_observations'];draws=[draw for backend in observations if backend['format']=='svg'for draw in backend['actual_draws']if draw.get('axes')and all(a.get('gid')for a in draw['axes'])];assert draws,'actual_source_axes_geometry_missing'
 axes={a['gid']:a for a in draws[-1]['axes']};artists={a['gid']:a for a in scene['artists']};ownership=collections.defaultdict(list)
 def walk(element,owner=None):
  identifier=element.get('id');owner=identifier if identifier in axes else owner
  if owner and identifier in artists:ownership[owner].append(artists[identifier])
  for child in element:walk(child,owner)
 walk(ET.fromstring(svg_bytes));colorbars={a['actual_colorbar_owner']['axes_gid']for a in artists.values()if a.get('actual_colorbar_owner')};data={}
 for gid,items in ownership.items():
  if gid in colorbars:continue
  values=[a for a in items if a.get('visible')and(a.get('role')in('data_line','collection','source_image')or a.get('data_patch'))]
  if values:data[gid]=values
 # Deduplicate overlapping/twin axes using actual source draw rectangles.
 groups=[]
 def overlap(a,b):
  x,y,w,h=a;X,Y,W,H=b;return max(0,min(x+w,X+W)-max(x,X))*max(0,min(y+h,Y+H)-max(y,Y))/max(1e-12,min(w*h,W*H))
 for gid in sorted(data):
  box=axes[gid]['position_figure_fraction_bounds'];matched=next((group for group in groups if any(overlap(box,axes[g]['position_figure_fraction_bounds'])>=.8 for g in group)),None)
  if matched is None:groups.append([gid])
  else:matched.append(gid)
 text=sorted({' '.join(str(a.get('text','')).split())for a in artists.values()if a.get('role')=='text'and a.get('visible')and str(a.get('text','')).strip()});labels=[t for t in text if re.search('[A-Za-z\u3400-\u9fff]',t)and not re.fullmatch(r'[0-9eE+.,%\-\s]+',t)];words=set(re.findall(r'[a-z][a-z0-9]*',' '.join(labels).lower()));terms=sorted(words&TERMS)
 values=[a for group in data.values()for a in group];images=[a for a in values if a.get('role')=='source_image'];matrices=[a['shape']for a in images if len(a.get('shape',[]))==2 and min(a['shape'][:2])>=16];lines=sum(a.get('role')=='data_line'for a in values);dense_lines=sum(a.get('role')=='data_line'and a.get('x_original',{}).get('shape',[0])[0]>=4 for a in values);families=sorted({a.get('role')for a in values})
 return dict(actual_source_data_panels=len(groups),actual_axes_in_data_panels=groups,colorbar_axes_excluded=sorted(colorbars),actual_data_artists=len(values),actual_data_lines=lines,actual_dense_data_lines=dense_lines,actual_data_families=families,source_image_components=len(images),large_matrix_shapes=matrices,actual_data_patches=sum(bool(a.get('data_patch'))for a in values),actual_collections=sum(a.get('role')=='collection'for a in values),actual_distribution_collections=sum(a.get('role')=='collection'and a.get('artist_class')=='PolyCollection'and any(path.get('vertices',{}).get('shape',[0])[0]>=20 for path in a.get('paths',[]))for a in values),distinct_non_numeric_source_labels=len(labels),non_numeric_source_label_characters=sum(map(len,labels)),scientific_text_signals=terms,source_data_point_or_path_vertices=scene['data_point_or_path_vertex_count'],path_vertices_not_counted_as_logical_nodes=True,source_scene_sha256=sha(scene_bytes),source_SVG_sha256=sha(svg_bytes))
def classify(f):
 rich=f['distinct_non_numeric_source_labels']>=8 and f['non_numeric_source_label_characters']>=60
 complexity=[]
 if f['actual_source_data_panels']>=3 and f['actual_data_artists']>=6 and rich:complexity.append('three_or_more_independent_actual_data_panels')
 if f['actual_source_data_panels']>=2 and len(f['actual_data_families'])>=2 and rich and(f['actual_dense_data_lines']>=3 or f['source_image_components']>=2):complexity.append('coupled_heterogeneous_data_panels')
 if f['actual_source_data_panels']>=2 and f['actual_distribution_collections']>=8 and f['distinct_non_numeric_source_labels']>=12 and rich:complexity.append('multiple_data_distribution_panels')
 if f['actual_dense_data_lines']>=8 and f['distinct_non_numeric_source_labels']>=16:complexity.append('many_actual_data_series_with_distinct_labels')
 if f['large_matrix_shapes']and f['distinct_non_numeric_source_labels']>=16:complexity.append('large_explicit_source_matrix_with_labels')
 if complexity and len(f['scientific_text_signals'])>=2:return'complex_scientific_candidate',complexity
 if f['actual_source_data_panels']<=1 and f['actual_data_lines']<=3 and f['source_image_components']==f['actual_data_patches']==0 and f['actual_collections']<=f['actual_data_lines']:return'simple_deprioritized',['few_actual_series_on_one_data_panel']
 return'structure_or_scientific_context_review',complexity or['actual_complexity_not_proved_by_current_rules']
def main():
 root=R/'clean/complex_scientific_chart_curation_v3'/uuid.uuid4().hex;root.mkdir(parents=True);policy=dict(method='actual_source_Artist_arrays_and_original_SVG_ownership_and_actual_draw_axes',independent_panel_overlap_fraction=.8,sparse_two_bar_or_two_line_panels_not_automatically_complex=True,boxplot_whisker_or_caps_not_counted_as_dense_series=True,scatter_marker_collections_not_counted_as_distributions=True,only_explicit_two_dimensional_arrays_are_matrices=True,colorbar_axes_not_data_panels=True,scientific_text_terms=sorted(TERMS),source_policy_only=True,candidate_or_QA_scores_not_used_for_source_features=True,existing_profiles_remain_independent=True,no_original_reference_changed=True,all_nonselected_originals_retained=True,strict_full8_main_not_changed=True)
 (root/'policy.json').write_bytes(raw(policy));start=time.monotonic();selected=[];audit=[];counts=collections.Counter();inputs=[]
 for profile in ['provider_original_reference_aligned','source_replay_aligned','source_svg_backend_replay_aligned']:
  p=BASE/(profile+'.jsonl');blob=p.read_bytes();inputs.append(dict(file=str(p.relative_to(R)),sha256=sha(blob)))
  for row in map(json.loads,blob.splitlines()):
   result=dict(id=row['id'],raw_source_pair_id=row['raw_source_pair_id'],source=row['source'],profile=profile)
   try:
    features=source_features(row);status,reasons=classify(features);result.update(status=status,reasons=reasons,features=features)
    if status=='complex_scientific_candidate':selected.append(row)
   except Exception as e:result.update(status='source_structure_error',reason=type(e).__name__+':'+str(e))
   counts[result['status']]+=1;audit.append(result)
 assert len(audit)==1875
 for name,values in [('source_audit.jsonl',audit),('complex_scientific_candidates.jsonl',selected)]:
  p=root/name;p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in values));p.chmod(0o444)
 output=dict(root=str(root),input_pairs=len(audit),counts=dict(counts),selected=len(selected),source_inputs=inputs,source_policy_sha256=sha((root/'policy.json').read_bytes()),producer_sha256=sha(Path(__file__).read_bytes()),elapsed_seconds=time.monotonic()-start,scientific_value_individually_certified=False,selected_source_structure_and_scientific_text_evidence=True,strict_full8_main_changed=False,new_conversions=0,new_QA=0,model_calls=0,goal_complete=False)
 output['files']={name:dict(file=str((root/name).relative_to(R)),sha256=sha((root/name).read_bytes()))for name in ['source_audit.jsonl','complex_scientific_candidates.jsonl','policy.json']};(root/'summary.json').write_bytes(raw(output));(root/'policy.json').chmod(0o444);print(json.dumps(output))
if __name__=='__main__':main()
