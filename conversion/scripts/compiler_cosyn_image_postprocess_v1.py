"""Exact official CoSyn image postprocess and its explicit complete-frame map.

The returned PNG and source identity determine the output. The immutable target
reference supplies no scale, resampler, crop, translation, or other parameter.
The geometry helper carries the same pixel-grid transform to a SOURCE SVG;
native conversion and independent full QA must consume that derived SVG.
"""
import ast,contextlib,copy,functools,hashlib,io,json,math,re
from pathlib import Path
import xml.etree.ElementTree as E
from PIL import Image,__version__ as PILLOW_VERSION
POLICY='official_CoSyn_process_image_full_frame_v1'
UNIT='CoSyn_official_conditional_thumbnail_alpha_white_RGB_integer_grid_v1'
PRODUCER_COMMIT='0f06dbc585b0a48d543a8559ba63d79ecb4127e5'
PRODUCER_URL='https://github.com/allenai/pixmo-docs/blob/'+PRODUCER_COMMIT+'/pipeline/utils/utils.py'
PRODUCER_FUNCTION_SHA256='db86dea2f615ca1799977873677e7d188ba1388d9fdc77e6c4b6ea09adf5dccc'
OFFICIAL_HELPER_SOURCE="def compute_major_px_ratio(image):\n    # Compute the ratio of the most common pixel in the image\n    px_count = {}\n    for px in image.getdata():\n        if px in px_count:\n            px_count[px] += 1\n        else:\n            px_count[px] = 1\n    \n    max_px = max(px_count, key=px_count.get)\n    return px_count[max_px] / len(image.getdata())"
OFFICIAL_PROCESS_IMAGE_SOURCE="def process_image(image, max_size=(2560, 1440), major_px_threshold=0.95, aspect_ratio_threshold=5, filter_small=True):\n    # Resize the image if it exceeds the maximum size\n    if image.size[0] * image.size[1] > max_size[0] * max_size[1]:\n        image.thumbnail(max_size, Image.Resampling.LANCZOS)\n    \n    # Convert alpha channel to white background\n    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):\n        alpha = image.convert('RGBA').split()[-1]\n        bg = Image.new(\"RGBA\", image.size, (255, 255, 255, 255))\n        bg.paste(image, mask=alpha)\n        image = bg.convert(\"RGB\")\n    else:\n        image = image.convert(\"RGB\")\n    \n    major_px_ratio = compute_major_px_ratio(image)\n    if major_px_ratio > major_px_threshold: print(\"Warning: Image is monochromatic.\", major_px_ratio); return None\n\n    byte_array = image.tobytes()\n    width, height = image.size\n\n    aspect_ratio = max(width, height) / min(width, height)\n    if aspect_ratio > aspect_ratio_threshold: print(\"Warning: Image aspect ratio is too high.\"); return None\n\n    if min(width, height) < 128 and filter_small: print(\"Warning: Image is too small.\"); return None\n\n    image_from_byte_array = Image.frombytes(\"RGB\", (width, height), byte_array)\n    \n    return image_from_byte_array"
sha=lambda b:hashlib.sha256(b).hexdigest()
if sha(OFFICIAL_PROCESS_IMAGE_SOURCE.encode())!=PRODUCER_FUNCTION_SHA256:raise RuntimeError('official_process_image_source_identity_changed')
_PROVIDER={'Image':Image}
exec(compile(OFFICIAL_HELPER_SOURCE+'\n\n'+OFFICIAL_PROCESS_IMAGE_SOURCE,PRODUCER_URL,'exec'),_PROVIDER)
MAX_SIZE=(2560,1440)
AREA_THRESHOLD=MAX_SIZE[0]*MAX_SIZE[1]

@functools.lru_cache(maxsize=1)
def configuration():
 import PIL
 directory=Path(PIL.__file__).parent
 files=[Path(__file__)]+sorted(directory.glob('*.py'))+sorted(directory.glob('*.so'))
 pins={str(p.resolve()):sha(p.read_bytes()) for p in files}
 return dict(unit=UNIT,policy=POLICY,pins=pins,pillow_version=PILLOW_VERSION,provider='allenai--CoSyn-400K',provider_commit=PRODUCER_COMMIT,provider_URL=PRODUCER_URL,provider_function_sha256=PRODUCER_FUNCTION_SHA256,constants=dict(max_size=list(MAX_SIZE),area_threshold=AREA_THRESHOLD,resampling='PIL.Image.Resampling.LANCZOS',alpha_background=[255,255,255,255],output_mode='RGB',major_px_threshold=.95,aspect_ratio_threshold=5,min_side=128),requires_identity_bound_fresh_Graphviz_PNG=True,target_selects_no_parameter=True,source_SVG_and_native_must_share_output_pixel_grid=True)

def _identity(source):
 if source.get('source')!='allenai--CoSyn-400K' or (source.get('source_format') or source.get('format'))!='python':raise ValueError('official_postprocess_requires_CoSyn_Python_source')
 identifier=source.get('pair_sha256') or source.get('id')
 if not re.fullmatch('[0-9a-f]{64}',str(identifier)):raise ValueError('official_postprocess_invalid_pair_identity')
 for name in ['code_sha256','image_sha256']:
  if not re.fullmatch('[0-9a-f]{64}',str(source.get('source_'+name) or source.get(name))):raise ValueError('official_postprocess_missing_source_hash')
 return dict(id=identifier,source_code_sha256=source.get('source_code_sha256') or source.get('code_sha256'),source_image_sha256=source.get('source_image_sha256') or source.get('image_sha256'))

def canvas_plan(source_size):
 sw,sh=map(int,source_size)
 if min(sw,sh)<=0 or max(sw,sh)>32768:raise ValueError('official_postprocess_source_canvas_out_of_bounds')
 # Pillow itself decides integer dimensions, entirely from the SOURCE size.
 # A one-bit empty image keeps this dimensions-only operation inexpensive.
 probe=Image.new('1',(sw,sh))
 thumbnail=sw*sh>AREA_THRESHOLD
 if thumbnail:probe.thumbnail(MAX_SIZE,Image.Resampling.LANCZOS)
 ow,oh=probe.size
 return dict(policy=POLICY,source_canvas=[sw,sh],output_canvas=[ow,oh],conditional_thumbnail=thumbnail,source_area=sw*sh,threshold_area=AREA_THRESHOLD,bounding_box=list(MAX_SIZE),scale_x=ow/sw,scale_y=oh/sh,translation=[0,0],pixel_centers='source_center=(output_center+0.5)*source_size/output_size-0.5',crop=False,padding=False,all_source_pixel_extent_preserved=True,integer_output_grid=True,parameters_from_target=False)

def postprocess(png,source):
 identity=_identity(source);image=Image.open(io.BytesIO(png))
 if image.format!='PNG':raise ValueError('official_postprocess_requires_returned_PNG')
 plan=canvas_plan(image.size);message=io.StringIO()
 with contextlib.redirect_stdout(message):out=_PROVIDER['process_image'](image)
 if out is None:return dict(ok=False,reason='official_provider_image_filter_rejected',identity=identity,mapping=plan,provider_message=message.getvalue(),model_calls=0)
 if list(out.size)!=plan['output_canvas'] or out.mode!='RGB':raise RuntimeError('official_postprocess_dimension_or_mode_diverged')
 stream=io.BytesIO();out.save(stream,format='PNG');blob=stream.getvalue()
 return dict(ok=True,png=blob,mapping=plan,evidence=dict(schema=POLICY,identity=identity,input_png_sha256=sha(png),output_png_sha256=sha(blob),output_RGB_pixels_sha256=sha(out.tobytes()),source_mode=image.mode,output_mode=out.mode,pillow_version=PILLOW_VERSION,provider_commit=PRODUCER_COMMIT,provider_function_sha256=PRODUCER_FUNCTION_SHA256,all_source_content_mapped=True,no_crop_no_padding=True,no_reference_parameters=True),model_calls=0)

def match_reference_canvas(processed,reference_size):
 # The forward result is already fixed; this is an equality check, never an
 # inverse fit from the rounded reference dimensions.
 ok=processed.get('ok') is True and processed['mapping']['output_canvas']==list(reference_size)
 return dict(ok=ok,reason='official_postprocess_canvas_matches_reference' if ok else 'source_reference_canvas_mismatch_after_official_postprocess',actual_output_canvas=processed.get('mapping',{}).get('output_canvas'),reference_canvas=list(reference_size),parameters_from_reference=False)

def verify_postprocess(source_png,processed_png,source):
 replay=postprocess(source_png,source)
 if not replay['ok']:raise ValueError('official_postprocess_source_filtered_on_replay')
 expected=Image.open(io.BytesIO(replay['png']));candidate=Image.open(io.BytesIO(processed_png))
 if candidate.format!='PNG' or candidate.mode!='RGB' or candidate.size!=expected.size or candidate.tobytes()!=expected.tobytes():raise ValueError('official_postprocess_pixels_do_not_reproduce_exact_source')
 return dict(ok=True,policy=POLICY,source_png_sha256=sha(source_png),processed_png_sha256=sha(processed_png),fresh_official_replay_png_sha256=sha(replay['png']),complete_RGB_pixels_exactly_replayed=True,mapping=replay['mapping'],reference_selects_no_parameter=True)

def register_svg(svg,mapping,source_svg_sha256):
 if sha(svg)!=source_svg_sha256:raise ValueError('official_postprocess_SOURCE_SVG_identity_changed')
 expected=canvas_plan(mapping['source_canvas'])
 if mapping!=expected:raise ValueError('official_postprocess_unreplayed_or_modified_mapping')
 root=E.fromstring(svg);namespace='http://www.w3.org/2000/svg'
 if root.tag!='{'+namespace+'}svg':raise ValueError('official_postprocess_requires_SOURCE_SVG')
 if any(n.tag.rsplit('}',1)[-1] in ('image','foreignObject','script','filter','mask','clipPath','use','textPath','style') for n in root.iter()):raise ValueError('official_postprocess_unsupported_SOURCE_SVG_feature')
 if not root.get('viewBox'):raise ValueError('official_postprocess_missing_original_viewbox')
 view=list(map(float,root.get('viewBox').replace(',',' ').split()))
 if len(view)!=4 or min(view[2:])<=0 or not all(math.isfinite(v) for v in view):raise ValueError('official_postprocess_invalid_original_viewbox')
 if root.get('x') not in (None,'0') or root.get('y') not in (None,'0'):raise ValueError('official_postprocess_existing_SVG_position_pending')
 styles=dict(item.split(':',1) for item in root.get('style','').split(';') if ':' in item)
 if any(k.strip() in ('width','height','transform','position') for k in styles):raise ValueError('official_postprocess_SOURCE_root_layout_style_pending')
 sw,sh=mapping['source_canvas'];ow,oh=mapping['output_canvas'];original_children=[E.tostring(c) for c in root]
 original_root_attributes=dict(root.attrib);root.set('width',str(sw));root.set('height',str(sh));root.set('x','0');root.set('y','0')
 # This inner SOURCE viewport is exactly the existing source capture's
 # current-PNG viewport. The outer wrapper carries the provider's complete
 # per-axis integer-grid map, including Pillow's unavoidable dimension roundoff.
 wrapper=E.Element('{'+namespace+'}svg',dict(width=str(ow),height=str(oh),viewBox='0 0 '+str(sw)+' '+str(sh),preserveAspectRatio='none'))
 wrapper.append(root);serialized=E.tostring(wrapper,encoding='unicode')
 # The current source capture embeds SVG as HTML. A generated ns0:svg tag
 # would become an HTML unknown element there, so emit a literal SVG tag
 # with a default namespace, without changing ElementTree's global registry.
 declaration=re.search(r'xmlns:([A-Za-z_][\w.-]*)="'+re.escape(namespace)+r'"',serialized)
 if declaration:
  prefix=declaration[1];serialized=serialized.replace(declaration[0],'xmlns="'+namespace+'" '+declaration[0],1)
  serialized=re.sub(r'<(/?)'+re.escape(prefix)+r':([A-Za-z_][\w.-]*)',r'<\1\2',serialized)
 blob=serialized.encode()
 if [E.tostring(c) for c in root]!=original_children:raise RuntimeError('official_postprocess_SOURCE_children_changed')
 proof=dict(policy=POLICY,source_svg_sha256=sha(svg),registered_svg_sha256=sha(blob),mapping=mapping,source_viewport=mapping['source_canvas'],output_viewport=mapping['output_canvas'],original_root_attributes=original_root_attributes,source_children_unchanged=True,original_node_edge_ids_labels_paths_paint_unchanged=True,pixel_frame_transform_complete=True,native_emitter_must_consume_registered_SVG=True,independent_full_source_native_font_visual_editing_QA_still_mandatory=True)
 return blob,proof

def verify_registered_svg(source_svg,registered_svg,mapping,source_svg_sha256):
 expected,proof=register_svg(source_svg,mapping,source_svg_sha256)
 if registered_svg!=expected:raise ValueError('official_postprocess_registered_SOURCE_SVG_changed')
 return dict(ok=True,policy=POLICY,source_svg_sha256=source_svg_sha256,registered_svg_sha256=sha(registered_svg),complete_source_structure_and_frame_rederived=True,native_full_QA_still_required=True)
