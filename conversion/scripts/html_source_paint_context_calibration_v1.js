({operation,object,baseline,variant,mutation})=>{
 const rect=r=>({x:r.x,y:r.y,width:r.width,height:r.height});
 const props=['font','fontFamily','fontSize','fontWeight','fontStyle','fontStretch','fontSynthesis','fontKerning','fontFeatureSettings','fontVariationSettings','fontVariantCaps','fontVariantLigatures','letterSpacing','wordSpacing','whiteSpace','whiteSpaceCollapse','textWrapMode','tabSize','direction','textRendering','lineHeight','textTransform','textAlign','textDecorationLine','textDecorationColor','textDecorationStyle','textDecorationThickness','textUnderlineOffset','color','webkitTextStrokeWidth','webkitTextStrokeColor','webkitFontSmoothing','opacity','mixBlendMode','filter','transform','translate','scale','rotate','perspective','contain','isolation','willChange'];
 const css=e=>Object.fromEntries(props.map(k=>[k,getComputedStyle(e)[k]]));
 const ranges=n=>[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)].map(({segment,index})=>{const r=document.createRange();r.setStart(n,index);r.setEnd(n,index+segment.length);return{text:segment,start:index,...rect(r.getBoundingClientRect())};});
 if(operation==='initialize'){
  const owner=window.__img2codeAlignOwners[object.qaOwner],node=owner.childNodes[object.qaTextNodeIndex];
  if(node.nodeType!==Node.TEXT_NODE)throw Error('original_text_node_missing');
  const raw=node.textContent.slice(object.qaTextStart,object.qaTextEnd);if(raw!==object.text)throw Error('source_literal_fragment_changed');
  const ancestry=[];for(let e=owner;e;e=e.parentElement)ancestry.push({tag:e.tagName,className:e.getAttribute('class'),rect:rect(e.getBoundingClientRect()),css:css(e)});
  const walker=document.createTreeWalker(owner,NodeFilter.SHOW_TEXT),paragraphNodes=[];while(walker.nextNode())paragraphNodes.push(walker.currentNode);
  const original={owner,node,object,raw,baseline,ownerRect:rect(owner.getBoundingClientRect()),ownerCss:css(owner),allCss:[...getComputedStyle(owner)].map(k=>[k,getComputedStyle(owner).getPropertyValue(k)]),originalRanges:ranges(node),originalCss:css(owner),ancestry,paragraphNodes,paragraphOriginalRanges:paragraphNodes.map(ranges)};
  window.__sourcePaintContextCalibrationV1=original;
  return {object,rawUnicode:raw,wholeOriginalTextNode:node.textContent,ownerChildNodes:[...owner.childNodes].map(n=>({type:n.nodeType,text:n.nodeType===3?n.textContent:null,tag:n.nodeType===1?n.tagName:null})),ownerRect:original.ownerRect,ownerCss:original.ownerCss,ancestry,wholeTextRanges:original.originalRanges,baseline,devicePixelRatio,screen:{width:innerWidth,height:innerHeight,scrollX,scrollY}};
 }
 const p=window.__sourcePaintContextCalibrationV1;if(!p)throw Error('calibration_not_initialized');
 if(operation==='hide'){
  const targets=variant.startsWith('paragraph_')?p.paragraphNodes:[p.node],rs=targets.map(node=>{const r=document.createRange();r.setStart(node,variant.startsWith('paragraph_')?0:p.object.qaTextStart);r.setEnd(node,variant.startsWith('paragraph_')?node.length:p.object.qaTextEnd);return r;});
  CSS.highlights.set('paint-context-calibration',new Highlight(...rs));const style=document.createElement('style');style.textContent='::highlight(paint-context-calibration){color:transparent;text-shadow:none;text-decoration-color:transparent;}';document.head.append(style);p.hideStyle=style;
  return {ranges:rs.map(r=>({rangeStart:r.startOffset,rangeEnd:r.endOffset})),allOriginalRangesUnchanged:JSON.stringify(p.paragraphNodes.map(ranges))===JSON.stringify(p.paragraphOriginalRanges),allOriginalCssUnchanged:JSON.stringify(css(p.owner))===JSON.stringify(p.originalCss)};
 }
 if(operation==='clear'){
  p.overlay?.remove();p.overlay=null;p.hideStyle?.remove();p.hideStyle=null;CSS.highlights.delete('paint-context-calibration');
  return{allOriginalRangesUnchanged:JSON.stringify(ranges(p.node))===JSON.stringify(p.originalRanges),allOriginalCssUnchanged:JSON.stringify(css(p.owner))===JSON.stringify(p.originalCss)};
 }
 if(operation!=='overlay')throw Error('unknown_calibration_operation');
 const ns='http://www.w3.org/2000/svg',xn='http://www.w3.org/1999/xhtml';let host,textElement,textNode,outer,marker=null,baselineProof=null;
 const setCopied=e=>{for(const key of props){const value=p.ownerCss[key];if(value!==undefined&&value!=='')e.style[key]=value;}};
 const svgRoot=()=>{const s=document.createElementNS(ns,'svg');s.setAttribute('width',innerWidth);s.setAttribute('height',innerHeight);s.setAttribute('viewBox',`0 0 ${innerWidth} ${innerHeight}`);s.setAttribute('preserveAspectRatio','none');s.style.cssText='position:absolute;left:0;top:0;overflow:visible;pointer-events:none;z-index:2147483647;';return s;};
 if(variant==='line_svg'){
  outer=svgRoot();textElement=document.createElementNS(ns,'text');setCopied(textElement);textElement.style.whiteSpace='pre';textElement.setAttribute('x',p.object.x);textElement.setAttribute('y',p.baseline);textElement.setAttributeNS('http://www.w3.org/XML/1998/namespace','xml:space','preserve');textNode=document.createTextNode(p.raw);textElement.append(textNode);outer.append(textElement);document.body.append(outer);host=textElement;
  const b=textElement.getStartPositionOfChar(0),m=textElement.getScreenCTM();baselineProof={basis:'actual_SVG_alphabetic_start_and_screenCTM',local:{x:b.x,y:b.y},matrix:[m.a,m.b,m.c,m.d,m.e,m.f],screen:{x:b.x*m.a+b.y*m.c+m.e,y:b.x*m.b+b.y*m.d+m.f}};
 }else{
  const paragraph=variant.startsWith('paragraph_'),foreign=variant.endsWith('_foreignObject');
  if(paragraph){
   if(p.ownerCss.transform!=='none'||p.ownerCss.translate!=='none'||p.ownerCss.scale!=='none'||p.ownerCss.rotate!=='none')throw Error('paragraph_transformed_owner_pending');
   host=p.owner.cloneNode(true);const originalElements=[p.owner,...p.owner.querySelectorAll('*')],cloneElements=[host,...host.querySelectorAll('*')];
   if(originalElements.length!==cloneElements.length)throw Error('source_paragraph_tree_changed');
   originalElements.forEach((e,i)=>{const cs=getComputedStyle(e),target=cloneElements[i];target.removeAttribute('id');target.removeAttribute('class');for(const key of cs)target.style.setProperty(key,cs.getPropertyValue(key),'important');});
   for(const[key,value]of Object.entries({position:'absolute',left:p.ownerRect.x+'px',top:p.ownerRect.y+'px',margin:'0',width:p.ownerRect.width+'px',height:p.ownerRect.height+'px',boxSizing:'border-box',pointerEvents:'none',zIndex:'2147483647'}))host.style.setProperty(key.replace(/[A-Z]/g,m=>'-'+m.toLowerCase()),value,'important');
   // The original object is text only; its CSS background/border are already
   // present in the untouched source. The calibration duplicates text paint.
   for(const[key,value]of Object.entries({background:'transparent',borderColor:'transparent',boxShadow:'none'}))host.style.setProperty(key.replace(/[A-Z]/g,m=>'-'+m.toLowerCase()),value,'important');
   const sourceIndex=p.paragraphNodes.indexOf(p.node),tw=document.createTreeWalker(host,NodeFilter.SHOW_TEXT),clonedNodes=[];while(tw.nextNode())clonedNodes.push(tw.currentNode);if(clonedNodes.length!==p.paragraphNodes.length||clonedNodes.some((n,i)=>n.textContent!==p.paragraphNodes[i].textContent))throw Error('paragraph_raw_Unicode_or_text_node_tree_changed');textNode=clonedNodes[sourceIndex];textElement=textNode.parentElement;
  }else{
   host=document.createElementNS(xn,'div');setCopied(host);host.style.cssText+=';position:absolute;left:'+p.object.x+'px;top:0px;display:block;white-space:pre;width:max-content;margin:0;padding:0;border:0;pointer-events:none;z-index:2147483647;';textNode=document.createTextNode(p.raw);host.append(textNode);textElement=host;
  }
  if(foreign){outer=svgRoot();const fo=document.createElementNS(ns,'foreignObject');fo.setAttribute('x',0);fo.setAttribute('y',0);fo.setAttribute('width',innerWidth);fo.setAttribute('height',innerHeight);fo.style.overflow='visible';fo.append(host);outer.append(fo);}else outer=host;
  document.body.append(outer);
  if(!paragraph){
   marker=document.createElementNS(xn,'span');marker.style.cssText='all:initial;display:inline-block;vertical-align:baseline;width:0;height:0;line-height:0;font-size:0;margin:0;padding:0;border:0;opacity:0;overflow:hidden;';host.append(marker);const before=rect(marker.getBoundingClientRect()),delta=p.baseline-before.y;host.style.top=delta+'px';const after=rect(marker.getBoundingClientRect());baselineProof={basis:'actual_zero_paint_inline_baseline_marker',before,sourceBaseline:p.baseline,geometryDerivedTop:delta,after};const beforeRemove=ranges(textNode);marker.remove();if(JSON.stringify(ranges(textNode))!==JSON.stringify(beforeRemove))throw Error('baseline_marker_changed_overlay_ranges');
  }
 }
 p.overlay=outer;p.overlayTextNode=textNode;
 if(mutation==='removed_character')textNode.deleteData(0,1);
 else if(mutation==='wrong_font')textElement.style.fontFamily='Courier New';
 else if(mutation==='wrong_color'){textElement.style.color='rgb(255,0,0)';textElement.style.webkitTextFillColor='rgb(255,0,0)';}
 else if(mutation==='wrong_spacing')textElement.style.letterSpacing='1px';
 else if(mutation==='true_displacement')outer.style.transform='translate(0px,1px)';
 else if(mutation)throw Error('unknown_semantic_mutation');
 if(variant==='line_svg'&&mutation==='wrong_color')textElement.style.fill='rgb(255,0,0)';
 if(variant==='line_svg'&&!mutation)textElement.style.fill=p.ownerCss.color;
 const targetRanges=ranges(textNode),sourceRanges=p.originalRanges.filter(g=>variant.startsWith('paragraph_')||g.start>=p.object.qaTextStart&&g.start<p.object.qaTextEnd);
 const diffs=targetRanges.length===sourceRanges.length?targetRanges.map((g,i)=>({index:i,text:g.text,dx:g.x-sourceRanges[i].x,dy:g.y-sourceRanges[i].y,dw:g.width-sourceRanges[i].width,dh:g.height-sourceRanges[i].height})):[];
 return{variant,mutation:mutation||null,rawUnicode:textNode.textContent,originalSourceRawUnicode:p.raw,paragraphOriginalUnicode:p.node.textContent,targetRanges,sourceRanges,maximumAbsoluteRangeDifference:diffs.length?Math.max(...diffs.flatMap(g=>[Math.abs(g.dx),Math.abs(g.dy),Math.abs(g.dw),Math.abs(g.dh)])):null,rangeDifferences:diffs,baselineProof,targetCss:css(textElement),sourceCss:p.ownerCss,originalSourceRangesUnchanged:JSON.stringify(ranges(p.node))===JSON.stringify(p.originalRanges),originalSourceCssUnchanged:JSON.stringify(css(p.owner))===JSON.stringify(p.originalCss),outerMarkup:outer.outerHTML};
}
