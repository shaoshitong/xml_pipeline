"""Full opaque SVG fill+stroke outlines and certified continuous boundaries.

Miter and bevel joins are constructed as SVG specifies, including the complete
bevel when the miter limit is exceeded. No discrete Hausdorff value is promoted
to an upper bound; both complete closed perimeters use 1-Lipschitz intervals.
"""
import heapq,math
POLICY='opaque_closed_svg_paint_continuous_one_pixel_certificate_v1'

def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def area(p):return sum(cross(a,b) for a,b in zip(p,p[1:]+p[:1]))/2
def require(ok,reason):
 if not ok:raise ValueError(reason)

def simple(p):
 def turn(a,b,c):return cross((b[0]-a[0],b[1]-a[1]),(c[0]-a[0],c[1]-a[1]))
 n=len(p)
 for i,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
  for j,(c,d) in enumerate(zip(p,p[1:]+p[:1])):
   if j<=i or (j-i)%n in (1,n-1):continue
   if turn(a,b,c)*turn(a,b,d)<-1e-12 and turn(c,d,a)*turn(c,d,b)<-1e-12:return False
 return True

def outline(points,width,join='miter',miterlimit=4):
 points=list(map(tuple,points));require(len(points)>=3 and abs(area(points))>1e-8 and simple(points),'invalid_or_self_intersecting_source_paint_polygon');require(math.isfinite(width) and 0<=width<=16,'unsupported_source_marker_outline_width');require(join in ('miter','bevel') and math.isfinite(miterlimit) and miterlimit>=1,'unsupported_source_marker_join')
 if not width:return points
 orientation=1 if area(points)>0 else -1;r=width/2;result=[]
 for i,p in enumerate(points):
  before=points[i-1];after=points[(i+1)%len(points)];a=(p[0]-before[0],p[1]-before[1]);b=(after[0]-p[0],after[1]-p[1]);al=math.hypot(*a);bl=math.hypot(*b);require(min(al,bl)>1e-8,'degenerate_source_marker_outline_segment');a=(a[0]/al,a[1]/al);b=(b[0]/bl,b[1]/bl);na=(orientation*a[1],-orientation*a[0]);nb=(orientation*b[1],-orientation*b[0]);pa=(p[0]+r*na[0],p[1]+r*na[1]);pb=(p[0]+r*nb[0],p[1]+r*nb[1]);den=cross(a,b)
  if abs(den)<1e-10:
   require(a[0]*b[0]+a[1]*b[1]>0,'source_marker_outline_cusp');result.append(pa);continue
  t=cross((pb[0]-pa[0],pb[1]-pa[1]),b)/den;intersection=(pa[0]+t*a[0],pa[1]+t*a[1]);convex=den*orientation>0;ratio=math.dist(intersection,p)/r
  if convex and (join=='bevel' or ratio>miterlimit+1e-10):result.extend([pa,pb])
  else:result.append(intersection)
 require(simple(result) and abs(area(result))>=abs(area(points))-1e-8,'source_marker_stroke_offset_requires_boolean_union_frontend')
 return result

def distance(point,poly):
 best=float('inf')
 for a,b in zip(poly,poly[1:]+poly[:1]):
  dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy;t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/den)) if den else 0;best=min(best,math.dist(point,(a[0]+t*dx,a[1]+t*dy)))
 return best

def directed(source,target,limit=1.,maximum_intervals=20000):
 heap=[];serial=0;lower=0.;evaluations=0
 def push(a,b,da,db):
  nonlocal serial,lower
  lower=max(lower,da,db);upper=(da+db+math.dist(a,b))/2;heapq.heappush(heap,(-upper,serial,a,b,da,db));serial+=1
 for a,b in zip(source,source[1:]+source[:1]):
  da=distance(a,target);db=distance(b,target);evaluations+=2;push(a,b,da,db)
 while heap and serial<maximum_intervals:
  upper=-heap[0][0]
  if upper<=limit+1e-10:return {'ok':True,'lower_bound_px':lower,'upper_bound_px':upper,'evaluations':evaluations,'whole_closed_perimeter':True,'certificate':'one_lipschitz_segment_interval_upper_bound'}
  if lower>limit+1e-10:return {'ok':False,'lower_bound_px':lower,'upper_bound_px':upper,'evaluations':evaluations,'whole_closed_perimeter':True,'certificate':'actual_point_to_all_opposite_segments_exceeds_limit'}
  _,_,a,b,da,db=heapq.heappop(heap);mid=((a[0]+b[0])/2,(a[1]+b[1])/2);dm=distance(mid,target);evaluations+=1
  if math.dist(a,b)<1e-7:return {'ok':False,'lower_bound_px':max(lower,dm),'upper_bound_px':upper,'evaluations':evaluations,'whole_closed_perimeter':True,'certificate':'numerically_unresolved_boundary_not_accepted'}
  push(a,mid,da,dm);push(mid,b,dm,db)
 return {'ok':False,'lower_bound_px':lower,'upper_bound_px':-heap[0][0] if heap else lower,'evaluations':evaluations,'whole_closed_perimeter':True,'certificate':'finite_interval_budget_exhausted_not_accepted'}

def certificate(a,b,limit=1.):
 forward=directed(a,b,limit);backward=directed(b,a,limit)
 return {'ok':forward['ok'] and backward['ok'],'lower_bound_px':max(forward['lower_bound_px'],backward['lower_bound_px']),'upper_bound_px':max(forward['upper_bound_px'],backward['upper_bound_px']),'limit_px':limit,'source_to_native':forward,'native_to_source':backward,'policy':POLICY,'both_full_closed_paint_boundaries':True}
