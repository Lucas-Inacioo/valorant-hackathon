import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from valorant.ui import data


class StoredOnDiskTests(unittest.TestCase):
    def test_only_the_default_selection_is_kept_on_disk_and_read_back(self):
        calls = []

        @data.stored_on_disk
        def compute(signature, match_ids, kind):
            calls.append((match_ids, kind))
            return {"ids": match_ids, "kind": kind}

        with tempfile.TemporaryDirectory() as folder, patch.object(data, "STORE_DIR", Path(folder)), patch.object(
            data, "default_match_ids", return_value=("a", "b")
        ), patch.object(data, "stored_version", return_value="v1"):
            self.assertEqual({"ids": ("a", "b"), "kind": "x"}, compute("sig", ("a", "b"), "x"))
            self.assertEqual({"ids": ("a", "b"), "kind": "x"}, compute("sig", ("a", "b"), "x"))
            compute("sig", ("a",), "x")
            compute("sig", ("a",), "x")
            self.assertEqual([(("a", "b"), "x"), (("a",), "x"), (("a",), "x")], calls)
            self.assertEqual(1, len(list(Path(folder).glob("*.pkl.gz"))))
            with patch.object(data, "stored_version", return_value="v2"):
                compute("sig", ("a", "b"), "x")
            self.assertEqual(["v2"], [path.name.split("-")[0] for path in Path(folder).glob("*.pkl.gz")])


if __name__ == "__main__":
    unittest.main()
