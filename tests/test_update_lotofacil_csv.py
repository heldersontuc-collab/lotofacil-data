import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("updater", ROOT / "scripts/update_lotofacil_csv.py")
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


def result(n, date=None):
    return {"numero": n, "dataApuracao": date or f"{n:02d}/01/2026", "listaDezenas": [f"{x:02d}" for x in range(1, 16)]}


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "draws.csv"
        self.calls = []

    def seed(self, ids, bom=False):
        header = (",".join(u.HEADER) + "\n").encode()
        data = (b"\xef\xbb\xbf" if bom else b"") + header
        self.path.write_bytes(data + b"".join(u.row_bytes(u.official_record(result(n))) for n in ids))
        return self.path.read_bytes()

    def fetcher(self, maximum=5, overrides=None, failure=None):
        def fetch(n=None):
            self.calls.append(n)
            if n == failure and failure is not None:
                raise OSError("network failure")
            return copy.deepcopy((overrides or {}).get(n, result(n or maximum)))
        return fetch

    def test_backfills_every_gap_and_preserves_existing_lines(self):
        before = self.seed([1, 3, 5], bom=True)
        self.assertEqual(u.update(self.path, self.fetcher()), [2, 4])
        after = self.path.read_bytes()
        self.assertTrue(after.startswith(b"\xef\xbb\xbf"))
        for line in before.splitlines(keepends=True):
            self.assertIn(line, after.splitlines(keepends=True))
        self.assertEqual(u.validate_file(self.path), (5, 5))
        self.assertEqual(self.calls, [None, 2, 4])

    def test_multiple_missed_latest_results_are_recovered(self):
        self.seed([1, 2])
        self.assertEqual(u.update(self.path, self.fetcher()), [3, 4, 5])
        self.assertEqual(self.calls, [None, 2, 3, 4])

    def test_no_change_is_byte_idempotent(self):
        before = self.seed(range(1, 6))
        self.assertEqual(u.update(self.path, self.fetcher()), [])
        self.assertEqual(self.path.read_bytes(), before)

    def test_failed_second_missing_fetch_writes_nothing(self):
        before = self.seed([1, 3, 5])
        with self.assertRaises(OSError):
            u.update(self.path, self.fetcher(failure=4))
        self.assertEqual(self.path.read_bytes(), before)

    def test_wrong_requested_contest_writes_nothing(self):
        before = self.seed([1, 3, 5])
        with self.assertRaises(u.ValidationError):
            u.update(self.path, self.fetcher(overrides={2: result(3)}))
        self.assertEqual(self.path.read_bytes(), before)

    def test_stale_api_cannot_regress_database(self):
        before = self.seed(range(1, 6))
        with self.assertRaises(u.ValidationError):
            u.update(self.path, self.fetcher(maximum=4))
        self.assertEqual(self.path.read_bytes(), before)

    def test_existing_max_is_checked_even_when_latest_advanced(self):
        before = self.seed([1, 2])
        bad = result(2)
        bad["listaDezenas"][-1] = "25"
        with self.assertRaises(u.ValidationError):
            u.update(self.path, self.fetcher(overrides={2: bad}))
        self.assertEqual(self.path.read_bytes(), before)

    def test_equal_latest_conflict_is_not_silently_accepted(self):
        before = self.seed(range(1, 6))
        with self.assertRaises(u.ValidationError):
            u.update(self.path, self.fetcher(overrides={None: result(5, "06/01/2026")}))
        self.assertEqual(self.path.read_bytes(), before)

    def test_number_order_does_not_create_false_conflict(self):
        before = self.seed(range(1, 6))
        reversed_numbers = result(5)
        reversed_numbers["listaDezenas"].reverse()
        self.assertEqual(u.update(self.path, self.fetcher(overrides={None: reversed_numbers})), [])
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_payloads_fail_without_writes(self):
        cases = [None, [], {}, result(True, "05/01/2026"), result(5.0, "05/01/2026"), result("05", "05/01/2026")]
        for key, value in [("dataApuracao", "31/02/2026"), ("dataApuracao", "2026-01-05"), ("listaDezenas", [1]*15), ("listaDezenas", list(range(15))), ("listaDezenas", list(range(1, 15)) + [True]), ("listaDezenas", list(range(1, 15)) + [15.0])]:
            bad = result(5)
            bad[key] = value
            cases.append(bad)
        for bad in cases:
            with self.subTest(payload=bad):
                before = self.seed(range(1, 6))
                with self.assertRaises(u.ValidationError):
                    u.update(self.path, self.fetcher(overrides={None: bad}))
                self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_existing_csv_is_never_rewritten(self):
        for ids in ([1, 1], [2, 1]):
            before = self.seed(ids)
            with self.assertRaises(u.ValidationError):
                u.update(self.path, self.fetcher())
            self.assertEqual(self.path.read_bytes(), before)
        for raw in (b"wrong,header\n", b"concurso,data\n1,01/01/2026\n", b"\xff"):
            self.path.write_bytes(raw)
            with self.assertRaises(u.ValidationError):
                u.update(self.path, self.fetcher())
            self.assertEqual(self.path.read_bytes(), raw)

    def test_dates_must_remain_ordered(self):
        before = self.seed([1, 3, 5])
        with self.assertRaises(u.ValidationError):
            u.update(self.path, self.fetcher(overrides={2: result(2, "04/01/2026")}))
        self.assertEqual(self.path.read_bytes(), before)

    def test_validation_rejects_gaps_without_network(self):
        self.seed([1, 3])
        with self.assertRaises(u.ValidationError):
            u.validate_file(self.path)

    def test_new_file_is_complete(self):
        self.assertEqual(u.update(self.path, self.fetcher(maximum=3)), [1, 2, 3])
        self.assertEqual(u.validate_file(self.path), (3, 3))

    def test_quoted_existing_fields_are_preserved(self):
        self.seed([1])
        before = self.path.read_bytes().replace(b"1,01/01/2026", b'"1","01/01/2026"')
        self.path.write_bytes(before)
        u.update(self.path, self.fetcher(maximum=2))
        self.assertTrue(self.path.read_bytes().startswith(before))

    def test_no_final_newline_is_preserved_or_refused_safely(self):
        before = self.seed([1]).rstrip(b"\r\n")
        self.path.write_bytes(before)
        self.assertEqual(u.update(self.path, self.fetcher(maximum=1)), [])
        with self.assertRaises(u.ValidationError):
            u.update(self.path, self.fetcher(maximum=2))
        self.assertEqual(self.path.read_bytes(), before)

    def test_concurrent_local_change_detected(self):
        before = self.seed([1])
        self.path.write_bytes(before + b"external change")
        with self.assertRaises(u.ValidationError):
            u.atomic_write(self.path, b"replacement", before)
        self.assertEqual(self.path.read_bytes(), before + b"external change")
        self.assertEqual(list(self.path.parent.glob(".draws.csv.*")), [])

    def test_atomic_replace_failure_keeps_original(self):
        before = self.seed([1])
        with patch.object(u.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                u.update(self.path, self.fetcher(maximum=2))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob(".draws.csv.*")), [])

    def test_http_timeout_retries_are_bounded(self):
        with patch.object(u.urllib.request, "urlopen", side_effect=TimeoutError()), patch.object(u.time, "sleep"):
            with self.assertRaises(RuntimeError):
                u.fetch(2)
            self.assertEqual(u.urllib.request.urlopen.call_count, 3)

    def test_bad_json_is_not_written(self):
        before = self.seed([1])
        with self.assertRaises(json.JSONDecodeError):
            u.update(self.path, lambda n=None: json.loads("not json"))
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
