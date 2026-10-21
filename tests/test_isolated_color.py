import unittest
import numpy as np
from pixel_color_stabilizer.isolated_color import isolated_color_mask, merge_isolated_colors


class IsolatedColorTests(unittest.TestCase):
    def test_single_color_dot_joins_surrounding_region_and_preserves_alpha(self):
        a = np.full((7, 7, 4), [70, 80, 90, 255], np.uint8)
        a[3, 3, :3] = [160, 130, 70]
        b, report = merge_isolated_colors(a)
        self.assertTrue(np.array_equal(b[..., 3], a[..., 3]))
        self.assertTrue(np.all(b[..., :3] == [70, 80, 90]))
        self.assertEqual(report['merged'], 1)
        self.assertEqual(report['remaining'], 0)

    def test_diagonal_color_pair_is_not_isolated_or_eroded(self):
        a = np.full((7, 7, 4), [70, 80, 90, 255], np.uint8)
        a[2, 2, :3] = a[3, 3, :3] = [160, 130, 70]
        b, report = merge_isolated_colors(a)
        self.assertFalse(isolated_color_mask(a)[2, 2])
        self.assertTrue(np.array_equal(a, b))
        self.assertEqual(report['merged'], 0)

    def test_transparent_same_rgb_is_not_a_matching_neighbor(self):
        a = np.zeros((5, 5, 4), np.uint8)
        a[2, 2] = [0, 0, 0, 255]
        self.assertTrue(isolated_color_mask(a)[2, 2])
        b, report = merge_isolated_colors(a)
        self.assertTrue(np.array_equal(a, b))
        self.assertEqual(report['unattached_no_region'], 1)

    def test_border_and_original_connected_clusters_remain_safe(self):
        a = np.full((6, 6, 4), [70, 80, 90, 255], np.uint8)
        a[0, 0, :3] = [160, 130, 70]
        a[2:4, 2, :3] = [160, 130, 70]
        b, report = merge_isolated_colors(a)
        self.assertEqual(report['merged'], 1)
        self.assertTrue(np.array_equal(b[2:4, 2], a[2:4, 2]))

    def test_chain_of_original_singletons_can_join_existing_region(self):
        a = np.zeros((7, 7, 4), np.uint8)
        a[3, 1:3] = [70, 80, 90, 255]
        a[3, 3] = [160, 130, 70, 255]
        a[3, 4] = [160, 50, 50, 255]
        b, report = merge_isolated_colors(a)
        self.assertEqual(report['merged'], 2)
        self.assertEqual(report['remaining'], 0)
        self.assertTrue(np.array_equal(a[..., 3], b[..., 3]))


if __name__ == '__main__':
    unittest.main()
