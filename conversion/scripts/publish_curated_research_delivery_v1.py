"""Unify curated deliverables while preserving every evidence/reference grade."""
from pathlib import Path
import collections,datetime,hashlib,json,time,uuid
R=Path('/backup/shaoshitong/img2code_20261029')
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
def checked(ref):
    p=R/ref['file'];b=p.read_bytes();assert sha(b)==ref['sha256'];return p,b
def rows(ref):return[json.loads(l)for l in checked(ref)[1].splitlines()if l]
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def main():
    main_pointer=read(R/'clean/complexity_curation_20261102T054553Z_v1/current.json');mref=main_pointer['views']['paired_priority_complex'];main_rows=rows(mref)
    chart=read(R/'clean/complex_scientific_charts/current.json');chart_rows=rows(chart['curated_pairs'])
    arxiv=read(R/'clean/complex_arxiv_native/current.json');arxiv_rows=rows(arxiv['curated_pairs'])
    inputs=[('complex_paper_diagrams_and_posters',main_rows,'paper_diagrams_and_posters_full8'),('complex_scientific_charts',chart_rows,None),('complex_arxiv_native',arxiv_rows,'arxiv_author_native_source_replay')]
    chart_views={'provider_original_reference_aligned':'scientific_chart_provider_original','source_replay_aligned':'scientific_chart_source_replay','source_svg_backend_replay_aligned':'scientific_chart_source_SVG_backend_replay'}
    started=time.monotonic()
    while True:
        catalog=read(R/'clean/research_pairs_catalog/current.json');index=rows(catalog['index']);by_id={r['id']:r for r in index};aliases=collections.defaultdict(set)
        for pair in index:
            for source in pair['source_records']:aliases[(source.get('source_id'),pair['code_sha256'])].add(pair['id'])
        selected={};unmatched=[];memberships=collections.Counter()
        for name,items,required in inputs:
            for item in items:
                matches={item['id']}if name=='complex_arxiv_native'and item['id']in by_id and by_id[item['id']]['code_sha256']==item['code_sha256']else aliases.get((item['id'],item['code_sha256']),set())
                expected=required or chart_views[item['profile']]
                matches={i for i in matches if expected in by_id[i]['quality_views']}
                if len(matches)!=1:unmatched.append(dict(view=name,id=item['id'],matches=len(matches)));continue
                identifier=next(iter(matches));row=selected.setdefault(identifier,dict(by_id[identifier],curation_memberships=[]))
                row['curation_memberships'].append(dict(view=name,source_id=item['id'],source_profile=item.get('profile'),curation_subview=item.get('curation_view')));memberships[name]+=1
        if not unmatched:break
        if time.monotonic()-started>120:raise RuntimeError('Verified catalogue has not yet incorporated selected immutable source rows: '+json.dumps(unmatched[:5]))
        time.sleep(5)
    assert memberships['complex_paper_diagrams_and_posters']==len(main_rows)and memberships['complex_scientific_charts']==len(chart_rows)and memberships['complex_arxiv_native']==len(arxiv_rows)
    root=R/'clean/curated_complex_research_delivery_v1'/uuid.uuid4().hex;root.mkdir(parents=True);target=root/'pairs.jsonl';target.write_text(''.join(json.dumps(selected[i],sort_keys=True)+'\n'for i in sorted(selected)))
    views=collections.Counter(v for r in selected.values()for v in r['quality_views']);manifest=asset(target)
    report=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(root),unique_code_RGBA_pairs=len(selected),input_rows=sum(len(r)for _,r,_ in inputs),exact_pair_duplicates_merged=sum(len(r)for _,r,_ in inputs)-len(selected),curation_memberships=dict(memberships),evidence_view_counts=dict(views),views_overlap_and_must_not_be_added=True,pairs=manifest,inputs=dict(strict_main=mref,complex_charts=chart,complex_arxiv=arxiv,verified_catalogue=catalog['index']),source_grade_notes=dict(paper_diagrams='Full8 under declared source/reference contracts; RAP uses reconstructed released HTML templates with original posters auxiliary.',scientific_charts='Actual source arrays/panels and scientific text screening, with recorded positive/negative PNG spot checks; provider-original, Agg and SVG source replay remain separate.',arxiv='Source-native topology and labeled-composite screening with actual PNG spot checks; original-PDF visual grade only where explicitly recorded. Runtime-bound bundled fonts do not certify standalone font portability.'),all_payloads_HKUST=True,source_records_retain_complete_manifest_backlinks=True,strict_full8_not_claimed_for_all_delivery_rows=True,new_normal_calls=0,new_QA_calls=0,new_model_calls=0,goal_complete=False,producer=asset(Path(__file__)))
    summary=root/'summary.json';summary.write_text(json.dumps(report,indent=2))
    text=f'''# 复杂科研图配对：当前筛选快照

共 {len(selected)} 个按源码与实际 RGBA 去重的 PNG＋可编辑代码配对；文件均在 `{R}`。

- 科研框图及海报：{len(main_rows)} 对，通过各自声明参考图合同的 full8 验收和复杂度筛选；RAP 的参考为发布/重建 HTML 模板，原海报位图另存为辅助材料。
- 复杂科学图表：{len(chart_rows)} 对，依据实际源码数组、子图结构和科学文字筛选，并抽查真实 PNG。原始参考图、Agg 重放和 SVG 后端重放等级分别保留。
- arXiv 复杂图：{len(arxiv_rows)} 对，包括 {arxiv['curation_views']['complex_native_framework']} 对框图及 {arxiv['curation_views']['labeled_source_image_composite']} 对带原生标注的图像组合。其中 {arxiv['original_PDF_visual_rows']} 对另有原始 PDF 图像核验，其余 {arxiv['source_replay_only_rows']} 对为作者源码重放等级。

使用 `pairs.jsonl` 的 `code_file`、`image_file`，相对路径以以上 HKUST 根目录解析。`quality_views` 记录技术证据等级，`curation_memberships` 记录筛选视图，`source_records` 链接冻结的完整来源记录；证据视图有重叠，数量不能直接相加。

源码重放不等于原始图像保真。arXiv 作者源码的字体依赖已按运行环境固定并保存，未统一宣称独立字体可移植性。被保留待审及未选中的原始数据均未删除。

当前转换批次仍在运行。这是一份有界、可核验的筛选快照，尚未宣称整个目标完成。
'''
    (root/'README.md').write_text(text)
    for p in root.iterdir():p.chmod(0o444)
    parent=R/'clean/curated_complex_research_delivery';parent.mkdir(exist_ok=True);pointer=dict(pairs=asset(target),summary=asset(summary),readme=asset(root/'README.md'),unique_code_RGBA_pairs=len(selected),curation_memberships=dict(memberships),quality_views_overlap=True,goal_complete=False);tmp=parent/'current.tmp';tmp.write_text(json.dumps(pointer,indent=2));tmp.replace(parent/'current.json');print(json.dumps(pointer))
if __name__=='__main__':main()
