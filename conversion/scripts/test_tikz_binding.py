import json
from native_worker import W
from tikz_connectivity import bind
id='0001784b9f3b28598732c2dc034369bd2dc5274e31e8a2a945bb3bc4a6fb15c2';work=W/'pdf_native_connected_pilot'/id
xml,report=bind((W/'pdf_native_pilot'/id/'diagram.drawio').read_text(),json.loads((work/'source_dom.json').read_text()),(W/'tikz_pilot'/id/'source.tex').read_text());print(json.dumps(report));(work/'diagram.drawio').write_text(xml);(work/'binding.json').write_text(json.dumps(report,indent=2))
