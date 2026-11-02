#!/usr/bin/env python3
"""Diagnose the real diagrams.net embed load on HKUST; no diagram data input."""
import argparse
import json
from pathlib import Path
import re
import time

URL='https://embed.diagrams.net/?embed=1&proto=json&spin=1&ui=min&dark=0&noSaveBtn=1&noExitBtn=1'


def chromium_path(explicit):
    if explicit:return explicit
    installed=sorted(Path.home().joinpath('.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'),
        key=lambda p:int(re.search(r'chromium-(\d+)',str(p)).group(1)),reverse=True)
    if not installed:raise FileNotFoundError('No installed full Chromium executable found')
    return str(installed[0])


def page_probe(context,label,out,timeout):
    page=context.new_page()
    trace=[]
    def record(kind,**values):
        if len(trace)<400:trace.append({'elapsed':round(time.monotonic()-start,3),'kind':kind,**values})
    start=time.monotonic()
    page.on('console',lambda msg:record('console',level=msg.type,text=msg.text[:1500]))
    page.on('pageerror',lambda error:record('pageerror',text=str(error)[:2000]))
    page.on('requestfailed',lambda request:record('requestfailed',url=request.url,failure=request.failure))
    page.on('response',lambda response:record('response',status=response.status,url=response.url)
      if response.status>=400 or 'embed.diagrams.net' in response.url else None)
    result={'mode':label,'url':URL}
    listener='''window.img2codeProbeMessages=[];
    window.addEventListener('message',e=>{
      let d=e.data;try{if(typeof d==='string')d=JSON.parse(d);}catch(_){}
      const record={origin:e.origin,event:d&&d.event,action:d&&d.action,
        type:typeof d,preview:JSON.stringify(d).slice(0,500)};
      if(window.img2codeProbeMessages.length<100)window.img2codeProbeMessages.push(record);
    });'''
    try:
        if label=='iframe_about_blank':
            page.set_content('<!doctype html><html><head><title>img2code embed probe</title></head><body>'+
              '<script>'+listener+'</script><iframe id="editor" style="width:1400px;height:1000px" '+
              'src="'+URL+'"></iframe></body></html>',wait_until='domcontentloaded',timeout=timeout)
        else:
            page.add_init_script(listener)
            nav=page.goto(URL,wait_until='domcontentloaded',timeout=timeout)
            result['navigation_status']=None if nav is None else nav.status
        try:
            page.wait_for_function("window.img2codeProbeMessages && window.img2codeProbeMessages.some(x=>x.event==='init')",timeout=timeout)
            result['init_received']=True
        except Exception as exc:
            result['init_received']=False;result['init_error']=str(exc)[:1000]
    except Exception as exc:
        result['navigation_error']=type(exc).__name__+': '+str(exc)[:2000]
    try:
        result['title']=page.title()
        result['page_url']=page.url
        result['messages']=page.evaluate('window.img2codeProbeMessages||[]')
        frames=[]
        for frame in page.frames:
            info={'url':frame.url,'name':frame.name}
            try:
                info['document']=frame.evaluate('''({readyState:document.readyState,
                  origin:location.origin,title:document.title,
                  EditorUi:typeof window.EditorUi,App:typeof window.App,
                  Graph:typeof window.Graph,mxClient:typeof window.mxClient,
                  bodyText:(document.body&&document.body.innerText||'').slice(0,2500)})''')
            except Exception as exc:info['inspection_error']=str(exc)[:1000]
            frames.append(info)
        result['frames']=frames
        screenshot=out/(label+'.png')
        page.screenshot(path=str(screenshot),timeout=15000,animations='disabled')
        result['screenshot']=str(screenshot)
    except Exception as exc:
        result['inspection_error']=str(exc)[:2000]
    result['elapsed_seconds']=round(time.monotonic()-start,3)
    result['trace']=trace
    (out/(label+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    page.close()
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',default='/backup/shaoshitong/img2code_20261029/evaluation/browser_probe_'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
    ap.add_argument('--proxy',default='http://127.0.0.1:7890')
    ap.add_argument('--executable-path')
    ap.add_argument('--timeout-ms',type=int,default=45000)
    ap.add_argument('--ignore-https-errors',action='store_true',help='Diagnostic rerun only after certificate-error evidence; disabled by default')
    args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    result={'started':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'url':URL,
      'proxy':args.proxy,'ignore_https_errors':args.ignore_https_errors,
      'diagram_data_supplied':False,'out':str(out)}
    try:
        import requests
        response=requests.get(URL,proxies={'http':args.proxy,'https':args.proxy},
          timeout=30,verify=not args.ignore_https_errors)
        result['http_probe']={'status':response.status_code,'url':response.url,
          'content_type':response.headers.get('Content-Type'),
          'content_length_received':len(response.content),
          'content_security_policy':response.headers.get('Content-Security-Policy'),
          'x_frame_options':response.headers.get('X-Frame-Options'),
          'contains_html':'<html' in response.text.lower(),
          'title':(re.findall(r'<title[^>]*>(.*?)</title>',response.text,re.S|re.I)or[''])[0][:500]}
    except Exception as exc:result['http_probe']={'error':type(exc).__name__+': '+str(exc)[:2000]}
    try:
        from playwright.sync_api import sync_playwright
        executable=chromium_path(args.executable_path);result['executable_path']=executable
        with sync_playwright()as p:
            browser=p.chromium.launch(headless=True,executable_path=executable,
              args=['--disable-dev-shm-usage'],proxy={'server':args.proxy})
            result['browser_version']=browser.version
            context=browser.new_context(viewport={'width':1500,'height':1100},
              ignore_https_errors=args.ignore_https_errors)
            result['iframe']=page_probe(context,'iframe_about_blank',out,args.timeout_ms)
            result['top_level']=page_probe(context,'top_level',out,args.timeout_ms)
            browser.close()
    except Exception as exc:result['browser_error']=type(exc).__name__+': '+str(exc)[:4000]
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    compact={k:v for k,v in result.items()if k not in ('iframe','top_level')}
    for name in ('iframe','top_level'):
        if name in result:compact[name]={k:v for k,v in result[name].items()if k!='trace'}
    print(json.dumps(compact,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
