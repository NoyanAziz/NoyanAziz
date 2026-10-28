import datetime as dt
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('activity', Path(__file__).resolve().parents[1]/'scripts/update_activity.py')
activity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activity)


def pr(created, merged=None, private=False, added=10, deleted=3):
    return dict(createdAt=created, mergedAt=merged, additions=added, deletions=deleted,
                repository=dict(isPrivate=private))


class ActivityTests(unittest.TestCase):
    now = dt.datetime(2026, 1, 6, 12, tzinfo=dt.timezone.utc)

    def test_old_pr_merged_this_year_counts_merged_not_opened(self):
        result = activity.aggregate([pr('2025-12-20T00:00:00Z', '2026-01-01T00:00:00Z')], self.now)
        self.assertEqual((result['prs_opened'], result['prs_merged']), (0, 1))
        self.assertEqual((result['pr_lines_added'], result['pr_lines_deleted']), (10, 3))
        self.assertEqual(result['lines_added'], 0)  # PR volume never overwrites commit volume.

    def test_private_is_excluded_unless_explicitly_enabled(self):
        rows = [pr('2026-01-05T00:00:00Z', '2026-01-06T00:00:00Z', private=True)]
        self.assertEqual(activity.aggregate(rows, self.now)['prs_opened'], 0)
        result = activity.aggregate(rows, self.now, True)
        self.assertEqual(result['prs_opened'], 1)
        self.assertEqual(result['pr_lines_added'], 10)
        self.assertEqual(activity.aggregate(rows, self.now)['pr_lines_added'], 0)
        self.assertNotIn('repository', str(result))

    def test_week_boundaries_and_future_data(self):
        rows = [pr('2026-01-04T23:59:59Z'), pr('2026-01-05T00:00:00Z'), pr('2026-01-06T13:00:00Z')]
        result = activity.aggregate(rows, self.now)
        self.assertEqual([w['opened'] for w in result['weeks'][-2:]], [1, 1])
        self.assertEqual(result['prs_opened'], 2)
        self.assertEqual(result['lines_added'], 0)
        self.assertEqual(result['pr_lines_added'], 0)

    def test_utc_year_boundary(self):
        rows = [pr('2025-12-31T23:59:59Z', '2025-12-31T23:59:59Z'),
                pr('2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')]
        result = activity.aggregate(rows, self.now)
        self.assertEqual((result['prs_opened'], result['prs_merged']), (1, 1))

    def test_zero_activity_is_valid_svg(self):
        result = activity.aggregate([], self.now)
        root = ET.fromstring(activity.svg(result))
        self.assertEqual(root.tag, '{http://www.w3.org/2000/svg}svg')
        self.assertEqual(len(result['weeks']), 12)

    def test_compact_numbers_preserve_correct_magnitude(self):
        self.assertEqual(activity.compact_number(1_063_040), '1.06M')
        self.assertEqual(activity.compact_number(806_317), '806K')
        self.assertEqual(activity.compact_number(221), '221')

    def test_pr_volume_and_commit_volume_stay_separate_in_card(self):
        result = activity.aggregate([pr('2026-01-01T00:00:00Z', '2026-01-02T00:00:00Z',
                                       added=1_063_040, deleted=806_317)], self.now)
        result.update(lines_added=264_066, lines_deleted=816_541, commits_authored=491,
                      prs_contributed=217, others_prs_contributed=36)
        card = activity.svg(result)
        ET.fromstring(card)
        self.assertIn('1.06M', card)
        self.assertIn('PR lines added', card)
        self.assertIn('commit lines: +264K / −817K', card)
        self.assertEqual(result['pr_lines_added'], 1_063_040)
        self.assertEqual(result['lines_added'], 264_066)


if __name__ == '__main__':
    unittest.main()
