() => {
 const objects=[],unsupported=[];let serial=0;
 function visible(r,el){let l=Math.max(r.x,0),t=Math.max(r.y,0),right=Math.min(r.right??r.x+r.w,innerWidth),bottom=Math.min(r.bottom??r.y+r.h,innerHeight);for(let a=el;a;a=a.parentElement){const c=getComputedStyle(a),b=a.getBoundingClientRect();if([c.overflow,c.overflowX,c.overflowY].some(v=>["hidden","clip","scroll","auto"].includes(v))){l=Math.max(l,b.left);t=Math.max(t,b.top);right=Math.min(right,b.right);bottom=Math.min(bottom,b.bottom);}}return right>l&&bottom>t;}
 const box=r=>({x:r.x,y:r.y,w:r.width,h:r.height});
 function clipInfo(r,el){let left=0,top=0,right=innerWidth,bottom=innerHeight,chain=[],unmodeled=[];for(let a=el;a;a=a.parentElement){const c=getComputedStyle(a),b=a.getBoundingClientRect(),clipX=['hidden','clip','scroll','auto'].includes(c.overflowX),clipY=['hidden','clip','scroll','auto'].includes(c.overflowY);if(c.transform!=='none'||c.clipPath!=='none'||c.maskImage!=='none'||['scroll','auto'].includes(c.overflowX)||['scroll','auto'].includes(c.overflowY))unmodeled.push({tag:a.localName,transform:c.transform,clipPath:c.clipPath,maskImage:c.maskImage,overflowX:c.overflowX,overflowY:c.overflowY});if(clipX||clipY){const l=b.left+(parseFloat(c.borderLeftWidth)||0),rr=b.right-(parseFloat(c.borderRightWidth)||0),t=b.top+(parseFloat(c.borderTopWidth)||0),bb=b.bottom-(parseFloat(c.borderBottomWidth)||0);if(clipX){left=Math.max(left,l);right=Math.min(right,rr);}if(clipY){top=Math.max(top,t);bottom=Math.min(bottom,bb);}const radius=[c.borderTopLeftRadius,c.borderTopRightRadius,c.borderBottomLeftRadius,c.borderBottomRightRadius];chain.push({tag:a.localName,className:a.className,clipX,clipY,left:l,right:rr,top:t,bottom:bb,radius});if(radius.some(x=>parseFloat(x)>0))unsupported.push({reason:'rounded_ancestor_clip_requires_shape_mask',tag:a.localName});}}const rect={x:Math.max(r.x,left),y:Math.max(r.y,top),right:Math.min(r.x+r.w,right),bottom:Math.min(r.y+r.h,bottom)};rect.w=rect.right-rect.x;rect.h=rect.bottom-rect.y;return {rect,chain,unmodeled,partial:rect.x>r.x||rect.y>r.y||rect.right<r.x+r.w||rect.bottom<r.y+r.h};}
 const rgba=s=>{const a=s.match(/[\d.]+/g);return a?{color:'#'+a.slice(0,3).map(v=>Math.round(+v).toString(16).padStart(2,'0')).join(''),opacity:a.length>3?+a[3]:1}:{color:s,opacity:1}};
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
  if(fill.opacity>0||bw>0)objects.push({id:++serial,type:'rect',...box(r),fill,stroke:border,bw,radius:parseFloat(cs.borderTopLeftRadius)||0,opacity});
  if(tag==='img'){
   let b=box(r);if(cs.objectFit==='contain'&&el.naturalWidth&&el.naturalHeight){let scale=Math.min(r.width/el.naturalWidth,r.height/el.naturalHeight);b={x:r.x+(r.width-el.naturalWidth*scale)/2,y:r.y+(r.height-el.naturalHeight*scale)/2,w:el.naturalWidth*scale,h:el.naturalHeight*scale};}
   objects.push({id:++serial,type:'image',...b,src:el.currentSrc||el.src,loaded:el.complete&&el.naturalWidth>0,opacity});return;
  }
  for(const n of el.childNodes){
   if(n.nodeType===1){walk(n);continue;}if(n.nodeType!==3||!n.textContent.trim())continue;
   const txt=n.textContent;let groups=[];for(const match of txt.matchAll(/\S+/gu)){
    const range=document.createRange();range.setStart(n,match.index);range.setEnd(n,match.index+match[0].length);const rects=[...range.getClientRects()].filter(r=>r.width&&r.height);
    if(rects.length!==1){unsupported.push({reason:'word_spans_multiple_lines',text:match[0].slice(0,40)});continue;}
    const b=rects[0],last=groups.at(-1);
    if(last&&Math.abs(last.y-b.y)<1&&b.x>=last.x){last.text+=' '+match[0];last.w=Math.max(last.x+last.w,b.right)-last.x;last.h=Math.max(last.h,b.height);}
    else groups.push({...box(b),text:match[0]});
   }
   for(const g of groups)if(visible(g,el))objects.push({sourceClip:clipInfo(g,el),id:++serial,type:'text',...g,color:rgba(cs.color),fontSize:parseFloat(cs.fontSize),fontFamilyRaw:cs.fontFamily,fontFamily:cs.fontFamily.split(',')[0].replace(/["']/g,''),bold:parseInt(cs.fontWeight)>=600||cs.fontWeight==='bold',italic:cs.fontStyle==='italic',underline:cs.textDecorationLine.includes('underline'),opacity});
  }
 }
 walk(document.body);return {objects,unsupported,width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,text:document.body.innerText};
}
