"""Prove author-backend raster colorbars as independent source components."""
import base64,collections,hashlib,math
import numpy as np
sha=lambda b:hashlib.sha256(b).hexdigest()
def prove(scene,dom,registration):
 images=[o for o in dom['objects'] if o['type']=='image'];axesimages={a['gid'] for a in scene['artists'] if a.get('role')=='source_image'};result=[];obs={r['format']:r for r in scene['actual_source_export_settings'].get('backend_export_observations',[])}
 for image in images:
  if image.get('artist_gid') in axesimages:continue
  gid=image.get('artist_gid');proof={'source_svg_object':image['id'],'source_Axes_GID':gid,'ok':False,'component_origin':'Matplotlib_backend_rasterized_colorbar','editable_scope':'independent image component; palette cells are not individually editable','full_original_QuadMesh_data_retained':True}
  try:
   if sum(o.get('artist_gid')==gid for o in images)!=1:raise ValueError('multiple_raster_components_in_same_axes')
   candidates=[a for a in scene['artists'] if a.get('axes_gid')==gid and a.get('role')=='collection'];meshes=[a for a in candidates if a['artist_class']=='QuadMesh'];other_nonempty=[a for a in candidates if a['artist_class']!='QuadMesh' and (a.get('paths') or int(np.prod((a.get('color_array') or {}).get('shape',[0]))))]
   if len(meshes)!=1 or other_nonempty:raise ValueError('unique_recorded_colorbar_QuadMesh_not_proven')
   mesh=meshes[0];owner=mesh.get('actual_colorbar_owner') or {};norm=mesh.get('actual_norm') or {}
   if not owner.get('is_Colorbar_solids') or owner.get('axes_gid')!=gid or owner.get('class')!='matplotlib.colorbar.Colorbar':raise ValueError('actual_Colorbar_owner_not_recorded')
   if norm.get('class')!='matplotlib.colors.Normalize' or not all(isinstance(norm.get(k),(int,float)) and math.isfinite(norm[k]) for k in ['vmin','vmax']):raise ValueError('nonlinear_or_unknown_colorbar_norm_typed_pending')
   n=len(mesh['paths'])
   if n<2 or mesh['facecolors']['shape']!=[n,4] or (mesh.get('color_array') or {}).get('shape') not in [[n],[n,1]] or any(p['vertices']['shape']!=[5,2] for p in mesh['paths']):raise ValueError('complete_colorbar_path_RGBA_data_shape_mismatch')
   if set(obs)!={'svg','png'}:raise ValueError('actual_backend_draw_not_recorded')
   svgaxes=[a for a in obs['svg']['actual_draws'][-1]['axes'] if a['gid']==gid];aggaxes=[a for a in obs['png']['actual_draws'][-1]['axes'] if a['gid']==gid]
   if len(svgaxes)!=1 or len(aggaxes)!=1:raise ValueError('source_colorbar_axes_GID_not_unique')
   x,y,w,h=svgaxes[0]['bbox_pixel_bounds'];scale,_,_,_,tx,ty=registration['SVG_to_Agg_affine'];svg_height=registration['actual_backend_bbox_inches']['svg'][3]*72;expected=[x*scale+tx,(svg_height-y-h)*scale+ty,w*scale,h*scale];actual=[image['bbox'][k] for k in ['x','y','w','h']]
   if max(abs(a-b) for a,b in zip(actual,expected))>1.1 or max(w,h)/max(1e-9,min(w,h))<8:raise ValueError('source_image_not_narrow_actual_colorbar_axes_bbox')
   head,payload=image['href'].split(',',1)
   if ';base64' not in head or not head.startswith('data:image/png'):raise ValueError('colorbar_is_not_embedded_source_PNG')
   proof.update(ok=True,unique_QuadMesh_GID=mesh['gid'],source_QuadMesh_path_count=n,source_QuadMesh_RGBA_shape=mesh['facecolors']['shape'],source_QuadMesh_data_shape=mesh['color_array']['shape'],source_QuadMesh_norm=norm,source_Colorbar_owner=owner,actual_source_SVG_Axes=svgaxes[0],actual_source_Agg_Axes=aggaxes[0],actual_source_bbox_in_registered_Agg_frame=expected,source_SVG_image_bbox=actual,source_embedded_PNG_sha256=sha(base64.b64decode(payload)),source_image_href_sha256=sha(image['href'].encode()),complete_QuadMesh_record_sha256=sha(__import__('json').dumps(mesh,sort_keys=True).encode()),whole_plot_wrapper=False,transform_invented=False)
  except Exception as e:proof['typed_pending_reason']=str(e)
  result.append(proof)
 return result
