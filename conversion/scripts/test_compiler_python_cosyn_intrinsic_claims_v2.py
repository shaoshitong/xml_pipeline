import datetime
import unittest

import compiler_python_cosyn_intrinsic_claims_v2 as claims


class ClaimIdentityTests(unittest.TestCase):
    def job(self,pid,updated='2026-11-01T00:00:00+00:00'):
        row=[None]*13;row[12]=pid;row[8]=updated;return tuple(row)

    def test_missing_claim_requires_no_process_probe(self):
        self.assertFalse(claims.inspect(self.job(None),process_identity=lambda _:self.fail('unexpected probe'))['blocked'])

    def test_dead_PID_claim_is_preserved_and_does_not_block(self):
        job=self.job(123);out=claims.inspect(job,process_identity=lambda _:None)
        self.assertFalse(out['blocked']);self.assertFalse(out['canonical_claim_changed']);self.assertEqual(out['stored_worker_pid'],123);self.assertEqual(job[12],123)

    def test_zombie_is_not_active(self):
        self.assertFalse(claims.inspect(self.job(123),process_identity=lambda _:dict(state='Z',start_ticks=100))['blocked'])

    def test_live_reused_PID_born_after_claim_is_not_its_owner(self):
        timestamp=datetime.datetime.fromisoformat('2026-11-01T00:00:00+00:00').timestamp()
        out=claims.inspect(self.job(123),process_identity=lambda _:dict(state='S',start_ticks=1000),boot_time=timestamp,ticks_per_second=100)
        self.assertFalse(out['blocked']);self.assertEqual(out['disposition'],'time_proved_reused_PID_claim_preserved')

    def test_live_earlier_birth_is_conservatively_pending(self):
        timestamp=datetime.datetime.fromisoformat('2026-11-01T00:00:00+00:00').timestamp()
        self.assertTrue(claims.inspect(self.job(123),process_identity=lambda _:dict(state='S',start_ticks=100),boot_time=timestamp-20,ticks_per_second=100)['blocked'])

    def test_live_claim_without_timestamp_proof_stays_pending(self):
        self.assertTrue(claims.inspect(self.job(123,'not-a-time'),process_identity=lambda _:dict(state='S',start_ticks=100),boot_time=0,ticks_per_second=100)['blocked'])

if __name__=='__main__':unittest.main()
