"""Hash-pinned native author source control envelope, no execution."""
from pathlib import Path
import hashlib,json
P=Path('/backup/shaoshitong/img2code_20261029/release/compiler_iterations/controls/drawio_author_raw_template_native_controls_20261101_v3/proof.json')
def verify():
 import drawio_author_iteration_program_v2 as program
 from compiler_types_program_v1 import asset
 bundle=json.loads(P.read_bytes());bundle['definition']=asset(P);program.check_controls(bundle);return bundle
def configuration():
 verify();return {str(P):hashlib.sha256(P.read_bytes()).hexdigest()}
