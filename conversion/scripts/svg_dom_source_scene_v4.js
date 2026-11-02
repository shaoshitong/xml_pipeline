endpointInput => {
 const endpointFacts=endpointInput.owners,endpointRequests=[],instanceFacts=new Map(endpointInput.instances.map(f=>[JSON.stringify(f.descriptor),f]));
 const root=document.querySelector('svg'),objects=[],issues=[],nodes={};let serial=0,markerDepth=0,useDepth=0;
 const mat=m=>[m.a,m.b,m.c,m.d,m.e,m.f];
 const symbolBuilder=(__SOURCE_SYMBOL_VIEWPORT_BUILDER_V1__),symbolFacts=new WeakMap();
 const symbolHosts=[...document.querySelectorAll('svg use')].filter(e=>!e.closest('defs,symbol,marker,clipPath,mask'));
 for(const f of endpointInput.symbols||[]){if(!f.proof?.ok)continue;const e=symbolHosts[f.index];if(!e)throw Error('symbol_host_missing');const m=e.getScreenCTM(),b=e.getBoundingClientRect(),descriptor={attributes:[...e.attributes].map(a=>[a.name,a.value]),matrix:[m.a,m.b,m.c,m.d,m.e,m.f],bbox:{x:b.x,y:b.y,w:b.width,h:b.height}};if(JSON.stringify(descriptor)!==JSON.stringify(f.descriptor))throw Error('symbol_actual_host_changed');symbolFacts.set(e,f);}


 const sourceEndpointMap=new WeakMap(),describeEndpointOwners=(__SOURCE_ENDPOINT_DESCRIPTORS_V1__),sourceEndpointRows=describeEndpointOwners(root);
 if(!Array.isArray(endpointFacts)||endpointFacts.length!==sourceEndpointRows.length)throw Error('source_endpoint_owner_inventory_changed');
 for(let i=0;i<sourceEndpointRows.length;i++){const actual=sourceEndpointRows[i],fact=endpointFacts[i];if(actual.index!==fact.index||JSON.stringify(actual.descriptor)!==JSON.stringify(fact.descriptor))throw Error('source_endpoint_owner_descriptor_changed');sourceEndpointMap.set(actual.element,fact);}

 const box=b=>({x:b.x,y:b.y,w:b.width,h:b.height});

 const sceneIssues=[],sceneAncestors={},sceneUseContexts={},sceneMarkerContexts={},sceneAncestorIds=new WeakMap();
 const sceneUseStack=[],sceneMarkerStack=[];let sceneAncestorSerial=0,sceneUseSerial=0,sceneMarkerSerial=0;
 const sceneCssKeys=['fill','stroke','color','paintOrder','strokeWidth','fillOpacity','strokeOpacity','opacity','strokeLinecap','strokeLinejoin','strokeDasharray','strokeDashoffset','strokeMiterlimit','fillRule','vectorEffect','filter','clipPath','maskImage','mixBlendMode','isolation','overflow','fontFamily','fontSize','fontWeight','fontStyle','fontKerning','fontFeatureSettings','fontVariationSettings','letterSpacing','wordSpacing','textDecorationLine','display','visibility','animationName'];
 function sceneColorAlpha(value){
  if(!value||value==='context-fill'||value==='context-stroke'||value.startsWith('url('))return null;
  if(value==='none'||value==='transparent')return 0;
  const alpha=x=>x.trim().endsWith('%')?parseFloat(x)/100:parseFloat(x);
  if(value.includes('/'))return alpha(value.slice(value.lastIndexOf('/')+1).replace(/\)\s*$/,''));
  const m=value.match(/^(?:rgba?|hsla?)\(([^)]+)\)$/i);if(m){const parts=m[1].split(/\s*,\s*/);return parts.length===4?alpha(parts[3]):1;}
  if(/^#[0-9a-f]{8}$/i.test(value))return parseInt(value.slice(-2),16)/255;
  if(/^#[0-9a-f]{4}$/i.test(value))return parseInt(value.slice(-1),16)/15;
  return 1;
 }
 const sceneCss=cs=>({...Object.fromEntries(sceneCssKeys.map(k=>[k,cs[k]??null])),fillColorAlpha:sceneColorAlpha(cs.fill),strokeColorAlpha:sceneColorAlpha(cs.stroke),colorAlpha:sceneColorAlpha(cs.color)});
 const sceneOpacity=el=>{let p=1;for(let e=el;e&&e instanceof SVGElement;e=e.parentElement)p*=+getComputedStyle(e).opacity;return p};
 function sceneIssue(reason,detail={},severity='unsupported',scope='source_paint'){
  const issue={reason,...detail,severity,scope};sceneIssues.push(issue);if(severity==='unsupported')issues.push(issue);return issue;
 }
 function sceneAncestor(el){
  if(sceneAncestorIds.has(el))return sceneAncestorIds.get(el);
  const ref='a'+(++sceneAncestorSerial),cs=getComputedStyle(el),data={};sceneAncestorIds.set(el,ref);
  for(const a of el.attributes||[])if(a.name.startsWith('data-'))data[a.name]=a.value;
  const classes=(el.getAttribute('class')||'').split(/\s+/).filter(Boolean),id=el.id||'',roles=[];
  for(const role of ['node','edge','graph','cluster'])if(classes.includes(role))roles.push({role:'graphviz_'+role,basis:'class'});
  for(const key of ['role','data-role','data-node','data-edge','data-source','data-target','data-from','data-to'])if(el.hasAttribute(key))roles.push({role:el.getAttribute(key),basis:key});
  if(/(?:^|[_:\-])(arrow|edge|node|connector|link)(?:[_:\-]|$)/i.test(id))roles.push({role:'relation_name_hint',basis:'id'});
  if(/^(axes|matplotlib\.axis|axis|line2d|PathCollection|PolyCollection|PatchCollection|text|patch)(?:[_:.]|$)/i.test(id))roles.push({role:'plot_group_name_hint',basis:'id'});
  if(/^(PathCollection|PolyCollection|PatchCollection)[_:]/.test(id))roles.push({role:'matplotlib_collection_hint',basis:'id'});
  if(/^text_\d+$/.test(id))roles.push({role:'matplotlib_text_hint',basis:'id'});
  if(/^(MJX|MathJax)/i.test(id)||classes.some(c=>/^(mjx|MathJax)/i.test(c)))roles.push({role:'mathjax_group_hint',basis:'id_or_class'});
  if(/^(?:glyph\d*[-_]|(?:DejaVu|Liberation|STIX|CM|CMMI|CMSY|Arial|Helvetica|TimesNewRoman)[A-Za-z0-9_-]*[-_][0-9A-Fa-f]+$|MJX[-_])/i.test(id))roles.push({role:'font_glyph_definition_hint',basis:'id'});
  sceneAncestors[ref]={tag:el.localName,id,classes,role:el.getAttribute('role'),ariaLabel:el.getAttribute('aria-label'),data,opacity:+cs.opacity,mixBlendMode:cs.mixBlendMode,isolation:cs.isolation,transform:el.getAttribute('transform'),roleHints:roles};
  return ref;
 }
 function sceneAncestry(el){const refs=[];for(let p=el;p&&p instanceof SVGElement;p=p.parentElement)refs.push(sceneAncestor(p));return refs.reverse()}
 function sceneObject(el,cs){
  const ancestry=sceneAncestry(el),groups=[],roleRefs=[...ancestry];for(const context of sceneUseStack)roleRefs.push(...(sceneUseContexts[context]?.callAncestry||[]));for(const ref of [...new Set(roleRefs)])for(const h of sceneAncestors[ref].roleHints)groups.push({ref,...h});
  return {sceneAncestry:ancestry,sceneGroupRoles:groups,sceneComputedCss:sceneCss(cs),sceneAncestorOpacity:ancestry.map(ref=>({ref,opacity:sceneAncestors[ref].opacity})),sceneUseContexts:[...sceneUseStack],sceneMarkerContexts:[...sceneMarkerStack]};
 }
 const sceneUnion=items=>{const bs=items.filter(Boolean);if(!bs.length)return null;const x=Math.min(...bs.map(b=>b.x)),y=Math.min(...bs.map(b=>b.y));return {x,y,w:Math.max(...bs.map(b=>b.x+b.w))-x,h:Math.max(...bs.map(b=>b.y+b.h))-y}};
 const sceneBBoxDelta=(a,b)=>a&&b?{x:b.x-a.x,y:b.y-a.y,w:b.w-a.w,h:b.h-a.h}:null;
 const sceneBBoxSame=(a,b)=>a&&b&&['x','y','w','h'].every(k=>Math.abs(a[k]-b[k])<=.03);
 function sceneNorm(m){const a=m.a*m.a+m.b*m.b,c=m.c*m.c+m.d*m.d,b=m.a*m.c+m.b*m.d;return Math.sqrt(Math.max(0,(a+c+Math.sqrt((a-c)*(a-c)+4*b*b))/2))}
 function sceneMatrix(m){const sx=Math.hypot(m.a,m.b),sy=Math.hypot(m.c,m.d),dot=m.a*m.c+m.b*m.d,det=m.a*m.d-m.b*m.c;return {matrix:mat(m),sx,sy,determinant:det,operatorNorm:sceneNorm(m),axisAligned:Math.abs(m.b)<1e-8&&Math.abs(m.c)<1e-8,reflection:det<0,similarity:Math.abs(sx-sy)<=Math.max(1,sx,sy)*1e-6&&Math.abs(dot)<=Math.max(1,sx*sy)*1e-6}}
 function sceneClosure(tag,el){
  if(['rect','circle','ellipse','polygon'].includes(tag))return {kind:'primitive',subpathCount:1,closedSubpaths:1,openSubpaths:0,explicitlyClosed:true};
  if(['line','polyline'].includes(tag))return {kind:'primitive',subpathCount:1,closedSubpaths:0,openSubpaths:1,explicitlyClosed:false};
  const d=el.getAttribute('d')||'',commands=d.match(/[MmLlHhVvCcSsQqTtAaZz]/g)||[];let current=null,subpaths=[];
  for(const command of commands){const c=command.toUpperCase();if(c==='M'){if(current)subpaths.push(current);current={closed:false,implicitStart:false}}else if(c==='Z'){if(!current)current={closed:false,implicitStart:true};current.closed=true}else{if(!current||current.closed){if(current)subpaths.push(current);current={closed:false,implicitStart:true}}}}
  if(current)subpaths.push(current);return {kind:'path_command_metadata_only',subpathCount:subpaths.length,closedSubpaths:subpaths.filter(s=>s.closed).length,openSubpaths:subpaths.filter(s=>!s.closed).length,explicitlyClosed:!!subpaths.length&&subpaths.every(s=>s.closed&&!s.implicitStart),requiresAuthoritativePathParse:true};
 }
 function sceneGeometry(el,tag,matrix){
  const result={matrix:sceneMatrix(matrix),closure:sceneClosure(tag,el),sampledPoints:null,localLength:null,steps:0,arcStepDeviceUpperBound:null,samplingCapReached:false,samplingBasis:'getTotalLength/getPointAtLength with screen CTM operator-norm arc bound'};
  if(!el.getTotalLength){result.samplingError='no_geometry_length_api';return result}
  try{const length=el.getTotalLength(),scale=sceneNorm(matrix),wanted=Math.max(1,Math.ceil(length*scale/2)),steps=Math.min(3000,wanted),points=[];
   for(let i=0;i<=steps;i++){const p=el.getPointAtLength(length*i/steps).matrixTransform(matrix);points.push([p.x,p.y])}
   Object.assign(result,{localLength:length,steps,sampledPoints:points,arcStepDeviceUpperBound:length*scale/steps,samplingCapReached:wanted>3000});
   if(wanted>3000)sceneIssue('scene_geometry_sampling_capped',{id:el.id,tag,wantedSteps:wanted,actualSteps:steps,arcStepDeviceUpperBound:result.arcStepDeviceUpperBound},'informational','geometry_sampling');
  }catch(e){result.samplingError=String(e);sceneIssue('scene_geometry_sampling_failed',{id:el.id,tag,error:String(e)},'informational','geometry_sampling')}
  return result;
 }
 function sceneRules(){const found=[];function walkRules(rules){for(const r of rules||[]){if(r.selectorText)found.push(r.selectorText);if(r.cssRules)walkRules(r.cssRules)}}for(const s of document.styleSheets)try{walkRules(s.cssRules)}catch(e){sceneIssue('scene_stylesheet_rules_uninspectable',{error:String(e)})}return found}
 const sceneSelectors=sceneRules();
 function sceneSelectorRisks(originals,clones){const risks=[];function compare(a,b){if(!a||!b)return;for(const selector of sceneSelectors)try{const x=a.matches(selector),y=b.matches(selector);if(x!==y)risks.push({selector,sourceTag:a.localName,sourceId:a.id||'',sourceMatches:x,cloneMatches:y})}catch(e){}const ac=[...a.children],bc=[...b.children];for(let i=0;i<Math.min(ac.length,bc.length);i++)compare(ac[i],bc[i])}for(let i=0;i<Math.min(originals.length,clones.length);i++)compare(originals[i],clones[i]);return risks}
 function sceneQuad(m,rect){return [[rect.x,rect.y],[rect.x+rect.w,rect.y],[rect.x+rect.w,rect.y+rect.h],[rect.x,rect.y+rect.h]].map(([x,y])=>{const p=new DOMPoint(x,y).matrixTransform(m);return [p.x,p.y]})}
 function sceneMarkerViewport(marker,mw,mh,rx,ry,T){
  const vb=marker.viewBox.baseVal,raw=marker.getAttribute('preserveAspectRatio')||'xMidYMid meet',parts=raw.trim().split(/\s+/),align=parts.find(p=>/^x(?:Min|Mid|Max)Y(?:Min|Mid|Max)$/.test(p))||'xMidYMid',none=parts.includes('none'),slice=parts.includes('slice');let sx=vb.width?mw/vb.width:1,sy=vb.height?mh/vb.height:1;
  if(!none){sx=sy=(slice?Math.max:Math.min)(sx,sy)}const extraX=mw-(vb.width||mw)*sx,extraY=mh-(vb.height||mh)*sy,ax=align.includes('xMin')?0:align.includes('xMax')?1:.5,ay=align.includes('YMin')?0:align.includes('YMax')?1:.5,tx=-(vb.x||0)*sx+extraX*ax,ty=-(vb.y||0)*sy+extraY*ay;
  const local={x:(0-tx)/sx,y:(0-ty)/sy,w:mw/sx,h:mh/sy},world=root.getScreenCTM().multiply(T),cs=getComputedStyle(marker);
  return {viewBox:{x:vb.x,y:vb.y,w:vb.width,h:vb.height},markerWidth:mw,markerHeight:mh,refX:{raw:marker.getAttribute('refX'),value:rx,unitType:marker.refX.baseVal.unitType,valueInSpecifiedUnits:marker.refX.baseVal.valueInSpecifiedUnits},refY:{raw:marker.getAttribute('refY'),value:ry,unitType:marker.refY.baseVal.unitType,valueInSpecifiedUnits:marker.refY.baseVal.valueInSpecifiedUnits},markerUnits:marker.getAttribute('markerUnits')||'strokeWidth',orient:marker.getAttribute('orient')||'0',overflow:cs.overflow,preserveAspectRatio:raw,viewport:{width:mw,height:mh},viewportInMarkerCoordinates:local,viewportScreenPolygon:sceneQuad(world,local),syntheticContentScreenCTM:mat(world),viewportClipRequired:cs.overflow!=='visible',viewportClipProven:false,syntheticCloneIsActualMarkerPaint:false,viewportScreenPolygonBasis:'synthetic base-clone CTM; not an independent clipped marker paint measurement',refCoordinateInterpretationProven:![2].includes(marker.refX.baseVal.unitType)&&![2].includes(marker.refY.baseVal.unitType)};
 }
 const sceneDynamic=root.querySelectorAll('animate,animateTransform,animateMotion,set');if(sceneDynamic.length)sceneIssue('scene_dynamic_svg_animation_unproven',{count:sceneDynamic.length});

 function group(el,cls){const g=el.closest('g.'+cls);if(!g)return null;let title=[...g.children].find(e=>e.localName==='title')?.textContent;return {id:g.id,title,bbox:box(g.getBoundingClientRect())};}

 // display/opacity suppress a whole subtree. Visibility is inherited but may
 // be reset by a descendant, so only the actual painting leaf decides it.
 function sourceSubtreeBlocked(el){for(let p=el;p;p=p.parentElement){const c=getComputedStyle(p);if(c.display==='none'||+c.opacity===0)return true;if(p===root)break;}return false;}
 function sourceTextPainted(node){const p=node.parentElement;return p&&getComputedStyle(p).visibility==='visible'&&!p.closest('defs,marker,symbol,pattern,clipPath,mask')&&!sourceSubtreeBlocked(p);}
 function sourceInstanceVisibilityRisk(el){const blocked=p=>{const c=getComputedStyle(p);return c.visibility!=='visible'||c.display==='none'||+c.opacity===0;};for(const p of [el,...el.querySelectorAll('*')])if(blocked(p))return true;for(let p=el.parentElement;p;p=p.parentElement){if(blocked(p))return true;if(p===root)break;}return false;}
 function walk(el){
  const tag=el.localName;
  if(['defs','title','desc','metadata','style','script','filter','marker','clipPath','mask','symbol'].includes(tag))return;
  const cs=getComputedStyle(el);
  if(sourceSubtreeBlocked(el))return;
  for(const k of ['filter','clipPath','maskImage'])if(cs[k]&&cs[k]!=='none')issues.push({id:el.id,tag,reason:k,value:cs[k]});
  let opacity=1;for(let p=el;p&&p instanceof SVGElement;p=p.parentElement)opacity*=+getComputedStyle(p).opacity;
  const matrix=el.getScreenCTM?.();if(!matrix)return;
  if(tag==='switch')sceneIssue('scene_switch_selection_unproven',{id:el.id,tag});
  if(el.getAnimations?.().length)sceneIssue('scene_active_animation_unproven',{id:el.id,tag,count:el.getAnimations().length});
  if(['svg','g','a','switch'].includes(tag)){for(const c of el.children)walk(c);return;}
  if(tag!=='text'&&tag!=='use'&&cs.visibility!=='visible')return;
  if(tag==='use'&&cs.visibility!=='visible'){issues.push({id:el.id,tag,reason:'source_use_visibility_context_requires_instance_proof'});return;}
  const s={fill:cs.fill,stroke:cs.stroke,strokeWidth:parseFloat(cs.strokeWidth)||0,fillOpacity:+cs.fillOpacity,strokeOpacity:+cs.strokeOpacity,opacity,linecap:cs.strokeLinecap,linejoin:cs.strokeLinejoin,dash:cs.strokeDasharray,fillRule:cs.fillRule};
  for(const k of ['fill','stroke'])if(s[k].includes('url('))issues.push({id:el.id,tag,reason:k+'_paint_server',value:s[k]});
  const node=group(el,'node'),edge=group(el,'edge');if(node)nodes[node.id]=node;
  const common={id:'v'+(++serial),sourceId:el.id,tag,matrix:mat(matrix),style:s,node:node?.id,edge:edge||null,...sceneObject(el,cs)};
  const paint=cs.fill.match(/url\(["']?#([^"')]+)["']?\)/);if(paint){const grad=document.getElementById(paint[1]);if(grad?.localName==='linearGradient'){common.gradient={tag:'linearGradient',units:grad.getAttribute('gradientUnits')||'objectBoundingBox',transform:grad.getAttribute('gradientTransform'),x1:grad.getAttribute('x1')||'0%',y1:grad.getAttribute('y1')||'0%',x2:grad.getAttribute('x2')||'100%',y2:grad.getAttribute('y2')||'0%',stops:[...grad.querySelectorAll('stop')].map(x=>({offset:x.offset.baseVal,color:getComputedStyle(x).stopColor,opacity:+getComputedStyle(x).stopOpacity}))};}}
  if(cs.mixBlendMode!=='normal')issues.push({id:el.id,reason:'mix_blend_mode',value:cs.mixBlendMode});
  if(cs.fillRule==='evenodd')issues.push({id:el.id,reason:'evenodd_requires_review'});
  if(tag==='text'){
   if(el.querySelector('textPath')){issues.push({id:el.id,tag,reason:'textPath'});return;}
   const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let n,offset=0;
   while(n=walker.nextNode()){
    if(!n.textContent.trim()||!sourceTextPainted(n)){offset+=n.textContent.length;continue;}
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
     const sceneText={parentAncestry:sceneAncestry(parent),computedCss:sceneCss(c),actualOpacityProduct:sceneOpacity(parent),baseMappedOpacity:opacity};if(Math.abs(sceneText.actualOpacityProduct-opacity)>1e-8)sceneIssue('scene_text_descendant_opacity_not_in_base_mapping',{id:common.id+'t'+offset,actualOpacity:sceneText.actualOpacityProduct,baseOpacity:opacity});
     objects.push({...common,sceneText,id:common.id+'t'+offset,type:'text',text:n.textContent,bbox:textBox,originalBoundingBox:box(r),nativeRotation,rotationHandled,fontFamily:c.fontFamily,fontSize:parseFloat(c.fontSize)*scale,color:c.fill,bold:parseInt(c.fontWeight)>=600,italic:c.fontStyle==='italic',underline:c.textDecorationLine.includes('underline'),opacity});
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
   const sceneGeo=sceneGeometry(el,tag,matrix);if(!points&&sceneGeo.sampledPoints){points=sceneGeo.sampledPoints;endpoints=[points[0],points.at(-1)]}
   const obj={...common,type:'shape',attrs:a,d:el.getAttribute('d'),pointsAttr:el.getAttribute('points'),bbox:box(el.getBoundingClientRect()),sampledPoints:points,endpoints,markerStart:cs.markerStart,markerEnd:cs.markerEnd,sceneGeometry:sceneGeo};objects.push(obj);
   if(cs.markerMid!=='none')issues.push({id:el.id,reason:'marker_mid'});
   if(!markerDepth)for(const [position,url] of [['start',cs.markerStart],['end',cs.markerEnd]]){
    if(url==='none')continue;
    try{
     const name=url.match(/url\(["']?#([^"')]+)["']?\)/)?.[1],marker=document.getElementById(name);if(!marker)throw Error('missing marker '+url);if(sourceInstanceVisibilityRisk(marker))throw Error('source_marker_visibility_context_requires_instance_proof');
     let fact=sourceEndpointMap.get(el);if(!fact){const row=describeEndpointOwners(root).find(row=>row.element===el);if(!row)throw Error('source_instance_endpoint_descriptor_missing');fact=instanceFacts.get(JSON.stringify(row.descriptor));if(!fact){endpointRequests.push(row.descriptor);throw Error('source_instance_endpoint_facts_pending');}sourceEndpointMap.set(el,fact);} const endpoint=fact.direction[position],p=new DOMPoint(...endpoint.point_local),orient=marker.getAttribute('orient')||'0';let angle;if(orient==='auto'||orient==='auto-start-reverse'){const v=endpoint.forward_local;angle=Math.atan2(v[1],v[0])*180/Math.PI;if(orient==='auto-start-reverse'&&position==='start')angle+=180;}else angle=marker.orientAngle.baseVal.value;
     const unit=marker.getAttribute('markerUnits')==='userSpaceOnUse'?1:parseFloat(cs.strokeWidth);const vb=marker.viewBox.baseVal,mw=marker.markerWidth.baseVal.value,mh=marker.markerHeight.baseVal.value;let sx=vb.width?mw/vb.width:1,sy=vb.height?mh/vb.height:1;if((marker.getAttribute('preserveAspectRatio')||'xMidYMid meet')!=='none')sx=sy=Math.min(sx,sy);const rx=marker.refX.baseVal.value,ry=marker.refY.baseVal.value;
     const T=root.getScreenCTM().inverse().multiply(matrix).translate(p.x,p.y).rotate(angle).scale(unit).scale(sx,sy).translate(-rx,-ry);const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('transform','matrix('+mat(T).join(',')+')');g.style.fill=getComputedStyle(marker).fill;g.style.stroke=getComputedStyle(marker).stroke;
     for(const c of marker.children)g.appendChild(c.cloneNode(true));root.appendChild(g);for(const c of g.querySelectorAll('*')){if(c.getAttribute('fill')==='context-stroke')c.setAttribute('fill',cs.stroke);if(c.getAttribute('fill')==='context-fill')c.setAttribute('fill',cs.fill);}
     const context='m'+(++sceneMarkerSerial),viewport=sceneMarkerViewport(marker,mw,mh,rx,ry,T),sourceChildren=[...marker.children],cloneChildren=[...g.children],selectorRisks=sceneSelectorRisks(sourceChildren,cloneChildren);
     const markerContext={id:context,owner:obj.id,side:position,markerDefinitionId:name,url,ownerAncestry:common.sceneAncestry,definitionAncestry:sceneAncestry(marker),ownerComputedCss:sceneCss(cs),definitionComputedCss:sceneCss(getComputedStyle(marker)),ownerActualBBox:box(el.getBoundingClientRect()),ownerBBoxIsOriginalDocumentInstance:sceneUseStack.length===0&&sceneMarkerStack.length===0,...viewport,selectorRisks,syntheticCloneBBox:box(g.getBoundingClientRect()),syntheticCloneLocalBBox:box(g.getBBox()),risks:[]};sceneMarkerContexts[context]=markerContext;
     if(viewport.viewportClipRequired){markerContext.risks.push('synthetic_clone_does_not_apply_marker_viewport_clip');sceneIssue('scene_marker_viewport_clip_unproven',{id:obj.id,markerContext:context,side:position,markerDefinitionId:name},'unsupported','marker_viewport')}
     if((marker.getAttribute('preserveAspectRatio')||'').includes('slice')){markerContext.risks.push('base_clone_uses_meet_scale_for_slice');sceneIssue('scene_marker_slice_mapping_unproven',{id:obj.id,markerContext:context})}
     if(!viewport.refCoordinateInterpretationProven){markerContext.risks.push('percent_ref_coordinates');sceneIssue('scene_marker_percent_ref_unproven',{id:obj.id,markerContext:context})}
     if(selectorRisks.length){markerContext.risks.push('selector_context_changed');sceneIssue('scene_marker_clone_css_context_changed',{id:obj.id,markerContext:context,selectorRisks})}
     const before=objects.length;sceneMarkerStack.push(context);markerDepth++;try{for(const c of g.children)walk(c)}finally{markerDepth--;sceneMarkerStack.pop()}
     const addedObjects=objects.slice(before);for(const added of addedObjects){added.markerOwner=obj.id;added.markerSide=position;added.markerDefinitionId=name;added.markerContext=context}
     markerContext.emittedObjectIds=addedObjects.map(o=>o.id);markerContext.emittedBBox=sceneUnion(addedObjects.map(o=>o.bbox));g.remove();obj[position+'MarkerExpanded']=true;
    }catch(e){markerDepth=0;issues.push({id:obj.id,reason:'marker_expansion_failed',error:String(e)});}
   }
   return;
  }
  if(tag==='use'){
   let g=null,context=null;
   try{
    if(useDepth>=8)throw Error('cyclic/deep use');const href=el.getAttribute('href')||el.getAttributeNS('http://www.w3.org/1999/xlink','href');if(!href?.startsWith('#'))throw Error('external use');const src=document.getElementById(href.slice(1));if(!src)throw Error('missing use target');if(sourceInstanceVisibilityRisk(src))throw Error('source_use_visibility_context_requires_instance_proof');let T=root.getScreenCTM().inverse().multiply(matrix).translate(el.x.baseVal.value,el.y.baseVal.value);
    const symbolFact=src.localName==='symbol'?symbolFacts.get(el):null;if(src.localName==='symbol'&&!symbolFact)throw Error('source_symbol_actual_viewport_unproved');
    context='u'+(++sceneUseSerial);const call={id:context,callId:common.id,sourceId:el.id||'',href,callAncestry:common.sceneAncestry,callComputedCss:sceneCss(cs),callOpacityProduct:sceneOpacity(el),actualCallBBox:box(el.getBoundingClientRect()),actualCallBBoxIsOriginalDocumentInstance:sceneUseStack.length===0&&sceneMarkerStack.length===0,parentUseContexts:[...sceneUseStack],parentMarkerContexts:[...sceneMarkerStack],actualCallBBoxMeaning:'Current DOM call bbox; synthetic invocation context must be interpreted through parent contexts, and is not clipped marker paint.',sourceDefinitionAncestry:sceneAncestry(src),sourceDefinitionTag:src.localName,sourceDefinitionId:src.id||'',sourceDefinitionComputedCss:sceneCss(getComputedStyle(src)),x:el.x.baseVal.value,y:el.y.baseVal.value,width:el.width.baseVal.value,height:el.height.baseVal.value,preserveAspectRatio:el.getAttribute('preserveAspectRatio'),sourceDefinitionPreserveAspectRatio:src.getAttribute('preserveAspectRatio'),sourceDefinitionOverflow:getComputedStyle(src).overflow,sourceDefinitionViewBox:src.viewBox?{x:src.viewBox.baseVal.x,y:src.viewBox.baseVal.y,w:src.viewBox.baseVal.width,h:src.viewBox.baseVal.height}:null,syntheticCloneIsActualUsePaint:false,risks:[]};sceneUseContexts[context]=call;
    let symbolViewport=null;if(symbolFact){const made=symbolBuilder(root,el,symbolFact.definition);g=made.g;symbolViewport=made.v;call.actualSymbolViewportProof=symbolFact.proof;}else{g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('transform','matrix('+mat(T).join(',')+')');for(const k of ['fill','stroke','strokeWidth','color','fontFamily','fontSize'])g.style[k]=cs[k];g.appendChild(src.cloneNode(true));root.appendChild(g);}
    call.syntheticViewportContainerBBox=box(g.getBoundingClientRect());call.syntheticCloneBBox=symbolViewport?sceneUnion([...symbolViewport.querySelectorAll('path,line,polyline,polygon,rect,circle,ellipse')].map(e=>box(e.getBoundingClientRect()))):box(g.getBoundingClientRect());call.syntheticCloneLocalBBox=box(g.getBBox());call.cloneComputedCss=sceneCss(getComputedStyle(g));call.cloneOpacityProduct=sceneOpacity(g);call.syntheticCloneScreenCTM=mat(g.getScreenCTM());call.bboxDelta=sceneBBoxDelta(call.actualCallBBox,call.syntheticCloneBBox);call.bboxMatches=sceneBBoxSame(call.actualCallBBox,call.syntheticCloneBBox);
    const sourceChildren=src.localName==='symbol'?[...src.children]:[src],cloneChildren=[...(symbolViewport||g).children];call.selectorRisks=sceneSelectorRisks(sourceChildren,cloneChildren);
    if(!call.bboxMatches){call.risks.push('actual_call_and_synthetic_clone_bbox_differ');sceneIssue('scene_use_expansion_bbox_mismatch',{id:common.id,useContext:context,actualBBox:call.actualCallBBox,cloneBBox:call.syntheticCloneBBox})}
    if(Math.abs(call.callOpacityProduct-call.cloneOpacityProduct)>1e-8){call.risks.push('ancestor_or_call_opacity_not_forwarded');sceneIssue('scene_use_opacity_context_changed',{id:common.id,useContext:context,callOpacity:call.callOpacityProduct,cloneOpacity:call.cloneOpacityProduct})}
    const forwarded=new Set(['fill','stroke','strokeWidth','color','fontFamily','fontSize','opacity','filter','clipPath','maskImage','mixBlendMode','isolation','overflow','display','visibility','animationName']);call.unforwardedComputedCss=sceneCssKeys.filter(k=>!forwarded.has(k)&&call.callComputedCss[k]!==call.cloneComputedCss[k]).map(property=>({property,call:call.callComputedCss[property],clone:call.cloneComputedCss[property]}));
    const textOnly=new Set(['fontWeight','fontStyle','fontKerning','fontFeatureSettings','fontVariationSettings','letterSpacing','wordSpacing','textDecorationLine']),strokeOnly=new Set(['strokeLinecap','strokeLinejoin','strokeDasharray','strokeDashoffset','strokeMiterlimit','vectorEffect']);call.referenceContainsText=src.localName==='text'||!!src.querySelector('text');call.referenceMayStroke=cs.stroke!=='none'||[src,...src.querySelectorAll('*')].some(e=>getComputedStyle(e).stroke!=='none');call.paintRelevantUnforwardedCss=call.unforwardedComputedCss.filter(p=>(!textOnly.has(p.property)||call.referenceContainsText)&&(!strokeOnly.has(p.property)||call.referenceMayStroke));
    if(call.paintRelevantUnforwardedCss.length){call.risks.push('unforwarded_inherited_css');sceneIssue('scene_use_inherited_css_context_not_forwarded',{id:common.id,useContext:context,properties:call.paintRelevantUnforwardedCss})}
    if(call.selectorRisks.length){call.risks.push('selector_context_changed');sceneIssue('scene_use_clone_selector_context_changed',{id:common.id,useContext:context,selectorRisks:call.selectorRisks})}
    if(src.localName==='symbol'&&!symbolFact?.proof?.full_paint_contained_in_viewport&&call.sourceDefinitionOverflow!=='visible'){call.risks.push('symbol_viewport_clip_not_proven');sceneIssue('scene_use_symbol_viewport_clip_unproven',{id:common.id,useContext:context},'unsupported','use_viewport')}
    const before=objects.length;sceneUseStack.push(context);useDepth++;try{for(const c of g.children)walk(c)}finally{useDepth--;sceneUseStack.pop()}
    const expanded=objects.slice(before);call.emittedObjectIds=expanded.map(o=>o.id);call.emittedBBox=sceneUnion(expanded.map(o=>o.bbox));g.remove();return;
   }catch(e){if(g)g.remove();useDepth=0;issues.push({id:el.id,reason:'use_expansion_failed',error:String(e)});if(context)sceneUseContexts[context].error=String(e);return;}
  }
  if(tag==='image'){
   const href=el.getAttribute('href')||el.getAttributeNS('http://www.w3.org/1999/xlink','href');if(href?.startsWith('data:image/')){objects.push({...common,type:'image',href,bbox:box(el.getBoundingClientRect()),sceneImage:{preserveAspectRatio:el.getAttribute('preserveAspectRatio')||'xMidYMid meet',attrs:a,matrix:sceneMatrix(matrix),axisAligned:Math.abs(matrix.b)<1e-8&&Math.abs(matrix.c)<1e-8,reflection:matrix.a*matrix.d-matrix.b*matrix.c<0,flipX:Math.abs(matrix.b)<1e-8&&Math.abs(matrix.c)<1e-8&&matrix.a<0,flipY:Math.abs(matrix.b)<1e-8&&Math.abs(matrix.c)<1e-8&&matrix.d<0,viewportBBox:box(el.getBoundingClientRect())}});if(Math.abs(matrix.b)>.001||Math.abs(matrix.c)>.001)issues.push({id:el.id,reason:'image_transform_requires_review'});return;}
  }
  issues.push({id:el.id,tag,reason:'unsupported_visible_element'});
 }
 walk(root);return {sourceEndpointRequests:endpointRequests,objects,issues,nodes,sourceText:root.textContent,sceneIssues,sceneMetadata:{version:1,ancestors:sceneAncestors,useContexts:sceneUseContexts,markerContexts:sceneMarkerContexts,root:{id:root.id||'',viewBox:{x:root.viewBox.baseVal.x,y:root.viewBox.baseVal.y,w:root.viewBox.baseVal.width,h:root.viewBox.baseVal.height},width:root.width.baseVal.value,height:root.height.baseVal.value,preserveAspectRatio:root.getAttribute('preserveAspectRatio')||'xMidYMid meet'},metadataText:(root.querySelector('metadata')?.textContent||'').slice(0,8192),objectSerialFinal:serial}};
}
