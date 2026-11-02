"""Source-only constrained native-classic fit to actual four SVG vertices.

Two native factory kinds are considered. A bounded deterministic convex norm
problem fits corresponding whole closed polygon segments, never raster pixels.
Its vertex correspondence is an analytic upper bound on both continuous
boundary distances; the independent verifier inspects actual native SVG paint.
"""
import math,re
POLICY='actual_four_source_vertices_constrained_native_classic_minimax_v1'

def polygon(obj):
 values=list(map(float,re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',obj.get('pointsAttr') or '')));a,b,c,d,e,f=obj['matrix'];points=[]
 if len(values)%2:raise ValueError('odd_source_polygon_coordinates')
 for x,y in zip(values[::2],values[1::2]):
  point=(a*x+c*y+e,b*x+d*y+f)
  if not points or math.dist(point,points[-1])>1e-8:points.append(point)
 if len(points)>1 and math.dist(points[0],points[-1])<1e-8:points.pop()
 return points

def correspondence_upper(source,native):
 """Analytic upper bound for every point of every closed line segment.

For matched oriented edges, linear interpolation of endpoint displacements has
norm at most their maximum by convexity. Every point on both polygons has this
corresponding point, including concave notch edges and the closing edge.
"""
 if len(source)!=len(native) or len(source)<3:raise ValueError('closed_polygon_correspondence_arity_changed')
 candidates=[]
 for reverse in (False,True):
  ordered=list(reversed(native)) if reverse else list(native)
  for shift in range(len(ordered)):
   paired=ordered[shift:]+ordered[:shift];errors=[math.dist(a,b) for a,b in zip(source,paired)];candidates.append((max(errors),reverse,shift,errors))
 upper,reverse,shift,errors=min(candidates)
 return {'upper_bound_px':upper,'matched_vertex_distances_px':errors,'reverse':reverse,'cyclic_shift':shift,'whole_closed_segments_proven':True,'method':'convex_norm_of_linear_interpolation_on_every_corresponding_closed_segment','is_upper_bound_not_discrete_hausdorff':True}

def classic(obj,points,side,diagnostic=None):
 import numpy as np
 from scipy.optimize import minimize
 poly=polygon(obj)
 if len(poly)!=4:return None
 end,near=(points[-1],points[-2]) if side=='end' else (points[0],points[1]);outward=np.array(end)-near;norm=np.linalg.norm(outward)
 if norm<1e-6:return None
 outward=outward/norm;tip=np.array(max(poly,key=lambda p:np.dot(p,outward)));normal=np.array([-outward[1],outward[0]]);left=np.array(max(poly,key=lambda p:np.dot(np.array(p)-tip,normal)));right=np.array(min(poly,key=lambda p:np.dot(np.array(p)-tip,normal)));mid=(left+right)/2;u=tip-mid;length=float(np.linalg.norm(u));width=float(np.linalg.norm(left-right))
 if min(length,width)<.5:return None
 u=u/length;v=np.array([-u[1],u[0]])
 if np.dot(u,outward)<.97:return None
 # The actual concave notch is read, not replaced by an ideal 5/9 depth.
 others=[np.array(p) for p in poly if min(np.linalg.norm(np.array(p)-q) for q in (tip,left,right))>1e-6]
 if len(others)!=1:return None
 notch=others[0];depth=float(np.dot(tip-notch,u));lateral=float(np.dot(notch-tip,v))
 if not .25*length<depth<.9*length or abs(lateral)>.1*width:return None
 # Source cyclic order must really be tip -> base -> concave notch -> base.
 expected=[tip,left,notch,right]
 if correspondence_upper(poly,[tuple(p) for p in expected])['upper_bound_px']>1e-6:return None
 source=np.array([[np.dot(p-tip,u),np.dot(p-tip,v)] for p in expected]);candidates=[];tip_limit=min(1.,.15*length)
 for kind,ratio in (('classic',1.),('classicThin',2/3)):
  low=max(.8*length,.8*width/ratio,.2);high=min(1.2*length,1.2*width/ratio)
  if low>=high:continue
  # z=(native depth, along-tip shift, normal-tip shift, maximum error).
  matrices=np.array([[[0,1,0],[0,0,1]],[[-1,1,0],[ratio/2,0,1]],[[-.75,1,0],[0,0,1]],[[-1,1,0],[-ratio/2,0,1]]],float)
  def errors(z):return np.linalg.norm(np.einsum('ijk,k->ij',matrices,z[:3])-source,axis=1)
  def constraints(z):return np.r_[z[3]-errors(z),tip_limit-np.hypot(z[1],z[2])]
  def jacobian(z):
   diff=np.einsum('ijk,k->ij',matrices,z[:3])-source;n=np.linalg.norm(diff,axis=1);j=np.zeros((5,4));j[:4,3]=1
   for i in range(4):
    if n[i]>1e-14:j[i,:3]=-diff[i]@matrices[i]/n[i]
   r=np.hypot(z[1],z[2])
   if r>1e-14:j[4,1:3]=-z[1:3]/r
   return j
  initial=np.array([min(high,max(low,(length+depth)/1.75)),0.,0.,0.]);initial[3]=max(errors(initial))+1e-6
  solved=minimize(lambda z:z[3],initial,jac=lambda z:np.array([0.,0.,0.,1.]),bounds=[(low,high),(-tip_limit,tip_limit),(-tip_limit,tip_limit),(0.,2*length)],constraints=[{'type':'ineq','fun':constraints,'jac':jacobian}],method='SLSQP',options={'maxiter':150,'ftol':1e-11,'disp':False})
  if not solved.success or min(constraints(solved.x))< -1e-7 or not np.isfinite(solved.x).all():continue
  paint=obj.get('original_computed_paint');paint_proof=None;paint_fit=None
  if paint:
   from plantuml_marker_closed_paint_v1 import outline,certificate as closed_certificate
   a,b,c,d,_,_=obj['matrix'];stroke=float(paint['strokeWidth'])*math.sqrt(abs(a*d-b*c));source_outline=outline(poly,stroke,paint['linejoin'],paint['miterlimit'])
   def sampled(vertices,step=.08):
    return np.array([((1-t)*np.array(a)+t*np.array(b)) for a,b in zip(vertices,vertices[1:]+vertices[:1]) for t in np.linspace(0,1,max(2,math.ceil(math.dist(a,b)/step)))])
   source_samples=sampled(source_outline)
   def distances(samples,vertices):
    starts=np.array(vertices);ends=np.roll(starts,-1,axis=0);delta=ends-starts;relative=samples[:,None,:]-starts[None,:,:];fraction=np.clip(np.sum(relative*delta,axis=2)/np.maximum(np.sum(delta*delta,axis=1),1e-20),0,1);nearest=starts[None,:,:]+fraction[:,:,None]*delta[None,:,:];return np.sqrt(np.sum((samples[:,None,:]-nearest)**2,axis=2)).min(axis=1)
   def native_polygon(z):return [tuple(tip+p[0]*u+p[1]*v) for p in np.einsum('ijk,k->ij',matrices,z)]
   def objective(z):
    native_outline=outline(native_polygon(z),stroke,paint['linejoin'],paint['miterlimit']);error=max(float(distances(source_samples,native_outline).max()),float(distances(sampled(native_outline),source_outline).max()));return error+100*max(0,math.hypot(z[1],z[2])-tip_limit)
   refined=minimize(objective,solved.x[:3],method='Powell',bounds=[(low,high),(-tip_limit,tip_limit),(-tip_limit,tip_limit)],options={'maxiter':100,'maxfev':1500,'xtol':1e-7,'ftol':1e-9})
   if diagnostic is not None:diagnostic.append({'kind':kind,'refined_success':bool(refined.success),'message':str(refined.message),'point':refined.x.tolist(),'objective':float(refined.fun)})
   # A finite proposal need not prove numerical optimality. A returned bounded
   # point is usable only if its entire visible paint independently certifies.
   if not np.isfinite(refined.x).all() or math.hypot(refined.x[1],refined.x[2])>tip_limit+1e-7:continue
   solved.x[:3]=refined.x;paint_proof=closed_certificate(source_outline,outline(native_polygon(refined.x),stroke,paint['linejoin'],paint['miterlimit']))
   if diagnostic is not None:diagnostic[-1]['paint_certificate']=paint_proof
   if not paint_proof['ok']:continue
   paint_fit={'source_only':True,'raster_inputs':False,'objective':'bidirectional_source_opaque_fill_and_SVG_stroke_outline_distance','samples_maximum_step_px':.08,'function_evaluations':int(refined.nfev),'optimizer_converged':bool(refined.success),'optimizer_message':str(refined.message),'finite_proposal_certified_without_optimality_claim':True,'predicted_full_paint_certificate':paint_proof}
  native_depth,along,normal=map(float,solved.x[:3]);physical=tip+along*u+normal*v;native_local=np.einsum('ijk,k->ij',matrices,solved.x[:3]);native_world=[tuple(tip+p[0]*u+p[1]*v) for p in native_local];certificate=correspondence_upper(poly,native_world)
  if diagnostic is not None:diagnostic.append({'kind':kind,'center_line_correspondence':certificate})
  # SVG's visible marker is fill union stroke. A latent centerline notch can
  # differ by slightly more than one pixel while both complete visible paint
  # boundaries are closer. Keep that diagnostic; acceptance still requires the
  # independently measured full-paint certificate and the old PNG gates.
  if paint_proof is None and certificate['upper_bound_px']>1+1e-8:continue
  candidates.append({'tip':tuple(physical),'axis':tuple(u),'length':native_depth,'width':native_depth*ratio,'arrow':kind,'source_type':POLICY,'source_tip':tuple(tip),'source_length':length,'source_width':width,'source_notch_depth':depth,'source_notch_normal_offset':lateral,'source_four_vertices':[list(p) for p in poly],'tip_shift':{'along':along,'normal':normal,'limit':tip_limit},'geometric_fit_certificate':certificate,'solver':'SLSQP_convex_second_order_norm_constraints_no_raster_inputs','solver_iterations':int(solved.nit),'maximum_source_vertex_displacement_px':certificate['upper_bound_px'],'full_source_paint_fit':paint_fit,'contour_approximation':True})
 return min(candidates,key=lambda c:(c['maximum_source_vertex_displacement_px'],math.hypot(c['tip_shift']['along'],c['tip_shift']['normal']),c['arrow'])) if candidates else None
