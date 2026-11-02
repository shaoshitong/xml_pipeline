from pathlib import Path
import copy,json,sys,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_pipeline_20261102_v1/controls/real_negative_v1';D.mkdir(parents=True,exist_ok=False);sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from matplotlib_plot_quality_v1 import coverage
from auto_quality_common import image_quality
P=R/'clean/matplotlib_plot_development_20261102_v1/cases/2f1586fb57bc6ecf8568d1a53cb2cad77a52b8cdc125b69a27fe4a5709734ecb';V=P/'native_development_v3';root=ET.fromstring((V/'diagram.drawio').read_text());dom=json.loads((V/'source_dom.json').read_text());clips=json.loads((V/'vector_clip_evidence.json').read_text());parent=root.find('.//mxGraphModel/root');target=next(c for c in parent if c.get('vertex')=='1' and c.get('matplotlib_artist_gid')=='matplotlib_artist_2');parent.remove(target);drop=coverage(ET.tostring(root,encoding='unicode'),dom,clips)
textroot=ET.fromstring((V/'diagram.drawio').read_text());label=next(c for c in textroot.iter('mxCell') if 'shape=text;' in c.get('style',''));label.set('value','DELIBERATELY_CHANGED_LABEL');text=coverage(ET.tostring(textroot,encoding='unicode'),dom,clips)
bad=P/'native_development_v1';meta=json.loads((bad/'native_render.json').read_text());alpha=image_quality((P/'capture_0.png').read_bytes(),(bad/'native.png').read_bytes(),{},meta['actual_text_positions'])
report={'ok':not drop['ok'] and not text['ok'] and not alpha['ok'],'omitted_real_data_path_rejected':not drop['ok'],'changed_live_label_rejected':not text['ok'],'real_opaque_band_regression_rejected_by_unchanged_pixel_gate':not alpha['ok'],'alpha_gate_failures':alpha['failures'],'no_dataset_source_executed_again':True,'model_calls':0,'source_originals_unchanged':True}
assert report['ok'];(D/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
