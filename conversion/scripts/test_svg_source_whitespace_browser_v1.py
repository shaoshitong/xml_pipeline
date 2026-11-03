"""Real browser source/HTML controls for literal boundary whitespace."""
from pathlib import Path
import html,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))

def main():
    from playwright.sync_api import sync_playwright
    from svg_source_whitespace_native_v1 import wrap
    from compiler_scene_text_v2 import wrap as old_wrap
    controls=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu'])
        context=browser.new_context(viewport={'width':500,'height':180},java_script_enabled=False,service_workers='block');context.route('**/*',lambda r:r.abort());page=context.new_page()
        session=context.new_cdp_session(page);session.send('DOM.enable',{'includeWhitespace':'all'});session.send('CSS.enable')
        def observe(text,value):
            page.set_content('<style>html,body{margin:0;padding:0}svg{display:block}#native{font:16px Arial;white-space:normal;display:inline-block}</style><svg width="500" height="60"><text id="source" x="0" y="30" font-family="Arial" font-size="16" xml:space="preserve">'+html.escape(text)+'</text></svg><div id="native">'+value+'</div>')
            page.evaluate('document.fonts.ready');before=page.screenshot();result={}
            root=session.send('DOM.getDocument',{'depth':1})['root']['nodeId']
            for key in ['source','native']:
                node=session.send('DOM.querySelector',{'nodeId':root,'selector':'#'+key})['nodeId']
                fonts=session.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
                chars=page.evaluate('''id=>{const e=document.getElementById(id),w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT),out=[];let n;while(n=w.nextNode())for(const {segment,index}of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){const r=document.createRange();r.setStart(n,index);r.setEnd(n,index+segment.length);const b=r.getBoundingClientRect();out.push({text:segment,width:b.width,height:b.height});}return out;}''',key)
                result[key]={'fonts':sorted((f['postScriptName'],f['glyphCount'])for f in fonts if f['glyphCount']), 'chars':chars}
            assert page.screenshot()==before
            a,b=result['source'],result['native'];same_text=[c['text']for c in a['chars']]==[c['text']for c in b['chars']];same_fonts=a['fonts']==b['fonts'];delta=max([abs(x[k]-y[k])for x,y in zip(a['chars'],b['chars'])for k in ['width','height']]or[0])
            return dict(same_text=same_text,same_physical_fonts_and_glyph_counts=same_fonts,maximum_dimension_delta=delta,ok=same_text and same_fonts and delta<=.03)
        try:
            for text in [' 8','Model ',' The latent variable ','a  b ','Plain label']:
                fixed=observe(text,wrap(text,'v1',{'dx':0,'dy':0}));assert fixed['ok'],(text,fixed)
                old=observe(text,old_wrap(text,'v1',{'dx':0,'dy':0}));assert old['ok']==(text==text.strip()),(text,old)
                controls.append(dict(text=text,fixed=fixed,old=old))
            wrong_font=observe('Research ','<span style="white-space:pre;font-family:monospace">Research </span>');assert not wrong_font['ok']
            dropped_space=observe('Research ',wrap('Research','v1',{'dx':0,'dy':0}));assert not dropped_space['ok']
        finally:session.detach();context.close();browser.close()
    root=R/'conversion/source_whitespace_browser_controls_v1'/uuid.uuid4().hex;root.mkdir(parents=True);out=dict(root=str(root),controls=controls,wrong_font_rejected=wrong_font,dropped_space_rejected=dropped_space,new_normal_calls=0,new_QA_calls=0,passed=True,thresholds_unchanged=True);(root/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))

if __name__=='__main__':main()
