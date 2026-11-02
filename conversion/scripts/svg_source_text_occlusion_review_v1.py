"""Read-only browser hit-stack evidence for possible covered source labels.

Review evidence only: it cannot qualify a pair or change source/converter QA.
"""
import argparse,hashlib,io,json,sys,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
JS=r'''()=>{const rows=[],painted=e=>{for(let p=e;p&&p instanceof SVGElement;p=p.parentElement){const c=getComputedStyle(p);if(c.display==='none'||c.visibility!=='visible'||+c.opacity===0)return false;}return true;};for(const text of document.querySelectorAll('svg text')){if(text.closest('defs,marker,symbol,clipPath,mask')||!painted(text))continue;let walker=document.createTreeWalker(text,NodeFilter.SHOW_TEXT),node;while(node=walker.nextNode()){if(!node.textContent.trim())continue;const chars=[];for(const {segment,index}of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(node.textContent)){if(!segment.trim())continue;const range=document.createRange();range.setStart(node,index);range.setEnd(node,index+segment.length);const b=range.getBoundingClientRect();if(!(b.width>0&&b.height>0))continue;let eligible=0,covered=0;const occluders=[];for(const rx of [.25,.5,.75])for(const ry of [.3,.6,.8]){const x=b.x+b.width*rx,y=b.y+b.height*ry,hits=document.elementsFromPoint(x,y),own=hits.findIndex(e=>e===text||text.contains(e));if(own<0)continue;eligible++;const over=hits.slice(0,own).find(e=>{if(!['rect','circle','ellipse','path','polygon'].includes(e.localName))return false;const c=getComputedStyle(e);return painted(e)&&c.fill!=='none'&&c.fill!=='transparent'&&+c.fillOpacity>=.95&&+c.opacity>=.95});if(over){covered++;occluders.push({tag:over.localName,id:over.id||'',fill:getComputedStyle(over).fill})}}if(covered&&covered>=eligible/2)chars.push({grapheme:segment,box:[b.x,b.y,b.width,b.height],covered_hit_samples:covered,eligible_hit_samples:eligible,occluders:[...new Map(occluders.map(o=>[JSON.stringify(o),o])).values()]});}const total=[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(node.textContent)].filter(x=>x.segment.trim()).length;if(chars.length>=2&&chars.length/Math.max(1,total)>=.15)rows.push({text:node.textContent,covered_graphemes:chars.length,total_graphemes:total,characters:chars,decision:'potential_source_label_occlusion_review'});}}return{labels:rows,potential_occluded_labels:rows.length,inspection:'actual_elementsFromPoint_stack_at_grapheme_ranges',changes_to_source_DOM:false,qualification_or_rejection_not_implied:true}}'''

def inspect(page,source,size):
    page.set_content('<style>html,body{margin:0;padding:0;background:white}svg{display:block}</style>'+source)
    page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h)}',list(size))
    page.evaluate('()=>document.fonts.ready');before=page.screenshot(type='png');result=page.evaluate(JS);assert page.screenshot(type='png')==before,'read_only_occlusion_observer_changed_pixels';return result

def main():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    import compiler_svg_scene_frontend_v12 as frontend
    parser=argparse.ArgumentParser();parser.add_argument('--selftest',action='store_true');parser.add_argument('--reviewed-pairs',type=Path);args=parser.parse_args()
    with sync_playwright()as p:
        browser=p.chromium.launch(executable_path=frontend.CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
        try:
            context=browser.new_context(viewport={'width':500,'height':150},device_scale_factor=1,java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:route.abort());page=context.new_page()
            if args.selftest:
                text='<text x="20" y="70" font-size="30">Research diagram label</text>';rect='<rect x="60" y="30" width="340" height="65" fill="white"/>'
                fixtures=[('text_above_background',rect+text,False),('covered_text',text+rect,True),('outline_only',text+rect.replace('fill="white"','fill="none" stroke="black"'),False),('invisible_cover',text+rect.replace('/>',' opacity="0"/>'),False)]
                results=[]
                for name,body,expected in fixtures:
                    result=inspect(page,'<svg xmlns="http://www.w3.org/2000/svg" width="500" height="150">'+body+'</svg>',(500,150));assert bool(result['labels'])==expected,(name,result);results.append(dict(name=name,expected_occlusion=expected,observed_occluded_labels=result['potential_occluded_labels']))
                print(json.dumps(dict(actual_browser_controls=results,read_only=True)),flush=True);return
            assert args.reviewed_pairs and args.reviewed_pairs.resolve().is_relative_to((R/'clean').resolve())
            output=R/'clean/source_content_review_v1'/uuid.uuid4().hex;output.mkdir(parents=True);rows=[]
            for line in args.reviewed_pairs.read_text().splitlines():
                row=json.loads(line);pair=row['pair'];source=(R/pair['original_source_code']).read_bytes();assert hashlib.sha256(source).hexdigest()==pair['source_code_sha256'];reference=(R/pair['original_reference']).read_bytes();assert hashlib.sha256(reference).hexdigest()==pair['source_image_sha256'];size=Image.open(io.BytesIO(reference)).size;page.set_viewport_size(dict(width=size[0],height=size[1]));review=inspect(page,source.decode('utf-8-sig'),size);rows.append(dict(id=pair['id'],source_sha256=pair['source_code_sha256'],**review))
            (output/'source_text_occlusion_reviews.jsonl').write_text(''.join(json.dumps(row)+'\n'for row in rows));summary=dict(root=str(output),samples=len(rows),flagged=sum(bool(row['labels'])for row in rows),rows=[dict(id=row['id'],labels=[dict(text=v['text'],covered_graphemes=v['covered_graphemes'],total_graphemes=v['total_graphemes'])for v in row['labels']])for row in rows],new_normal_conversions=0,new_QA_calls=0,new_model_calls=0,source_and_qualification_unchanged=True);(output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
            context.close()
        finally:browser.close()

if __name__=='__main__':main()
