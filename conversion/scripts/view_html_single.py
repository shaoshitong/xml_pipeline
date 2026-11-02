import base64,io
from pathlib import Path
from PIL import Image
W=Path('/backup/shaoshitong/img2code_20261029/conversion');im=Image.open(W/'html_batch_review.jpg').crop((0,470,1200,940));b=io.BytesIO();im.save(b,format='JPEG',quality=55);print(base64.b64encode(b.getvalue()).decode())
