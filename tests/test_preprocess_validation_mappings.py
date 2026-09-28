import unittest

import pandas as pd

from scripts.preprocess_data import map_nhanes_yes_no, nhanes_bp_meds_feature


class TestNhanesBinaryMapping(unittest.TestCase):
    def test_only_explicit_yes_no_codes_are_mapped(self):
        mapped = map_nhanes_yes_no(pd.Series([1, 2, 3, 7, 9, None]))
        self.assertEqual(mapped.iloc[0], 1.0)
        self.assertEqual(mapped.iloc[1], 0.0)
        self.assertTrue(mapped.iloc[2:].isna().all())

    def test_bp_meds_uses_bpq050a_and_never_falls_back_to_label(self):
        raw = pd.DataFrame({"BPQ020": [1, 2]})
        self.assertTrue(nhanes_bp_meds_feature(raw).isna().all())
        raw["BPQ050A"] = [2, 1]
        mapped = nhanes_bp_meds_feature(raw)
        self.assertEqual(mapped.tolist(), [0.0, 1.0])


if __name__ == "__main__":
    unittest.main()
