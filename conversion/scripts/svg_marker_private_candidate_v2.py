"""Copy one complete RO prototype into a real closed private data root.

No symlink, canonical payload, owner, job, queue or outcome is written. Existing
prototype results remain partial if the independent whole-source profile fails.
"""
from pathlib import Path
import copy,json,hashlib,sys
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';P=W/'prototype/svg_marker_composition_v2';sys.path.insert(0,str(P));import svg_marker_composition_profile_v2 as profile
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def require(ok,reason):
    if not ok:raise ValueError(reason)
def encoded(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def prepare(input_record,composition_work,data_root):
    work=Path(composition_work).resolve();require(work.is_relative_to((W/'prototype/svg_marker_font_composition_v1').resolve()),'unowned_marker_composition_source');data_root=Path(data_root).resolve();require(data_root.is_relative_to((P/'private_roots').resolve()) and not data_root.exists(),'new_private_data_root_required');data_root.mkdir(parents=True);(data_root/'clean').mkdir();copied={}
    def store(relative,data):
        relative=Path(relative);require(not relative.is_absolute() and '..' not in relative.parts,'invalid_private_asset_locator');target=data_root/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():require(target.read_bytes()==data,'private_asset_collision')
        else:target.write_bytes(data)
        copied[str(relative)]={'sha256':sha(data),'bytes':len(data)};return {'file':str(relative),'sha256':sha(data)}
    def copy_clean(value):
        if isinstance(value,dict):
            for item in value.values():copy_clean(item)
        elif isinstance(value,list):
            for item in value:copy_clean(item)
        elif isinstance(value,str) and value.startswith('clean/') and '\0' not in value:
            logical=Path(value)
            if '..' in logical.parts:raise ValueError('source_clean_locator_has_parent_escape')
            source=(R/logical).resolve(strict=True);require(source.is_relative_to((R/'clean').resolve()),'source_asset_not_canonical_clean')
            if source.is_file():store(logical,source.read_bytes())
    copy_clean(input_record);before=Path(work/'baseline.drawio').read_bytes();before_png=Path(work/'baseline.png').read_bytes();require(sha(before)==input_record['code_sha256'] and sha(before_png)==input_record['image_sha256'],'composition_input_is_not_current_frozen_pair');out_xml=(work/'font_marker.drawio').read_bytes();out_png=(work/'font_marker.png').read_bytes();digest=sha(out_xml);base=Path('clean/marker_composition_v2')/input_record['id']/digest;assets={}
    for key,name in [('baseline_xml','baseline.drawio'),('baseline_png','baseline.png'),('marker_xml','marker.drawio'),('marker_png','marker.png'),('font_baseline_xml','font_baseline.drawio'),('font_baseline_png','font_baseline.png'),('font_details','font_details.json'),('observed_fonts','observed_fonts.json'),('composition_report','composition_report.json')]:assets[key]=store(base/'evidence'/name,(work/name).read_bytes())
    assets['baseline_record']=store(base/'evidence/input_record.json',encoded(input_record));report=json.loads((work/'composition_report.json').read_text());fonts=list(copy.deepcopy(input_record.get('native_embedded_fonts') or []))
    for font in report['font_composition']['fonts'].values():
        source=Path(font['file']);original=Path(font['original_file']);raw=source.read_bytes();prior=original.read_bytes();require(sha(raw)==font['sha256'] and sha(prior)==font['original_sha256'],'prototype_font_bytes_changed');new=store(Path('clean/font_assets')/source.name,raw);old=store(Path('clean/font_assets')/('original_'+font['original_sha256']+original.suffix.lower()),prior);fonts.append({**{key:value for key,value in font.items() if key not in ['file','uri','original_file']},'file':new['file'],'original_file':old['file'],'source_system_font_path':str(original)})
    code=store(base/'diagram.drawio',out_xml);image=store(base/'image.png',out_png);proof={'version':2,'policy':profile.POLICY,'id':input_record['id'],'assets':assets,'input_code_sha256':input_record['code_sha256'],'input_image_sha256':input_record['image_sha256'],'output_code_sha256':code['sha256'],'output_image_sha256':image['sha256'],'source_code_sha256':input_record['source_code_sha256'],'source_image_sha256':input_record['source_image_sha256'],'prototype_only':True,'source_coverage_is_independently_rechecked_not_inherited':True,'accepted':False,'published':False,'model_calls':0};proof_entry=store(Path('conversion/svg_marker_composition_v2')/input_record['id']/'composition.json',encoded(proof));keep=['id','source_pair_sha256','source','category','source_format','source_record','source_code_sha256','source_image_sha256','original_source_code','original_reference','source_render_svg','source_render_svg_sha256','source_render_pdf','source_render_pdf_sha256','source_render_png','source_render_png_sha256','original_source_data','source_data_sha256','source_assets','original_vector_assets','fonts'];candidate={key:copy.deepcopy(input_record[key]) for key in keep if key in input_record};candidate.update(format='drawio',code_file=code['file'],code_sha256=code['sha256'],image_file=image['file'],image_sha256=image['sha256'],model=None,conversion_method='fresh_source_triangle_marker_physical_font_and_dependency_paint_composition_v2',quality_state='pending_readonly_independent_whole_source_quality',native_embedded_fonts=fonts,svg_marker_composition_v2=proof_entry,render=json.loads((work/'font_marker.native.json').read_text()),native_font_validation={'input_code_sha256':sha((work/'marker.drawio').read_bytes()),'output_code_sha256':code['sha256'],'input_image_sha256':sha((work/'marker.png').read_bytes()),'output_image_sha256':image['sha256'],'native_pixels_unchanged':True,'physical_faces_and_glyph_counts_preserved':True,'all_actual_fonts_custom':True,'audit':proof_entry['file'],'accepted':False});record_file=data_root/'candidate_record.json';record_file.write_bytes(encoded(candidate));manifest={'id':candidate['id'],'data_root':str(data_root),'record_file':str(record_file),'record_sha256':sha(record_file.read_bytes()),'assets':copied,'all_assets_are_regular_files_not_symlinks':all((data_root/path).is_file() and not (data_root/path).is_symlink() for path in copied),'canonical_mutations':0,'accepted':False,'published':False};(data_root/'asset_manifest.json').write_bytes(encoded(manifest));return manifest
