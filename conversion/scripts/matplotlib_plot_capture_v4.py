"""Executed only inside the existing bwrap source sandbox."""
from pathlib import Path
import collections,hashlib,json,sys,traceback,random
import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib._tight_bbox as mpl_tight_bbox
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.collections import Collection
from matplotlib.image import AxesImage
from matplotlib.patches import Patch
from matplotlib.backends.backend_svg import RendererSVG
from matplotlib import font_manager
root=Path('/work');captures=[];captured_figures=set();original=Figure.savefig;observed_svg_fonts={};observed_generators=[]
active_export=None
original_adjust_bbox=mpl_tight_bbox.adjust_bbox
def observed_adjust_bbox(fig,bbox_inches,fixed_dpi=None):
 if active_export is not None:
  active_export['bbox_adjustments'].append({'bbox_inches_bounds':list(bbox_inches.bounds),'fixed_dpi':fixed_dpi,'figure_dpi_at_adjust':fig.dpi})
 return original_adjust_bbox(fig,bbox_inches,fixed_dpi)
mpl_tight_bbox.adjust_bbox=observed_adjust_bbox
original_figure_draw=Figure.draw
def observed_figure_draw(fig,renderer):
 result=original_figure_draw(fig,renderer)
 if active_export is not None:
  active_export['actual_draws'].append({'renderer':type(renderer).__module__+'.'+type(renderer).__name__,'figure_dpi_at_draw':fig.dpi,'figure_bbox_pixel_bounds':list(fig.bbox.bounds),'axes':[{'index':i,'gid':ax.get_gid(),'position_figure_fraction_bounds':list(ax.get_position().bounds),'bbox_pixel_bounds':list(ax.bbox.bounds)} for i,ax in enumerate(fig.axes)]})
 return result
Figure.draw=observed_figure_draw
original_default_rng=np.random.default_rng
def observed_default_rng(seed=None):
 g=original_default_rng(seed);observed_generators.append({'generator':g,'seed_argument_type':type(seed).__name__,'seed_argument':seed if isinstance(seed,(int,str,type(None))) else '<nonprimitive>','before':g.bit_generator.state});return g
np.random.default_rng=observed_default_rng
def rng_state():
 n=np.random.get_state();p=random.getstate();return {'numpy_legacy':{'algorithm':n[0],'keys':n[1].tolist(),'position':n[2],'has_gaussian':n[3],'cached_gaussian':n[4]},'python_random':p,'independent_default_rng_generators':[{'seed_argument_type':r['seed_argument_type'],'seed_argument':r['seed_argument'],'before':r['before'],'after':r['generator'].bit_generator.state} for r in observed_generators]}
def font_record(fontpath,requested=()):
 p=Path(fontpath);blob=p.read_bytes();digest=hashlib.sha256(blob).hexdigest();dest=root/'fonts'/(digest+p.suffix);dest.parent.mkdir(exist_ok=True)
 if not dest.exists():dest.write_bytes(blob)
 r=observed_svg_fonts.setdefault(digest,{'file':str(dest.relative_to(root)),'sha256':digest,'resolved_runtime_path':str(p),'font_name':font_manager.FontProperties(fname=str(p)).get_name(),'requested_families':[],'actual_SVG_renderer_font_observation':True})
 r['requested_families']=sorted(set(r['requested_families'])|set(requested));return digest
glyph_path_events=[]
original_svg_text_path=RendererSVG._draw_text_as_path
def observed_svg_text_path(self,*args,**kwargs):
 glyph_path_events.append({'method':'RendererSVG._draw_text_as_path','text_sha256':hashlib.sha256(str(args[3]).encode()).hexdigest() if len(args)>3 else None});return original_svg_text_path(self,*args,**kwargs)
RendererSVG._draw_text_as_path=observed_svg_text_path
original_svg_text=RendererSVG._draw_text_as_text
def observed_svg_text(self,gc,x,y,text,prop,angle,ismath,mtext=None):
 if ismath:
  result=self._text2path.mathtext_parser.parse(text,72,prop)
  for font,fontsize,char,gx,gy in result.glyphs:font_record(font.fname)
 else:font_record(font_manager.findfont(prop,fallback_to_default=True),prop.get_family())
 return original_svg_text(self,gc,x,y,text,prop,angle,ismath,mtext)
RendererSVG._draw_text_as_text=observed_svg_text
sha=lambda b:hashlib.sha256(b).hexdigest()
def json_exact(value):
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,np.ndarray):return value.tolist()
    raise TypeError('nonserializable_source_metadata:'+type(value).__name__)
def array(value):
    try:a=np.asarray(value)
    except ValueError:return {'sequence_length':len(value),'sequence_values':[array(v) for v in value],'all_values_retained':True}
    values=a.tolist()
    def plain(v):
        if isinstance(v,list):return [plain(x) for x in v]
        if isinstance(v,(str,int,float,bool,type(None))):return v
        if hasattr(v,'isoformat'):return {'python_type':type(v).__name__,'isoformat':v.isoformat()}
        return {'python_type':type(v).__name__,'representation':str(v)}
    out={'dtype':str(a.dtype),'shape':list(a.shape),'values':plain(values),'all_values_retained':True}
    if np.ma.isMaskedArray(value):out['original_mask']=np.ma.getmaskarray(value).tolist()
    return out
def scene(fig):
    fig.canvas.draw();artists=[];fonts={};data_points=0
    for i,a in enumerate(fig.findobj()):
        gid='matplotlib_artist_'+str(i);old=a.get_gid();a.set_gid(gid);r={'gid':gid,'original_gid':old,'artist_class':type(a).__name__,'visible':a.get_visible()}
        if isinstance(a,Text) and a.get_text():
            text=a.get_text();font=Path(font_manager.findfont(a.get_fontproperties(),fallback_to_default=True));blob=font.read_bytes();digest=sha(blob);dest=root/'fonts'/(digest+font.suffix);dest.parent.mkdir(exist_ok=True)
            if not dest.exists():dest.write_bytes(blob)
            fonts[digest]={'file':str(dest.relative_to(root)),'sha256':digest,'resolved_runtime_path':str(font),'font_name':a.get_fontproperties().get_name()}
            r.update(role='text',text=text,font_sha256=digest,font_family=a.get_fontfamily(),font_size_points=a.get_fontsize(),rotation=a.get_rotation())
        elif isinstance(a,Line2D):
            path=a.get_path();path.should_simplify=False
            r.update(role='data_line' if a.axes is not None and a in a.axes.lines else 'tick_or_other_line',x_original=array(a.get_xdata(orig=True)),y_original=array(a.get_ydata(orig=True)),path_vertices=array(path.vertices),path_codes=array(path.codes) if path.codes is not None else None,marker=str(a.get_marker()),path_should_simplify=False)
            if r['role']=='data_line':data_points+=len(path.vertices)
        elif isinstance(a,Collection):
            paths=a.get_paths()
            for p in paths:p.should_simplify=False
            r.update(role='collection',paths=[{'vertices':array(p.vertices),'codes':array(p.codes) if p.codes is not None else None} for p in paths],offsets=array(a.get_offsets()),sizes=array(a.get_sizes()) if hasattr(a,'get_sizes') else None)
            r['color_array']=array(a.get_array()) if a.get_array() is not None else None;r['facecolors']=array(a.get_facecolors());r['edgecolors']=array(a.get_edgecolors());r['linewidths']=array(a.get_linewidths());r['specialized_data_arrays']={name:array(getattr(a,name)) for name in ['U','V','u','v','Umask','levels','allsegs','allkinds'] if hasattr(a,name)}
            data_points+=sum(len(p.vertices) for p in paths)+len(a.get_offsets())
        elif isinstance(a,Patch):
            path=a.get_path();path.should_simplify=False;r.update(role='patch',data_patch=bool(a.axes is not None and a in a.axes.patches),path_vertices=array(path.vertices),path_codes=array(path.codes) if path.codes is not None else None,affine_matrix=a.get_transform().get_matrix().tolist(),transform_is_affine=a.get_transform().is_affine)
        elif isinstance(a,AxesImage):
            raw=np.asarray(a.get_array());name='image_artist_'+str(i)+'.npy';np.save(root/name,raw,allow_pickle=False);maskname='image_artist_'+str(i)+'_mask.npy';np.save(root/maskname,np.ma.getmaskarray(a.get_array()),allow_pickle=False);r.update(mask_file=maskname,mask_sha256=sha((root/maskname).read_bytes()),role='source_image',array_file=name,array_sha256=sha((root/name).read_bytes()),shape=list(raw.shape),extent=list(a.get_extent()))
        else:continue
        artists.append(r)
    return {'axes':len(fig.axes),'axes_names':[a.name for a in fig.axes],'figure_size_inches':list(fig.get_size_inches()),'figure_dpi':fig.dpi,'artists':artists,'fonts':list(fonts.values()),'axes_containers':[{'axes':ai,'class':type(c).__name__,'label':c.get_label(),'data_values':array(c.datavalues) if hasattr(c,'datavalues') else None} for ai,ax in enumerate(fig.axes) for c in ax.containers],'all_data_vertices_and_offsets_retained':True,'data_point_or_path_vertex_count':data_points,'path_simplification_disabled':True,'text_not_glyph_paths_contract':'svg.fonttype=none; source mathtext is retained as SVG text/tspan where supported.'}
def capture(fig,*args,**kwargs):
    global active_export
    index=len(captures);prefix='capture_'+str(index);requested=str(args[0]) if args else str(kwargs.pop('fname','<unspecified>'));kwargs=dict(kwargs)
    rc={k:matplotlib.rcParams[k] for k in ['savefig.dpi','savefig.bbox','savefig.pad_inches','savefig.transparent','savefig.facecolor','savefig.edgecolor','savefig.format','figure.dpi','figure.figsize']}
    settings={'actual_source_requested_filename':requested,'actual_source_savefig_kwargs':{k:v if isinstance(v,(str,int,float,bool,type(None),list,tuple,dict)) else str(v) for k,v in kwargs.items()},'rcParams_at_actual_savefig_call':rc,'figure_DPI_at_call':fig.dpi,'figure_inches_at_call':list(fig.get_size_inches()),'PNG_and_SVG_backend_override_recorded':True,'fixed_export_overrides':{'svg.fonttype':'none','path.simplify':False,'agg.path.chunksize':0,'image.composite_image':False},'no_reference_pixel_fitting':True}
    kwargs.pop('format',None)
    info=scene(fig);svg=root/(prefix+'.svg');png=root/(prefix+'.png')
    export_dpi=kwargs.get('dpi',rc['savefig.dpi']);export_dpi=getattr(fig,'_original_dpi',fig.dpi) if export_dpi=='figure' else float(export_dpi)
    settings['backend_export_observations']=[]
    with matplotlib.rc_context({'svg.fonttype':'none','svg.hashsalt':'matplotlib_plot_v1','path.simplify':False,'agg.path.chunksize':0,'image.composite_image':False}):
        for format,file in [('svg',svg),('png',png)]:
            active_export={'format':format,'resolved_export_dpi':export_dpi,'full_figure_inches':list(fig.get_size_inches()),'bbox_adjustments':[],'actual_draws':[]}
            try:original(fig,str(file),format=format,**kwargs)
            finally:settings['backend_export_observations'].append(active_export);active_export=None
    info['fonts']=list({r['sha256']:r for r in info['fonts']+list(observed_svg_fonts.values())}.values());info['actual_source_export_settings']=settings
    (root/(prefix+'_scene.json')).write_text(json.dumps(info,ensure_ascii=False,indent=2,default=json_exact)+'\n');captured_figures.add(id(fig));captures.append({'svg':svg.name,'png':png.name,'scene':prefix+'_scene.json','scene_sha256':sha((root/(prefix+'_scene.json')).read_bytes()),'source_requested_save':requested,'svg_sha256':sha(svg.read_bytes()),'png_sha256':sha(png.read_bytes()),'axes':info['axes'],'data_point_or_path_vertex_count':info['data_point_or_path_vertex_count']})
Figure.savefig=capture
plt.show=lambda *a,**k:[capture(plt.figure(n),'show_capture') for n in plt.get_fignums() if id(plt.figure(n)) not in captured_figures]
try:
    source=(root/'source.py').read_bytes();rng_before=rng_state();initial_rc={k:matplotlib.rcParams[k] for k in ['savefig.dpi','savefig.bbox','savefig.pad_inches','savefig.transparent','figure.dpi','figure.figsize']}
    with matplotlib.rc_context({'path.simplify':False,'agg.path.chunksize':0,'image.composite_image':False}):exec(compile(source,'/work/source.py','exec'),{'__name__':'__main__','__file__':'/work/source.py'})
    for n in plt.get_fignums():
        if id(plt.figure(n)) not in captured_figures:capture(plt.figure(n),'implicit_final_capture')
    status={'ok':bool(captures),'captures':captures,'source_code_sha256':sha(source),'runtime':{'python':sys.version,'matplotlib':matplotlib.__version__,'numpy':np.__version__},'source_code_modified':False,'random_seed_injected':False,'source_text_glyph_path_events':glyph_path_events,'RNG_state_before':rng_before,'RNG_state_after':rng_state(),'initial_rcParams':initial_rc,'complete_export_parameters_recorded':True,'execution_contract':'Current pinned runtime, not asserted historical dataset producer.'}
except BaseException as e:status={'ok':False,'error':type(e).__name__+':'+str(e),'traceback':traceback.format_exc()[-5000:],'captures':captures}
(root/'execution.json').write_text(json.dumps(status,ensure_ascii=False,indent=2,default=json_exact)+'\n');print(json.dumps({k:status[k] for k in status if k not in {'traceback','RNG_state_before','RNG_state_after'}},default=json_exact));sys.exit(0 if status['ok'] else 1)
