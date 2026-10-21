import unittest
import numpy as np
from pixel_color_stabilizer.core import temporal_mode

RED = [200, 30, 30, 255]
BLUE = [20, 30, 200, 255]


class TemporalModeTests(unittest.TestCase):
    def frames(self, n=5):
        arrays = [np.zeros((6, 7, 4), np.uint8) for _ in range(n)]
        for i, a in enumerate(arrays):
            a[1:5, 1:6] = RED
            a[2, 2] = BLUE if i in (1, 3) else RED
        return arrays

    def test_scoped_mode_keeps_input_and_outside_range_and_region(self):
        arrays = self.frames(); original = [a.copy() for a in arrays]
        result, report = temporal_mode(arrays, 2, 4, [{'x': 2, 'y': 2, 'width': 1, 'height': 1}])
        # Frames 2..4: blue/red/blue -> blue. Exactly one sample changes.
        expected = [a.copy() for a in arrays]; expected[2][2, 2] = BLUE
        for actual, base, wanted in zip(arrays, original, result):
            np.testing.assert_array_equal(actual, base)
        for actual, wanted in zip(result, expected):
            np.testing.assert_array_equal(actual, wanted)
        self.assertEqual(report['changed_pixels'], 1)
        self.assertEqual(report['changed_positions'], 1)

    def test_ties_take_first_occurrence_and_overlaps_do_not_double_count(self):
        arrays = self.frames(2); arrays[0][2, 2] = BLUE; arrays[1][2, 2] = RED
        rect = {'x': 2, 'y': 2, 'width': 1, 'height': 1}
        result, report = temporal_mode(arrays, 1, 2, [rect, rect])
        self.assertEqual(result[1][2, 2].tolist(), BLUE)
        self.assertEqual(report['selected_pixels'], 1)
        self.assertEqual(report['changed_pixels'], 1)

    def test_transparency_never_votes_or_changes_including_hidden_rgb(self):
        arrays = self.frames(5)
        for a in arrays[:3]:
            a[2, 2] = [66, 77, 88, 0]
        arrays[3][2, 2] = BLUE; arrays[4][2, 2] = RED
        result, _ = temporal_mode(arrays, 1, 5, [{'x': 2, 'y': 2, 'width': 2, 'height': 2}])
        for i in range(5):
            np.testing.assert_array_equal(result[i][..., 3], arrays[i][..., 3])
        self.assertEqual(result[0][2, 2].tolist(), [66, 77, 88, 0])
        self.assertEqual(result[4][2, 2].tolist(), BLUE)

    def test_min_ratio_can_preserve_uncertain_coordinates(self):
        arrays = self.frames(2)
        result, report = temporal_mode(arrays, 1, 2, [{'x': 2, 'y': 2, 'width': 1, 'height': 1}], .75)
        self.assertEqual(report['changed_pixels'], 0)
        for a, b in zip(arrays, result):
            np.testing.assert_array_equal(a, b)

    def test_invalid_bounds_and_partial_alpha_fail(self):
        arrays = self.frames()
        for start, end, rects in [(0, 3, []), (4, 2, []), (1, 6, []),
                                  (1, 2, [{'x': 6, 'y': 0, 'width': 2, 'height': 1}]),
                                  (True, 2, [{'x': 1, 'y': 1, 'width': 2, 'height': 2}])]:
            with self.assertRaises(ValueError):
                temporal_mode(arrays, start, end, rects)
        arrays[0][0, 0, 3] = 128
        with self.assertRaises(ValueError):
            temporal_mode(arrays, 1, 2, [{'x': 1, 'y': 1, 'width': 2, 'height': 2}])

    def test_optional_cleanup_repairs_new_boundary_orphan_only_in_explicit_halo(self):
        arrays = [np.full((6, 7, 4), BLUE, np.uint8) for _ in range(3)]
        arrays[0][2, 2:4] = RED
        for a in arrays[1:]:
            a[2, 3:5] = RED
        rect = [{'x': 2, 'y': 2, 'width': 1, 'height': 1}]
        unchanged_boundary, _ = temporal_mode(arrays, 1, 3, rect, cleanup_isolated=True)
        self.assertEqual(unchanged_boundary[0][2, 3].tolist(), RED)
        result, report = temporal_mode(arrays, 1, 3, rect, cleanup_isolated=True, cleanup_halo=1)
        self.assertEqual(result[0][2, 3].tolist(), BLUE)
        self.assertEqual(report['cleanup_changed_pixels'], 1)
        self.assertEqual(report['changed_pixels'], 2)
        for old, new in zip(arrays, result):
            np.testing.assert_array_equal(old[..., 3], new[..., 3])
            difference = np.any(old != new, axis=2)
            difference[1:4, 1:4] = False
            self.assertFalse(difference.any())

    def test_cleanup_options_reject_ambiguous_types(self):
        rect = [{'x': 2, 'y': 2, 'width': 1, 'height': 1}]
        for options in ({'cleanup_isolated': 'false'}, {'cleanup_halo': True}, {'cleanup_halo': 2}):
            with self.assertRaises(ValueError):
                temporal_mode(self.frames(), 1, 3, rect, **options)

    def test_majority_empty_clears_every_frame_and_hidden_rgb(self):
        arrays = self.frames()
        for a in arrays[:3]:
            a[2, 2] = [66, 77, 88, 0]
        result, report = temporal_mode(arrays, 1, 5, [{'x': 2, 'y': 2, 'width': 1, 'height': 1}], alpha_mode='majority')
        for a in result:
            self.assertEqual(a[2, 2].tolist(), [0, 0, 0, 0])
        self.assertEqual(report['cleared_pixels'], 2)
        self.assertEqual(report['filled_pixels'], 0)
        self.assertTrue(report['alpha_changed'])

    def test_majority_counts_all_opaque_colors_together_before_choosing_rgb(self):
        arrays = self.frames()
        for a, value in zip(arrays, ([9, 8, 7, 0], RED, BLUE, [1, 2, 3, 0], RED)):
            a[2, 2] = value
        original = [a.copy() for a in arrays]
        result, report = temporal_mode(arrays, 1, 5, [{'x': 2, 'y': 2, 'width': 1, 'height': 1}], alpha_mode='majority')
        # Empty has two votes, red two, blue one. Occupancy is 3/5: fill red.
        for a in result:
            self.assertEqual(a[2, 2].tolist(), RED)
        for a, b in zip(arrays, original):
            np.testing.assert_array_equal(a, b)
        self.assertEqual(report['filled_pixels'], 2)
        self.assertEqual(report['cleared_pixels'], 0)

    def test_half_empty_tie_fills_and_color_tie_is_first_observed(self):
        arrays = self.frames(4)
        for a, value in zip(arrays, ([0, 0, 0, 0], BLUE, [0, 0, 0, 0], RED)):
            a[2, 2] = value
        result, _ = temporal_mode(arrays, 1, 4, [{'x': 2, 'y': 2, 'width': 1, 'height': 1}], alpha_mode='majority')
        for a in result:
            self.assertEqual(a[2, 2].tolist(), BLUE)

    def test_majority_respects_rectangles_and_inclusive_frame_range(self):
        arrays = self.frames()
        arrays[1][2, 2, 3] = 0
        expected = [a.copy() for a in arrays]
        # 2..4 contains empty/red/blue -> two opaque votes; first opaque is red.
        for a in expected[1:4]:
            a[2, 2] = RED
        result, _ = temporal_mode(arrays, 2, 4, [{'x': 2, 'y': 2, 'width': 1, 'height': 1}], alpha_mode='majority')
        for a, b in zip(result, expected):
            np.testing.assert_array_equal(a, b)

    def test_majority_cleanup_keeps_selected_rgba_identical_with_moving_neighbors(self):
        arrays = [np.full((6, 7, 4), BLUE, np.uint8) for _ in range(3)]
        arrays[1][:] = [20, 190, 30, 255]
        arrays[2][:] = [20, 190, 30, 255]
        for a in arrays:
            a[2, 2] = RED
        arrays[0][2, 2] = 0
        result, report = temporal_mode(arrays, 1, 3, [{'x': 2, 'y': 2, 'width': 1, 'height': 1}],
                                       alpha_mode='majority', cleanup_isolated=True, cleanup_halo=1)
        for a in result[1:]:
            np.testing.assert_array_equal(a[2, 2], result[0][2, 2])
        self.assertEqual(result[0][2, 2, 3], 255)
        self.assertEqual(report['filled_pixels'], 1)

    def test_majority_rejects_unknown_modes_and_confidence_that_would_break_rule(self):
        rect = [{'x': 2, 'y': 2, 'width': 1, 'height': 1}]
        for options in ({'alpha_mode': 'invalid'}, {'alpha_mode': 'majority', 'min_ratio': .7}):
            with self.assertRaises(ValueError):
                temporal_mode(self.frames(), 1, 3, rect, **options)


