"""Build a standalone, offline HTML viewer from actual rollout artifacts."""

import argparse
import base64
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re


def read_json(path, warnings):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as error:
        warnings.append(f"{path.name} 尚不完整：{type(error).__name__}")
        return None


def asset(path):
    if not path.is_file():
        return None
    data = path.read_bytes()
    if not data:
        return None
    return {"data": base64.b64encode(data).decode(), "bytes": len(data),
            "sha256": sha256(data).hexdigest()}


def audit(path, warnings):
    requests = image_requests = image_inputs = 0
    models = set()
    for line in path.read_text().splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            warnings.append(f"{path.name} 有未完成的审计行，未计入统计")
            continue
        if "response_to" in record:
            continue
        requests += 1
        images = record.get("image_inputs", [])
        image_requests += bool(images)
        image_inputs += len(images)
        if record.get("model"):
            models.add(record["model"])
    return {"file": path.name, "requests": requests, "image_requests": image_requests,
            "image_inputs": image_inputs, "models": sorted(models)}


def gpu_summary(path):
    if not path.is_file():
        return None
    rows = list(csv.DictReader(path.read_text().splitlines(), skipinitialspace=True))
    memory, utilization, names = [], [], set()
    for row in rows:
        for key, value in row.items():
            if key is None or not isinstance(value, str) or not value:
                continue
            if key == "name":
                names.add(value.strip())
            match = re.match(r"\s*(\d+(?:\.\d+)?)", value)
            if match and key.startswith("memory.used"):
                memory.append(float(match[1]))
            if match and key.startswith("utilization.gpu"):
                utilization.append(float(match[1]))
    return {"samples": len(rows), "names": sorted(names),
            "peak_memory_mib": max(memory, default=None),
            "peak_utilization": max(utilization, default=None)}


def collect_run(name, root):
    warnings = []
    episode = root / "episode"
    case = episode / "case"
    protocol = read_json(episode / "protocol.json", warnings) or {}
    found = set()
    for pattern in ("round*.*", "review*.json"):
        for path in case.glob(pattern):
            match = re.match(r"(?:round|review)(\d+)[.]", path.name)
            if match:
                found.add(int(match[1]))
    for role in ("generator", "reviewer"):
        for path in (episode / role).glob("round*/status.json"):
            found.add(int(path.parent.name.removeprefix("round")))
    planned = protocol.get("rounds")
    if isinstance(planned, int) and planned > 0:
        found.update(range(1, planned + 1))
    rounds = []
    for number in sorted(found):
        review = case / f"review{number}.json"
        statuses = {}
        for role in ("generator", "reviewer"):
            status = read_json(episode / role / f"round{number}/status.json", warnings)
            statuses[role] = ({key: status.get(key) for key in
                              ("exit", "completed", "seconds", "tool_calls")} if status else None)
        rounds.append({"number": number, "png": asset(case / f"round{number}.png"),
                       "xml": asset(case / f"round{number}.drawio"), "statuses": statuses,
                       "review": review.read_text() if review.is_file() else None,
                       "review_expected": number != planned})
    grade_path = next((p for p in (root / "host-grade.json", episode / "host-grade.json")
                       if p.is_file()), root / "host-grade.json")
    grade = read_json(grade_path, warnings)
    # Keep gold object labels, normalized gold XML, and raw comparator pages private.
    if grade is not None:
        grade = {"counts": {key: grade.get("counts", {}).get(key) for key in "ABC"},
                 "metric": {key: grade.get("metric", {}).get(key)
                            for key in ("weights", "weights_status", "E", "R", "formula")}}
    return {"name": name, "path": str(root), "protocol": {
                key: protocol.get(key) for key in
                ("generator", "reviewer", "reviewer_frozen", "separate_model_instances", "rounds")},
            "rounds": rounds, "grade": grade,
            "completed_marker": (episode / "completed.json").is_file(),
            "launch": read_json(root / "launch-result.json", warnings),
            "audits": [audit(p, warnings) for p in sorted(root.glob("*-requests.jsonl"))],
            "gpu": gpu_summary(root / "gpu.csv"), "warnings": warnings}


PAGE = r"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>Draw.io rollout 产物对照</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#fff;color:#17202a;font:15px/1.6 system-ui,-apple-system,sans-serif}main{max-width:1440px;margin:auto;padding:28px}h1{font-size:26px;margin:0 0 8px}h2{font-size:17px;margin:0 0 10px}.muted{color:#66717e}.bar{display:flex;gap:16px;align-items:end;flex-wrap:wrap;padding:18px 0;position:sticky;top:0;background:#fffffff5;z-index:2}label{display:flex;flex-direction:column;gap:4px;font-size:13px}select,button,.download{font:inherit;border:1px solid #cdd5de;border-radius:7px;padding:8px 12px;background:#fff;color:#17202a}select{min-width:180px}button,.download{cursor:pointer}.download{text-decoration:none;display:inline-block}.download[aria-disabled=true]{color:#89939e;pointer-events:none}.card{border:1px solid #dce2e9;border-radius:10px;padding:16px;margin-bottom:18px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}.image-box{height:58vh;min-height:260px;display:flex;align-items:center;justify-content:center;overflow:auto;background:#fafbfc;border:1px solid #e5e9ee;border-radius:7px}.image-box img{max-width:100%;max-height:100%;object-fit:contain;cursor:zoom-in}.missing{color:#7a6570;text-align:center;padding:30px}table{width:100%;border-collapse:collapse;margin:8px 0}th,td{text-align:left;padding:9px 8px;border-bottom:1px solid #e8ecf0;vertical-align:top}th{font-weight:600;font-size:13px;color:#526071}.scroll{overflow:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f9fb;border-radius:7px;padding:14px;font:13px/1.65 ui-monospace,monospace}summary{cursor:pointer;font-weight:600}.stats{display:flex;gap:16px;flex-wrap:wrap}.stat{min-width:100px}.stat strong{display:block;font-size:23px}.badge{display:inline-block;border:1px solid #dce2e9;border-radius:20px;padding:3px 10px;margin:4px 6px 4px 0;font-size:13px}.ok{color:#166146}.fail{color:#9c3c37}#notes{font-size:13px}dialog{width:95vw;height:94vh;border:1px solid #cdd5de;border-radius:10px;padding:16px}dialog::backdrop{background:#0008}.zoom-scroll{overflow:auto;height:calc(100% - 50px);text-align:center}.zoom-scroll img{max-width:none}footer{font-size:12px;color:#66717e;padding:15px 0}@media(max-width:760px){main{padding:16px}.pair{grid-template-columns:1fr}.image-box{height:50vh}.bar{gap:10px}select{min-width:145px}h1{font-size:22px}}
</style>
<main>
<h1>Draw.io rollout 产物对照</h1>
<div class="muted">实验阶段：rollout，无参数更新。Reviewer 按实验协议使用独立冻结模型；下方单独显示协议记录是否齐全。阶段完成、Reviewer 的 PASS 和宿主对象统计均不代表质量合格。</div>
<div class="bar"><label>模型 / 运行<select id="runs"></select></label><label>轮次<select id="rounds"></select></label><a id="xml" class="download">下载本轮 XML</a></div>
<section class="card"><h2 id="run-title"></h2><div id="protocol"></div><div id="run-status"></div><div id="source" class="muted"></div></section>
<section class="pair"><div class="card"><h2>原图</h2><div id="reference" class="image-box"></div></div><div class="card"><h2 id="candidate-title">候选</h2><div id="candidate" class="image-box"></div><div id="artifact" class="muted"></div></div></section>
<section class="card"><h2>本轮阶段记录</h2><div class="scroll"><table><thead><tr><th>角色</th><th>阶段状态</th><th>退出码</th><th>工具调用</th><th>耗时 / 秒</th></tr></thead><tbody id="stages"></tbody></table></div><div class="muted">工具次数取自 status.json；缺失记录显示“未记录”。PNG / XML 文件存在不等于模型阶段成功。</div></section>
<section class="card"><details><summary>Reviewer JSON 原文</summary><pre id="review"></pre></details></section>
<section class="card"><h2>请求与 GPU 审计</h2><div id="audit"></div><div id="gpu" class="muted"></div><div class="muted">图片请求为含图片输入的请求；图片输入次数包含历史重放。请求记录不表示请求成功或模型已正确理解图像。</div></section>
<section class="card"><h2>运行级宿主对象评分</h2><div class="muted">仅显示已存在的 host-grade.json，不将其归因于当前所选轮次。对象级标记受比较器覆盖范围和容差限制。</div><div id="grade"></div></section>
<div id="notes" class="muted"></div><footer id="footer"></footer>
</main><dialog id="zoom"><button id="close">关闭大图</button><div class="zoom-scroll"><img id="zoom-image" alt="原始分辨率图像"></div></dialog>
<script id="data" type="application/json">__DATA__</script>
<script>
const data=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);
const value=(x,missing='未记录')=>x===null||x===undefined?missing:String(x);
function text(id,x){$(id).textContent=x}
function option(select,label,v){const el=document.createElement('option');el.textContent=label;el.value=v;select.append(el)}
function image(id,file,label){const box=$(id);box.replaceChildren();if(!file){const p=document.createElement('div');p.className='missing';p.textContent='未完成：缺少可展示的 PNG';box.append(p);return}const img=document.createElement('img');img.src='data:image/png;base64,'+file.data;img.alt=label;img.onerror=()=>{box.textContent='PNG 文件存在，但浏览器无法解码'};img.onclick=()=>{$('zoom-image').src=img.src;$('zoom').showModal()};box.append(img)}
function stage(s,expected){if(!expected&&!s)return '末轮无 Review 阶段';if(!s)return '未完成：缺少状态文件';if(s.exit!==null&&s.exit!==undefined&&s.exit!==0)return '失败';return s.exit===0&&s.completed===true?'阶段完成':'未完成'}
function row(table,values){const tr=document.createElement('tr');for(const v of values){const td=document.createElement('td');td.textContent=v;tr.append(td)}table.append(tr)}
function draw(){
 const run=data.runs[Number($('runs').value)],round=run.rounds.find(r=>r.number===Number($('rounds').value)),p=run.protocol;
 text('run-title',run.name);text('source','产物来源：'+run.path);
 text('protocol','Generator：'+value(p.generator)+'；Reviewer：'+value(p.reviewer)+'；独立模型实例：'+(p.separate_model_instances===true?'协议已记录':'未记录')+'；Reviewer 冻结：'+(p.reviewer_frozen===true?'协议已记录':'未记录'));
 const exit=run.launch?.exit;text('run-status','主机完成标记：'+(run.completed_marker?'存在':'未完成 / 未发现')+'；launch 退出码：'+value(exit));
 image('reference',data.reference,'原图');image('candidate',round?.png,'候选图');text('candidate-title',round?'候选 · 第 '+round.number+' 轮':'候选 · 暂无轮次产物');
 text('artifact',round?'PNG：'+(round.png?'已有文件':'未完成')+'；XML：'+(round.xml?round.xml.bytes+' 字节，SHA256 '+round.xml.sha256:'未完成'):'未完成：未发现任何轮次文件或协议轮次记录');
 const link=$('xml');link.removeAttribute('href');link.setAttribute('aria-disabled',!round?.xml);link.textContent=round?.xml?'下载本轮 XML':'XML 未完成';if(round?.xml){link.href='data:application/xml;base64,'+round.xml.data;link.download=run.name+'-round'+round.number+'.drawio'}
 $('stages').replaceChildren();for(const role of ['generator','reviewer']){const s=round?.statuses[role];row($('stages'),[role==='generator'?'Generator':'Reviewer',stage(s,role==='generator'||round?.review_expected!==false),value(s?.exit),value(s?.tool_calls),value(s?.seconds)])}
 text('review',round?.review??(round?.review_expected===false?'末轮无 Review 阶段；未发现 Reviewer JSON。':'未完成：未发现 Reviewer JSON。'));
 const a=$('audit');a.replaceChildren();if(!run.audits.length){a.textContent='未完成：未发现请求审计文件。'}else{const table=document.createElement('table');row(table,['审计文件 / 模型','请求数','含图请求','图片输入次数']);for(const item of run.audits)row(table,[item.file+' / '+item.models.join(', '),item.requests,item.image_requests,item.image_inputs]);a.append(table)}
 text('gpu',run.gpu?'GPU：'+(run.gpu.names.join(', ')||'名称未记录')+'；采样行数 '+run.gpu.samples+'；峰值显存 '+value(run.gpu.peak_memory_mib)+' MiB；峰值利用率 '+value(run.gpu.peak_utilization)+'%':'未完成：未发现 GPU 采样文件。');
 const g=$('grade');g.replaceChildren();if(!run.grade){g.textContent='未完成：未发现可读取的 host-grade.json。'}else{const metric=run.grade.metric,weights=metric.weights||{},unset=metric.weights_status==='unset'||['a','b','c'].some(k=>weights[k]===null||weights[k]===undefined);const stats=document.createElement('div');stats.className='stats';for(const [label,num]of [...'ABC'].map(k=>[k,run.grade.counts[k]]).concat([['E',unset?'未定':value(metric.E,'未定义')],['R',unset?'未定':value(metric.R,'未定义')]])){const part=document.createElement('div');part.className='stat';const strong=document.createElement('strong');strong.textContent=value(num);part.append(strong,document.createTextNode(label));stats.append(part)}g.append(stats);const p=document.createElement('p');p.className='muted';p.textContent='权重 a / b / c：'+['a','b','c'].map(k=>value(weights[k],'未定')).join(' / ')+'；'+value(metric.formula,'公式未记录');g.append(p)}
 text('notes',run.warnings.join('；'));text('footer','离线自包含报告 · 生成时间 '+data.generated+' · 不包含原始模型 reasoning 或隐藏思维。');
}
function selectRun(){const run=data.runs[Number($('runs').value)],select=$('rounds');select.replaceChildren();for(const r of run.rounds)option(select,'第 '+r.number+' 轮'+(r.png?'':' · PNG 未完成'),r.number);if(!run.rounds.length)option(select,'暂无轮次',0);const ready=run.rounds.filter(r=>r.png);if(ready.length)select.value=ready.at(-1).number;draw()}
for(const [i,run]of data.runs.entries())option($('runs'),run.name,i);$('runs').onchange=selectRun;$('rounds').onchange=draw;$('close').onclick=()=>$('zoom').close();selectRun();
</script></html>"""


def make_html(reference, runs):
    data = {"reference": asset(reference), "runs": runs,
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    return PAGE.replace("__DATA__", payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--run", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.reference.is_file():
        parser.error("--reference PNG 文件不存在")
    runs = []
    for entry in args.run:
        name, separator, path = entry.partition("=")
        if not separator or not name or not path:
            parser.error("--run 格式为 NAME=PATH")
        runs.append(collect_run(name, Path(path).expanduser().resolve()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(make_html(args.reference, runs), encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "runs": len(runs),
                      "bytes": args.output.stat().st_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
