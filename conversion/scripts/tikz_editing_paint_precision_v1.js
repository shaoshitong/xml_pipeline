(function(root){
  'use strict';
  const POLICY='SVG_DOMRect_binary32_corner_intervals_v1';
  const floor=1e-4,MAX_COORDINATE=2*8192;
  const halfUlp=v=>{const a=Math.abs(v);return a===0?Math.pow(2,-150):Math.pow(2,Math.max(-149,Math.floor(Math.log2(a))-23)-1);};
  function prove(before,after,offset){
    const observations=[];
    if(!before||!after||!offset)return {ok:false,policy:POLICY,reason:'missing_painted_corner_observation'};
    const points=r=>({left:r.x,right:r.x+r.width,top:r.y,bottom:r.y+r.height});
    const b=points(before),a=points(after);
    for(const key of ['left','right','top','bottom']){
      const axis=key==='left'||key==='right'?'x':'y',wanted=offset[axis];
      if(![a[key],b[key],wanted].every(Number.isFinite)||Math.max(Math.abs(a[key]),Math.abs(b[key]))>MAX_COORDINATE)return {ok:false,policy:POLICY,reason:'native_paint_coordinate_precision_outside_supported_canvas'};
      const roundoff=8*Number.EPSILON*Math.max(1,Math.abs(a[key]),Math.abs(b[key]),Math.abs(wanted));
      const interval=halfUlp(a[key])+halfUlp(b[key])+roundoff,bound=Math.max(floor,interval),actual=a[key]-b[key],error=Math.abs(actual-wanted);
      observations.push({corner:key,actual,expected:wanted,error,bound,binary32_interval:interval});
      if(error>bound)return {ok:false,policy:POLICY,reason:'painted_corner_did_not_follow_source_edit',observations};
    }
    return {ok:true,policy:POLICY,original_tolerance_floor_px:floor,source_canvas_bound_px:8192,observations};
  }
  const api=Object.freeze({policy:POLICY,prove,binary32HalfUlp:halfUlp});
  root.tikzEditingPaintPrecisionV1=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
