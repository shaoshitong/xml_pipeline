# 复杂科研图配对集：验收交付

共 **1505 对 PNG＋可编辑 drawio/XML**，按代码与实际 RGBA 像素去重。所有数据保存在 HKUST3 `/backup/shaoshitong/img2code_20261029`。

| 筛选视图 | 数量 | 参考与证据等级 |
| --- | ---: | --- |
| 科研框图及海报 | 1151 | 通过各自参考图合同的 full8 和复杂内容筛选；RAP 为发布/重建 HTML 模板，原海报位图作为辅助资料 |
| 复杂科学图表 | 92 | 原图、Agg 重放、SVG 重放分别标记；依据真实源码数组、子图结构和科学文字筛选并看图抽查 |
| arXiv 复杂图 | 262 | 99 对框图，163 对原生标注图像组合；90 对另有原始 PDF 图像核验，172 对为作者源码重放等级 |

`pairs.jsonl` 的 `code_file`、`image_file` 相对以上 HKUST 根目录解析。`quality_views` 保留技术证据等级，`curation_memberships` 保留筛选视图，`source_records` 链接冻结的完整来源记录。证据视图有重叠，不能重复相加。

本次通过验证的 SVG 适用范围 **1149 个原始样本已全部核对**：934 个本轮终态记录，其余保留已有合格产物；遗漏为 0。独立未见验证 43 张，基线 0 张合格，修复后 17 张合格。相同原图和源码哈希的对照中，**77 个旧失败经修复后合格**。所有固定批次已结束，基础设施错误为 0。

arXiv 图对应的初次提交年份为 2023—2026，涉及 175 个论文版本；这不是期刊发表年份。实际尝试的直接 PDF 导入候选另存，未混入原始 PDF 保真等级。作者源码字体依赖按运行环境固定并保存，未统一声明独立字体可移植性。

仍未解决的来源包括 SciDiagram 的字体/参考差异和 SVG 特效，DwT 的来源未核实与原图不符，DaTikZ 的 PDF→SVG 栅格差异，以及 SVG 箭头轮廓、图层交错、画布和字形问题。所有失败、待审和未选中原始资料均保留；逐项验收及失败明细见 `completion_audit.json` 和其引用的冻结审计。未把全部原始候选数量当作合格数据。

稳定入口：`clean/curated_complex_research_delivery/current.json`。本次冻结交付目录：`/backup/shaoshitong/img2code_20261029/clean/curated_complex_research_delivery_final_v2/3d52c6873d3c48d0a1ab43c108a30480`。
