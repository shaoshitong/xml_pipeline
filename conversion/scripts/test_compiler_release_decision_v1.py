"""Preregistered release gate boundaries, using synthetic result metadata only."""
import unittest
from compiler_evaluate_validation_v1 import decision


class ReleaseDecisionTests(unittest.TestCase):
    def pairs(self,n=30,passed=6):
        return [dict(id=str(i),cluster='cluster'+str(i),B='abandoned',
                     C='qualified' if i<passed else 'abandoned',infrastructure_failure=False) for i in range(n)]

    def test_default_twenty_percent_boundary_and_new_gain(self):
        result=decision(self.pairs())
        self.assertTrue(result['passed']);self.assertEqual(result['new_qualified_clusters'],6)

    def test_five_successes_out_of_thirty_is_insufficient(self):
        self.assertFalse(decision(self.pairs(passed=5))['passed'])

    def test_baseline_overlap_does_not_count_as_conversion_gain(self):
        pairs=self.pairs();pairs[0]['B']=pairs[1]['B']='qualified'
        result=decision(pairs);self.assertEqual(result['new_qualified_clusters'],4);self.assertFalse(result['passed'])

    def test_baseline_positive_regression_blocks_even_with_net_gain(self):
        pairs=self.pairs(passed=12);pairs[-1]['B']='qualified'
        self.assertFalse(decision(pairs)['passed'])

    def test_same_cluster_does_not_count_as_thirty_unseen_clusters(self):
        pairs=self.pairs()
        for row in pairs:row['cluster']='same'
        self.assertFalse(decision(pairs)['passed'])

    def test_infrastructure_or_controls_failure_blocks(self):
        pairs=self.pairs();pairs[-1]['infrastructure_failure']=True
        self.assertFalse(decision(pairs)['passed']);self.assertFalse(decision(self.pairs(),False)['passed'])

    def test_small_fully_successful_cohort_cannot_replace_sample_size(self):
        self.assertFalse(decision(self.pairs(n=29,passed=29))['passed'])


if __name__=='__main__':unittest.main()
