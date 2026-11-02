() => {
 const root=document.querySelector('svg'),objects=[],issues=[],nodes={};let serial=0,markerDepth=0,useDepth=0;
 const mat=m=>[m.a,m.b,m.c,m.d,m.e,m.f];
 const box=b=>({x:b.x,y:b.y,w:b.width,h:b.height});
 function group(el,cls){const g=el.closest('g.'+cls);if(!g)return null;let title=[...g.children].find(e=>e.localName==='title')?.textContent;return {id:g.id,title,bbox:box(g.getBoundingClientRect())};}
 function plotClips(el){let clips=[];for(let p=el;p&&p instanceof SVGElement;p=p.parentElement){if(p.__mplClipContext)clips.push(...p.__mplClipContext);const value=getComputedStyle(p).clipPath;if(value&&value!=='none'){const id=value.match(/#([^\s"')]+)/)?.[1],def=id&&document.getElementById(id),rect=def?.children.length===1&&def.children[0].localName==='rect'?def.children[0]:null;if(!rect||(def.getAttribute('clipPathUnits')||'userSpaceOnUse')!=='userSpaceOnUse'||def.hasAttribute('transform')||rect.hasAttribute('transform')){issues.push({reason:'plot_nonrect_or_transformed_clip_requires_another_family',id});continue;}const m=p.getScreenCTM();if(Math.abs(m.b)>1e-7||Math.abs(m.c)>1e-7){issues.push({reason:'plot_non_axis_aligned_clip',id});continue;}const a=new DOMPoint(rect.x.baseVal.value,rect.y.baseVal.value).matrixTransform(m),b=new DOMPoint(rect.x.baseVal.value+rect.width.baseVal.value,rect.y.baseVal.value+rect.height.baseVal.value).matrixTransform(m);clips.push({id,x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),w:Math.abs(b.x-a.x),h:Math.abs(b.y-a.y)});}if(p===root)break;}return clips;}
 function walk(el){
  const tag=el.localName;
  if(['defs','title','desc','metadata','style','script','filter','marker','clipPath','mask','symbol'].includes(tag))return;
  const cs=getComputedStyle(el);
  if(cs.display==='none'||cs.visibility==='hidden'||+cs.opacity===0)return;
  for(const k of ['filter','clipPath','maskImage'])if(cs[k]&&cs[k]!=='none')issues.push({id:el.id,tag,reason:k,value:cs[k]});
  let opacity=1;for(let p=el;p&&p instanceof SVGElement;p=p.parentElement)opacity*=+getComputedStyle(p).opacity;
  const matrix=el.getScreenCTM?.();if(!matrix)return;
  if(['svg','g','a','switch'].includes(tag)){for(const c of el.children)walk(c);return;}
  const s={fill:cs.fill,stroke:cs.stroke,strokeWidth:parseFloat(cs.strokeWidth)||0,fillOpacity:+cs.fillOpacity,strokeOpacity:+cs.strokeOpacity,opacity,linecap:cs.strokeLinecap,linejoin:cs.strokeLinejoin,dash:cs.strokeDasharray,fillRule:cs.fillRule};
  for(const k of ['fill','stroke'])if(s[k].includes('url('))issues.push({id:el.id,tag,reason:k+'_paint_server',value:s[k]});
  const node=group(el,'node'),edge=group(el,'edge');if(node)nodes[node.id]=node;
  const common={id:'v'+(++serial),sourceId:el.id,artist_gid:(()=>{for(let p=el;p&&p instanceof SVGElement;p=p.parentElement){if(p.__mplArtistGid)return p.__mplArtistGid;if((p.id||'').startsWith('matplotlib_artist_'))return p.id;if(p===root)break;}return null;})(),plot_clip_rectangles:plotClips(el),strokeMiterlimit:parseFloat(cs.strokeMiterlimit)||4,dashoffset:parseFloat(cs.strokeDashoffset)||0,tag,matrix:mat(matrix),style:s,node:node?.id,edge:edge||null};
  const paint=cs.fill.match(/url\(["']?#([^"')]+)["']?\)/);if(paint){const grad=document.getElementById(paint[1]);if(grad?.localName==='linearGradient'){common.gradient={tag:'linearGradient',units:grad.getAttribute('gradientUnits')||'objectBoundingBox',transform:grad.getAttribute('gradientTransform'),x1:grad.getAttribute('x1')||'0%',y1:grad.getAttribute('y1')||'0%',x2:grad.getAttribute('x2')||'100%',y2:grad.getAttribute('y2')||'0%',stops:[...grad.querySelectorAll('stop')].map(x=>({offset:x.offset.baseVal,color:getComputedStyle(x).stopColor,opacity:+getComputedStyle(x).stopOpacity}))};}}
  if(cs.mixBlendMode!=='normal')issues.push({id:el.id,reason:'mix_blend_mode',value:cs.mixBlendMode});
  if(cs.fillRule==='evenodd')issues.push({id:el.id,reason:'evenodd_requires_review'});
  if(tag==='text'){
   if(el.querySelector('textPath')){issues.push({id:el.id,tag,reason:'textPath'});return;}
   const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let n,offset=0;
   while(n=walker.nextNode()){
    if(!n.textContent.trim()){offset+=n.textContent.length;continue;}
    const parent=n.parentElement,c=getComputedStyle(parent);const range=document.createRange();range.selectNodeContents(n);const r=range.getBoundingClientRect();
    if(r.width&&r.height){
     const pm=parent.getScreenCTM();const scale=Math.hypot(pm.a,pm.b),rotation=Math.atan2(pm.b,pm.a)*180/Math.PI;
     let textBox=box(r),nativeRotation=0,rotationHandled=false;
     const sy=Math.hypot(pm.c,pm.d),uniform=scale>0&&pm.a*pm.d-pm.b*pm.c>0&&Math.abs(sy-scale)<Math.max(scale,.01)*.0001&&Math.abs(pm.a*pm.c+pm.b*pm.d)<Math.max(scale*scale,.01)*.0001;
     if(Math.abs(rotation)>.01&&uniform&&!el.hasAttribute('rotate')&&!el.querySelector('[rotate]')){
      const saved=root.getAttribute('style'),prior=getComputedStyle(root).transform;
      try{
       root.style.setProperty('transform','rotate('+(-rotation)+'deg) '+(prior==='none'?'':prior),'important');root.style.setProperty('transform-origin','0 0','important');
       const flat=range.getBoundingClientRect();if(!(flat.width>0&&flat.height>0))throw Error('empty unrotated text range');
       textBox={x:r.x+r.width/2-flat.width/2,y:r.y+r.height/2-flat.height/2,w:flat.width,h:flat.height};nativeRotation=rotation;rotationHandled=true;
      }finally{if(saved===null)root.removeAttribute('style');else root.setAttribute('style',saved);}
     }
     if((Math.abs(rotation)>.01||Math.abs(pm.c)>.01||Math.abs(sy-scale)>.01)&&!rotationHandled)issues.push({id:el.id,reason:'text_transform',matrix:mat(pm)});
     objects.push({...common,id:common.id+'t'+offset,type:'text',text:n.textContent,bbox:textBox,originalBoundingBox:box(r),nativeRotation,rotationHandled,fontFamily:c.fontFamily,fontSize:parseFloat(c.fontSize)*scale,color:c.fill,bold:parseInt(c.fontWeight)>=600,italic:c.fontStyle==='italic',underline:c.textDecorationLine.includes('underline'),opacity});
    }
    offset+=n.textContent.length;
   }return;
  }
  const a={};for(const k of ['x','y','width','height','rx','ry','cx','cy','r','x1','y1','x2','y2'])a[k]=el[k]?.baseVal?.value??+(el.getAttribute(k)||0);
  if(['path','rect','circle','ellipse','line','polyline','polygon'].includes(tag)){
   let endpoints=null,points=null;
   if((edge||cs.markerStart!=='none'||cs.markerEnd!=='none')&&el.getTotalLength){
    const length=el.getTotalLength();const steps=Math.min(3000,Math.max(1,Math.ceil(length/2)));points=[];for(let i=0;i<=steps;i++){const p=el.getPointAtLength(length*i/steps).matrixTransform(matrix);points.push([p.x,p.y]);}endpoints=[points[0],points.at(-1)];
   }
   const obj={...common,type:'shape',attrs:a,d:el.getAttribute('d'),pointsAttr:el.getAttribute('points'),bbox:box(el.getBoundingClientRect()),sampledPoints:points,endpoints,markerStart:cs.markerStart,markerEnd:cs.markerEnd};objects.push(obj);
   if(cs.markerMid!=='none')issues.push({id:el.id,reason:'marker_mid'});
   if(!markerDepth)for(const [position,url] of [['start',cs.markerStart],['end',cs.markerEnd]]){
    if(url==='none')continue;
    try{
     const name=url.match(/url\(["']?#([^"')]+)["']?\)/)?.[1],marker=document.getElementById(name);if(!marker)throw Error('missing marker '+url);
     const len=el.getTotalLength(),p=el.getPointAtLength(position==='start'?0:len),q=el.getPointAtLength(position==='start'?Math.min(.1,len):Math.max(0,len-.1));let angle=Math.atan2(position==='start'?q.y-p.y:p.y-q.y,position==='start'?q.x-p.x:p.x-q.x)*180/Math.PI;const orient=marker.getAttribute('orient')||'0';if(orient==='auto-start-reverse'&&position==='start')angle+=180;else if(!orient.startsWith('auto'))angle=parseFloat(orient);
     const unit=marker.getAttribute('markerUnits')==='userSpaceOnUse'?1:parseFloat(cs.strokeWidth);const vb=marker.viewBox.baseVal,mw=marker.markerWidth.baseVal.value,mh=marker.markerHeight.baseVal.value;let sx=vb.width?mw/vb.width:1,sy=vb.height?mh/vb.height:1;if((marker.getAttribute('preserveAspectRatio')||'xMidYMid meet')!=='none')sx=sy=Math.min(sx,sy);const rx=marker.refX.baseVal.value,ry=marker.refY.baseVal.value;
     const T=root.getScreenCTM().inverse().multiply(matrix).translate(p.x,p.y).rotate(angle).scale(unit).scale(sx,sy).translate(-rx,-ry);const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('transform','matrix('+mat(T).join(',')+')');g.style.fill=getComputedStyle(marker).fill;g.style.stroke=getComputedStyle(marker).stroke;
     for(const c of marker.children)g.appendChild(c.cloneNode(true));root.appendChild(g);for(const c of g.querySelectorAll('*')){if(c.getAttribute('fill')==='context-stroke')c.setAttribute('fill',cs.stroke);if(c.getAttribute('fill')==='context-fill')c.setAttribute('fill',cs.fill);}
     const before=objects.length;markerDepth++;for(const c of g.children)walk(c);markerDepth--;for(const added of objects.slice(before))added.markerOwner=obj.id;g.remove();obj[position+'MarkerExpanded']=true;
    }catch(e){markerDepth=0;issues.push({id:obj.id,reason:'marker_expansion_failed',error:String(e)});}
   }
   return;
  }
  if(tag==='use'){
   let g=null;
   try{if(useDepth>=8)throw Error('cyclic/deep use');const href=el.getAttribute('href')||el.getAttributeNS('http://www.w3.org/1999/xlink','href');if(!href?.startsWith('#'))throw Error('external use');const src=document.getElementById(href.slice(1));if(!src)throw Error('missing use target');let T=root.getScreenCTM().inverse().multiply(matrix).translate(el.x.baseVal.value,el.y.baseVal.value);if(src.localName==='symbol'){const v=src.viewBox.baseVal;if(v.width){const sx=el.width.baseVal.value/v.width,sy=el.height.baseVal.value/v.height;if(Math.abs(sx-sy)>.001)issues.push({id:el.id,reason:'use_symbol_aspect_requires_review'});T=T.scale(sx,sy).translate(-v.x,-v.y);}}g=document.createElementNS('http://www.w3.org/2000/svg','g');g.__mplClipContext=plotClips(el);g.__mplArtistGid=common.artist_gid;let alpha=1;for(let p=el;p&&p instanceof SVGElement;p=p.parentElement){alpha*=+getComputedStyle(p).opacity;if(p===root)break;}g.style.opacity=alpha;g.setAttribute('transform','matrix('+mat(T).join(',')+')');for(const k of ['fill','stroke','strokeWidth','fillOpacity','strokeOpacity','strokeLinecap','strokeLinejoin','strokeMiterlimit','strokeDasharray','strokeDashoffset','fillRule','color','fontFamily','fontSize','fontWeight','fontStyle'])g.style[k]=cs[k];if(src.localName==='symbol')for(const c of src.children)g.appendChild(c.cloneNode(true));else g.appendChild(src.cloneNode(true));root.appendChild(g);useDepth++;for(const c of g.children)walk(c);useDepth--;g.remove();return;}catch(e){if(g)g.remove();useDepth=0;issues.push({id:el.id,reason:'use_expansion_failed',error:String(e)});return;}
  }
  if(tag==='image'){
   const href=el.getAttribute('href')||el.getAttributeNS('http://www.w3.org/1999/xlink','href');if(href?.startsWith('data:image/')){objects.push({...common,type:'image',href,bbox:box(el.getBoundingClientRect())});if(Math.abs(matrix.b)>.001||Math.abs(matrix.c)>.001)issues.push({id:el.id,reason:'image_transform_requires_review'});return;}
  }
  issues.push({id:el.id,tag,reason:'unsupported_visible_element'});
 }
 walk(root);return {objects,issues,nodes,sourceText:root.textContent};
}
