"""Register SVG coordinates to Agg using observed Matplotlib export bounds only."""
import math
import xml.etree.ElementTree as ET
def registration(scene,svg_bytes,png_size):
 settings=scene['actual_source_export_settings'];observations=settings.get('backend_export_observations',[]);by={r['format']:r for r in observations};width,height=png_size
 if observations:
  if set(by)!={'svg','png'}:raise ValueError('missing_actual_backend_export_observation')
  dpi=float(by['png']['resolved_export_dpi']);boxes={}
  for format in ['svg','png']:
   r=by[format];rows=r['bbox_adjustments'];full=r['full_figure_inches'];boxes[format]=rows[0]['bbox_inches_bounds'] if rows else [0,0,*full]
   if any(max(abs(float(a)-float(b)) for a,b in zip(x['bbox_inches_bounds'],boxes[format]))>1e-7 for x in rows):raise ValueError('backend_export_bbox_changes_with_rasterization')
  axes=[by[f]['actual_draws'][-1]['axes'] for f in ['svg','png']]
  if len(axes[0])!=len(axes[1]):raise ValueError('source_backend_axes_count_changed')
  for a,b in zip(*axes):
   if a['gid']!=b['gid'] or max(abs(float(x)-float(y)) for x,y in zip(a['position_figure_fraction_bounds'],b['position_figure_fraction_bounds']))>1e-6:raise ValueError('source_backend_layout_geometry_changed_requires_per_axes_contract')
  provenance='observed_official_matplotlib_adjust_bbox_and_actual_draw_axes'
 else:
  kwargs=settings['actual_source_savefig_kwargs'];rc=settings['rcParams_at_actual_savefig_call']
  if kwargs.get('bbox_inches',rc['savefig.bbox']):raise ValueError('legacy_tight_capture_missing_actual_backend_bbox_no_pixel_fit_or_source_reexecution')
  dpi=kwargs.get('dpi',rc['savefig.dpi']);dpi=float(settings['figure_DPI_at_call'] if dpi=='figure' else dpi);boxes={f:[0,0,*settings['figure_inches_at_call']] for f in ['svg','png']};provenance='source_declared_full_figure_inches_and_actual_export_DPI_no_tight_crop'
 if not math.isfinite(dpi) or dpi<=0:raise ValueError('invalid_actual_export_DPI')
 sx,sy,sw,sh=map(float,boxes['svg']);px,py,pw,ph=map(float,boxes['png']);root=ET.fromstring(svg_bytes);vb=list(map(float,root.get('viewBox').split()))
 if max(abs(vb[0]),abs(vb[1]),abs(vb[2]-sw*72),abs(vb[3]-sh*72))>2e-5:raise ValueError('actual_SVG_viewBox_not_observed_bbox_72pt_per_inch')
 if abs(width-pw*dpi)>1.01 or abs(height-ph*dpi)>1.01:raise ValueError('actual_Agg_pixels_not_observed_bbox_at_recorded_DPI')
 scale=dpi/72;tx=(sx-px)*dpi;ty=((py+ph)-(sy+sh))*dpi;view=[-tx/scale,-ty/scale,width/scale,height/scale]
 return {'provenance':provenance,'resolved_Agg_DPI':dpi,'actual_backend_bbox_inches':boxes,'SVG_to_Agg_affine':[scale,0,0,scale,tx,ty],'registered_viewBox':view,'preserveAspectRatio':'none','actual_Agg_size':[width,height],'source_geometry_or_data_changed':False,'pixel_fit':False}
