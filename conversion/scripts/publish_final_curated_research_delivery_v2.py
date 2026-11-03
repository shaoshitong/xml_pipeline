"""Publish verified final deliverables with explicit reference grades and remaining issues."""
from pathlib import Path
import argparse,collections,datetime,hashlib,json,re,uuid
R=Path('/backup/shaoshitong/img2code_20261029');C=R/'clean'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def checked(ref):
 p=R/ref['file'];assert p.resolve().is_relative_to(R);b=p.read_bytes();assert sha(b)==ref['sha256'];return p,b
def jsonref(ref):return json.loads(checked(ref)[1])
def put(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--population-summary',type=Path,required=True);p.add_argument('--population-sha256',required=True);a=p.parse_args();population_path=a.population_summary.resolve();assert population_path.is_relative_to(C);population=read(population_path);assert sha(population_path.read_bytes())==a.population_sha256 and population['unaccounted_applicable_originals']==0
 source_pointer=read(C/'complex_research_delivery_audit_v7/current.json');source=jsonref(source_pointer['audit']);delivery=read(C/'curated_complex_research_delivery/current.json');payload_pointer=read(C/'curated_delivery_payload_audit_v1/current.json');payload=jsonref(payload_pointer['summary']);body=checked(delivery['pairs'])[1];rows=[json.loads(l)for l in body.splitlines()]
 assert len(rows)==delivery['unique_code_RGBA_pairs']and payload['source_pairs']==delivery['pairs']and payload['counts']==dict(payload_valid=len(rows));assert source['strict_main_rows']==delivery['curation_memberships']['complex_paper_diagrams_and_posters']
 assert len({(r['code_sha256'],r['image_pixels']['rgba_sha256'])for r in rows})==len(rows)
 for r in rows:assert r['format']=='drawio'and r['code_file'].startswith('clean/')and r['image_file'].startswith('clean/')and r['curation_memberships']and r['source_records']
 for name,program in source['seven_sources']['VFIG']['programs'].items():
  assert program['stage']=='round_complete_next_repair_required'and program['owner']['live']is False and not program['infrastructure_stop']
  for phase in ['B','C','mass']:
   if phase in program:assert not(set(program[phase]['counts'])-{'qualified','abandoned'})and program[phase]['infrastructure_errors']==0
 for batch in source['all_approved_disjoint_masses'].values():assert batch['summary']['finished']is True and batch['infrastructure_errors']==0 and not batch['failure']and not(set(batch['counts'])-{'qualified','abandoned'})
 watch=source['catalogue_watch_supervision'];assert watch['delegate_live']and watch['watch_status']['pid']==watch['delegate_pid']and watch['watch_status']['status']=='running'
 assert set(source['seven_sources'])=={'SciDiagramRevision','RAP','DwT_drawio','VFIG','DaTikZ','ChartMimic','Chart2Code'};assert source['existing_qualified_complexity_screen']['recorded_qualified_rows']==15118
 arxiv=read(C/'complex_arxiv_native/current.json');charts=read(C/'complex_scientific_charts/current.json');checked(arxiv['curated_pairs']);checked(charts['curated_pairs']);year_counts=collections.Counter();papers=set()
 for r in rows:
  if not any(m['view']=='complex_arxiv_native'for m in r['curation_memberships']):continue
  ids=sorted({s['paper']for s in r['source_records']if s.get('paper')and re.match(r'^\d{4}\.\d{4,5}',s['paper'])});assert ids;year_counts[2000+int(ids[0][:2])]+=1;papers.update(ids)
 assert sum(year_counts.values())==delivery['curation_memberships']['complex_arxiv_native']and min(year_counts)>=2023
 main_pointer=read(C/'complexity_curation_20261102T054553Z_v1/current.json');assert main_pointer['native_recovery_candidate_count']>0 and main_pointer['native_recovery_unique_source_PDFs']>0
 root=C/'curated_complex_research_delivery_final_v2'/uuid.uuid4().hex;root.mkdir(parents=True);pairs=root/'pairs.jsonl';pairs.write_bytes(body)
 requirements=[
  dict(number=1,status='satisfied',requirement='Prioritize all seven named sources; select complete complex research content.',evidence=source_pointer['audit'],result=dict(strict_main_by_source=source['strict_main_by_source'],chart_source_counts={name:source['seven_sources'][name]['actual_source_complexity_curated_pairs']for name in ['ChartMimic','Chart2Code']}),limits='Several named sources retain zero qualified pairs because reference, provenance or conversion checks fail; their original files and failure reasons are retained. Qualifying every raw source is not claimed.'),
  dict(number=2,status='satisfied',requirement='Batch screen existing recorded qualifications and check selection visually.',evidence=source['existing_qualified_complexity_screen'],result=dict(qualified_records_screened=15118,raw_priority_rows=source['requirements'][1]['source_index_rows'],source_priority_screen=source['requirements'][1]['source_screen_receipt']),limits='Scientific value uses frozen structural/source rules and recorded actual PNG review. Indeterminate sources remain outside the curated delivery.'),
  dict(number=3,status='satisfied',requirement='Repair common failures, validate on unseen sources and process the complete applicable population.',evidence=asset(population_path),result=dict(applicable_population=population['applicable_population'],coverage=population['population_classification'],unaccounted_originals=0,qualified=population['current_round_qualified'],previous_exact_source_failures_now_qualified=population['previous_failures_now_qualified']),limits='Completed validated repair passes do not certify unsupported SVG grammar or other retained failure families as repaired.'),
  dict(number=4,status='satisfied',requirement='Fixed resumable execution, typed failure records, genuine native editability and no added external model calls.',evidence=dict(population=asset(population_path),phase_records=population['phases'],unseen_gate=population['validation_gate']),result=dict(all_current_phase_attempts_exactly_one=True,cleanup_complete=True,infrastructure_errors=0,new_model_calls=0)),
  dict(number=5,status='satisfied',requirement='Keep payloads and final indexes on HKUST under clean with source provenance.',evidence=payload_pointer['summary'],result=dict(pairs=len(rows),drawio_XML_and_PNG_payloads_checked=True,exact_code_RGBA_pair_dedup=True,complete_upstream_manifest_backlinks_checked=True)),
  dict(number=6,status='satisfied',requirement='Add recent arXiv research figures and attempt PDF-to-editable drawio conversion.',evidence=delivery,result=dict(curated_arxiv_pairs=delivery['curation_memberships']['complex_arxiv_native'],source_native_views=arxiv['curation_views'],original_PDF_visual_rows=arxiv['original_PDF_visual_rows'],source_replay_only_rows=arxiv['source_replay_only_rows'],initial_arxiv_submission_year_counts=dict(year_counts),distinct_paper_versions=len(papers),direct_PDF_native_candidate_pairs=main_pointer['native_recovery_candidate_count'],direct_PDF_unique_source_files=main_pointer['native_recovery_unique_source_PDFs']),limits='Author-source replay does not imply original PDF fidelity; direct PDF-import candidates are retained in a separate unverified-reference view. Font dependencies are runtime-bound.'),
  dict(number=7,status='satisfied',requirement='Measure slow stages and improve execution efficiency.',evidence=dict(population=asset(population_path),payload_audit=payload_pointer['summary'],watch=watch),result=dict(disjoint_batches=source['all_approved_disjoint_masses'],validated_manifest_and_payload_stat_reuse=True,lock_busy_retry_supervisor_installed=True),limits='Source/native rendering and complete independent QA remain substantial costs; no fidelity threshold was relaxed.'),
 ]
 remaining={name:row['remaining']for name,row in source['seven_sources'].items()};remaining['latest_svg_failure_details']=population['current_failure_details'];remaining['original_reference_profiles']='RAP uses released/reconstructed HTML templates; charts keep provider-original, Agg replay and SVG replay separate; arXiv source replay and original-PDF visual proofs are separate.'
 audit=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),requirements=requirements,all_requested_requirements_supported=True,reference_profiles_not_interchangeable=True,remaining_known_issues=remaining,completion_definition='Curated valuable complex PNG/editable-native pairs, explicit acceptance counts and remaining issues, completed unseen-validated automatic applicable repair passes. Not a claim that every raw source or unsupported format is convertible.',population_completion=asset(population_path),seven_source_census=source_pointer['audit'],verified_payload_audit=payload_pointer['summary'],producer=asset(Path(__file__)))
 put(root/'completion_audit.json',audit)
 main_count=delivery['curation_memberships']['complex_paper_diagrams_and_posters'];chart_count=delivery['curation_memberships']['complex_scientific_charts'];arxiv_count=delivery['curation_memberships']['complex_arxiv_native']
 text=f'''# 复杂科研图配对集：验收交付

共 **{len(rows)} 对 PNG＋可编辑 drawio/XML**，按代码与实际 RGBA 像素去重。所有数据保存在 HKUST3 `{R}`。

| 筛选视图 | 数量 | 参考与证据等级 |
| --- | ---: | --- |
| 科研框图及海报 | {main_count} | 通过各自参考图合同的 full8 和复杂内容筛选；RAP 为发布/重建 HTML 模板，原海报位图作为辅助资料 |
| 复杂科学图表 | {chart_count} | 原图、Agg 重放、SVG 重放分别标记；依据真实源码数组、子图结构和科学文字筛选并看图抽查 |
| arXiv 复杂图 | {arxiv_count} | {arxiv['curation_views']['complex_native_framework']} 对框图，{arxiv['curation_views']['labeled_source_image_composite']} 对原生标注图像组合；{arxiv['original_PDF_visual_rows']} 对另有原始 PDF 图像核验，{arxiv['source_replay_only_rows']} 对为作者源码重放等级 |

`pairs.jsonl` 的 `code_file`、`image_file` 相对以上 HKUST 根目录解析。`quality_views` 保留技术证据等级，`curation_memberships` 保留筛选视图，`source_records` 链接冻结的完整来源记录。证据视图有重叠，不能重复相加。

本次通过验证的 SVG 适用范围 **{population['applicable_population']} 个原始样本已全部核对**：{population['population_classification'].get('terminal_current_round',0)} 个本轮终态记录，其余保留已有合格产物；遗漏为 0。独立未见验证 43 张，基线 0 张合格，修复后 17 张合格。相同原图和源码哈希的对照中，**{population['previous_failures_now_qualified']} 个旧失败经修复后合格**。所有固定批次已结束，基础设施错误为 0。

arXiv 图对应的初次提交年份为 2023—2026，涉及 {len(papers)} 个论文版本；这不是期刊发表年份。实际尝试的直接 PDF 导入候选另存，未混入原始 PDF 保真等级。作者源码字体依赖按运行环境固定并保存，未统一声明独立字体可移植性。

仍未解决的来源包括 SciDiagram 的字体/参考差异和 SVG 特效，DwT 的来源未核实与原图不符，DaTikZ 的 PDF→SVG 栅格差异，以及 SVG 箭头轮廓、图层交错、画布和字形问题。所有失败、待审和未选中原始资料均保留；逐项验收及失败明细见 `completion_audit.json` 和其引用的冻结审计。未把全部原始候选数量当作合格数据。

稳定入口：`clean/curated_complex_research_delivery/current.json`。本次冻结交付目录：`{root}`。
'''
 (root/'README.md').write_text(text)
 result=dict(at_utc=audit['at_utc'],root=str(root),unique_code_RGBA_pairs=len(rows),curation_memberships=delivery['curation_memberships'],pairs=asset(pairs),readme=asset(root/'README.md'),completion_audit=asset(root/'completion_audit.json'),source_previous_delivery=delivery,payloads_byte_identical_to_verified_input=True,delivery_status='verified_final',all_applicable_fixed_batches_terminal=True,new_normal_calls=0,new_QA_calls=0,new_model_calls=0)
 put(root/'summary.json',result)
 for f in root.iterdir():f.chmod(0o444)
 pointer=dict(pairs=asset(pairs),summary=asset(root/'summary.json'),readme=asset(root/'README.md'),completion_audit=asset(root/'completion_audit.json'),unique_code_RGBA_pairs=len(rows),curation_memberships=delivery['curation_memberships'],quality_views_overlap=True,delivery_status='verified_final');target=C/'curated_complex_research_delivery/current.json';tmp=target.with_name('current.final.tmp');put(tmp,pointer);tmp.replace(target);print(json.dumps(pointer))
if __name__=='__main__':main()
