import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from totobox import theme as T  # noqa: E402
from totobox.screens.mei_video import KONAMI, KonamiWatcher, load_clip  # noqa: E402


class KonamiTest(unittest.TestCase):
    def feed_all(self, w, actions):
        return [w.feed(a) for a in actions]

    def test_exact_code_fires_once_on_last_arrow(self):
        self.assertEqual(self.feed_all(KonamiWatcher(), KONAMI), [False] * 7 + [True])

    def test_extra_ups_before_still_count(self):  # holding up repeats it
        self.assertTrue(self.feed_all(KonamiWatcher(), ("up",) + KONAMI)[-1])

    def test_other_button_breaks_it(self):
        self.assertFalse(any(self.feed_all(KonamiWatcher(), KONAMI[:4] + ("a",) + KONAMI[4:])))

    def test_starts_over_after_firing(self):
        w = KonamiWatcher()
        self.feed_all(w, KONAMI)
        self.assertFalse(w.feed("right"))


class ClipTest(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(T.MEI_VIDEO), "clip not built")
    def test_clip_is_small_and_frames_are_jpegs(self):
        fps, w, h, data, frames = load_clip(T.MEI_VIDEO)
        self.assertEqual((fps, w, h, len(frames)), (20, 216, 384, 120))
        self.assertLess(len(data), 2 * 1024 * 1024)
        for off, size in frames:
            self.assertEqual(bytes(data[off:off + 2]), b"\xff\xd8")
            self.assertEqual(bytes(data[off + size - 2:off + size]), b"\xff\xd9")
