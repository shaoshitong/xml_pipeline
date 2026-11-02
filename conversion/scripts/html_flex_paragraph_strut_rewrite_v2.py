"""Font-only raw declaration append preserves source nonfont numeric bytes."""
REWRITE=r'''([label,specs,struts])=>{
 const fragment=document.createElement('div');fragment.innerHTML=Graph.sanitizeHtml(label);
 const w=document.createTreeWalker(fragment,NodeFilter.SHOW_TEXT),nodes=[];while(w.nextNode())if(w.currentNode.textContent.length)nodes.push(w.currentNode);
 if(nodes.length!==specs.length)throw Error('paragraph_font_original_Text_scope_changed');
 const elements=[...fragment.querySelectorAll('*')],styles=[];
 for(const spec of struts){if(spec.kind!=='element')continue;const element=elements[spec.index];if(!element)throw Error('paragraph_font_strut_original_element_missing');styles.push({index:spec.index,before:element.getAttribute('style')});if(!/^[A-Za-z0-9_, -]+$/.test(spec.family)||!/^normal$|^[0-9]+$/.test(String(spec.weight))||!['normal','italic','oblique'].includes(spec.style))throw Error('paragraph_font_override_literal_pending');const before=element.getAttribute('style')||'';element.setAttribute('style',before+(before.trim().endsWith(';')?'':';')+'font-family:'+spec.family+';font-weight:'+spec.weight+';font-style:'+spec.style+';');}
 for(let i=0;i<nodes.length;i++){
  const node=nodes[i],spec=specs[i];if(node.textContent!==spec.text||spec.index!==i)throw Error('paragraph_font_original_Text_node_changed');
  if(spec.preserve_unpainted_whitespace)continue;
  const span=document.createElement('span');span.setAttribute('data-native-source-font-run-v1',String(i));span.style.fontFamily=spec.family;span.style.fontWeight=spec.weight;span.style.fontStyle=spec.style;node.replaceWith(span);span.append(node);
 }
 const inverse=fragment.cloneNode(true);for(const span of inverse.querySelectorAll('[data-native-source-font-run-v1]'))span.replaceWith(...span.childNodes);
 const inverseElements=[...inverse.querySelectorAll('*')];for(const change of styles){if(change.before===null)inverseElements[change.index].removeAttribute('style');else inverseElements[change.index].setAttribute('style',change.before);}
 const original=document.createElement('div');original.innerHTML=Graph.sanitizeHtml(label);
 if(inverse.innerHTML!==original.innerHTML)throw Error('paragraph_font_nonfont_markup_or_raw_Unicode_changed');
 return{markup:fragment.innerHTML,inverse_exact:true,element_strut_styles_restored_exactly:true,strut_source_styles:styles};
}'''
