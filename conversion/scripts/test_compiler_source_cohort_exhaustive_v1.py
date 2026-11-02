import copy
import unittest
from compiler_source_cohort_exhaustive_v1 import validate


class ExhaustiveSourceCohortTests(unittest.TestCase):
    def fixture(self, count=15):
        info=dict(source_only=True,scope=26754,selected=count,
                  full_scope_manifest=dict(unique_scope=131904,duplicate_scope_rows=0,
                    manifest_sha256='361bce924762d14481da9b541cfbcf0f6879f97618fbc750922ac1c918a70a85'),
                  eligible_observed_families=count,all_remaining_observed_families_selected=True,
                  unknown_families_retained_in_bulk=True,minimum100_met=count==100)
        rows=[dict(id=str(i),cluster='independent:'+str(i),seq=i+1)for i in range(count)]
        return info,rows

    def test_all_fifteen_families_are_valid_without_lowering_gate(self):
        proof=validate(*self.fixture())
        self.assertTrue(proof['shortage_exhaustive_exception'])
        self.assertEqual(proof['fixed_minimum_new_qualified'],5)
        self.assertEqual(proof['fixed_minimum_qualified_fraction'],.2)

    def test_even_three_families_do_not_lower_fixed_plus_five(self):
        self.assertEqual(validate(*self.fixture(3))['fixed_minimum_new_qualified'],5)

    def test_full_hundred_uses_regular_rule(self):
        self.assertFalse(validate(*self.fixture(100))['shortage_exhaustive_exception'])

    def test_empty_is_not_a_successful_validation(self):
        with self.assertRaisesRegex(ValueError,'empty_or_inconsistent'):validate(*self.fixture(0))

    def test_omitted_families_cannot_be_called_exhaustive(self):
        info,rows=self.fixture();info['eligible_observed_families']=16
        with self.assertRaisesRegex(ValueError,'not_proven_exhaustive'):validate(info,rows)

    def test_discarded_unknown_families_invalidates_exception(self):
        info,rows=self.fixture();info['unknown_families_retained_in_bulk']=False
        with self.assertRaisesRegex(ValueError,'not_proven_exhaustive'):validate(info,rows)

    def test_incomplete_global_scope_invalidates_exception(self):
        info,rows=self.fixture();info['full_scope_manifest']['unique_scope']-=1
        with self.assertRaisesRegex(ValueError,'not_proven_exhaustive'):validate(info,rows)

    def test_same_family_cannot_count_twice(self):
        info,rows=self.fixture();rows[1]['cluster']=rows[0]['cluster']
        with self.assertRaisesRegex(ValueError,'duplicate_source_cohort_component'):validate(info,rows)

    def test_same_original_cannot_count_twice(self):
        info,rows=self.fixture();rows[1]['id']=rows[0]['id']
        with self.assertRaisesRegex(ValueError,'duplicate_source_cohort_original'):validate(info,rows)

    def test_reordering_is_rejected(self):
        info,rows=self.fixture();rows.reverse()
        with self.assertRaisesRegex(ValueError,'order_changed'):validate(info,rows)


if __name__=='__main__':unittest.main()
