async xml => {
  const fail = (reason, detail={}) => { throw new Error(reason+': '+JSON.stringify(detail)); };
  const finite=p=>p && Number.isFinite(p.x) && Number.isFinite(p.y);
  const close=(a,b,t=1e-6)=>Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=t;
  const point=p=>p?{x:p.x,y:p.y}:null;
  const samePoint=(a,b)=>finite(a)&&finite(b)&&close(a.x,b.x)&&close(a.y,b.y);
  document.body.innerHTML='<div id="native-editing-v4" style="width:8192px;height:8192px;position:relative"></div>';
  const g=new Graph(document.getElementById('native-editing-v4'));
  try {
    const doc=mxUtils.parseXml(xml),models=doc.getElementsByTagName('mxGraphModel');
    if(models.length!==1)fail('one_uncompressed_native_model_required');
    new mxCodec(doc).decode(models[0],g.model);
    g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();
    const cells=Object.values(g.model.cells),edges=cells.filter(c=>c.edge);
    if(cells.length>20000||edges.length>4096)fail('unsupported_native_editing_size',{cells:cells.length,edges:edges.length});
    const descendants=c=>(c.children||[]).flatMap(x=>[x,...descendants(x)]);
    const ancestor=(owner,c)=>{for(let p=c;p;p=g.model.getParent(p))if(p===owner)return true;return false;};
    const xmlModel=()=>mxUtils.getXml(new mxCodec().encode(g.model));
    const stateSnapshot=()=>Object.fromEntries(cells.map(c=>{
      const s=g.view.getState(c);
      return [c.id,s?{x:s.x,y:s.y,width:s.width,height:s.height,points:s.absolutePoints?.map(point)||null}:null];
    }));
    const baselineModel=xmlModel(),baselineStates=stateSnapshot();
    const sameStates=(before,after)=>{
      if(Object.keys(before).length!==Object.keys(after).length)return false;
      for(const id of Object.keys(before)){
        const a=before[id],b=after[id];if(!a||!b){if(a!==b)return false;continue;}
        for(const key of ['x','y','width','height'])if(!close(a[key],b[key]))return false;
        if(Boolean(a.points)!==Boolean(b.points)||a.points&&a.points.length!==b.points.length)return false;
        for(let i=0;i<(a.points||[]).length;i++)if(a.points[i]||b.points[i]){
          if(!samePoint(a.points[i],b.points[i]))return false;
        }
      }
      return true;
    };
    const end=(state,source)=>state.absolutePoints?.[source?0:state.absolutePoints.length-1];
    const visibleState=(edge,source)=>{
      const terminal=g.model.getTerminal(edge,source),state=g.view.getState(terminal),visible=g.view.getState(edge)?.getVisibleTerminalState(source);
      if(!terminal){const p=edge.geometry?.getTerminalPoint(source);if(!finite(p))fail('native_free_endpoint_missing_explicit_finite_source_geometry',{edge:edge.id,source});const portKey=source?mxConstants.STYLE_SOURCE_PORT:mxConstants.STYLE_TARGET_PORT;if(g.view.getState(edge)?.style?.[portKey])fail('native_free_endpoint_has_dangling_named_port',{edge:edge.id,source});return null;}
      if(!terminal||!terminal.vertex||!state||visible?.cell!==terminal)fail('unsupported_missing_hidden_or_collapsed_terminal',{edge:edge.id,side:source?'source':'target',terminal:terminal?.id});
      const portKey=source?mxConstants.STYLE_SOURCE_PORT:mxConstants.STYLE_TARGET_PORT;
      const portId=g.view.getState(edge).style[portKey];
      if(portId!=null&&portId!==''){
        const port=g.model.getCell(portId);
        if(!port||!port.vertex||!g.view.getState(port)||!ancestor(terminal,port))fail('native_port_not_owned_by_bound_terminal',{edge:edge.id,port:portId,terminal:terminal.id});
      }
      return state;
    };
    const endpointProof=(edge,source)=>{
      const state=g.view.getState(edge);
      if(!state||!finite(end(state,source))||!state.shape?.points?.length)fail('unsupported_edge_has_no_live_native_polyline',{edge:edge.id});
      const sourceState=visibleState(edge,true),targetState=visibleState(edge,false);
      // Start from a separate state with both terminal points invalidated. The
      // model waypoint geometry is rerouted before perimeter clipping. Reusing the
      // already clipped/shortened native path would feed a postprocessed path
      // back into clipping and incorrectly reject short orthogonal routes.
      const expectedState=state.clone();
      expectedState.absolutePoints=state.absolutePoints.map(p=>p?.clone()||null);
      g.view.updateFixedTerminalPoints(expectedState,sourceState,targetState);
      g.view.updatePoints(expectedState,edge.geometry?.points,sourceState,targetState);
      g.view.updateFloatingTerminalPoints(expectedState,sourceState,targetState);
      const actual=end(state,source),expected=end(expectedState,source),painted=end({absolutePoints:state.shape.points},source);
      if(!samePoint(actual,expected))fail('native_terminal_endpoint_differs_from_current_constraint_or_perimeter',{edge:edge.id,side:source?'source':'target',actual:point(actual),expected:point(expected)});
      if(!samePoint(actual,painted))fail('native_painted_endpoint_detached_from_routed_endpoint',{edge:edge.id,actual:point(actual),painted:point(painted)});
      const terminalState=source?sourceState:targetState;const constraint=terminalState?g.getConnectionConstraint(state,terminalState,source):null;
      return {actual:point(actual),expected:point(expected),painted:point(painted),mode:terminalState?(constraint?.point?'fixed_constraint':'floating_native_perimeter'):'free_native_coordinate',constraint:constraint?.point?{point:point(constraint.point),perimeter:constraint.perimeter,dx:constraint.dx||0,dy:constraint.dy||0}:null};
    };
    const position=c=>{const s=g.view.getState(c);return s?{id:c.id,x:s.x,y:s.y}:null;};
    const rigidVertices=owner=>descendants(owner).filter(c=>{
      if(!c.vertex||!g.view.getState(c))return false;
      for(let p=g.model.getParent(c);p&&p!==owner;p=g.model.getParent(p))if(p.edge)return false;
      return true;
    });
    const labelGroups=edge=>(edge.children||[]).filter(c=>c.vertex&&g.view.getState(c)).map(label=>{
      const members=[label,...descendants(label).filter(c=>c.vertex&&g.view.getState(c))];
      if(descendants(label).some(c=>c.edge))fail('unsupported_native_edge_nested_inside_compound_label',{edge:edge.id,label:label.id});
      return {label:label.id,members:members.map(position)};
    });
    const moves=[];
    for(const edge of edges)for(const source of [true,false]){
      const terminalState=visibleState(edge,source);
      if(!terminalState){
        const before=endpointProof(edge,source),original=edge.geometry.clone(),interventions=[];
        const key=source?'sourcePoint':'targetPoint',oldPoint=original.getTerminalPoint(source),labels=labelGroups(edge);
        for(const offset of [{x:17,y:11},{x:-13,y:19}]){
          const moved=original.clone();moved.setTerminalPoint(new mxPoint(oldPoint.x+offset.x,oldPoint.y+offset.y),source);
          const beforePaint=g.view.getState(edge).shape.node.innerHTML;
          g.model.beginUpdate();g.model.setGeometry(edge,moved);g.model.endUpdate();g.view.validate();
          const after=endpointProof(edge,source),delta={x:after.actual.x-before.actual.x,y:after.actual.y-before.actual.y};
          if(!close(delta.x,offset.x)||!close(delta.y,offset.y))fail('native_free_endpoint_did_not_follow_explicit_geometry',{edge:edge.id,source,offset,delta});
          if(g.view.getState(edge).shape.node.innerHTML===beforePaint)fail('native_free_endpoint_shaft_or_marker_paint_did_not_respond',{edge:edge.id,source});
          const labelDeltas=labels.map(group=>({label:group.label,members:group.members.map(c=>{const p=position(g.model.getCell(c.id));if(!p)fail('native_free_edge_label_member_disappeared',{id:c.id});return {id:c.id,x:p.x-c.x,y:p.y-c.y};})}));
          for(const group of labelDeltas)for(const member of group.members)if(!close(member.x,group.members[0].x)||!close(member.y,group.members[0].y))fail('native_free_edge_compound_label_members_move_independently',{edge:edge.id,label:group.label});
          g.model.beginUpdate();g.model.setGeometry(edge,original);g.model.endUpdate();g.view.validate();
          if(xmlModel()!==baselineModel||!sameStates(baselineStates,stateSnapshot()))fail('native_free_endpoint_restore_changed_model_or_state',{edge:edge.id,source});
          endpointProof(edge,source);if(g.view.getState(edge).shape.node.innerHTML!==beforePaint)fail('native_free_endpoint_actual_paint_not_restored',{edge:edge.id,source});interventions.push({offset,delta,before,after,child_deltas:[],label_member_deltas:labelDeltas,actual_native_paint_changed:true,actual_native_paint_restored:true,model_and_all_live_states_restored:true});
        }
        moves.push({edge:edge.id,side:source?'source':'target',terminal:null,moved_edge:edge.id,mode:'free_native_coordinate',explicit_geometry_point:point(oldPoint),interventions,ok:true});continue;
      }
      const terminal=terminalState.cell;
      let owner=terminal;
      while(owner.geometry?.relative){
        const parent=g.model.getParent(owner);
        if(!parent?.vertex)fail('unsupported_relative_terminal_without_movable_vertex_owner',{edge:edge.id,terminal:terminal.id});
        owner=parent;
      }
      if(!owner.geometry||!g.view.getState(owner))fail('native_terminal_has_no_movable_geometry',{edge:edge.id,terminal:terminal.id});
      const before=endpointProof(edge,source),original=owner.geometry.clone(),originalOwner=position(owner);
      const children=rigidVertices(owner).map(position),labels=labelGroups(edge),interventions=[];
      for(const offset of [{x:17,y:11},{x:-13,y:19}]){
        const moved=original.clone();moved.x+=offset.x;moved.y+=offset.y;
        g.model.beginUpdate();g.model.setGeometry(owner,moved);g.model.endUpdate();g.view.validate();
        if(g.model.getTerminal(edge,source)!==terminal)fail('native_terminal_identity_changed_during_move',{edge:edge.id});
        const currentOwner=position(owner);
        if(!close(currentOwner.x-originalOwner.x,offset.x)||!close(currentOwner.y-originalOwner.y,offset.y))fail('native_vertex_did_not_move_by_requested_physical_offset',{owner:owner.id,offset,actual:currentOwner,before:originalOwner});
        const after=endpointProof(edge,source),delta={x:after.actual.x-before.actual.x,y:after.actual.y-before.actual.y};
        const childDeltas=children.map(c=>{const p=position(g.model.getCell(c.id));if(!p)fail('native_owned_child_disappeared',{id:c.id});return {id:c.id,x:p.x-c.x,y:p.y-c.y};});
        for(const child of childDeltas)if(!close(child.x,offset.x)||!close(child.y,offset.y))fail('native_owned_child_did_not_follow_vertex',{owner:owner.id,child,offset});
        const labelDeltas=labels.map(group=>({label:group.label,members:group.members.map(c=>{const p=position(g.model.getCell(c.id));if(!p)fail('native_edge_label_member_disappeared',{id:c.id});return {id:c.id,x:p.x-c.x,y:p.y-c.y};})}));
        for(const group of labelDeltas)for(const member of group.members)if(!close(member.x,group.members[0].x)||!close(member.y,group.members[0].y))fail('native_compound_edge_label_members_move_independently',{edge:edge.id,label:group.label});
        g.model.beginUpdate();g.model.setGeometry(owner,original);g.model.endUpdate();g.view.validate();
        if(xmlModel()!==baselineModel||!sameStates(baselineStates,stateSnapshot()))fail('native_move_restore_changed_model_or_rendered_state',{edge:edge.id,side:source?'source':'target'});
        endpointProof(edge,source);
        interventions.push({offset,delta,before,after,child_deltas:childDeltas,label_member_deltas:labelDeltas,model_and_all_live_states_restored:true});
      }
      if(!interventions.some(x=>Math.abs(x.delta.x)>1e-6||Math.abs(x.delta.y)>1e-6))fail('native_endpoint_unaffected_by_two_terminal_interventions',{edge:edge.id,terminal:terminal.id});
      moves.push({edge:edge.id,terminal:terminal.id,moved_vertex:owner.id,side:source?'source':'target',mode:before.mode,interventions,ok:true});
    }
    const vertexMoves=[],vertices=cells.filter(c=>c.vertex&&g.view.getState(c));
    const paintedRects=c=>[c,...descendants(c)].flatMap(member=>{
      const state=g.view.getState(member),out=[];
      const color=v=>v&&v!=='none'&&v!=='transparent'&&!/rgba\([^)]*,\s*0\s*\)$/.test(v);
      for(const element of state?.shape?.node?.querySelectorAll('path,rect,circle,ellipse,polygon,polyline,line')||[]){
        const cs=getComputedStyle(element),opacity=Number(cs.opacity);
        if(cs.display==='none'||cs.visibility==='hidden'||!(opacity>0)||!(color(cs.fill)&&Number(cs.fillOpacity)>0||color(cs.stroke)&&Number(cs.strokeOpacity)>0&&parseFloat(cs.strokeWidth)>0))continue;
        const b=element.getBoundingClientRect();if(b.width||b.height)out.push({x:b.x,y:b.y,width:b.width,height:b.height});
      }
      // A draw.io foreignObject wrapper may span the whole graph viewport.
      // Actual logical glyph ranges, rather than that nonpainting wrapper,
      // establish that every owned text run followed its edited vertex.
      if(state?.text?.node){const walker=document.createTreeWalker(state.text.node,NodeFilter.SHOW_TEXT);while(walker.nextNode()){
        const text=walker.currentNode;if(!text.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(text);
        for(const b of range.getClientRects())if(b.width&&b.height)out.push({x:b.x,y:b.y,width:b.width,height:b.height});
      }}
      return out;
    });
    for(const vertex of vertices){
      const original=vertex.geometry.clone(),interventions=[];
      for(const offset of [{x:17,y:11},{x:-13,y:19}]){
        const before=g.view.getState(vertex),position={x:before.x,y:before.y},paint=paintedRects(vertex),changed=original.clone();
        if(changed.relative){changed.offset=changed.offset?.clone()||new mxPoint();changed.offset.x+=offset.x;changed.offset.y+=offset.y;}
        else{changed.x+=offset.x;changed.y+=offset.y;}
        g.model.setGeometry(vertex,changed);g.view.validate();
        const after=g.view.getState(vertex),paintAfter=paintedRects(vertex),delta={x:after.x-position.x,y:after.y-position.y};
        if(!close(after.x-position.x,offset.x)||!close(after.y-position.y,offset.y))fail('tikz_vertex_did_not_follow_actual_native_edit',{cell:vertex.id,offset});
        if(paint.length!==paintAfter.length)fail('tikz_vertex_edit_changed_paint_object_count',{cell:vertex.id});
        for(let i=0;i<paint.length;i++)if(!close(paintAfter[i].x-paint[i].x,offset.x,1e-4)||!close(paintAfter[i].y-paint[i].y,offset.y,1e-4)||!close(paintAfter[i].width,paint[i].width,1e-4)||!close(paintAfter[i].height,paint[i].height,1e-4))fail('tikz_actual_vertex_paint_or_owned_glyphs_did_not_follow',{cell:vertex.id,offset,member:i,before:paint[i],after:paintAfter[i],observed:{x:paintAfter[i].x-paint[i].x,y:paintAfter[i].y-paint[i].y,width:paintAfter[i].width-paint[i].width,height:paintAfter[i].height-paint[i].height}});
        g.model.setGeometry(vertex,original.clone());g.view.validate();
        if(xmlModel()!==baselineModel||!sameStates(baselineStates,stateSnapshot()))fail('tikz_vertex_edit_did_not_restore_entire_model_and_states',{cell:vertex.id});
        interventions.push({offset,actual_native_vertex_delta:delta,painted_members:paint.length,actual_native_paint_followed:true,model_and_all_live_states_restored:true});
      }
      vertexMoves.push({cell:vertex.id,interventions,ok:true});
    }
    return {ok:true,edge_count:edges.length,moves,vertex_count:vertices.length,vertex_moves:vertexMoves,interventions_per_terminal:2,model_and_all_live_states_restored:true,scope:'Complete PGF/PDF source verified separately; every native vertex and both bound/free connector sides undergo two actual edits and restoration.'};
  } finally {g.destroy();}
}
