"""Fresh original-use versus exact source-expansion pixel and context proof."""
import hashlib
import math

BEGIN=r'''a=>{const root=document.querySelector('svg'),box=e=>{const b=e.getBoundingClientRect();return{x:b.x,y:b.y,w:b.width,h:b.height}},same=(x,y)=>['x','y','w','h'].every(k=>Math.abs(x[k]-y[k])<.001);const candidates=[...root.querySelectorAll('use')].filter(e=>!e.closest('defs,marker,symbol,pattern,clipPath,mask')&&(e.getAttribute('href')||e.getAttributeNS('http://www.w3.org/1999/xlink','href'))===a.href&&same(box(e),a.actualCallBBox));if(candidates.length!==1)throw Error('source_actual_use_call_not_unique');const el=candidates[0],src=document.getElementById(a.href.slice(1)),cs=getComputedStyle(el);if(!src||!['g','path','line','polyline','polygon','rect','circle','ellipse'].includes(src.localName))throw Error('source_use_definition_requires_separate_viewport_or_text_proof');const T=root.getScreenCTM().inverse().multiply(el.getScreenCTM()).translate(el.x.baseVal.value,el.y.baseVal.value),g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('transform','matrix('+[T.a,T.b,T.c,T.d,T.e,T.f].join(',')+')');for(const k of ['fill','stroke','strokeWidth','color','fontFamily','fontSize'])g.style[k]=cs[k];g.appendChild(src.cloneNode(true));root.appendChild(g);if(!same(box(g),a.syntheticCloneBBox)){g.remove();throw Error('source_use_replacement_bbox_changed')}window.__sourceUseReplacement={el,g,style:el.getAttribute('style')};el.style.setProperty('display','none','important');return{actualCallBBox:a.actualCallBBox,replacementBBox:box(g),replacementMatrix:[T.a,T.b,T.c,T.d,T.e,T.f]}}'''
END=r'''()=>{const a=window.__sourceUseReplacement;if(a){a.g.remove();if(a.style===null)a.el.removeAttribute('style');else a.el.setAttribute('style',a.style);delete window.__sourceUseReplacement}}'''


def audit(page,dom):
    for context in dom.get('sceneMetadata',{}).get('useContexts',{}).values():
        if not context.get('actualCallBBoxIsOriginalDocumentInstance') or context.get('parentUseContexts') or context.get('parentMarkerContexts'):
            continue
        if context.get('risks') or context.get('selectorRisks') or context.get('paintRelevantUnforwardedCss'):
            continue
        before=page.screenshot(type='png')
        try:
            observed=page.evaluate(BEGIN,context)
            replaced=page.screenshot(type='png')
        finally:
            page.evaluate(END)
        if page.screenshot(type='png')!=before:
            raise ValueError('source_use_audit_changed_source_pixels')
        context['actual_source_use_replacement_proof']=dict(
            ok=before==replaced,method='actual_original_call_hidden_exact_source_clone_replacement_v1',
            original_sha256=hashlib.sha256(before).hexdigest(),replacement_sha256=hashlib.sha256(replaced).hexdigest(),
            source_restored=True,**observed)
    return dom


def require_owner(dom,owner):
    if owner is None:
        raise ValueError('source_marker_owner_missing')
    contexts=owner.get('sceneUseContexts',[])
    if not contexts:
        return dict(mode='original_document_owner')
    if len(contexts)!=1:
        raise ValueError('source_marker_nested_use_requires_composed_instance_proof')
    ctx=dom.get('sceneMetadata',{}).get('useContexts',{}).get(contexts[0],{})
    proof=ctx.get('actual_source_use_replacement_proof',{})
    if not ctx.get('actualCallBBoxIsOriginalDocumentInstance') or ctx.get('parentUseContexts') or ctx.get('parentMarkerContexts') or ctx.get('sourceDefinitionTag')=='symbol':
        raise ValueError('source_marker_use_call_not_original_unclipped_instance')
    if ctx.get('risks') or ctx.get('selectorRisks') or ctx.get('paintRelevantUnforwardedCss'):
        raise ValueError('source_marker_use_context_css_or_geometry_unproven')
    if proof.get('ok')is not True or proof.get('source_restored')is not True or proof.get('method')!='actual_original_call_hidden_exact_source_clone_replacement_v1' or proof.get('original_sha256')!=proof.get('replacement_sha256') or not proof.get('original_sha256'):
        raise ValueError('source_marker_use_actual_pixel_replacement_unproven')
    if owner['id']not in ctx.get('emittedObjectIds',[]):
        raise ValueError('source_marker_owner_not_in_proved_source_use')
    for original,replacement in [(ctx.get('actualCallBBox',{}),ctx.get('syntheticCloneBBox',{})),(ctx.get('actualCallBBox',{}),proof.get('replacementBBox',{}))]:
        if not all(k in original and k in replacement and math.isfinite(original[k]) and math.isfinite(replacement[k]) and abs(original[k]-replacement[k])<.001 for k in ['x','y','w','h']):
            raise ValueError('source_marker_use_replacement_bbox_changed')
    return dict(mode='fresh_original_call_exact_source_clone',use_context=contexts[0],proof=proof)
