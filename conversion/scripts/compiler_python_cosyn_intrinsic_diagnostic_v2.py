"""Finite consumed-case SVG/native intrinsic text diagnosis; no candidates."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
IDS=('61e2902e76dfac2ba33d344fc89a78c16efb39bd44fbd171943133d04917a00d','5a168a15ecd06ff195a1910509f228151d223045bbf38535da73141350c9e95b','a213c15534b068ae23a356f04358c364d1c112323692ed390e7709deffe8300b')
sha=lambda b:hashlib.sha256(b).hexdigest()

OBSERVE=r"""()=>{const rows={};for(const e of document.querySelectorAll('text[data-intrinsic-id]')){const cs=getComputedStyle(e),m=e.getScreenCTM(),c=e.getCTM(),root=e.ownerSVGElement,n=e.firstChild;const styles={};for(const key of cs){if(/^(?:font|text|word|letter|line|white|direction|writing|unicode|dominant|alignment|baseline)/.test(key))styles[key]=cs.getPropertyValue(key);}const chars=[];for(const {segment,index}of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){const r=document.createRange();r.setStart(n,index);r.setEnd(n,index+segment.length);const b=r.getBoundingClientRect();chars.push({text:segment,x:b.x,y:b.y,width:b.width,height:b.height});}const mat=m=>[m.a,m.b,m.c,m.d,m.e,m.f];const advances=[];for(let i=1;i<=e.getNumberOfChars();i++)advances.push(e.getSubStringLength(0,i));rows[e.getAttribute('data-intrinsic-id')]={styles,screenCTM:mat(m),localCTM:mat(c),rootCTM:mat(root.getScreenCTM()),rootViewBox:root.getAttribute('viewBox'),bbox:{x:e.getBBox().x,y:e.getBBox().y,width:e.getBBox().width,height:e.getBBox().height},computedTextLength:e.getComputedTextLength(),advances,chars,originalAttributes:Object.fromEntries([...e.attributes].filter(a=>!a.name.includes('family')).map(a=>[a.name,a.value]))};}return rows;}"""

NATIVE=r"""async ([xml,width,height])=>{const d=document.getElementById('graph');d.style.cssText='position:relative;margin:0;padding:0;border:0;overflow:hidden;background:white;width:'+width+'px;height:'+height+'px';d.setAttribute('data-mxgraph',JSON.stringify({xml,nav:false,resize:false,responsive:false,'auto-fit':false,'auto-origin':false,'browser-translate':false,'allow-zoom-in':false,'allow-zoom-out':false,center:false,border:0,zoom:1,lightbox:false,editable:false,'dark-mode':'light','show-note-icons':false}));GraphViewer.createViewerForElement(d,v=>{window.evalViewer=v});}"""


def load(identifier):
    candidates=sorted((R/'clean/compiler_python_cosyn_frontend_v1'/identifier[:2]/identifier).glob('*/baseline.drawio'))
    if not candidates:raise ValueError('missing_consumed_baseline:'+identifier)
    baseline=candidates[0];xml=baseline.read_text();model=ET.fromstring(xml);carrier=json.loads(next(c for c in model.iter('mxCell')if c.get('id')=='0').get('dataCoSynOfficialCompleteFrameV1'))
    directories=sorted((R/'clean/compiler_python_cosyn_frame_v1'/identifier[:2]/identifier).glob('*'))
    frame=next(p for p in directories if sha((p/'source.registered.svg').read_bytes())==carrier['registered_source_svg_sha256'])
    positions=json.loads((frame/'source_positions.json').read_text());dom=json.loads((frame/'source_dom.json').read_text());native=json.loads((baseline.parent/'baseline_native_info.json').read_text())
    matrix={o['id']:o['matrix']for o in dom['objects']if o['type']=='text'}
    families={}
    for cell in model.iter('mxCell'):
        if cell.get('id')not in positions:continue
        inner=ET.fromstring(cell.get('value'));text=next(e for e in inner.iter()if e.tag.rsplit('}',1)[-1]=='text');families[cell.get('id')]=text.get('font-family')
    modelnode=model.find('.//mxGraphModel');css=[]
    for pair in modelnode.get('extFonts','').split('|'):
        if not pair:continue
        family,uri=pair.split('^',1);css.append('@font-face{font-family:'+json.dumps(family)+';src:url('+json.dumps(uri)+');font-weight:normal;font-style:normal;}')
    return dict(id=identifier,xml=xml,svg=(frame/'source.registered.svg').read_text(),source=positions,baseline=native,matrix=matrix,families=families,css='\n'.join(css),files={str(p.relative_to(R)):sha(p.read_bytes())for p in [baseline,baseline.parent/'baseline_native_info.json',frame/'source_positions.json',frame/'source_dom.json',frame/'source.registered.svg']})


def metrics(source,native):
    out={}
    for key,want in source.items():
        got=native[key];a,b=want['chars'],got['chars']
        if [x['text']for x in a]!=[x['text']for x in b]:raise ValueError('fresh_diagnostic_text_changed:'+key)
        dx=[y['x']-x['x']for x,y in zip(a,b)];dy=[y['y']-x['y']for x,y in zip(a,b)];mx,my=statistics.median(dx),statistics.median(dy)
        out[key]=dict(chars=len(a),median_translation=[mx,my],spacing_residual=max(max(abs(x-mx)for x in dx),max(abs(y-my)for y in dy)),width_error=max(abs(y['width']-x['width'])for x,y in zip(a,b)),height_error=max(abs(y['height']-x['height'])for x,y in zip(a,b)))
    return out


def run(output):
    from playwright.sync_api import sync_playwright
    from fixed_batch_conversion_adapters_v1 import CHROME
    from native_worker import native
    output=Path(output).resolve();assert output.is_relative_to(W);output.mkdir(parents=True,exist_ok=False)
    summaries=[]
    with sync_playwright()as playwright:
        browser=playwright.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
        try:
            for identifier in IDS:
                case=load(identifier);width,height=case['baseline']['canvas'];context=browser.new_context(viewport={'width':max(width,640),'height':max(height,480)},device_scale_factor=1,service_workers='block');context.route('**/*',lambda route:route.abort())
                try:
                    source=context.new_page();source.set_content('<style>html,body{margin:0;padding:0;background:white}svg{display:block}</style><style>'+case['css']+'</style>'+case['svg'])
                    source.evaluate('''([positions,families,w,h])=>{const svg=document.querySelector('svg');svg.style.width=w+'px';svg.style.height=h+'px';svg.setAttribute('width',w);svg.setAttribute('height',h);const texts=[...svg.querySelectorAll('text')];for(const [id,row]of Object.entries(positions)){const e=texts[row.source_element_index];e.setAttribute('data-intrinsic-id',id);e.style.fontFamily=families[id];e.style.fontWeight='normal';e.style.fontStyle='normal';}}''',[case['source'],case['families'],width,height]);source.evaluate('document.fonts.ready');freshsource=source.evaluate(OBSERVE)
                    page=context.new_page();page.set_content('<!doctype html><html><head><style>html,body{margin:0;padding:0;background:white}</style></head><body><div id="graph"></div></body></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'));page.evaluate(NATIVE,[case['xml'],width,height]);page.wait_for_function('window.evalViewer&&window.evalViewer.graph&&window.evalViewer.graph.view');page.evaluate('''([width,height])=>{const g=evalViewer.graph;g.sizeDidChange=function(){};g.view.scaleAndTranslate(1,0,0);g.view.validate();const d=document.getElementById('graph');d.style.width=width+'px';d.style.height=height+'px';}''',[width,height]);page.evaluate('document.fonts.ready');page.evaluate('''()=>{evalViewer.graph.refresh();evalViewer.graph.view.validate();for(const c of Object.values(evalViewer.graph.model.cells)){const n=evalViewer.graph.view.getState(c)?.text?.node;if(!n)continue;for(const t of n.querySelectorAll('text'))t.setAttribute('data-intrinsic-id',c.id);}}''');freshnative=page.evaluate(OBSERVE)
                    oldnative={x['cell']:{'chars':[c for run in x['runs']for c in run['chars']]}for x in case['baseline']['actual_text_positions']}
                    original_comparison=metrics(case['source'],freshsource);native_replay=metrics(oldnative,freshnative);comparison=metrics(freshsource,freshnative);differences={}
                    for key in freshsource:
                        a,b=freshsource[key],freshnative[key]
                        differences[key]=dict(metric=comparison[key],style_differences={k:[a['styles'].get(k),b['styles'].get(k)]for k in set(a['styles'])|set(b['styles'])if a['styles'].get(k)!=b['styles'].get(k)},screen_linear_delta=[b['screenCTM'][i]-a['screenCTM'][i]for i in range(4)],source_localCTM=a['localCTM'],native_localCTM=b['localCTM'],source_intrinsic_length=a['computedTextLength'],native_intrinsic_length=b['computedTextLength'],source_bbox=a['bbox'],native_bbox=b['bbox'])
                    record=dict(id=identifier,files=case['files'],source=freshsource,native=freshnative,source_replay=original_comparison,native_replay=native_replay,differences=differences)
                    with(output/(identifier+'.json')).open('x')as stream:json.dump(record,stream,ensure_ascii=False,indent=2)
                    bad={k:v for k,v in differences.items()if max(v['metric'][m]for m in ('spacing_residual','width_error','height_error'))>.03}
                    summaries.append(dict(id=identifier,source_replay_max=max(max(x[k]for k in ('spacing_residual','width_error','height_error'))for x in original_comparison.values()),native_replay_max=max(max(x[k]for k in ('spacing_residual','width_error','height_error'))for x in native_replay.values()),bad_runs=bad,source_text_runs=len(freshsource)))
                    print(json.dumps(summaries[-1]),flush=True)
                finally:context.close()
        finally:browser.close()
    (output/'summary.json').write_text(json.dumps(dict(diagnostic_only=True,candidates_published=False,model_calls=0,cases=summaries),indent=2)+'\n')
    return summaries

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);run(parser.parse_args().output)
