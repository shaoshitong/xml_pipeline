() => {
 const root=document.querySelector('svg'),ns=root.namespaceURI,groups=[],aliases=new Map(),issues=[];
 function add(g,name,kind,method){let uid='pu'+groups.length;const title=document.createElementNS(ns,'title');title.textContent=uid;g.insertBefore(title,g.firstChild);const oldId=g.id;g.id=uid;g.classList.add('node');const record={uid,name,kind,method,originalId:oldId,sourceLine:g.getAttribute('data-source-line')};groups.push(record);for(const alias of [name,oldId])if(alias){if(!aliases.has(alias))aliases.set(alias,[]);aliases.get(alias).push(uid);}return record;}
 const declared=[...root.querySelectorAll('g.entity,g.cluster')];for(const g of declared)add(g,g.getAttribute('data-entity'),g.classList.contains('cluster')?'cluster':'entity','engine_entity_metadata');
 for(const g of [...root.querySelectorAll('g[id]')]){if(g.classList.contains('node')||g.classList.contains('link')||g.closest('defs'))continue;const name=g.id.split('.').at(-1);if(g.querySelector(':scope > text')&&g.querySelector(':scope > rect,:scope > polygon,:scope > path,:scope > ellipse'))add(g,name,'entity','engine_state_group_identifier');}
 const links=[...root.querySelectorAll('g.link')];const resolve=name=>{const hits=[...new Set(aliases.get(name)||[])];return hits.length===1?document.getElementById(hits[0]):null;};
 const box=e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height};};
 const contains=(a,b)=>b.x>=a.x-.1&&b.y>=a.y-.1&&b.x+b.w<=a.x+a.w+.1&&b.y+b.h<=a.y+a.h+.1;
 const missing=[...new Set(links.flatMap(g=>[g.getAttribute('data-entity-1'),g.getAttribute('data-entity-2')]))].filter(n=>!resolve(n));
 for(const name of missing.filter(n=>!n.startsWith('.start.')&&!n.startsWith('.end.'))){
  const labels=[...root.querySelectorAll('text')].filter(e=>e.textContent===name&&!e.closest('g.node,g.link'));
  if(labels.length!==1)continue;const label=labels[0],lb=box(label);const rects=[...root.querySelectorAll('rect')].filter(e=>!e.closest('g.node,g.link')&&contains(box(e),lb)).sort((a,b)=>box(a).w*box(a).h-box(b).w*box(b).h);
  if(!rects.length)continue;const rect=rects[0],rb=box(rect),parent=rect.parentElement,owned=[...parent.children].filter(e=>!['g','defs'].includes(e.localName)&&!e.closest('g.node,g.link')&&contains(rb,box(e))&&e.localName!=='ellipse');
  if(!owned.includes(rect)||!owned.includes(label))continue;const g=document.createElementNS(ns,'g');parent.insertBefore(g,owned[0]);for(const e of owned)g.appendChild(e);add(g,name,'cluster','unique_exact_label_enclosing_rect');issues.push({reason:'plantuml_unwrapped_state_container_requires_source_review',entity:name});
 }
 const boundary=(b,p)=>{let dx=Math.max(b.x-p.x,0,p.x-b.x-b.w),dy=Math.max(b.y-p.y,0,p.y-b.y-b.h);return dx||dy?Math.hypot(dx,dy):Math.min(p.x-b.x,b.x+b.w-p.x,p.y-b.y,b.y+b.h-p.y);};
 function roundShape(e){
  if(e.closest('g.node,g.link,defs'))return false;const b=box(e);if(Math.min(b.w,b.h)<5||Math.max(b.w,b.h)>40||b.w/b.h<.8||b.w/b.h>1.25)return false;
  if(['circle','ellipse'].includes(e.localName))return true;if(!['path','polygon'].includes(e.localName)||!e.getTotalLength)return false;
  const l=e.getTotalLength(),m=e.getScreenCTM();if(l<=0)return false;
  for(let i=0;i<40;i++){const p=e.getPointAtLength(l*i/40).matrixTransform(m),r=Math.hypot((p.x-b.x-b.w/2)/(b.w/2),(p.y-b.y-b.h/2)/(b.h/2));if(r<.82||r>1.18)return false;}return true;
 }
 for(const name of missing.filter(n=>n.startsWith('.start.')||n.startsWith('.end.'))){
  const circles=[];for(const e of root.querySelectorAll('ellipse,circle,polygon,path'))if(roundShape(e)){
   const b=box(e),cx=b.x+b.w/2,cy=b.y+b.h/2;let c=circles.find(c=>Math.hypot(c.cx-cx,c.cy-cy)<.6);if(c){c.elements.push(e);if(b.w*b.h>c.b.w*c.b.h)c.b=b;}else circles.push({cx,cy,b,elements:[e]});
  }
  const options=[];for(const c of circles){let scores=[];for(const link of links){let side=link.getAttribute('data-entity-1')===name?0:link.getAttribute('data-entity-2')===name?1:null;if(side===null)continue;let path=link.querySelector('path');if(!path)continue;let m=path.getScreenCTM(),pts=[path.getPointAtLength(0).matrixTransform(m),path.getPointAtLength(path.getTotalLength()).matrixTransform(m)],other=resolve(link.getAttribute(side===0?'data-entity-2':'data-entity-1'));let candidates=pts.map((pt,i)=>({d:boundary(c.b,pt),other:other?boundary(box(other),pts[1-i]):0})).filter(x=>x.d<12);if(candidates.length)scores.push(Math.min(...candidates.map(x=>x.d+x.other)));}
   if(scores.length)options.push({circle:c,d:Math.min(...scores)});
  }
  options.sort((a,b)=>a.d-b.d);if(!options.length||(options.length>1&&options[1].d-options[0].d<1))continue;
  const c=options[0].circle,parents=new Set(c.elements.map(e=>e.parentElement));if(parents.size!==1)continue;let g=document.createElementNS(ns,'g');c.elements[0].parentElement.insertBefore(g,c.elements[0]);for(const e of c.elements)g.appendChild(e);const record=add(g,name,'entity','engine_terminal_name_unique_endpoint_round_shape');record.concentricPrimitiveCount=c.elements.length;issues.push({reason:'plantuml_initial_final_circle_binding_requires_source_review',entity:name,primitives:c.elements.length});
 }
 const edgeRecords=[];
 for(const link of links){const names=[link.getAttribute('data-entity-1'),link.getAttribute('data-entity-2')],nodes=names.map(resolve),paths=[...link.querySelectorAll(':scope > path')].filter(e=>getComputedStyle(e).fill==='none');let record={originalId:link.id,sourceLine:link.getAttribute('data-source-line'),entities:names};
  if(nodes.some(x=>!x)||paths.length!==1){issues.push({reason:'plantuml_link_metadata_unresolved',...record,pathCount:paths.length});continue;}
  const path=paths[0],m=path.getScreenCTM(),ends=[path.getPointAtLength(0).matrixTransform(m),path.getPointAtLength(path.getTotalLength()).matrixTransform(m)],bb=nodes.map(box);let forward=boundary(bb[0],ends[0])+boundary(bb[1],ends[1]),reverse=boundary(bb[1],ends[0])+boundary(bb[0],ends[1]);if(reverse+1<forward)nodes.reverse();
  const title=document.createElementNS(ns,'title');title.textContent=nodes.map(e=>e.id).join('->');link.insertBefore(title,link.firstChild);link.classList.add('edge');record.nodeIds=nodes.map(e=>e.id);record.orientationReversed=reverse+1<forward;edgeRecords.push(record);
 }
 const parents=[];for(const g of groups){let e=document.getElementById(g.uid),b=box(e),choices=groups.filter(x=>x.uid!==g.uid&&x.kind==='cluster'&&contains(box(document.getElementById(x.uid)),b)).sort((a,c)=>{let x=box(document.getElementById(a.uid)),y=box(document.getElementById(c.uid));return x.w*x.h-y.w*y.h;});if(choices.length){g.parent=choices[0].uid;parents.push({child:g.uid,parent:g.parent,method:'source_svg_unique_smallest_enclosing_cluster'});}g.bbox=b;}
 return {adapterVersion:'plantuml_dom_v2_round_terminals_and_polygon_states',diagramType:root.getAttribute('data-diagram-type'),groups,links:edgeRecords,parents,issues,expectedLinkCount:links.length};
}
