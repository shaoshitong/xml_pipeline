"""Development-only native SVG viewport reconstruction from actual UA shadows."""
from pathlib import Path
import hashlib,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
KEYS=['fill','stroke','color','paintOrder','strokeWidth','fillOpacity','strokeOpacity','opacity','strokeLinecap','strokeLinejoin','strokeDasharray','strokeDashoffset','strokeMiterlimit','fillRule','vectorEffect','filter','clipPath','maskImage','mixBlendMode','isolation','overflow','display','visibility','markerStart','markerEnd','markerMid']
SNAP=r'''function(keys){return[this,...this.querySelectorAll('*')].map((e,i)=>{if(!['symbol','svg','g','path','line','polyline','polygon','rect','circle','ellipse'].includes(e.localName))throw Error('nested_or_nonvector_symbol_needs_separate_proof:'+e.localName);const c=getComputedStyle(e),m=e.getScreenCTM(),b=e.getBBox();return{tag:i===0?'source_symbol_viewport':e.localName,attributes:[...e.attributes].filter(a=>i!==0||!['id','style','width','height'].includes(a.name)).map(a=>[a.name,a.value]).sort((a,b)=>a[0].localeCompare(b[0])),linearMatrix:[m.a,m.b,m.c,m.d],localBBox:[b.x,b.y,b.width,b.height],paint:Object.fromEntries(keys.map(k=>[k,c[k]])),viewport:i===0?[c.width==='auto'?e.width.baseVal.value:parseFloat(c.width),c.height==='auto'?e.height.baseVal.value:parseFloat(c.height)]:null}})}'''
def all_elements(node):
    yield node
    for child in node.get('children',[]):
        if child.get('nodeType')==1:yield from all_elements(child)

def inside(point,polygon):
    crosses=[(b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])for a,b in zip(polygon,polygon[1:]+polygon[:1])]
    return all(v>=-1e-6 for v in crosses)or all(v<=1e-6 for v in crosses)


D=Path(__file__).parent
BUILDER=(D/'svg_source_symbol_viewport_v1.js').read_text()
HOSTS="[...document.querySelectorAll('svg use')].filter(e=>!e.closest('defs,symbol,marker,clipPath,mask'))"


def collect(page):
    """Original page is never mutated. Reject unproved instances explicitly."""
    context=page.context;size=page.viewport_size;session=context.new_cdp_session(page)
    session.send('DOM.enable');session.send('DOM.getDocument',{'depth':1,'pierce':True})
    count=page.evaluate('()=>'+HOSTS+'.length');facts=[];html=page.content()
    def describe(expression,cdp):
        obj=cdp.send('Runtime.evaluate',{'expression':expression})['result']['objectId'];node=cdp.send('DOM.requestNode',{'objectId':obj})['nodeId'];return cdp.send('DOM.describeNode',{'nodeId':node,'depth':-1,'pierce':True})['node']
    def snapshot(node,cdp):
        obj=cdp.send('DOM.resolveNode',{'backendNodeId':node['backendNodeId']})['object']['objectId'];result=cdp.send('Runtime.callFunctionOn',{'objectId':obj,'functionDeclaration':SNAP,'arguments':[dict(value=KEYS)],'returnByValue':True})
        if result.get('exceptionDetails'):raise ValueError('source_symbol_shadow_snapshot_unsupported:'+str(result['exceptionDetails'])[:500])
        values=result['result']['value'];nodes=list(all_elements(node));assert len(values)==len(nodes)
        for value,n in zip(values,nodes):value['layoutQuads']=cdp.send('DOM.getContentQuads',{'backendNodeId':n['backendNodeId']})['quads']
        return values
    def mul(a,b):return[a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3]]
    try:
        for index in range(count):
            scratch=None;fact=dict(index=index)
            try:
                host=describe(HOSTS+'['+str(index)+']',session);roots=host.get('shadowRoots',[])
                if len(roots)!=1 or roots[0].get('shadowRootType')!='user-agent':continue
                actual=next(n for n in roots[0]['children']if n.get('nodeType')==1)
                if actual['localName']!='symbol':continue
                signature=page.evaluate('i=>{const e=('+HOSTS+')[i],m=e.getScreenCTM(),b=e.getBoundingClientRect();return{attributes:[...e.attributes].map(a=>[a.name,a.value]),matrix:[m.a,m.b,m.c,m.d,m.e,m.f],bbox:{x:b.x,y:b.y,w:b.width,h:b.height}}}',index)
                obj=session.send('DOM.resolveNode',{'backendNodeId':actual['backendNodeId']})['object']['objectId'];desc=session.send('Runtime.callFunctionOn',{'objectId':obj,'functionDeclaration':"function(keys){const c=getComputedStyle(this);return{attributes:[...this.attributes].map(a=>[a.name,a.value]),children:this.innerHTML,width:parseFloat(c.width),height:parseFloat(c.height),paint:Object.fromEntries(keys.map(k=>[k,c[k]]))}}",'arguments':[dict(value=KEYS)],'returnByValue':True})['result']['value']
                assert desc['width']>0 and desc['height']>0
                before=page.screenshot();a=snapshot(actual,session);A=signature['matrix'][:4];attrs=dict(desc['attributes']);vb=list(map(float,attrs.get('viewBox','0 0 0 0').replace(',',' ').split()));sx=desc['width']/vb[2]if vb[2]else 1;sy=desc['height']/vb[3]if vb[3]else 1;par=attrs.get('preserveAspectRatio','xMidYMid meet')
                if par!='none':sx=sy=max(sx,sy)if 'slice'in par else min(sx,sy)
                det=A[0]*A[3]-A[1]*A[2];assert det;inverse=[A[3]/det,-A[1]/det,-A[2]/det,A[0]/det];projection=mul(mul(A,[sx,0,0,sy]),inverse)
                for vector in a:vector['linearMatrix']=mul(projection,vector['linearMatrix'])
                scratch=context.new_page();scratch.set_viewport_size(size);scratch.set_content(html);scratch.evaluate('()=>document.fonts.ready');cdp=context.new_cdp_session(scratch);cdp.send('DOM.enable');cdp.send('DOM.getDocument',{'depth':1,'pierce':True})
                viewport=scratch.evaluate('a=>{window.__symbolViewportProbe=('+BUILDER+')(document.querySelector("svg"),('+HOSTS+')[a.index],a);return window.__symbolViewportProbe.viewport}',dict(index=index,**desc));b=snapshot(describe('window.__symbolViewportProbe.v',cdp),cdp)
                exact=a==b;contained=all(inside((q[i],q[i+1]),viewport)for item in a for q in item['layoutQuads']for i in range(0,len(q),2));assert page.screenshot()==before,'original_source_symbol_observer_changed_pixels'
                digest=lambda rows:hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                proof=dict(ok=exact and contained,actual_UA_shadow_inspected=True,original_shadow_sha256=digest(a),reconstructed_shadow_sha256=digest(b),full_paint_contained_in_viewport=contained,viewport=viewport,source_page_unchanged=True,paint_objects=len(a),method='isolated_native_symbol_viewport_exact_layout_v1')
                fact.update(descriptor=signature,definition=desc,proof=proof)
            except Exception as error:fact.update(proof=dict(ok=False,reason=str(error)[:1200]))
            finally:
                if scratch is not None:scratch.close()
            facts.append(fact)
    finally:session.detach()
    return facts
