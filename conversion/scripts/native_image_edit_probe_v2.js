async p => {
 const fail=(r,d={})=>{throw Error(r+': '+JSON.stringify(d))};
 const close=(a,b)=>Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=.03;
 const tick=async()=>{await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))};
 if(p.action==='init'){
  if(window.__sourceImageProbe)fail('native_image_probe_already_initialized');
  document.body.style.margin='0';document.body.style.background='white';document.body.innerHTML='<div id="source-image-probe" style="position:relative;background:white;width:'+p.width+'px;height:'+p.height+'px;overflow:hidden"></div>';
  const g=new Graph(document.getElementById('source-image-probe'));g.setEnabled(true);g.setPanning(false);g.view.setScale(1);g.view.setTranslate(0,0);
  const doc=mxUtils.parseXml(p.xml),models=doc.getElementsByTagName('mxGraphModel');if(models.length!==1)fail('native_image_one_model_required');
  for(const item of (models[0].getAttribute('extFonts')||'').split('|')){
   if(!item)continue;const sep=item.indexOf('^');if(sep<1)fail('native_image_invalid_embedded_font_declaration');const family=item.slice(0,sep),uri=item.slice(sep+1);if(!uri.startsWith('data:'))fail('native_image_external_font_not_allowed');const face=new FontFace(family,'url("'+uri+'")');await face.load();document.fonts.add(face);
  }
  new mxCodec(doc).decode(models[0],g.model);g.view.validate();await tick();g.refresh();g.view.validate();
  const encode=()=>mxUtils.getXml(new mxCodec().encode(g.model));
  const allStates=()=>Object.fromEntries(Object.values(g.model.cells).map(c=>{const s=g.view.getState(c);return[c.id,s?{x:s.x,y:s.y,w:s.width,h:s.height,absolutePoints:s.absolutePoints?.map(p=>p?[p.x,p.y]:null)||null,shapePoints:s.shape?.points?.map(p=>p?[p.x,p.y]:null)||null}:null]}));
  const inspect=(id,uri=false)=>{
   const c=g.model.getCell(id),s=g.view.getState(c);if(!c?.vertex||!s?.shape)fail('native_image_missing_live_vertex',{id});if(!g.isCellMovable(c))fail('native_image_individual_vertex_not_movable',{id});
   const st=g.getCellStyle(c);if(st.shape!=='image'||String(st.imageAspect)!=='0')fail('native_image_actual_shape_or_aspect_changed',{id});
   const nodes=[...(s.shape.node?.querySelectorAll('image')||[])];if(s.shape.node?.localName==='image')nodes.unshift(s.shape.node);if(nodes.length!==1)fail('native_image_requires_one_actual_image_painter',{id,nodes:nodes.length});const node=nodes[0],b=node.getBoundingClientRect(),container=g.container.getBoundingClientRect();let opacity=1;for(let e=node;e&&e!==g.container;e=e.parentElement){const v=Number(getComputedStyle(e).opacity);if(Number.isFinite(v))opacity*=v;}
   const href=node.getAttribute('href')||node.getAttributeNS('http://www.w3.org/1999/xlink','href')||'';if(!href.startsWith('data:image/'))fail('native_image_actual_uri_not_embedded',{id});
   const row={id,model_geometry:{x:c.geometry.x,y:c.geometry.y,w:c.geometry.width,h:c.geometry.height},state:{x:s.x,y:s.y,w:s.width,h:s.height},painted_rect:{x:b.x-container.x,y:b.y-container.y,w:b.width,h:b.height},opacity,screen_offset:s.shape.getSvgScreenOffset?.()??null,movable:g.isCellMovable(c),image_uri_unchanged:href===window.__sourceImageProbe?.uris[id]};if(uri)row.actual_image_uri=href;return row;
  };
  const state={g,encode,allStates,inspect,baselineModel:encode(),baselineStates:allStates(),uris:{},saved:{},expected:p.expected};window.__sourceImageProbe=state;
  const observations=[];
  for(const e of p.expected){
   const r=inspect(e.native_cell_id,true);state.uris[e.native_cell_id]=r.actual_image_uri;r.image_uri_unchanged=true;
   // Load the actual painter's URI independently; a header-only or broken image
   // node is not accepted as proof of rendered source media.
   const im=new Image();im.src=r.actual_image_uri;try{await im.decode()}catch(error){fail('native_image_actual_asset_failed_to_decode',{id:e.native_cell_id})};r.actual_intrinsic_size=[im.naturalWidth,im.naturalHeight];
   for(const key of ['x','y','w','h'])if(!close(r.state[key],e.paint_rect[key])||!close(r.painted_rect[key],e.paint_rect[key]))fail('native_image_actual_paint_rectangle_mismatch',{id:e.native_cell_id,key,observed:r.painted_rect[key],expected:e.paint_rect[key]});
   if(!close(r.opacity,e.opacity))fail('native_image_actual_opacity_mismatch',{id:e.native_cell_id});observations.push(r);
  }
  await tick();{g.refresh();g.view.validate();await tick();state.baselineModel=encode();state.baselineStates=allStates();}
  const finalObservations=p.expected.map(e=>{const r=inspect(e.native_cell_id,true);if(!r.image_uri_unchanged)fail('native_image_asset_changed_during_full_refresh',{id:e.native_cell_id});r.actual_intrinsic_size=observations.find(x=>x.id===e.native_cell_id).actual_intrinsic_size;return r;});return {ok:true,runtime_version:typeof mxClient!=='undefined'?mxClient.VERSION:null,images:finalObservations,model_and_live_states_restored:true};
 }
 const s=window.__sourceImageProbe;if(!s)fail('native_image_probe_not_initialized');const g=s.g;
 if(p.action==='move'){
  const c=g.model.getCell(p.id);if(!c?.geometry||s.saved[p.id])fail('native_image_mutation_owner_invalid',{id:p.id});const before=s.inspect(p.id);s.saved[p.id]=c.geometry.clone();const geo=c.geometry.clone();geo.x+=17;geo.y+=11;g.model.beginUpdate();try{g.model.setGeometry(c,geo)}finally{g.model.endUpdate()}g.view.validate();{g.refresh();g.view.validate();}await tick();const after=s.inspect(p.id);for(const k of ['x','y']){const delta=after.state[k]-before.state[k],paintDelta=after.painted_rect[k]-before.painted_rect[k];if(!close(delta,k==='x'?17:11)||!close(paintDelta,k==='x'?17:11))fail('native_image_actual_geometry_or_paint_did_not_follow',{id:p.id,k,delta,paintDelta});}if(!after.image_uri_unchanged)fail('native_image_asset_changed_during_geometry_mutation');return {ok:true,id:p.id,offset:{x:17,y:11},before,after};
 }
 if(p.action==='restore'){
  const c=g.model.getCell(p.id),geo=s.saved[p.id];if(!geo)fail('native_image_restore_without_saved_geometry');g.model.beginUpdate();try{g.model.setGeometry(c,geo)}finally{g.model.endUpdate()}delete s.saved[p.id];g.view.validate();{g.refresh();g.view.validate();}await tick();const exactModel=s.encode()===s.baselineModel,exactStates=JSON.stringify(s.allStates())===JSON.stringify(s.baselineStates);if(!exactModel||!exactStates)fail('native_image_model_or_all_states_not_restored',{exactModel,exactStates});return {ok:true,id:p.id,model_exactly_restored:exactModel,all_live_states_exactly_restored:exactStates,restored:s.inspect(p.id)};
 }
 if(p.action==='snapshot'){
  const owner=new WeakMap();for(const c of Object.values(g.model.cells)){const st=g.view.getState(c);if(st?.shape?.node)owner.set(st.shape.node,c.id+':shape');if(st?.text?.node)owner.set(st.text.node,c.id+':text');}
  const own=n=>{for(let q=n;q;q=q.parentElement)if(owner.has(q))return owner.get(q);return null;};
  if(!s.nodeIds){s.nodeIds=new WeakMap();s.nodeSerial=0;}const uid=n=>{if(!n)return null;if(!s.nodeIds.has(n))s.nodeIds.set(n,++s.nodeSerial);return s.nodeIds.get(n);};
  const svg=g.container.querySelector('svg');const nodes=svg?[svg,...svg.querySelectorAll('*')]:[];
  const dom=nodes.map((n,index)=>({index,uid:uid(n),parentUid:uid(n.parentElement),nextUid:uid(n.nextElementSibling),tag:n.localName,owner:own(n),attrs:[...n.attributes].map(a=>[a.name,a.value]),children:[...n.children].map(x=>uid(x))}));
  return {model:s.encode(),states:s.allStates(),svgOuterHTML:svg?.outerHTML||'',dom,paintOrder:nodes.filter(n=>!n.closest('defs')&&['path','rect','ellipse','circle','polygon','polyline','line','image','text','foreignObject'].includes(n.localName)).map(n=>({uid:uid(n),owner:own(n),tag:n.localName,d:n.getAttribute('d'),transform:n.getAttribute('transform'),fill:n.getAttribute('fill'),stroke:n.getAttribute('stroke')}))};
 }
 if(p.action==='dispose'){g.destroy();delete window.__sourceImageProbe;return {ok:true};}
 fail('native_image_unknown_probe_action');
}
