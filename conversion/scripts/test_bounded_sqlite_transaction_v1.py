import sqlite3
import tempfile
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
import bounded_sqlite_transaction_v1 as b


class BusyTests(unittest.TestCase):
    def test_only_actual_sqlite_busy_codes_are_retryable(self):
        self.assertTrue(b.is_busy(sqlite3.OperationalError('database is locked')));self.assertFalse(b.is_busy(ValueError('database is locked')));self.assertFalse(b.is_busy(sqlite3.OperationalError('disk I/O error')));error=sqlite3.OperationalError('database is locked');error.sqlite_errorcode=1;self.assertFalse(b.is_busy(error))
    def test_begin_never_borrows_a_preexisting_transaction(self):
        db=sqlite3.connect(':memory:');db.execute('create table t(n)');db.execute('insert into t values(1)')
        with self.assertRaises(RuntimeError):b.BusyBudget(1).begin(db)
        self.assertTrue(db.in_transaction);db.rollback();db.close()
    def test_default_driver_busy_timeout_is_removed_and_budget_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'a.sqlite';a=sqlite3.connect(path);a.execute('create table t(n)');a.commit();a.execute('begin immediate');other=sqlite3.connect(path,timeout=30);budget=b.BusyBudget(.15,.1);start=time.monotonic()
            with self.assertRaises(b.BusyBudgetExceeded):budget.begin(other)
            self.assertLess(time.monotonic()-start,1.5);self.assertEqual(other.execute('pragma busy_timeout').fetchone()[0],0);self.assertFalse(other.in_transaction);a.rollback();a.close();other.close()
    def test_business_work_does_not_consume_database_wait_budget(self):
        db=sqlite3.connect(':memory:');db.execute('create table t(n)');budget=b.BusyBudget(.1,.1);budget.begin(db);time.sleep(.15);db.execute('insert into t values(1)');budget.commit(db);self.assertEqual(db.execute('select count(*) from t').fetchone()[0],1);self.assertLess(budget.diagnostics()['wait_seconds'],.1);db.close()
    def test_commit_retries_same_transaction_without_replaying_mutations(self):
        db=sqlite3.connect(':memory:');db.execute('create table t(n)');budget=b.BusyBudget(1,.1);budget.begin(db);db.execute('insert into t values(1)');calls=[]
        def committing(connection,seconds):
            calls.append(1)
            if len(calls)==1:raise sqlite3.OperationalError('database is locked')
            connection.commit()
        with patch.object(b,'durable_commit',side_effect=committing):budget.commit(db)
        self.assertEqual(db.execute('select count(*) from t').fetchone()[0],1);self.assertEqual(len(calls),2);db.close()
    def test_commit_acknowledgement_after_completed_transaction_requires_receipt_probe(self):
        db=sqlite3.connect(':memory:');db.execute('create table t(n)');budget=b.BusyBudget(1,.1);budget.begin(db);db.execute('insert into t values(1)')
        def acklost(connection,seconds):connection.commit();raise sqlite3.OperationalError('database is locked')
        with patch.object(b,'durable_commit',side_effect=acklost),self.assertRaises(sqlite3.OperationalError):budget.commit(db)
        self.assertFalse(db.in_transaction);self.assertEqual(db.execute('select count(*) from t').fetchone()[0],1);self.assertEqual(budget.diagnostics()['commit_attempts'],1);db.close()
    def test_nonbusy_begin_error_is_not_retried(self):
        db=sqlite3.connect(':memory:');budget=b.BusyBudget(1,.1)
        with patch.object(b,'durable_begin',side_effect=sqlite3.OperationalError('disk I/O error')) as call,self.assertRaises(sqlite3.OperationalError):budget.begin(db)
        self.assertEqual(call.call_count,1);self.assertFalse(db.in_transaction);db.close()
    def test_busy_commit_exhaustion_leaves_own_transaction_for_caller_rollback(self):
        db=sqlite3.connect(':memory:');db.execute('create table t(n)');budget=b.BusyBudget(.1,.05);budget.begin(db);db.execute('insert into t values(1)')
        with patch.object(b,'durable_commit',side_effect=sqlite3.OperationalError('database is locked')),self.assertRaises(b.BusyBudgetExceeded):budget.commit(db)
        self.assertTrue(db.in_transaction);db.rollback();self.assertEqual(db.execute('select count(*) from t').fetchone()[0],0);db.close()

if __name__=='__main__':unittest.main()
