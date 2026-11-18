"""Export the finished paired experiment as one offline comparison page."""

import argparse
from base64 import b64encode
from collections import Counter
from hashlib import sha256
from html import escape, unescape
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


def read_json(path):
    return json.loads(path.read_text())


def audit(folder):
    stages = [f"gen-{n}" for n in range(1, 5)] + [f"review-{n}" for n in range(1, 4)]
    for stage in stages:
        state = read_json(folder / stage / "status.json")
        if state["exit"] or not state["completed"]:
            raise ValueError(f"Incomplete stage: {folder.name}/{stage}")
    calls = []
    responses = {}
    finals = {}
    for path in sorted(folder.glob("*/events.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines()
                if line.startswith("{") and line.endswith("}")]
        calls.extend({**row, "stage": path.parent.name} for row in rows if row["type"] == "tool_call")
        responses.update(((path.parent.name, row["callId"]), row) for row in rows
                         if row["type"] == "tool_result")
        finals[path.parent.name] = next((r["text"] for r in reversed(rows) if r["type"] == "final"), "")
    tool_counts = dict(Counter(call["tool"] for call in calls))
    checks = [call for call in calls if call["tool"] == "mcp__drawio__check"]
    rejected = [{"stage": call["stage"], "input": call["input"],
                 "result": responses[call["stage"], call["callId"]]["result"]}
                for call in checks if responses[call["stage"], call["callId"]]["status"] == "error"]
    completed = [call for call in checks
                 if responses[call["stage"], call["callId"]]["status"] == "completed"]
    expected = 0 if folder.name == "self" else 3
    if len(completed) != expected:
        raise ValueError(f"Unexpected completed MCP call count: {folder.name} {len(completed)}")
    if folder.name == "mcp" and [call["input"]["candidate"] for call in completed] != [
            f"round{n}.drawio" for n in range(1, 4)]:
        raise ValueError("MCP checks did not follow the three review rounds")
    return {"tool_counts": tool_counts, "mcp_calls": len(completed),
            "mcp_attempts": len(checks), "rejected_mcp_attempts": rejected,
            "final_answer": finals["gen-4"], "continuations": [
                p.parent.name for p in folder.glob("*-continuation-*/events.jsonl")]}


def xml_integrity(data, reference):
    def content(xml):
        cells = ET.fromstring(xml).findall(".//mxCell")
        labels = Counter(" ".join(unescape(re.sub("<[^>]+>", " ", c.get("value", ""))).split())
                         for c in cells if c.get("value"))
        return cells, labels

    cells, labels = content(data)
    _, expected = content(reference)
    ids = [c.get("id") for c in cells]
    return {"vertices": sum(c.get("vertex") == "1" for c in cells),
            "edges": sum(c.get("edge") == "1" for c in cells),
            "text_labels": sum(labels.values()), "text_multiset_matches_reference": labels == expected,
            "duplicate_ids": len(ids) - len(set(ids)),
            "dangling_references": sum(c.get(key) not in ids for c in cells
                                       for key in ("parent", "source", "target") if c.get(key))}


def collect(run, arm, target, gold):
    from verifier import Verifier

    folder = run / arm
    result = read_json(folder / "result.json")
    receipt = audit(folder)
    if read_json(folder / "case/selected.json").get("candidate") != "round4.drawio":
        raise ValueError("Model selected an unexpected final artifact")
    analysis = run / "analysis" / arm
    analysis.mkdir(parents=True)
    (analysis / "target.png").write_bytes(target)
    verifier = Verifier(analysis, gold, reveal_structure=True)
    rounds = []
    for n in range(1, 5):
        xml = folder / "case" / f"round{n}.drawio"
        data = xml.read_bytes()
        digest = sha256(data).hexdigest()
        if digest != result["checkpoints"][n - 1]["sha256"]:
            raise ValueError(f"Checkpoint changed after generation: {arm}/{n}")
        feedback, score = verifier.evaluate(data)
        row = {"round": n, "xml": str(xml), "sha256": digest,
               "png": str(analysis / feedback["candidate_png"]), "counts": feedback["structural_counts"],
               "native_png": str(folder / "case" / f"round{n}.png"), "score": score,
               "integrity": xml_integrity(data, gold.xml)}
        if n < 4:
            row["review"] = read_json(folder / "case" / f"review{n}.json")
        rounds.append(row)
        print(json.dumps({"arm": arm, "round": n, "counts": row["counts"]}), flush=True)
    return {"session_id": result["session_id"], "audit": receipt, "rounds": rounds}


def uri(data, media):
    return f"data:{media};base64," + b64encode(data).decode()


def picture(path, label):
    return (f'<figure><figcaption>{escape(label)}</figcaption>'
            f'<img tabindex="0" alt="{escape(label)}" src="{uri(path.read_bytes(), "image/png")}"></figure>')


def panels(folder, target, experiment):
    from PIL import Image

    sources = [("target", "目标图", target)] + [
        (arm, label, Path(experiment[arm]["rounds"][-1]["png"]))
        for arm, label in (("self", "自查"), ("mcp", "使用 MCP"))]
    body = ['<section><h2>最终版分区放大</h2><p>此处将候选渲染配准到目标图后裁剪；上方及各轮全图保留原始渲染边界。</p>']
    cuts = (0, .235, .565, .785, 1)
    for n, (left, right) in enumerate(zip(cuts, cuts[1:]), 1):
        body.append(f'<h3>分区 {n}</h3><div class="grid panels">')
        for arm, label, path in sources:
            output = folder / f"{arm}-panel{n}.png"
            with Image.open(path) as image:
                image.crop((round(left * image.width), 0, round(right * image.width), image.height)).save(output)
            body.append(picture(output, label))
        body.append('</div>')
    return ''.join(body) + '</section>'


def details(label, value):
    return (f'<details><summary>{escape(label)}</summary><pre>'
            + escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
            + "</pre></details>")


def page(folder, target, experiment):
    body = ['''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>DPSK 四轮重建对照</title>
<style>body{font:16px/1.6 system-ui,sans-serif;background:#eef3f4;color:#17262e;margin:0}
main{max-width:1450px;margin:auto;padding:24px}section{background:white;margin:18px 0;padding:18px;border:1px solid #d6e0e3;border-radius:10px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}figure{margin:0}figcaption{font-weight:650}
img{width:100%;height:230px;object-fit:contain;cursor:zoom-in}.panels img{height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:450px;overflow:auto;background:#f3f6f6;padding:10px}
summary{cursor:pointer}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:8px;border-bottom:1px solid #d6e0e3}
dialog{max-width:96vw;width:96vw;height:90vh;padding:8px;border:1px solid #789;box-sizing:border-box}dialog::backdrop{background:#000b}.zoom{height:calc(100% - 42px);overflow:auto}.zoom img{width:auto;height:auto;max-width:none;cursor:default}button{padding:7px 16px;margin:0 4px 6px 0}
a{color:#005d54}@media(max-width:850px){.grid{grid-template-columns:1fr}img{height:auto}main{padding:12px}}
</style></head><body><main><h1>DPSK 四轮重建对照</h1>
<p>两路分别从原图开始，各生成四版并 review 三次。自查一路只看目标和自己的历史版本，MCP 一路在 review 阶段额外读取结构报告。</p>
<p>执行中，自查首版触发过单回合超时，MCP 首次 review 曾返回空回答且缺少文件。两路均在原 session 内续跑并补齐产物。</p>
<p>MCP 只在三次 review 中开放。MCP 组最终生成时曾额外尝试调用，工具返回 unknown tool，没有提供第四次反馈。</p>
<p>以下自动诊断按对象匹配计算，包含配准和匹配不确定项。数字需要结合具体图像及 XML 判断。</p>
<p>点击任意图片可放大、横向滚动；下载包包含每版 XML、原始渲染、配准预览及三次 review。</p>
<section><h2>最终结果</h2><div class="grid">''', picture(target, "目标图")]
    labels = {"self": "自查", "mcp": "使用 MCP"}
    for arm in ("self", "mcp"):
        body.append(picture(Path(experiment[arm]["rounds"][-1]["native_png"]), labels[arm]))
    body.append("</div></section>")
    body.append(panels(folder, target, experiment))
    keys = ("label_changed", "edge_direction_reversed", "edge_binding_changed",
            "edge_arrowheads_changed", "edge_route_changed", "ambiguous_correspondence")
    body.append("<section><h2>结构诊断（包含疑似项）</h2><p>标签检查另以文本多重集合核对，详见各版完整性记录。把框内文字拆为独立文本等表示变化，也可能触发标签诊断；诊断数不等于实际错误数。</p><table><tr><th>版本</th><th>标签诊断</th><th>方向</th>"
                "<th>端点绑定</th><th>箭头样式</th><th>走线</th><th>匹配不确定</th></tr>")
    for n in range(4):
        for arm in ("self", "mcp"):
            counts = experiment[arm]["rounds"][n]["counts"]
            body.append(f"<tr><td>{labels[arm]} · {n + 1}</td>"
                        + "".join(f"<td>{counts.get(key, 0)}</td>" for key in keys) + "</tr>")
    body.append("</table></section>")
    for n in range(4):
        body.append(f'<section><h2>第 {n + 1} 版</h2><div class="grid">' + picture(target, "目标图"))
        for arm in ("self", "mcp"):
            row = experiment[arm]["rounds"][n]
            body.append(picture(Path(row["native_png"]), labels[arm]))
        body.append("</div>")
        for arm in ("self", "mcp"):
            row = experiment[arm]["rounds"][n]
            name = f"{arm}-round{n + 1}.drawio"
            body.append(f'<p><a download="{name}" href="{uri(Path(row["xml"]).read_bytes(), "application/xml")}">'
                        f"下载 {labels[arm]} 第 {n + 1} 版 XML</a></p>")
            body.append(details(labels[arm] + " · XML 完整性及标签内容核对", row["integrity"]))
            if "review" in row:
                body.append(details(labels[arm] + " · 本版 review 原文", row["review"]))
        body.append("</section>")
    for arm in ("self", "mcp"):
        body.append("<section><h2>" + labels[arm] + "的最终回答和审计</h2>"
                    + details("DPSK 最终回答", experiment[arm]["audit"]["final_answer"])
                    + details("会话与工具计数", {"session_id": experiment[arm]["session_id"],
                                              "audit": experiment[arm]["audit"]}) + "</section>")
    body.append('''</main><dialog id="viewer"><button id="close">关闭</button><button id="fit">适应宽度</button><button id="actual">原始尺寸</button><div class="zoom"><img id="large" alt="放大预览"></div></dialog>
<script>const viewer=document.getElementById('viewer'),large=document.getElementById('large');
function openImage(image){large.src=image.src;large.alt=image.alt;large.style.width='auto';viewer.showModal()}
document.querySelectorAll('figure img').forEach(image=>{image.onclick=()=>openImage(image);image.onkeydown=e=>{if(e.key==='Enter')openImage(image)}});
document.getElementById('close').onclick=()=>viewer.close();document.getElementById('fit').onclick=()=>large.style.width='100%';document.getElementById('actual').onclick=()=>large.style.width='auto';
</script></body></html>''')
    (folder / "index.html").write_text("".join(body), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "dataset", "manifest", "compiler"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    sys.path[:0] = [str(args.compiler / name) for name in
                    ("drawio_semantic_compiler", "drawio_compare", "scripts")]
    from compiler import compile_bytes

    record, = read_json(args.manifest).values()
    target = args.dataset / record["image_file"]
    if sha256(target.read_bytes()).hexdigest() != record["image_sha256"]:
        raise ValueError("Target image changed")
    gold_data = (args.dataset / record["code_file"]).read_bytes()
    if sha256(gold_data).hexdigest() != record["code_sha256"]:
        raise ValueError("Reference changed")
    gold = compile_bytes(gold_data)
    experiment = {arm: collect(args.run, arm, target.read_bytes(), gold) for arm in ("self", "mcp")}
    output = args.run / "review"
    output.mkdir()
    (output / "summary.json").write_text(json.dumps(experiment, ensure_ascii=False, indent=2))
    page(output, target, experiment)
    with ZipFile(output / "dpsk-four-round-review.zip", "w", ZIP_DEFLATED) as archive:
        archive.write(target, "target.png")
        for name in ("index.html", "summary.json"):
            archive.write(output / name, name)
        for arm in ("self", "mcp"):
            for row in experiment[arm]["rounds"]:
                archive.write(row["xml"], f"{arm}/round{row['round']}.drawio")
                archive.write(row["native_png"], f"{arm}/round{row['round']}.png")
                archive.write(row["png"], f"{arm}/aligned-round{row['round']}.png")
                if "review" in row:
                    archive.writestr(f"{arm}/review{row['round']}.json",
                                     json.dumps(row["review"], ensure_ascii=False, indent=2))
        for path in output.glob("*-panel*.png"):
            archive.write(path, "panels/" + path.name)
    print(output, flush=True)


if __name__ == "__main__":
    main()
