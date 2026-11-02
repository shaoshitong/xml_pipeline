"""Development-only native SVG viewport reconstruction from actual UA shadows."""
from pathlib import Path
import argparse,hashlib,json,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
KEYS=['fill','stroke','color','paintOrder','strokeWidth','fillOpacity','strokeOpacity','opacity','strokeLinecap','strokeLinejoin','strokeDasharray','strokeDashoffset','strokeMiterlimit','fillRule','vectorEffect','filter','clipPath','maskImage','mixBlendMode','isolation','overflow','display','visibility','markerStart','markerEnd','markerMid']
SNAP=r'''function(keys){return[this,...this.querySelectorAll('*')].map((e,i)=>{if(!['symbol','svg','g','path','line','polyline','polygon','rect','circle','ellipse'].includes(e.localName))throw Error('nested_or_nonvector_symbol_needs_separate_proof:'+e.localName);const c=getComputedStyle(e),m=e.getScreenCTM(),b=e.getBBox();return{tag:i===0?'source_symbol_viewport':e.localName,attributes:[...e.attributes].filter(a=>i!==0||!['id','style','width','height'].includes(a.name)).map(a=>[a.name,a.value]).sort((a,b)=>a[0].localeCompare(b[0])),linearMatrix:[m.a,m.b,m.c,m.d],localBBox:[b.x,b.y,b.width,b.height],paint:Object.fromEntries(keys.map(k=>[k,c[k]])),viewport:i===0?[c.width==='auto'?e.width.baseVal.value:parseFloat(c.width),c.height==='auto'?e.height.baseVal.value:parseFloat(c.height)]:null}})}'''
BEGIN=r'''a=>{const root=document.querySelector('svg'),el=[...document.querySelectorAll('svg use')].filter(e=>!e.closest('defs,symbol,marker,clipPath,mask'))[a.index],cs=getComputedStyle(el),T=root.getScreenCTM().inverse().multiply(el.getScreenCTM()).translate(el.x.baseVal.value,el.y.baseVal.value),g=document.createElementNS('http://www.w3.org/2000/svg','g'),v=document.createElementNS('http://www.w3.org/2000/svg','svg');g.setAttribute('transform','matrix('+[T.a,T.b,T.c,T.d,T.e,T.f].join(',')+')');for(const k of ['fill','stroke','strokeWidth','color','fontFamily','fontSize'])g.style[k]=cs[k];for(const [k,value]of a.attributes)v.setAttribute(k,value);v.setAttribute('width',a.width);v.setAttribute('height',a.height);v.innerHTML=a.children;v.removeAttribute('id');if(v.querySelector('[id]'))throw Error('symbol_descendant_ids_require_reference_remapping');for(const[k,value]of Object.entries(a.paint))v.style[k]=value;g.appendChild(v);root.appendChild(g);window.__symbolViewportProbe={g,v};const M=el.getScreenCTM().translate(el.x.baseVal.value,el.y.baseVal.value),points=[[0,0],[a.width,0],[a.width,a.height],[0,a.height]].map(p=>{const q=new DOMPoint(...p).matrixTransform(M);return[q.x,q.y]});return{viewport:points}}'''

def all_elements(node):
    yield node
    for child in node.get('children',[]):
        if child.get('nodeType')==1:yield from all_elements(child)

def inside(point,polygon):
    crosses=[(b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])for a,b in zip(polygon,polygon[1:]+polygon[:1])]
    return all(v>=-1e-6 for v in crosses)or all(v<=1e-6 for v in crosses)

def main():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    import io
    import compiler_svg_scene_frontend_v12 as frontend
    parser=argparse.ArgumentParser();parser.add_argument('--id',required=True);args=parser.parse_args()
    with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:db.row_factory=sqlite3.Row;job=dict(db.execute('select*from jobs where id=?',(args.id,)).fetchone())
    _,source,reference=frontend._inputs(job);size=Image.open(io.BytesIO(reference)).size;output=R/'conversion/symbol_viewport_layout_probe_v3'/uuid.uuid4().hex;output.mkdir(parents=True);results=[]
    with sync_playwright()as p:
        browser=p.chromium.launch(executable_path=frontend.CHROME,args=['--disable-dev-shm-usage','--disable-gpu']);context=browser.new_context(viewport=dict(width=size[0],height=size[1]),device_scale_factor=1,java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:route.abort());page=context.new_page();page.set_content('<style>html,body{margin:0;padding:0;background:white}svg{display:block}</style>'+source.decode('utf-8-sig'));page.evaluate('([w,h])=>{let s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h)}',list(size));page.evaluate('()=>document.fonts.ready');session=context.new_cdp_session(page);session.send('DOM.enable');session.send('DOM.getDocument',{'depth':1,'pierce':True});count=page.evaluate("()=>[...document.querySelectorAll('svg use')].filter(e=>!e.closest('defs,symbol,marker,clipPath,mask')).length")
        def describe(expression):
            obj=session.send('Runtime.evaluate',{'expression':expression})['result']['objectId'];node=session.send('DOM.requestNode',{'objectId':obj})['nodeId'];return session.send('DOM.describeNode',{'nodeId':node,'depth':-1,'pierce':True})['node']
        def snapshot(node):
            obj=session.send('DOM.resolveNode',{'backendNodeId':node['backendNodeId']})['object']['objectId'];result=session.send('Runtime.callFunctionOn',{'objectId':obj,'functionDeclaration':SNAP,'arguments':[dict(value=KEYS)],'returnByValue':True})
            if result.get('exceptionDetails'):raise ValueError(str(result['exceptionDetails']))
            values=result['result']['value'];nodes=list(all_elements(node));assert len(values)==len(nodes)
            for value,n in zip(values,nodes):value['layoutQuads']=session.send('DOM.getContentQuads',{'backendNodeId':n['backendNodeId']})['quads']
            return values
        for index in range(count):
            row=dict(index=index)
            try:
                host=describe("[...document.querySelectorAll('svg use')].filter(e=>!e.closest('defs,symbol,marker,clipPath,mask'))["+str(index)+']');roots=host.get('shadowRoots',[]);assert len(roots)==1 and roots[0]['shadowRootType']=='user-agent';actual=next(n for n in roots[0]['children']if n.get('nodeType')==1)
                if actual['localName']!='symbol':row.update(skipped='non_symbol_use_unchanged');results.append(row);continue
                obj=session.send('DOM.resolveNode',{'backendNodeId':actual['backendNodeId']})['object']['objectId'];desc=session.send('Runtime.callFunctionOn',{'objectId':obj,'functionDeclaration':"function(keys){const c=getComputedStyle(this);return{attributes:[...this.attributes].map(a=>[a.name,a.value]),children:this.innerHTML,width:parseFloat(c.width),height:parseFloat(c.height),paint:Object.fromEntries(keys.map(k=>[k,c[k]]))}}",'arguments':[dict(value=KEYS)],'returnByValue':True})['result']['value'];before=page.screenshot();a=snapshot(actual)
                host_obj=session.send('DOM.resolveNode',{'backendNodeId':host['backendNodeId']})['object']['objectId']
                A=session.send('Runtime.callFunctionOn',{'objectId':host_obj,'functionDeclaration':'function(){const m=this.getScreenCTM();return[m.a,m.b,m.c,m.d]}','returnByValue':True})['result']['value']
                attrs=dict(desc['attributes']);vb=list(map(float,attrs.get('viewBox','0 0 0 0').replace(',',' ').split()));sx=desc['width']/vb[2]if vb[2]else 1;sy=desc['height']/vb[3]if vb[3]else 1;par=attrs.get('preserveAspectRatio','xMidYMid meet')
                if par!='none':sx=sy=(max(sx,sy)if 'slice'in par else min(sx,sy))
                def mul(a,b):return[a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3]]
                determinant=A[0]*A[3]-A[1]*A[2];assert determinant
                inverse=[A[3]/determinant,-A[1]/determinant,-A[2]/determinant,A[0]/determinant];projection=mul(mul(A,[sx,0,0,sy]),inverse)
                for vector in a:vector['linearMatrix']=mul(projection,vector['linearMatrix'])
                original_page,original_session=page,session;scratch=context.new_page();scratch.set_viewport_size(dict(width=size[0],height=size[1]));scratch.set_content(page.content());scratch.evaluate('()=>document.fonts.ready');page=scratch;session=context.new_cdp_session(page);session.send('DOM.enable');session.send('DOM.getDocument',{'depth':1,'pierce':True})
                viewport=page.evaluate(BEGIN,dict(index=index,**desc))['viewport'];b=snapshot(describe('window.__symbolViewportProbe.v'));exact=a==b;contained=all(inside((q[i],q[i+1]),viewport)for item in a for q in item['layoutQuads']for i in range(0,len(q),2));(output/(str(index)+'_actual.json')).write_text(json.dumps(a));(output/(str(index)+'_reconstructed.json')).write_text(json.dumps(b));page.evaluate('()=>{window.__symbolViewportProbe.g.remove();delete window.__symbolViewportProbe}');scratch.close();page,session=original_page,original_session;restored=page.screenshot()==before;row.update(actual_shadow_and_reconstructed_vector_layout_exact=exact,full_paint_contained_in_viewport=contained,original_source_pixels_restored=restored,paint_objects=len(a),viewport=viewport)
                if not exact:row['differences']=[dict(index=i,fields=[k for k in x if x[k]!=y.get(k)])for i,(x,y)in enumerate(zip(a,b))if x!=y]
            except Exception as error:
                
                if 'scratch'in locals()and page is scratch:
                    scratch.close();page,session=original_page,original_session
                page.evaluate('()=>{if(window.__symbolViewportProbe){window.__symbolViewportProbe.g.remove();delete window.__symbolViewportProbe}}');row.update(supported=False,reason=str(error)[:1500])
            results.append(row)
        browser.close()
    summary=dict(id=args.id,root=str(output),source_sha256=hashlib.sha256(source).hexdigest(),cases=results,new_normal_conversions=0,full_QA_or_acceptance_claimed=False,source_files_unchanged=True);(output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
