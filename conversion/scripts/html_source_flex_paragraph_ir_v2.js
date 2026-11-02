// Original source structure; full-precision source border boxes are retained for lowering.
dom=>{
 const snapshot=(({object})=>{
 const root=window.__img2codeAlignOwners[object.qaOwner];
 const rect=r=>({x:r.x,y:r.y,width:r.width,height:r.height});
 const props=['border-top-left-radius','border-top-right-radius','border-bottom-left-radius','border-bottom-right-radius','display','box-sizing','width','height','min-width','min-height','max-width','max-height','margin-top','margin-right','margin-bottom','margin-left','padding-top','padding-right','padding-bottom','padding-left','border-top-width','border-right-width','border-bottom-width','border-left-width','border-top-style','border-right-style','border-bottom-style','border-left-style','overflow-x','overflow-y','overflow-wrap','word-break','hyphens','text-indent','text-align','text-align-last','vertical-align','line-break','writing-mode','text-orientation','unicode-bidi','font-family','font-size','font-weight','font-style','font-stretch','font-synthesis','font-kerning','font-feature-settings','font-variation-settings','font-variant-caps','font-variant-ligatures','letter-spacing','word-spacing','white-space','white-space-collapse','text-wrap-mode','tab-size','direction','text-rendering','line-height','text-transform','text-decoration-line','text-decoration-color','text-decoration-style','text-decoration-thickness','text-underline-offset','color','-webkit-text-fill-color','-webkit-text-stroke-width','-webkit-text-stroke-color','-webkit-font-smoothing','opacity','mix-blend-mode','align-content','align-items','align-self','justify-content','justify-items','justify-self','flex-direction','flex-wrap','flex-grow','flex-shrink','flex-basis','order','row-gap','column-gap'];
 const path=n=>{const out=[];for(let a=n;a!==root;a=a.parentNode)out.unshift([...a.parentNode.childNodes].indexOf(a));return out;};
 const originalElements=[root,...root.querySelectorAll('*')];
 if(originalElements.some(e=>!['DIV','P','H1','H2','H3','H4','H5','H6','LI','SPAN','B','STRONG','I','EM','U','S','SUB','SUP','BR','A'].includes(e.tagName)))throw Error('paragraph_non_inline_semantic_child_pending');
 const isFlex=e=>['flex','inline-flex'].includes(getComputedStyle(e).display);
 if(originalElements.slice(1).some(e=>!['inline','contents','none'].includes(getComputedStyle(e).display)&&!(isFlex(e.parentElement)&&['SPAN','B','STRONG','I','EM','U','S','SUB','SUP','A'].includes(e.tagName))))throw Error('paragraph_non_inline_or_blockified_flex_item_descendant_pending');
 for(const e of originalElements){const s=getComputedStyle(e);if(s.transform!=='none'||s.filter!=='none'||s.position!=='static'&&e!==root)throw Error('paragraph_source_effect_or_position_pending');if(s.backgroundImage!=='none'||s.textShadow!=='none')throw Error('paragraph_source_painted_effect_pending');}
 const cloned=root.cloneNode(true),clonedElements=[cloned,...cloned.querySelectorAll('*')];
 const cssEvidence=originalElements.map((e,i)=>{const source=getComputedStyle(e),dst=clonedElements[i],observed=Object.fromEntries(props.map(k=>[k,source.getPropertyValue(k)]));dst.removeAttribute('class');dst.removeAttribute('id');dst.removeAttribute('style');const typed={};for(const key of ['font-size','line-height','letter-spacing','word-spacing','vertical-align']){const v=e.computedStyleMap().get(key);if(v instanceof CSSUnitValue){const unit=v.unit==='number'?'':v.unit==='percent'?'%':v.unit;const literal=String(v.value)+unit;dst.style.setProperty(key,literal);typed[key]={value:v.value,unit:v.unit,literal};}}for(const[k,v]of Object.entries(observed))if(v!==''&&!typed[k])dst.style.setProperty(k,v);return{path:path(e),tag:e.tagName,rect:rect(e.getBoundingClientRect()),css:observed,typedNumericCSS:typed};});
 const bbox=rect(root.getBoundingClientRect());cloned.setAttribute('data-img2code-source-paragraph','v9');cloned.style.position='relative';cloned.style.left='0px';cloned.style.top='0px';cloned.style.width=bbox.width+'px';cloned.style.height=bbox.height+'px';cloned.style.boxSizing='border-box';cloned.style.margin='0px';cloned.style.background='transparent';cloned.style.borderColor='transparent';
 const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),textNodes=[];window.__sourceParagraphOriginalNodes=[];
 while(w.nextNode()){const n=w.currentNode,cs=getComputedStyle(n.parentElement),chars=[];for(const{segment,index}of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){const r=document.createRange();r.setStart(n,index);r.setEnd(n,index+segment.length);chars.push({text:segment,start:index,rectCount:r.getClientRects().length,...rect(r.getBoundingClientRect())});}textNodes.push({index:textNodes.length,path:path(n),text:n.textContent,child_index:[...n.parentNode.childNodes].indexOf(n),css:Object.fromEntries(props.map(k=>[k,cs.getPropertyValue(k)])),chars});window.__sourceParagraphOriginalNodes.push(n);}
 const subtreeOwners=window.__img2codeAlignOwners.map((e,i)=>e===root||root.contains(e)?i:null).filter(i=>i!==null);
 return{version:1,rootOwner:object.qaOwner,rootRect:bbox,markup:cloned.outerHTML,sourceTree:root.innerHTML,textNodes,cssEvidence,subtreeOwners,sourceRawUnicode:textNodes.map(n=>n.text).join(''),coordinate_policy:'original_source_owner_border_box_and_full_inline_tree_without_line_splitting',target_image_parameter_selection:false};
}
);
 const owners=window.__img2codeAlignOwners,groups=new Map();
 for(const o of dom.objects){if(o.type!=='text')continue;let root=owners[o.qaOwner];while(root&&['inline','contents'].includes(getComputedStyle(root).display))root=root.parentElement;
  if(!root||['BODY','HTML'].includes(root.tagName)||!['block','inline-block','list-item','flex','inline-flex'].includes(getComputedStyle(root).display))throw Error('paragraph_original_inline_formatting_host_pending');
  const key=owners.indexOf(root);if(key<0)throw Error('paragraph_original_host_missing_source_identity');if(!groups.has(key))groups.set(key,{root,objects:[]});groups.get(key).objects.push(o);
 }
 const rows=[],roundedOwnership=[];window.__sourceParagraphAllNodes=[];
 for(const[key,g]of groups){
  const row=snapshot({object:{qaOwner:key}});row.sourceObjectIDs=g.objects.map(o=>String(o.id+1));row.sourceFirstPaint=Math.min(...g.objects.map(o=>o.qaPaintEvent||0));row.sourceFirstOwner=g.objects[0].qaOwner;row.ancestorClip=[];
  for(let e=g.root.parentElement;e;e=e.parentElement){const c=getComputedStyle(e),x=['hidden','clip','scroll','auto'].includes(c.overflowX),y=['hidden','clip','scroll','auto'].includes(c.overflowY);if(!x&&!y)continue;const b=e.getBoundingClientRect(),r=['borderTopLeftRadius','borderTopRightRadius','borderBottomLeftRadius','borderBottomRightRadius'].map(k=>c[k]);if(r.some(v=>parseFloat(v)!==0))throw Error('paragraph_rounded_ancestor_clip_pending');if([c.borderLeftWidth,c.borderRightWidth,c.borderTopWidth,c.borderBottomWidth].some(v=>parseFloat(v)!==0))throw Error('paragraph_bordered_ancestor_clip_pending');row.ancestorClip.push({x,y,left:b.left,top:b.top,right:b.right,bottom:b.bottom,radius:r});}
  for(const e of g.root.querySelectorAll('*')){const c=getComputedStyle(e);if(c.backgroundColor!=='rgba(0, 0, 0, 0)'&&c.backgroundColor!=='transparent')throw Error('paragraph_nested_source_background_pending');if([c.borderLeftWidth,c.borderRightWidth,c.borderTopWidth,c.borderBottomWidth].some(v=>parseFloat(v)!==0))throw Error('paragraph_nested_source_border_pending');}
  for(let e=g.root;e;e=e.parentElement){const c=getComputedStyle(e);if(c.opacity!=='1'||c.mixBlendMode!=='normal')throw Error('paragraph_group_compositing_pending');}
  row.ancestorClipFrame=[Math.max(0,...row.ancestorClip.filter(a=>a.x).map(a=>a.left)),Math.max(0,...row.ancestorClip.filter(a=>a.y).map(a=>a.top)),Math.min(innerWidth,...row.ancestorClip.filter(a=>a.x).map(a=>a.right)),Math.min(innerHeight,...row.ancestorClip.filter(a=>a.y).map(a=>a.bottom))];
  for(const run of row.textNodes){run.globalTextNode=window.__sourceParagraphAllNodes.length;window.__sourceParagraphAllNodes.push(window.__sourceParagraphOriginalNodes[run.index]);}
  for(const objectID of row.sourceObjectIDs){
   const object=dom.objects.find(o=>String(o.id+1)===objectID);
   for(let a=owners[object.qaOwner];a;a=a.parentElement){
    const c=getComputedStyle(a),clipped=['hidden','clip','scroll','auto'].includes(c.overflowX)||['hidden','clip','scroll','auto'].includes(c.overflowY);
    const radii=['borderTopLeftRadius','borderTopRightRadius','borderBottomLeftRadius','borderBottomRightRadius'].map(k=>c[k]);
    if(!clipped||!radii.some(v=>parseFloat(v)>0))continue;
    if(a!==g.root&&!g.root.contains(a))throw Error('paragraph_rounded_clip_outside_original_cloned_markup_pending');
    roundedOwnership.push({sourceObjectID:objectID,clipOwner:owners.indexOf(a),paragraphRootOwner:key,overflowX:c.overflowX,overflowY:c.overflowY,radii,representation:'unchanged_original_CSS_clip_inside_cloned_paragraph_markup'});
   }
  }
  rows.push(row);
 }
 const covered=rows.flatMap(r=>r.sourceObjectIDs).sort(),expected=dom.objects.filter(o=>o.type==='text').map(o=>String(o.id+1)).sort();if(JSON.stringify(covered)!==JSON.stringify(expected))throw Error('paragraph_source_object_partition_not_exact');
 return{version:10,sourceFormattingGrammar:"original_block_inline_block_and_flex_with_semantic_inline_items",groups:rows,sourceRoundedClipOwnership:roundedOwnership,allSourceTextObjects:expected,allOriginalTextNodes:window.__sourceParagraphAllNodes.length,completeSourceObjectPartition:true,originalSourceUnicodeRetained:true};
}
