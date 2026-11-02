import unittest
from compiler_mermaid_alpha_iteration_pool_v2 import independent_components, was_normal_candidate_attempt


def item(identifier, keys, pending=True, known=True):
    return {'request':{'id':identifier,'source':{'code_sha256':'code_'+identifier,'image_sha256':'image_'+identifier}},
            'audit':{},'keys':set(keys),'pending':pending,'known':known}


class TransitiveExclusionTests(unittest.TestCase):
    def test_verified_overlap_deferral_does_not_consume_normal_conversion(self):
        result={'error_type':'ValueError','reason':'retryable_iteration_case_failure','detail':'deferred_birth_verified_active_conversion_overlap'}
        self.assertFalse(was_normal_candidate_attempt({'evaluation_phase':'candidate'},result,False))
        self.assertTrue(was_normal_candidate_attempt({'evaluation_phase':'candidate'},result,True))

    def test_ambiguous_interrupted_spawn_is_not_reexecuted(self):
        self.assertTrue(was_normal_candidate_attempt({'evaluation_phase':'candidate'},{},False))

    def test_baseline_and_existing_control_QA_are_not_normal_conversion(self):
        for phase in ('baseline','control_positive'):
            self.assertFalse(was_normal_candidate_attempt({'evaluation_phase':phase},{},False))

    def test_unsupported_bridge_connects_to_consumed_development(self):
        records=[item('dev',['left'],False),item('unsupported',['left','right'],False),item('candidate',['right'])]
        eligible,_=independent_components(records,{'dev'},set(),set(),set())
        self.assertEqual(eligible,[])
        self.assertEqual(records[-1]['audit']['component_members'],3)

    def test_family_unknown_bridge_blocks_independence_claim(self):
        records=[item('unknown',['family'],False,False),item('candidate',['family'])]
        eligible,_=independent_components(records,set(),set(),set(),set())
        self.assertEqual(eligible,[])
        self.assertEqual(records[-1]['audit']['disposition'],'population_family_unknown_component_not_independent')

    def test_multiple_candidates_in_component_only_one_validation_family(self):
        records=[item('a',['x']),item('bridge',['x','y'],False),item('b',['y'])]
        eligible,_=independent_components(records,set(),set(),set(),set())
        self.assertEqual(len(eligible),1)
        self.assertEqual(set(eligible[0]['cluster_keys'])-{'x','y'},{eligible[0]['cluster']})

    def test_distinct_source_families_are_both_retained(self):
        records=[item('a',['x']),item('b',['y'])]
        eligible,_=independent_components(records,set(),set(),set(),set())
        self.assertEqual({row['id']for row in eligible},{'a','b'})

    def test_cross_format_exact_image_excludes_connected_family(self):
        records=[item('candidate',['x']),item('bridge',['x','y'],False)]
        eligible,_=independent_components(records,set(),set(),{'image_bridge'},set())
        self.assertEqual(eligible,[])

    def test_reserved_hard_key_excludes_transitive_candidate(self):
        records=[item('bridge',['reserved','new'],False),item('candidate',['new'])]
        eligible,_=independent_components(records,set(),set(),set(),{'reserved'})
        self.assertEqual(eligible,[])

    def test_already_qualified_bridge_still_prevents_template_leakage(self):
        records=[item('qualified_development',['x'],False),item('candidate',['x'])]
        eligible,_=independent_components(records,{'qualified_development'},set(),set(),set())
        self.assertEqual(eligible,[])


if __name__=='__main__':unittest.main()
