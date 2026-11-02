from playwright.sync_api import sync_playwright
from native_worker import R,native
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome');page=b.new_page();page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'));print(page.evaluate('JSON.stringify({block:String(mxMarker.markers.block),classic:String(mxMarker.markers.classic),open:String(mxMarker.markers.open)})'));b.close()
