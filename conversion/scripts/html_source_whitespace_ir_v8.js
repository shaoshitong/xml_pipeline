() => {
 const objects=[],unsupported=[],qaWrappedWords=[],qaWhitespaceIR=[],qaOmittedWhitespace=[];let serial=0;const qaElements=[...document.querySelectorAll("*")];let qaEvent=0;
 function visible(r,el){let l=Math.max(r.x,0),t=Math.max(r.y,0),right=Math.min(r.right??r.x+r.w,innerWidth),bottom=Math.min(r.bottom??r.y+r.h,innerHeight);for(let a=el;a;a=a.parentElement){const c=getComputedStyle(a),b=a.getBoundingClientRect();if([c.overflow,c.overflowX,c.overflowY].some(v=>["hidden","clip","scroll","auto"].includes(v))){l=Math.max(l,b.left);t=Math.max(t,b.top);right=Math.min(right,b.right);bottom=Math.min(bottom,b.bottom);}}return right>l&&bottom>t;}
 const box=r=>({x:r.x,y:r.y,w:r.width,h:r.height});
 function clipInfo(r,el){let left=0,top=0,right=innerWidth,bottom=innerHeight,chain=[],unmodeled=[];for(let a=el;a;a=a.parentElement){const c=getComputedStyle(a),b=a.getBoundingClientRect(),clipX=['hidden','clip','scroll','auto'].includes(c.overflowX),clipY=['hidden','clip','scroll','auto'].includes(c.overflowY);if(c.transform!=='none'||c.clipPath!=='none'||c.maskImage!=='none'||['scroll','auto'].includes(c.overflowX)||['scroll','auto'].includes(c.overflowY))unmodeled.push({tag:a.localName,transform:c.transform,clipPath:c.clipPath,maskImage:c.maskImage,overflowX:c.overflowX,overflowY:c.overflowY});if(clipX||clipY){const l=b.left+(parseFloat(c.borderLeftWidth)||0),rr=b.right-(parseFloat(c.borderRightWidth)||0),t=b.top+(parseFloat(c.borderTopWidth)||0),bb=b.bottom-(parseFloat(c.borderBottomWidth)||0);if(clipX){left=Math.max(left,l);right=Math.min(right,rr);}if(clipY){top=Math.max(top,t);bottom=Math.min(bottom,bb);}const radius=[c.borderTopLeftRadius,c.borderTopRightRadius,c.borderBottomLeftRadius,c.borderBottomRightRadius];chain.push({tag:a.localName,className:a.className,clipX,clipY,left:l,right:rr,top:t,bottom:bb,radius});if(radius.some(x=>parseFloat(x)>0))unsupported.push({reason:'rounded_ancestor_clip_requires_shape_mask',tag:a.localName});}}const rect={x:Math.max(r.x,left),y:Math.max(r.y,top),right:Math.min(r.x+r.w,right),bottom:Math.min(r.y+r.h,bottom)};rect.w=rect.right-rect.x;rect.h=rect.bottom-rect.y;return {rect,chain,unmodeled,partial:rect.x>r.x||rect.y>r.y||rect.right<r.x+r.w||rect.bottom<r.y+r.h};}
 const rgba=s=>{const a=s.match(/[\d.]+/g);return a?{color:'#'+a.slice(0,3).map(v=>Math.round(+v).toString(16).padStart(2,'0')).join(''),opacity:a.length>3?+a[3]:1}:{color:s,opacity:1}};

 const segmenter=new Intl.Segmenter(undefined,{granularity:'grapheme'});
 function rangeInfo(n,start,end){const r=document.createRange();r.setStart(n,start);r.setEnd(n,end);return {bounds:r.getBoundingClientRect(),rects:[...r.getClientRects()]};}
 function mapWhitespace(n,start,end,mode){
  const preserve=['pre','pre-wrap','break-spaces'].includes(mode),preserveBreak=preserve||mode==='pre-line';
  if(!preserve&&!['normal','nowrap','pre-line'].includes(mode))throw Error('source CSS white-space mode unsupported: '+mode);
  const raw=n.textContent.slice(start,end),out=[];
  const emit=(a,b,text,kind)=>{const q=rangeInfo(n,a,b);out.push({raw:n.textContent.slice(a,b),text,start:a,end:b,kind,...q});};
  if(preserve){for(const g of segmenter.segment(raw)){const a=start+g.index,b=a+g.segment.length;emit(a,b,g.segment==='\n'?'':g.segment,g.segment==='\n'?'line_break':'literal_grapheme');}}
  else{for(const token of raw.matchAll(preserveBreak?/[\t\f\r ]+|\n|[^\t\n\f\r ]+/gu:/[\t\n\f\r ]+|[^\t\n\f\r ]+/gu)){
   const a=start+token.index,b=a+token[0].length;
   if(preserveBreak&&token[0]==='\n'){emit(a,b,'','line_break');continue;}
   if(/^[\t\n\f\r ]+$/u.test(token[0])){const q=rangeInfo(n,a,b),positive=q.rects.filter(r=>r.width>0&&r.height>0);out.push({raw:token[0],text:positive.length?' ':'',start:a,end:b,kind:positive.length?'CSS_collapsed_space':'CSS_trimmed_space',...q});}
   else for(const g of segmenter.segment(token[0])){const p=a+g.index;emit(p,p+g.segment.length,g.segment,'literal_grapheme');}
  }}
  return out;
 }
 window.__img2codeMapCSSWhitespace=mapWhitespace;
 function walk(el){
  if(el.nodeType!==1)return;const tag=el.localName,cs=getComputedStyle(el),r=el.getBoundingClientRect();
  if(cs.display==='none'||cs.visibility==='hidden'||+cs.opacity===0||!r.width||!r.height||!visible(r,el.parentElement))return;
  if(['script','style','link','meta','title'].includes(tag))return;
  if(tag==='svg'||tag==='canvas'){unsupported.push({tag,bbox:box(r)});return;}
  if(cs.zIndex!=='auto'&&cs.zIndex!=='0')unsupported.push({tag,reason:'css_stacking_order',zIndex:cs.zIndex});
  for(const pseudo of ['::before','::after']){const pc=getComputedStyle(el,pseudo);if(pc.content&&pc.content!=='none'&&pc.content!=='normal'&&pc.content!=='""')unsupported.push({tag,reason:'pseudo_content',pseudo,content:pc.content});}
  if(cs.transform!=='none')unsupported.push({tag,reason:'css_transform',transform:cs.transform});
  if(cs.backgroundImage!=='none')unsupported.push({tag,reason:'background_image'});
  let opacity=1;for(let a=el;a;a=a.parentElement)opacity*=+getComputedStyle(a).opacity;
  const fill=rgba(cs.backgroundColor),border=rgba(cs.borderTopColor),bw=parseFloat(cs.borderTopWidth)||0;
  if(fill.opacity>0||bw>0)objects.push({qaOwner:qaElements.indexOf(el),qaOwnerTag:el.tagName,qaPaintEvent:++qaEvent,id:++serial,type:'rect',...box(r),fill,stroke:border,bw,radius:parseFloat(cs.borderTopLeftRadius)||0,opacity});
  if(tag==='img'){
   let b=box(r);if(cs.objectFit==='contain'&&el.naturalWidth&&el.naturalHeight){let scale=Math.min(r.width/el.naturalWidth,r.height/el.naturalHeight);b={x:r.x+(r.width-el.naturalWidth*scale)/2,y:r.y+(r.height-el.naturalHeight*scale)/2,w:el.naturalWidth*scale,h:el.naturalHeight*scale};}
   objects.push({qaOwner:qaElements.indexOf(el),qaOwnerTag:el.tagName,qaPaintEvent:++qaEvent,id:++serial,type:'image',...b,src:el.currentSrc||el.src,loaded:el.complete&&el.naturalWidth>0,opacity});return;
  }

  for(const n of el.childNodes){
   if(n.nodeType===1){walk(n);continue;}if(n.nodeType!==3||!n.textContent.length)continue;
   const event=++qaEvent,mode=cs.whiteSpace,parts=mapWhitespace(n,0,n.textContent.length,mode),groups=[];let current=null;
   const complete=parts.map(t=>t.raw).join('');if(complete!==n.textContent)throw Error('source CSS whitespace Unicode coverage failed');
   for(const part of parts){
    if(part.kind==='line_break'){current=null;continue;}
    if(!part.text)continue;
    const rr=part.rects.filter(r=>r.width>0&&r.height>0),r=rr[0]||part.bounds;
    if(rr.length>1)throw Error('one source grapheme has multiple positive paint rows');
    if(!r.height)continue;
    if(!current||Math.abs(current.y-r.y)>=1||Math.abs(current.h-r.height)>=1){current={...box(r),text:'',qaTextStart:part.start,qaTextEnd:part.end,qaMappedGraphemes:[]};groups.push(current);}
    current.text+=part.text;current.qaTextEnd=part.end;current.qaMappedGraphemes.push({text:part.text,raw:part.raw,start:part.start,end:part.end,kind:part.kind});
    const right=Math.max(current.x+current.w,r.x+r.width);current.x=Math.min(current.x,r.x);current.w=right-current.x;current.y=Math.min(current.y,r.y);current.h=Math.max(current.h,r.height);
   }
   const decorated=(()=>{for(let a=el;a;a=a.parentElement)if(getComputedStyle(a).textDecorationLine!=='none')return true;return false;})();
   const nodeIndex=[...el.childNodes].indexOf(n),kept=[];
   for(const g of groups){
    if(!g.text.trim()&&!decorated){qaOmittedWhitespace.push({owner:qaElements.indexOf(el),node:nodeIndex,start:g.qaTextStart,end:g.qaTextEnd,raw:n.textContent.slice(g.qaTextStart,g.qaTextEnd),kind:'whitespace_only_line_without_decoration'});continue;}
    if(!visible(g,el))continue;
    kept.push(g);objects.push({sourceClip:clipInfo(g,el),id:++serial,type:'text',...g,qaOwner:qaElements.indexOf(el),qaOwnerTag:el.tagName,qaPaintEvent:event,qaTextNodeIndex:nodeIndex,qaWhiteSpace:mode,qaRawText:n.textContent.slice(g.qaTextStart,g.qaTextEnd),color:rgba(cs.color),fontSize:parseFloat(cs.fontSize),fontFamilyRaw:cs.fontFamily,fontFamily:cs.fontFamily.split(',')[0].replace(/["']/g,''),bold:parseInt(cs.fontWeight)>=600||cs.fontWeight==='bold',italic:cs.fontStyle==='italic',underline:cs.textDecorationLine.includes('underline'),opacity});
   }
   for(const match of n.textContent.matchAll(/[^\t\n\f\r ]+/gu)){
    const fragments=groups.flatMap(g=>{const start=Math.max(g.qaTextStart,match.index),end=Math.min(g.qaTextEnd,match.index+match[0].length);return end>start?[{text:n.textContent.slice(start,end),start,end,x:g.x,y:g.y,w:g.w,h:g.h}]:[];});
    if(fragments.length>1)qaWrappedWords.push({owner:qaElements.indexOf(el),event,start:match.index,source_word:match[0],fragments,source_graphemes:[...segmenter.segment(match[0])].length,all_logical_characters_preserved:fragments.map(x=>x.text).join('')===match[0]});
   }
   qaWhitespaceIR.push({owner:qaElements.indexOf(el),node:nodeIndex,whiteSpace:mode,rawText:n.textContent,rawUTF16Length:n.textContent.length,rawUnicodeRoundtrip:true,tokens:parts.map(({rects,bounds,...t})=>t),visibleLines:kept.map(g=>({start:g.qaTextStart,end:g.qaTextEnd,text:g.text})),hardBreaks:parts.filter(t=>t.kind==='line_break').map(({rects,bounds,...t})=>t)});
  }
 }
 walk(document.body);window.__img2codeAlignOwners=qaElements;return {qaWhitespaceIR,qaOmittedWhitespace,qaWrappedWords,qaElementCount:qaElements.length,objects,unsupported,width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,text:document.body.innerText};
}
