"""One finite source-only viewport diagnostic on four already-seen cases.

No target conversion, fitting, search, heldout read or canonical mutation.
The reported paint envelope is conservative, never claimed to be tight.
"""
import collections,io,json,math,sqlite3,sys,uuid
from pathlib import Path
import xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_languages_source_layout_v1 as c
from PIL import Image
CASES=('0005a67a974edb3bb5b4895389d0d314689bc67c773a13ddfbd64445d5f69c5f','0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641','04fab87123d9acfe24b7a8ef0b016177bba1851406b97a069a17302159b7f93f','741dba10f203580e613cfc70c0aa6e9d3650ef4188379018741dc6b7d762c1bd')

def envelope(dom,frame):
 boxes=[];kinds=collections.Counter();conservative_strokes=0
 for o in dom['objects']:
  b=o['bbox'];s=o.get('style') or {};padding=0.
  if o['type']=='shape' and s.get('stroke') not in (None,'none') and float(s.get('strokeOpacity',1))*float(s.get('opacity',1))>0:
   a,bm,cm,d,_,_=o['matrix'];frobenius=math.sqrt(a*a+bm*bm+cm*cm+d*d);padding=float(s.get('strokeWidth',0))*frobenius/2
   if s.get('linejoin')=='miter':padding*=4;conservative_strokes+=1
  b=o['bbox'];boxes.append([b['x']-padding,b['y']-padding,b['x']+b['w']+padding,b['y']+b['h']+padding]);kinds[o['type']]+=1
 require=bool(boxes)
 if not require:return None
 extent=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
 scale=frame['scale'];tx,ty=frame['translation'];source=[(extent[0]-tx)/scale,(extent[1]-ty)/scale,(extent[2]-tx)/scale,(extent[3]-ty)/scale];vx,vy,vw,vh=frame['source_viewBox']
 return {'projected_upper_envelope_xyxy':extent,'source_upper_envelope_xyxy':source,'source_viewbox_slack_ltrb':[source[0]-vx,source[1]-vy,vx+vw-source[2],vy+vh-source[3]],'objects':dict(kinds),'expanded_marker_objects':sum(bool(o.get('markerOwner')) for o in dom['objects']),'text_objects':sum(o['type']=='text' for o in dom['objects']),'miter_stroke_envelopes':conservative_strokes,'method':'DOM visible-object boxes including expanded arrow markers and whole text boxes; stroke half-width times matrix Frobenius bound, miter default4 conservative expansion','tight_exact_paint_bounds_proven':False,'cannot_justify_tight_crop_projection':True,'limitations':['CSS filter/mask/clip are rejected by source capture.','Conservative stroke boxes overestimate paint. Miter limit is not captured by the legacy extractor; default4 is an estimate and cannot prove full exact extent for explicit larger miter limits.','Root viewBox projection may clip paint outside the viewport; the envelope is diagnostic only.']}

def main():
 base=W/c.VERSION/'source_viewport_diagnostic'/uuid.uuid4().hex;base.mkdir(parents=True);db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30);db.execute('pragma query_only=ON');results=[];before_config=c.configuration()
 for ident in CASES:
  columns=[x[1] for x in db.execute('pragma table_info(jobs)')];row=db.execute('select * from jobs where id=?',(ident,)).fetchone();job=dict(zip(columns,row));old=json.loads(job['output_record']) if job['output_record'] else {};source,code,ref=c._inputs(old,job);refim=Image.open(io.BytesIO(ref));work=base/ident;capture=c._capture(source,code,ref,work);root=ET.fromstring(capture['svg']);frame=capture['frame']
  info={'id':ident,'format':source['format'],'provider':source['source'],'source_code_sha256':c.sha(code),'reference_sha256':c.sha(ref),'reference_size':list(refim.size),'raw_svg_root_attributes':{k:v for k,v in root.attrib.items() if k in ('viewBox','width','height','preserveAspectRatio','data-diagram-type')},'frame':frame,'paint_envelope':envelope(capture['dom'],frame),'old_conversion_method':old.get('conversion_method'),'old_source_renderer':old.get('source_renderer'),'old_plantuml_runtime_version':(old.get('plantuml_runtime') or {}).get('version'),'reference_metadata_engine_versions':str(refim.info.get('plantuml','')).splitlines()[:1],'source_svg_projection_visual':c._source_visual(ref,capture),'source_layout_changed':False,'parameter_search':False,'target_conversion_executed':False}
  if capture['engine_png']:
   engine=Image.open(io.BytesIO(capture['engine_png']));info['original_engine_png_size']=list(engine.size);info['engine_png_canvas_exactly_reference']=engine.size==refim.size
   if engine.size==refim.size:
    from auto_quality_common_v4 import image_quality
    info['raw_engine_png_reference_visual']=image_quality(ref,capture['engine_png'],{},None)
  else:info['original_engine_png_size']=None;info['engine_output_kind']='Mermaid source engine emits SVG; no independent natural PNG was generated or fitted'
  for name,blob in [('raw_source.svg',capture['svg']),('projected_source.svg',capture['projected_svg']),('projected_source.png',capture['png'])]:(work/name).write_bytes(blob)
  if capture['engine_png']:(work/'raw_engine.png').write_bytes(capture['engine_png'])
  info['canonical_snapshot_unchanged']=db.execute('select * from jobs where id=?',(ident,)).fetchone()==row;results.append(info);(work/'metadata.json').write_bytes(c.raw(info));print(json.dumps({k:info[k] for k in ('id','format','reference_size','raw_svg_root_attributes','original_engine_png_size','canonical_snapshot_unchanged')},ensure_ascii=False),flush=True)
 db.close();after=c.configuration();report={'version':'source_viewport_metadata_finite_readonly_v1','configuration_unchanged':before_config==after,'results':results,'v2_projection_justified':False,'reason':'Conservative DOM envelope is not a proven tight complete source paint extent. No source-only generic projection defect was established.','new_model_calls':0,'unseen_consumed':0,'canonical_mutations':0,'target_conversions':0,'report':str(base/'report.json')};(base/'report.json').write_bytes(c.raw(report));print(json.dumps({'report':report['report'],'configuration_unchanged':report['configuration_unchanged'],'v2_projection_justified':False}),flush=True)

if __name__=='__main__':main()
