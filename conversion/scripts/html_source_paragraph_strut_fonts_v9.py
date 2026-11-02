"""Actual per-element/host primary font struts; probes live only in observer."""
CAPTURE_JS=r'''
  const rawFragment=document.createElement('div');rawFragment.innerHTML=label;
  const template=fragment.firstElementChild,tree=n=>n.nodeType===3?['text',n.textContent]:n.nodeType===1?[n.tagName,[...n.childNodes].filter(c=>c.nodeType===1||c.nodeType===3).map(tree)]:null;
  if(!template)throw Error('paragraph_font_strut_original_root_missing');
  const matches=[...fo.querySelectorAll(template.tagName)].filter(e=>JSON.stringify(tree(e))===JSON.stringify(tree(template)));
  if(matches.length!==1)throw Error('paragraph_font_strut_original_live_tree_ambiguous');
  const liveRoot=matches[0],originalElements=[template,...template.querySelectorAll('*')],liveElements=[liveRoot,...liveRoot.querySelectorAll('*')],rawElements=[rawFragment.firstElementChild,...rawFragment.firstElementChild.querySelectorAll('*')];
  if(originalElements.length!==liveElements.length||originalElements.length!==rawElements.length)throw Error('paragraph_font_strut_source_element_scope_changed');
  const struts=[];let semanticIndex=0;
  const measure=(element,kind,index)=>{const css=getComputedStyle(element),metric=document.createElement('span');metric.id='paragraph_strut_'+result.length+'_'+struts.length;metric.textContent='M';Object.assign(metric.style,{position:'absolute',left:'0px',top:'0px',fontFamily:css.fontFamily,fontWeight:css.fontWeight,fontStyle:css.fontStyle,fontSize:css.fontSize,fontStretch:css.fontStretch,fontVariantCaps:css.fontVariantCaps});document.body.append(metric);struts.push({kind,index,metricSelector:'#'+metric.id,fontFamily:css.fontFamily,fontWeight:css.fontWeight,fontStyle:css.fontStyle,fontSize:css.fontSize,lineHeight:css.lineHeight,tag:element.tagName});};
  measure(liveRoot.parentElement,'cell',-1);
  for(let j=0;j<originalElements.length;j++){
   if(rawElements[j].hasAttribute('data-native-source-font-run-v1'))continue;
   measure(liveElements[j],'element',semanticIndex++);
  }
'''

REWRITE=r'''([label,specs,struts])=>{
 const fragment=document.createElement('div');fragment.innerHTML=Graph.sanitizeHtml(label);
 const w=document.createTreeWalker(fragment,NodeFilter.SHOW_TEXT),nodes=[];while(w.nextNode())if(w.currentNode.textContent.length)nodes.push(w.currentNode);
 if(nodes.length!==specs.length)throw Error('paragraph_font_original_Text_scope_changed');
 const elements=[...fragment.querySelectorAll('*')],styles=[];
 for(const spec of struts){if(spec.kind!=='element')continue;const element=elements[spec.index];if(!element)throw Error('paragraph_font_strut_original_element_missing');styles.push({index:spec.index,before:element.getAttribute('style')});element.style.fontFamily=spec.family;element.style.fontWeight=spec.weight;element.style.fontStyle=spec.style;}
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

def spec(strut,by_postscript,fonts):
 actual=[f for f in strut['primary_metric_fonts']if f.get('glyphCount',0)]
 if len(actual)!=1 or actual[0].get('isCustomFont'):raise ValueError('paragraph_source_primary_strut_physical_face_ambiguous')
 font=fonts[by_postscript[actual[0]['postScriptName']]]
 return{'kind':strut['kind'],'index':strut['index'],'family':font['family'],'weight':'normal'if font['physical_bold']else strut['fontWeight'],'style':'normal'if font['physical_italic']else strut['fontStyle'],'source_physical_primary_PostScript':actual[0]['postScriptName'],'source_fontFamily':strut['fontFamily'],'source_fontWeight':strut['fontWeight'],'source_fontStyle':strut['fontStyle'],'source_fontSize':strut['fontSize'],'source_lineHeight':strut['lineHeight'],'physical_bold':font['physical_bold'],'physical_italic':font['physical_italic']}

def signature(rows):
 return{(row['cell'],s['kind'],s['index']):sorted((f['postScriptName'],f['glyphCount'])for f in s['primary_metric_fonts']if f.get('glyphCount',0))for row in rows for s in row.get('struts',[])}
