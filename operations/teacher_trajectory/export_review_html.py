"""Export selected complete replies, inputs, images and tools to one offline HTML."""

import argparse
import base64
import gzip
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import time

from interruption import annotation
from review_server import read_events, tool_events
from store import canonical
from verify import open_archive


class Bundle:
    def __init__(self, store):
        self.store, self.nodes, self.images = store, {}, {}

    def include(self, reference):
        if reference in self.nodes:
            return
        node = json.loads(self.store.raw(reference))
        self.nodes[reference] = node
        if node[0] == "dict":
            children = [item[1] for item in node[1]]
        elif node[0] == "list":
            children = node[1]
        else:
            children = []
        for child in children:
            self.include(child)
        if node[0] == "image":
            self.images[node[2]] = base64.b64encode(self.store.raw(node[2])).decode()

    def pack(self, value):
        if isinstance(value, dict):
            node = ["dict", [[key, self.pack(item)] for key, item in value.items()]]
        elif isinstance(value, list):
            node = ["list", [self.pack(item) for item in value]]
        else:
            node = ["value", value]
        reference = sha256(canonical(node)).hexdigest()
        self.nodes.setdefault(reference, node)
        return reference


BOOTSTRAP = r"""
<script>
const traceReady = (async () => {
  const bytes = Uint8Array.from(atob('__PAYLOAD__'), c => c.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
  window.traceData = JSON.parse(await new Response(stream).text());
  window.traceMemo = new Map(); window.traceUrls = new Map();
})();
function traceBytes(text) { return Uint8Array.from(atob(text), c => c.charCodeAt(0)); }
function traceImage(hash, mime='image/png') {
  if (!traceUrls.has(hash)) traceUrls.set(hash, URL.createObjectURL(new Blob([traceBytes(traceData.images[hash])], {type:mime})));
  return traceUrls.get(hash);
}
function traceResolve(ref, raw=false) {
  const key = ref + ':' + raw;
  if (traceMemo.has(key)) return traceMemo.get(key);
  const n = traceData.nodes[ref]; let value;
  if (n[0] === 'dict') value = Object.fromEntries(n[1].map(([k,v])=>[k,traceResolve(v,raw)]));
  else if (n[0] === 'list') value = n[1].map(v=>traceResolve(v,raw));
  else if (n[0] === 'image') value = raw ? n[1]+','+traceData.images[n[2]] : {image:traceImage(n[2],n[1].slice(5).split(';')[0]),sha256:n[2]};
  else value = n[1];
  traceMemo.set(key,value); return value;
}
window.traceGet = async function(url) {
  await traceReady; const p=url.split('/').filter(Boolean);
  if(p[0]==='manifest') return traceData.manifest;
  if(p[0]==='calls') return traceData.calls.filter(r=>r.episode===p[1]);
  const row=traceData.calls.find(r=>r.id===Number(p[1]));
  if(!row) throw Error('Unknown recorded call');
  if(p[0]==='request') return traceResolve(row.request_ref);
  if(p[0]==='raw-request') return traceResolve(row.request_ref,true);
  const response=row.response_ref?traceResolve(row.response_ref,true):{};
  const events=traceResolve(traceData.events[row.episode]);
  const message=response.choices?.[0]?.message||{};
  const tools=(message.tool_calls||[]).map(call=>({model_call:call,executed_events:events.filter(e=>e.event.callId===call.id)}));
  return {...row,response,tool_execution:tools};
};
window.traceLink = function(a,text,url) {
  if(url.startsWith('http')) {a.href=url;return a;}
  const parts=url.split('/').filter(Boolean);
  if(parts[0]==='case' && url.endsWith('.png')) {const f=traceData.assets[url];a.href=traceImage(f.hash,f.mime);return a;}
  a.href='#';
  if(parts[0]==='wire') a.textContent='完整结构化 API 回复 JSON';
  if(parts[0]==='events') a.textContent=parts[2]+' 实际工具执行记录';
  a.onclick=async event=>{
    event.preventDefault();await traceReady;let value,mime='application/json',name='record.json';
    if(parts[0]==='case') {const f=traceData.assets[url];value=traceBytes(f.data);mime='text/plain';name=parts[2];}
    else if(parts[0]==='wire') {const row=traceData.calls.find(r=>r.id===Number(parts[1]));value=JSON.stringify(traceResolve(row.response_ref,true),null,2);name='reply-'+parts[1]+'.json';}
    else if(parts[0]==='events') {value=JSON.stringify(traceResolve(traceData.events[parts[1]]).filter(e=>e.source.startsWith(parts[2]+'/')),null,2);name=parts[2]+'-tools.json';}
    else {value=JSON.stringify(await traceGet(url),null,2);name='request-'+parts[1]+'.json';}
    const object=URL.createObjectURL(new Blob([value],{type:mime}));const download=document.createElement('a');download.href=object;download.download=name;download.click();setTimeout(()=>URL.revokeObjectURL(object),60000);
  };return a;
};
</script>
"""


def export(root, manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    store = open_archive(root)
    bundle, calls, events, assets = Bundle(store), [], {}, {}
    names = ("id", "episode", "role", "stage", "started", "ended", "status", "error", "usage",
             "cost_cny", "request_ref", "response_ref", "completed")
    for case in manifest["cases"]:
        folder = root / "episodes" / case["id"]
        query = """select id,episode,role,stage,started,ended,status,error,usage,cost_upper,
            request,response,completed from calls where episode=? order by id"""
        for values in store.db.execute(query, (case["id"],)).fetchall():
            row = dict(zip(names, values))
            for key in ("request_ref", "response_ref"):
                if row[key]:
                    bundle.include(row[key])
            row.update(annotation(store, {**row, "call_id": row["id"]}))
            if row["role"] != "generator" or row["status"] != 200 or row["error"]:
                row["supervision_eligible"] = False
            calls.append(row)
        records = [record for role in ("generator", "reviewer")
                   for path in sorted(folder.glob(role + "/round*/events.jsonl"))
                   for record in read_events(path, folder)
                   if record["event"].get("type") in ("tool_call", "tool_result")]
        events[case["id"]] = bundle.pack(records)
        for name, metadata in case["files"].items():
            raw = (folder / "case" / name).read_bytes()
            digest = sha256(raw).hexdigest()
            if digest != metadata["sha256"]:
                raise ValueError("Sample artifact changed: " + case["id"] + "/" + name)
            asset = {"hash": digest, "data": base64.b64encode(raw).decode(),
                     "mime": "image/png" if name.endswith(".png") else "text/plain"}
            assets["/case/" + case["id"] + "/" + name] = asset
            if name.endswith(".png"):
                bundle.images[digest] = asset.pop("data")
    data = {"manifest": manifest, "calls": calls, "events": events,
            "nodes": bundle.nodes, "images": bundle.images, "assets": assets}
    raw = canonical(data)
    packed = base64.b64encode(gzip.compress(raw, compresslevel=6, mtime=0)).decode()
    template = Path(__file__).with_name("trace_view.html").read_text()
    template = template.replace("完整历史与图片留在远端，按需加载。", "本文件已内嵌完整结构化回复、输入历史、图片和工具记录，不依赖 localhost。原始 SSE 和完整运行日志另存远端。")
    template = template.replace("原始 JSON 和 SSE 也可查看", "完整输入与结构化原始回复也已内嵌")
    template = template.replace("<script>", BOOTSTRAP.replace("__PAYLOAD__", packed) + "\n<script>", 1)
    output.write_text(template)
    result = {"at": time.time(), "html": str(output), "bytes": output.stat().st_size,
              "sha256": sha256(output.read_bytes()).hexdigest(), "cases": len(manifest["cases"]),
              "calls": len(calls), "dag_nodes": len(bundle.nodes), "images": len(bundle.images),
              "uncompressed_payload_bytes": len(raw), "external_requests_required": False,
              "raw_sse_included": False, "complete_structured_requests_and_replies_included": True}
    output.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def export_static(root, manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    store = open_archive(root)
    pieces, calls = [], 0
    def block(title, value):
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + escape(title) + '</summary><pre>' + escape(text) + '</pre></details>'
    for number, case in enumerate(manifest['cases'], 1):
        folder = root / 'episodes' / case['id']
        pieces.append('<section id="c-' + case['id'] + '"><h2>' + str(number) + ' · ' + escape(case['paper']) + '</h2>')
        pieces.append('<p>' + str(case['generator_decisions']) + ' 次生成决策 · <a href="' + escape(case['arxiv_url'], quote=True) + '">论文来源</a></p><div class="images">')
        for name, label in [('reference.png', '原图'), ('round1.png', '第一轮实际渲染'), ('round2.png', '第二轮实际渲染')]:
            raw = (folder / 'case' / name).read_bytes()
            if sha256(raw).hexdigest() != case['files'][name]['sha256']:
                raise ValueError('Selected image changed')
            pieces.append('<figure><figcaption>' + label + '</figcaption><img src="data:image/png;base64,' + base64.b64encode(raw).decode() + '"></figure>')
        pieces.append('</div>' + block('独立 DeepSeek Reviewer 的完整反馈', case['review']))
        events = tool_events(folder)
        rows = store.db.execute('select id,role,stage,request,response,status,error,cost_upper from calls where episode=? order by id', (case['id'],)).fetchall()
        for ident, role, stage, request, response, status, error, cost in rows:
            calls += 1
            reply = store.get(response) if response else {}
            choices = reply.get('choices', [])
            message = choices[0]['message'] if choices else {}
            mark = annotation(store, {'call_id': ident, 'request_ref': request, 'response_ref': response})
            eligibility = 'Reviewer 观察，不作为监督目标' if role == 'reviewer' else '还原质量未认证'
            if not mark['supervision_eligible']:
                eligibility = '超时后未执行，原文保留，不作监督目标'
            if status != 200 or error:
                eligibility = '请求失败或中断，原始错误保留'
            title = '#' + str(ident) + ' · ' + role + ' · 第 ' + str(stage) + ' 轮 · HTTP ' + str(status)
            pieces.append('<details class="call"><summary>' + escape(title) + '</summary><p class="muted">' + escape(eligibility) + '</p>')
            pieces.append(block('模型思考：reasoning_content（完整原文）', message.get('reasoning_content') or '此请求未返回 reasoning_content。'))
            pieces.append(block('模型文本答复：content（完整原文）', message.get('content') or '此请求无文本答复。'))
            tools = [{'model_call': call, 'executed_events': events.get(call['id'], [])} for call in message.get('tool_calls', [])]
            pieces.append(block('工具请求与实际执行、返回（完整记录）', tools))
            pieces.append(block('调用元数据与来源', {'id': ident, 'role': role, 'stage': stage, 'status': status, 'error': error, 'cost_estimate_cny': cost, 'request_ref': request, 'response_ref': response, 'usage': reply.get('usage'), 'execution_annotation': mark}))
            pieces.append('</details>')
        pieces.append('</section>')
    nav = ' · '.join('<a href="#c-' + c['id'] + '">' + str(i) + ' · ' + escape(c['paper']) + '</a>' for i, c in enumerate(manifest['cases'], 1))
    head = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>五条真实 DeepSeek 轨迹（独立阅读版）</title><style>body{font:15px/1.65 system-ui;color:#203447;background:#f5f7fa;max-width:1480px;margin:auto;padding:24px}h1{font-size:26px}section{margin:28px 0;padding:20px;background:white;border:1px solid #dae2e8;border-radius:12px}.images{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}figure{margin:0}figcaption{font-weight:600}img{width:100%;height:340px;object-fit:contain}details{border:1px solid #dbe3e9;border-radius:7px;margin:9px 0;padding:10px}summary{cursor:pointer;font-weight:600}.call{background:#f9fbfd}.muted{font-size:12px;color:#617386}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,monospace;max-height:70vh;overflow:auto;background:#f1f5f8;padding:12px}a{color:#14618b}@media(max-width:800px){body{padding:12px}.images{grid-template-columns:1fr}img{height:auto;max-height:650px}}</style><h1>五条真实 DeepSeek / DSH 轨迹</h1><p><b>DeepSeek 生成 + 独立 DeepSeek 会话审图；未训练，未提供金标 XML 或 MCP 对比反馈。</b></p><p>从当时 99 条已完成、已审计案例中固定随机抽样（seed 20261120）。完整性通过不等于画面完全还原。本文件内嵌原图、两轮实际渲染，以及每次调用的全部模型思考、文字答复和工具执行/返回；不补写推理或执行。展开各条记录查看，页面无需 JavaScript、服务器或 localhost。</p><p class="muted">本阅读版不重复内嵌每一步的完整输入历史与所有观察裁剪图；这些内容保存在另一份完整版和远端原始档案中。原始 SSE 与运行日志仍在远端保留。</p><nav>'''
    output.write_text(head + nav + '</nav>' + ''.join(pieces) + '</html>')
    result = {'at': time.time(), 'html': str(output), 'bytes': output.stat().st_size,
              'sha256': sha256(output.read_bytes()).hexdigest(), 'cases': len(manifest['cases']),
              'calls': calls, 'external_requests_required': False, 'javascript_required': False,
              'all_reply_reasoning_text_and_tools_included': True, 'full_inputs_in_separate_complete_html': True}
    output.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--static", action="store_true")
    args = parser.parse_args()
    writer = export_static if args.static else export
    print(json.dumps(writer(args.root, args.manifest, args.output)))


if __name__ == "__main__":
    main()
