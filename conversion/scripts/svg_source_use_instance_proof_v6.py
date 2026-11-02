"""Compare untouched original UA shadows with a separate reconstruction page."""
import hashlib,json
from svg_source_use_instance_proof_v5 import BEGIN,SNAPSHOT,require_owner

def audit(page,dom):
    context=page.context;session=context.new_cdp_session(page);session.send('DOM.enable');session.send('DOM.getDocument',{'depth':1,'pierce':True});html=page.content();before=page.screenshot(type='png')
    def nodes(root):
        yield root
        for child in root.get('children',[]):
            if child.get('nodeType')==1:yield from nodes(child)
    def describe(cdp,expression):
        obj=cdp.send('Runtime.evaluate',{'expression':expression})['result']['objectId'];key=cdp.send('DOM.requestNode',{'objectId':obj})['nodeId'];return cdp.send('DOM.describeNode',{'nodeId':key,'depth':-1,'pierce':True})['node']
    def snapshot(cdp,node):
        obj=cdp.send('DOM.resolveNode',{'backendNodeId':node['backendNodeId']})['object']['objectId'];result=cdp.send('Runtime.callFunctionOn',{'objectId':obj,'functionDeclaration':SNAPSHOT,'returnByValue':True})
        if result.get('exceptionDetails'):raise ValueError('actual_source_use_shadow_snapshot_failed:'+str(result['exceptionDetails']))
        values=result['result']['value'];elements=list(nodes(node));assert len(elements)==len(values),'source_use_paint_inventory_changed'
        for value,element in zip(values,elements):value['actualLayoutQuads']=cdp.send('DOM.getContentQuads',{'backendNodeId':element['backendNodeId']})['quads']
        return values
    def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    try:
        for value in dom.get('sceneMetadata',{}).get('useContexts',{}).values():
            if not value.get('actualCallBBoxIsOriginalDocumentInstance')or value.get('parentUseContexts')or value.get('parentMarkerContexts')or value.get('sourceDefinitionTag')=='symbol':continue
            if value.get('risks')or value.get('selectorRisks')or value.get('paintRelevantUnforwardedCss'):continue
            expression=r'''(()=>{const a=CONTEXT,box=e=>{const b=e.getBoundingClientRect();return{x:b.x,y:b.y,w:b.width,h:b.height}},same=(a,b)=>['x','y','w','h'].every(k=>Math.abs(a[k]-b[k])<.001);const found=[...document.querySelectorAll('svg use')].filter(e=>!e.closest('defs,marker,symbol,pattern,clipPath,mask')&&(e.getAttribute('href')||e.getAttributeNS('http://www.w3.org/1999/xlink','href'))===a.href&&same(box(e),a.actualCallBBox));if(found.length!==1)throw Error('source_actual_use_call_not_unique');return found[0]})()'''.replace('CONTEXT',json.dumps(value))
            original=describe(session,expression);shadows=original.get('shadowRoots',[])
            assert len(shadows)==1 and shadows[0].get('shadowRootType')=='user-agent','actual_source_use_UA_shadow_missing'
            roots=[n for n in shadows[0].get('children',[])if n.get('nodeType')==1];assert len(roots)==1,'actual_source_use_UA_shadow_not_unique';actual=snapshot(session,roots[0])
            scratch=context.new_page();cdp=None
            try:
                scratch.set_viewport_size(page.viewport_size);scratch.set_content(html);scratch.evaluate('()=>document.fonts.ready');observed=scratch.evaluate(BEGIN,value);cdp=context.new_cdp_session(scratch);cdp.send('DOM.enable');cdp.send('DOM.getDocument',{'depth':1,'pierce':True});clone=snapshot(cdp,describe(cdp,'window.__sourceUseReplacement.g.firstElementChild'))
            finally:
                if cdp is not None:cdp.detach()
                scratch.close()
            value['actual_source_use_replacement_proof']=dict(ok=actual==clone,method='actual_UA_use_shadow_and_exact_clone_layout_quads_vector_paint_v4',original_shadow_paint_sha256=digest(actual),clone_paint_sha256=digest(clone),shadow_paint_objects=len(actual),actual_UA_shadow_inspected=True,original_sha256=hashlib.sha256(before).hexdigest(),replacement_sha256=None,pixel_exact_diagnostic=None,source_restored=True,source_DOM_changed=False,original_use_display_changed=False,reconstruction_in_separate_page=True,**observed)
        assert page.screenshot(type='png')==before,'source_use_audit_changed_untouched_source_pixels'
    finally:session.detach()
    return dom
