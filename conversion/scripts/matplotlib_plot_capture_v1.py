"""Executed only inside the existing bwrap source sandbox."""
from pathlib import Path
import collections,hashlib,json,sys,traceback
import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.collections import Collection
from matplotlib.image import AxesImage
from matplotlib import font_manager
root=Path('/work');captures=[];captured_figures=set();original=Figure.savefig
sha=lambda b:hashlib.sha256(b).hexdigest()
def array(value):
    a=np.asarray(value)
    return {'dtype':str(a.dtype),'shape':list(a.shape),'values':a.tolist(),'all_values_retained':True}
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
            data_points+=sum(len(p.vertices) for p in paths)+len(a.get_offsets())
        elif isinstance(a,AxesImage):
            raw=np.asarray(a.get_array());name='image_artist_'+str(i)+'.npy';np.save(root/name,raw,allow_pickle=False);r.update(role='source_image',array_file=name,array_sha256=sha((root/name).read_bytes()),shape=list(raw.shape),extent=list(a.get_extent()))
        else:continue
        artists.append(r)
    return {'axes':len(fig.axes),'figure_size_inches':list(fig.get_size_inches()),'figure_dpi':fig.dpi,'artists':artists,'fonts':list(fonts.values()),'all_data_vertices_and_offsets_retained':True,'data_point_or_path_vertex_count':data_points,'path_simplification_disabled':True,'text_not_glyph_paths_contract':'svg.fonttype=none; source mathtext is retained as SVG text/tspan where supported.'}
def capture(fig,*args,**kwargs):
    index=len(captures);prefix='capture_'+str(index);requested=str(args[0]) if args else str(kwargs.pop('fname','<unspecified>'));kwargs=dict(kwargs);kwargs.pop('format',None)
    info=scene(fig);svg=root/(prefix+'.svg');png=root/(prefix+'.png')
    with matplotlib.rc_context({'svg.fonttype':'none','svg.hashsalt':'matplotlib_plot_v1','path.simplify':False,'agg.path.chunksize':0}):
        original(fig,str(svg),format='svg',**kwargs);original(fig,str(png),format='png',**kwargs)
    (root/(prefix+'_scene.json')).write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n');captured_figures.add(id(fig));captures.append({'svg':svg.name,'png':png.name,'scene':prefix+'_scene.json','source_requested_save':requested,'svg_sha256':sha(svg.read_bytes()),'png_sha256':sha(png.read_bytes()),'axes':info['axes'],'data_point_or_path_vertex_count':info['data_point_or_path_vertex_count']})
Figure.savefig=capture
plt.show=lambda *a,**k:[capture(plt.figure(n),'show_capture') for n in plt.get_fignums() if id(plt.figure(n)) not in captured_figures]
try:
    source=(root/'source.py').read_bytes()
    with matplotlib.rc_context({'path.simplify':False,'agg.path.chunksize':0}):exec(compile(source,'/work/source.py','exec'),{'__name__':'__main__','__file__':'/work/source.py'})
    for n in plt.get_fignums():
        if id(plt.figure(n)) not in captured_figures:capture(plt.figure(n),'implicit_final_capture')
    status={'ok':bool(captures),'captures':captures,'source_code_sha256':sha(source),'runtime':{'python':sys.version,'matplotlib':matplotlib.__version__,'numpy':np.__version__},'source_code_modified':False,'random_seed_injected':False,'execution_contract':'Current pinned runtime, not asserted historical dataset producer.'}
except BaseException as e:status={'ok':False,'error':type(e).__name__+':'+str(e),'traceback':traceback.format_exc()[-5000:],'captures':captures}
(root/'execution.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:status[k] for k in status if k!='traceback'}));sys.exit(0 if status['ok'] else 1)
