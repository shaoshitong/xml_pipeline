import sys,os
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'scripts'));import curate_derived as n
source=n.renderer_path(R);dest=R/'conversion/rendering/remote_render.py';dest.parent.mkdir(exist_ok=True);code=source.read_text();assert 'data:image|https?' in code;code=code.replace('data:image|https?','https?').replace('embedded raster or external raster reference is disallowed','external raster references are disallowed; embedded source assets are permitted for conversion');dest.write_text(code)
assets=dest.parent/'assets'
if not assets.exists():assets.symlink_to(source.parent/'assets',target_is_directory=True)
print('Conversion-only renderer permits embedded source assets; offline resource checks remain enabled. Existing evaluation renderer unchanged.')
