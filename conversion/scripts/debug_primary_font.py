import json
from native_worker import W
from portable_native_fonts_v2 import ready_page,capture,probe_primary
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome');page=ready_page(b)
 x=(W/'font_portability_probe_v2/0001c7fc6c8af5cb3c7b28e7e33e9f5f2abe1d782448c2240b6612a3fc8ffe0a/before.drawio').read_text();obs=capture(page,x)
 try:print(probe_primary(page,obs))
 except Exception as e:print(repr(e))
 b.close()
