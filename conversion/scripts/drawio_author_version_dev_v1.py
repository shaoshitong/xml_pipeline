"""Two preselected consumed sources: author-version versus current-source export.

All official source-only exports finish with hash-bound parameters before any
reference PNG is opened for metrics. Diagnostic source evidence, no acceptance.
"""
from pathlib import Path
import base64,hashlib,json,sys,urllib.parse,zlib,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
import drawio_author_version_export_v3 as exporter
import compiler_native_embedded_source_recovery_v1 as source_parser
PLAN=W/'drawio_author_export_source_dev_v1/fixed_two_20261101_v1/protocol.json'
PLAN_SHA='fddd5db1a76677e080c361515d6ddce4191b356ed076cfbcf6ed11e06bfdff65'
ROOT=PLAN.parent/'official_export_comparison_v1'
raw,sha,put=exporter.raw,exporter.sha,exporter.put

def checked(ref):
 p=Path(ref['file']);p=p if p.is_absolute()else R/p;p=p.resolve(strict=True)
 if not p.is_relative_to(R):raise ValueError('source_asset_outside_HKUST_root')
 b=p.read_bytes()
 if sha(b)!=ref['sha256']:raise ValueError('original_source_asset_changed:'+str(p))
 return b

def extract_complete_model(author,index,page_id):
 root=ET.fromstring(author)
 if root.tag!='mxfile':raise ValueError('author_metadata_not_full_mxfile')
 pages=[d for d in root if d.tag=='diagram']
 d=pages[index]
 if d.get('id')!=page_id:raise ValueError('frozen_author_page_identity_changed')
 inline=list(d.iter('mxGraphModel'))
 if inline:
  if len(inline)!=1:raise ValueError('multiple_models_in_selected_author_page')
  model=inline[0]
 else:
  payload=base64.b64decode((d.text or'').strip(),validate=True);text=zlib.decompress(payload,-15).decode();model=ET.fromstring(urllib.parse.unquote_to_bytes(text))
 if model.tag!='mxGraphModel':raise ValueError('selected_page_not_complete_native_model')
 return root,model,ET.tostring(model,encoding='utf-8')

def source_inputs(spec):
 record=json.loads(checked(spec['recovery_record']));gold=checked(record['assets']['original_provided_code']);author=checked(record['assets']['recovered_author_native'])
 assert sha(gold)==spec['original_code_sha256']and sha(author)==spec['recovered_author_sha256']
 root,model,model_bytes=extract_complete_model(author,spec['selected_author_page_index'],spec['selected_author_page_id'])
 assert(root.get('version'),root.get('scale'),root.get('border'))==(spec['version'],spec['scale'],spec['border'])
 model_info=source_parser.page(model,spec['selected_author_page_index'],spec['selected_author_page_id'],None)
 assert model_info['canonical_model_sha256']==spec['author_model_sha256']and model_info['cell_count']==spec['source_cells']
 provided=source_parser.document(gold);diff=source_parser.page_diff(provided['pages'][0],model_info)
 assert not any(diff['counts'].values())and not diff['provided_only_cell_IDs']and not diff['author_only_cell_IDs']
 assert set(diff['model_attribute_differences'])<={'dx','dy'}
 return record,model_bytes,model_info,diff

def score(reference,proposal):
 from PIL import Image
 import io,numpy as np
 a=Image.open(io.BytesIO(reference)).convert('RGBA');b=Image.open(io.BytesIO(proposal)).convert('RGBA')
 result={'reference_canvas':list(a.size),'source_export_canvas':list(b.size),'canvas_equal':a.size==b.size,'any_resize_crop_pad_align_or_target_fit':False,'RGBA_exact':a.size==b.size and a.tobytes()==b.tobytes()}
 if a.size!=b.size:return result
 x=np.array(a);y=np.array(b);result.update(RGBA_exact_pixel_fraction=float(np.all(x==y,axis=2).mean()),RGBA_mean_absolute_difference=float(np.abs(x.astype(float)-y).mean()),alpha_equal=bool(np.array_equal(x[:,:,3],y[:,:,3])))
 white=lambda im:Image.alpha_composite(Image.new('RGBA',im.size,'white'),im).convert('RGB')
 ax=np.array(white(a));by=np.array(white(b));result['white_composite_RGB_exact']=bool(np.array_equal(ax,by));result['white_composite_RGB_MAE']=float(np.abs(ax.astype(float)-by).mean())
 try:
  from skimage.metrics import structural_similarity
  result['whole_white_composite_SSIM']=float(structural_similarity(ax,by,data_range=255,channel_axis=2))
 except ImportError:result['whole_white_composite_SSIM']='skimage_not_installed'
 for name,array in [('reference',ax),('source',by)]:
  yy,xx=np.where(np.any(array<245,axis=2));result[name+'_whole_ink_bbox']=None if not len(xx)else[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)]
 return result

def run():
 assert sha(PLAN.read_bytes())==PLAN_SHA;plan=json.loads(PLAN.read_bytes());assert len(plan['selected'])==2 and all(s['old_consumed_development']for s in plan['selected'])
 ROOT.mkdir(parents=True,exist_ok=False)
 configs={v:exporter.configuration(v)for v in ('27.0.9','28.0.6','32.6.1')}
 protocol={'schema':'fixed_two_author_version_source_export_pre_pixel_protocol_v1','original_source_selection':{'file':str(PLAN),'sha256':PLAN_SHA},'only_consumed_ids':[s['id']for s in plan['selected']],'fixed_versions_per_id':{s['id']:[s['version'],'32.6.1']for s in plan['selected']},'configurations':configs,'exporter_file':str(Path(exporter.__file__).resolve()),'driver_file':str(Path(__file__).resolve()),'driver_sha256':sha(Path(__file__).read_bytes()),'width_limit':None,'scale':'literal PNG embedded author mxfile scale','border':'literal PNG embedded author mxfile border','transparent':False,'transparency_policy':'official showExportDialog transparent-background checkbox default false, not inferred from reference alpha','theme':'light','size':'diagram','ignore_selection':True,'grid':False,'graph_fitting_or_font_changes':False,'all_export_parameters_frozen_before_reference_metrics':True,'reference_pixel_reads_before_all_exports':0,'remaining_43_pixel_reads':0,'source_thresholds_changed':False,'qualified_claim':False,'model_calls':0}
 put(ROOT/'pre_pixel_protocol.json',raw(protocol));outputs=[]
 for spec in plan['selected']:
  record,model,info,diff=source_inputs(spec)
  for version in (spec['version'],'32.6.1'):
   out=ROOT/spec['id']/version;export=exporter.render(model,float(spec['scale']),float(spec['border']),version,out)
   native=source_parser.document(checked(export['assets']['native_roundtrip_model']));roundtrip=source_parser.page_diff(info,native['pages'][0]);put(out/'native_roundtrip_comparison.json',raw(roundtrip))
   row={'id':spec['id'],'source_author_version':spec['version'],'render_version':version,'original_image_sha256':spec['original_image_sha256'],'original_code_sha256':spec['original_code_sha256'],'recovered_author_sha256':spec['recovered_author_sha256'],'selected_page':spec['selected_author_page_index'],'source_model_sha256':sha(model),'source_model_canonical_sha256':info['canonical_model_sha256'],'original_Gold_content_difference_counts':diff['counts'],'original_Gold_vs_author_only_model_attrs':diff['model_attribute_differences'],'source_export':export['source_export'],'native_roundtrip_difference_counts':roundtrip['counts'],'native_roundtrip_only_before_cells':roundtrip['provided_only_cell_IDs'],'native_roundtrip_only_after_cells':roundtrip['author_only_cell_IDs'],'source_source_model_equivalence_except_editor_attrs':not any(roundtrip['counts'].values())and not roundtrip['provided_only_cell_IDs']and not roundtrip['author_only_cell_IDs'],'actual_physical_fonts':sorted({font.get('postScriptName')for cell in export['actual_platform_font_usage']for font in cell['fonts']if font.get('glyphCount',0)}),'actual_text_cells_with_physical_fonts':len(export['actual_platform_font_usage']),'source_evidence':{'file':str(out/'source_export_evidence.json'),'sha256':sha((out/'source_export_evidence.json').read_bytes())},'source_png':export['assets']['source_png'],'source_svg':export['assets']['source_svg'],'source_roundtrip':export['assets']['native_roundtrip_model'],'reference':record['assets']['original_reference'],'model_calls':0,'qualified':False}
   outputs.append(row);print(json.dumps({'stage':'source_export_finished_before_reference_metrics','id':spec['id'],'version':version,'canvas':export['source_export'],'physical_fonts':row['actual_physical_fonts'],'roundtrip':roundtrip['counts']}),flush=True)
 put(ROOT/'all_exports_completed_before_reference_metrics.json',raw({'source_exports':outputs,'export_count':4,'reference_pixels_read':False,'all_parameters_protocol':{'file':str(ROOT/'pre_pixel_protocol.json'),'sha256':sha((ROOT/'pre_pixel_protocol.json').read_bytes())}}))
 # First reference image decoding is here, after all four immutable source exports.
 for row in outputs:
  ref=checked(row['reference']);proposal=checked(row['source_png']);row['posthoc_reference_metrics']=score(ref,proposal);print(json.dumps({'stage':'posthoc_reference_metrics','id':row['id'],'version':row['render_version'],'metrics':row['posthoc_reference_metrics']}),flush=True)
 report={'schema':'two_consumed_author_version_official_source_export_comparison_v1','scope':2,'source_exports':4,'rows':outputs,'original_source_selection':{'file':str(PLAN),'sha256':PLAN_SHA},'pre_pixel_protocol':{'file':str(ROOT/'pre_pixel_protocol.json'),'sha256':sha((ROOT/'pre_pixel_protocol.json').read_bytes())},'before_reference_metrics_proof':{'file':str(ROOT/'all_exports_completed_before_reference_metrics.json'),'sha256':sha((ROOT/'all_exports_completed_before_reference_metrics.json').read_bytes())},'same_host_browser_across_versions':True,'actual_author_OS_and_Electron_reproduced':False,'all_original_source_models_and_font_declarations_preserved':True,'remaining43_reference_pixel_checks':0,'reference_derived_parameter_fitting':False,'qualified_or_released':0,'canonical_source_or_manifest_modified':False,'model_calls':0,'interpretation':'Exact original PNG reproduction is reported only for full RGBA equality. Similarity is diagnostic; this study does not replace strict-canvas/source/font/editing acceptance or justify a batch rollout.'}
 put(ROOT/'report.json',raw(report));print(json.dumps({'report':str(ROOT/'report.json'),'sha256':sha((ROOT/'report.json').read_bytes()),'author_version_RGBA_exact':sum(row['posthoc_reference_metrics']['RGBA_exact']for row in outputs if row['source_author_version']==row['render_version']),'current_RGBA_exact':sum(row['posthoc_reference_metrics']['RGBA_exact']for row in outputs if row['render_version']=='32.6.1'),'qualified':0}),flush=True);return report
if __name__=='__main__':run()
