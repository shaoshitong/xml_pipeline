ast=>{
 const ns='http://www.w3.org/2000/svg',norm=s=>(s||'').replace(/<br\s*\/?\s*>/gi,' ').replace(/<[^>]*>/g,'').replace(/\s+/g,' ').trim();
 if(ast.type!=='flowchart-v2' && ast.type!=='flowchart')throw Error('Unsupported source diagram type '+ast.type);
 if(ast.groups?.length)throw Error('Source subgraph hierarchy needs separate adapter');
 const visible=e=>{if(!e)return '';const c=e.cloneNode(true);for(const b of c.querySelectorAll('br'))b.replaceWith(document.createTextNode(' '));return c.textContent;};
 const v=Object.fromEntries(Array.isArray(ast.vertices)?ast.vertices:Object.entries(ast.vertices));const nodeMap={},groups=[],links=[];
 const title=(g,s)=>{let t=document.createElementNS(ns,'title');t.textContent=s;g.insertBefore(t,g.firstChild)};
 for(const [id,item] of Object.entries(v)){
  const candidates=[...document.querySelectorAll('g.node')].filter(g=>g.getAttribute('data-id')===id);
  if(candidates.length!==1)throw Error('Ambiguous or missing node '+id);const g=candidates[0],uid='mn'+groups.length;nodeMap[id]=uid;title(g,uid);g.setAttribute('id',uid);groups.push({sourceId:id,uid,expectedText:norm(item.text||id),visibleText:norm(visible(g.querySelector('.label'))),bbox:g.getBoundingClientRect().toJSON()});
  if(groups.at(-1).expectedText!==groups.at(-1).visibleText)throw Error('Source node text mismatch '+id);
 }
 const paths=[...document.querySelectorAll('path.flowchart-link')],labels=[...document.querySelectorAll('g.edgeLabels > g.edgeLabel')];
 if(paths.length!==ast.edges.length)throw Error('Source edge count mismatch');
 let labelIndex=0;const nonempty=ast.edges.filter(e=>norm(e.text));if(labels.length!==paths.length&&labels.length!==nonempty.length)throw Error('Ambiguous source edge-label count '+labels.length);
 for(let i=0;i<paths.length;i++){
  const p=paths[i],e=ast.edges[i],uid='me'+i;
  if(!p.classList.contains('LS-'+e.start)||!p.classList.contains('LE-'+e.end))throw Error('Source edge order/identity mismatch '+i);
  const label=labels.length===paths.length?labels[i]:norm(e.text)?labels[labelIndex++]:null;
  if(norm(visible(label))!==norm(e.text))throw Error('Source edge label mismatch '+i);
  const g=document.createElementNS(ns,'g');g.setAttribute('class','edge');g.setAttribute('id',uid);g.dataset.nativeEdgeId=uid;title(g,nodeMap[e.start]+'->'+nodeMap[e.end]);p.parentNode.insertBefore(g,p);g.appendChild(p);
  if(label){label.classList.add('edge');label.dataset.nativeEdgeId=uid;title(label,nodeMap[e.start]+'->'+nodeMap[e.end]);}
  links.push({uid,source:e.start,target:e.end,sourceUid:nodeMap[e.start],targetUid:nodeMap[e.end],text:norm(e.text),type:e.type});
 }
 return {groups,links,nodeMap,sourceType:ast.type};
}
