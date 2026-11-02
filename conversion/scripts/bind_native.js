xml=>{
 document.body.innerHTML='<div id="graph" style="width:8192px;height:8192px;position:relative"></div>';
 const container=document.getElementById('graph');const graph=new Graph(container);graph.setEnabled(false);const doc=mxUtils.parseXml(xml);const model=doc.getElementsByTagName('mxGraphModel')[0];new mxCodec(doc).decode(model,graph.getModel());graph.view.scaleAndTranslate(1,0,0);graph.view.validate();
 const states=Object.values(graph.model.cells).map(c=>graph.view.getState(c)).filter(Boolean),changes=[],unresolved=[];
 const nodes=states.filter(s=>s.cell.vertex&&s.width>3&&s.height>3&&s.style.shape!=='text'&&s.style.shape!=='line'&&s.style.strokeColor!=='none'&&s.style.opacity!==0);
 function candidate(p,edge){
  const choices=[];
  for(const s of nodes){if(s.cell.id===edge.id||graph.model.isAncestor(edge,s.cell))continue;
   const shape=s.style.shape;if(shape&&!['rectangle','swimlane','process','label'].includes(shape))continue;
   const dx=Math.max(s.x-p.x,0,p.x-s.x-s.width),dy=Math.max(s.y-p.y,0,p.y-s.y-s.height);let dist=dx||dy?Math.hypot(dx,dy):Math.min(p.x-s.x,s.x+s.width-p.x,p.y-s.y,s.y+s.height-p.y);
   if(dist<=1.25)choices.push({s,dist});
  }
  choices.sort((a,b)=>a.dist-b.dist);
  if(!choices.length||choices.length>1&&choices[1].dist-choices[0].dist<1)return null;
  return choices[0];
 }
 graph.model.beginUpdate();try{
  for(const state of states.filter(s=>s.cell.edge)){
   const edge=state.cell,points=state.absolutePoints;if(!points?.length)continue;
   for(const [source,p] of [[true,points[0]],[false,points.at(-1)]]){
    if(graph.model.getTerminal(edge,source)||!p)continue;const best=candidate(p,edge);
    if(!best){unresolved.push({edge:edge.id,terminal:source?'source':'target',point:{x:p.x,y:p.y}});continue;}
    const node=best.s,prefix=source?'exit':'entry',x=(p.x-node.x)/node.width,y=(p.y-node.y)/node.height;
    graph.model.setTerminal(edge,node.cell,source);let style=edge.style||'';for(const [key,value] of [[prefix+'X',x],[prefix+'Y',y],[prefix+'Perimeter',0],[prefix+'Dx',0],[prefix+'Dy',0]])style=mxUtils.setStyle(style,key,value);graph.model.setStyle(edge,style);changes.push({edge:edge.id,terminal:source?'source':'target',node:node.cell.id,anchor:{x,y},distance_to_rect_boundary:best.dist});
   }
  }
 }finally{graph.model.endUpdate();}
 const encoded=new mxCodec().encode(graph.model);const result={xml:mxUtils.getXml(encoded),changes,unresolved};graph.destroy();return result;
}
