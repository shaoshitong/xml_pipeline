import copy
import unittest
from arxiv_pair_identity_admission_v1 import admit_unique

def row(name, code, pixels, width=20):
    return dict(id=name, code_sha256=code*64,
                image_pixels=dict(width=width,height=30,rgba_sha256=pixels*64))

class PairIdentityAdmissionTest(unittest.TestCase):
    def test_independent_code_and_pixel_duplicates(self):
        base=[row('base','a','b')]
        candidates=[row('same_code','a','c'),row('same_pixels','d','b'),row('new','e','f'),row('new_code_duplicate','e','1'),row('new_pixel_duplicate','2','f')]
        accepted, rejected=admit_unique(base,candidates)
        self.assertEqual([r['id'] for r in accepted],['new'])
        self.assertEqual(len(rejected),4)
        self.assertIn('duplicate_code_SHA256',rejected[0]['reasons'])
        self.assertIn('duplicate_dimensions_prefixed_RGBA_SHA256',rejected[1]['reasons'])
    def test_baseline_and_original_rows_unchanged(self):
        base=[row('old1','a','b'),row('old2','c','b')]
        candidates=[row('new','d','e')]
        before=copy.deepcopy((base,candidates))
        accepted,rejected=admit_unique(base,candidates)
        self.assertEqual((base,candidates),before)
        self.assertIs(accepted[0],candidates[0])
        self.assertFalse(rejected)
    def test_rejected_other_identity_does_not_poison_future(self):
        accepted,_=admit_unique([row('old','a','b')],[row('rejected','a','c'),row('new','d','c')])
        self.assertEqual([r['id'] for r in accepted],['new'])
    def test_dimensions_distinguish_pixel_layout(self):
        accepted,_=admit_unique([row('old','a','b')],[row('new','c','b',width=30)])
        self.assertEqual(len(accepted),1)
    def test_invalid_proof_identity_fails_closed(self):
        for key,value in [('code_sha256','not-a-hash'),('image_pixels',dict(width=0,height=30,rgba_sha256='b'*64))]:
            bad=row('bad','c','d');bad[key]=value
            with self.assertRaises(ValueError):admit_unique([], [bad])

if __name__=='__main__':unittest.main()
