"""Schema-version and migration tests for storage.init_db."""

import os
import tempfile
import unittest
from unittest import mock

import storage


class SchemaVersionTestCase(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        os.unlink(self.db_path)
        self.original_db_path = storage.DB_PATH
        storage.DB_PATH = self.db_path

    def tearDown(self):
        storage.DB_PATH = self.original_db_path
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db_path + suffix)
            except FileNotFoundError:
                pass

    def _version(self):
        with storage._connect() as connection:
            return int(connection.execute("PRAGMA user_version").fetchone()[0])

    def test_fresh_database_is_stamped(self):
        storage.init_db()
        self.assertEqual(self._version(), storage.SCHEMA_VERSION)

    def test_init_is_idempotent(self):
        storage.init_db()
        storage.init_db()
        self.assertEqual(self._version(), storage.SCHEMA_VERSION)

    def test_newer_database_refuses_to_start(self):
        storage.init_db()
        with storage._connect() as connection:
            connection.execute("PRAGMA user_version = 99")
        with self.assertRaises(RuntimeError):
            storage.init_db()

    def test_pending_migration_runs_once(self):
        calls = []

        def migrate(connection):
            calls.append(1)
            connection.execute("CREATE TABLE migration_probe (id INTEGER)")

        with mock.patch.object(storage, "SCHEMA_VERSION", 2), mock.patch.dict(
            storage.MIGRATIONS, {2: migrate}
        ):
            storage.init_db()
            self.assertEqual(self._version(), 2)
            storage.init_db()
        self.assertEqual(calls, [1])


if __name__ == "__main__":
    unittest.main()
