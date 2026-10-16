import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core


class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.edit = dict(start=2, end=8, speed=1.5, layout='fit', title='제목', footer='', captions=True)

    def test_clips_at_both_boundaries_and_retimes(self):
        segments = [dict(start=0, end=1, text='제외'), dict(start=1, end=3, text='첫 문장'),
                    dict(start=7, end=10, text='마지막'), dict(start=8, end=9, text='제외')]
        result = core.clip_segments(segments, self.edit)
        self.assertEqual([s['text'] for s in result], ['첫 문장', '마지막'])
        self.assertAlmostEqual(result[0]['start'], 0)
        self.assertAlmostEqual(result[0]['end'], 2 / 3)
        self.assertAlmostEqual(result[1]['start'], 10 / 3)
        self.assertAlmostEqual(result[1]['end'], 4)
        self.assertEqual(segments[1]['start'], 1)

    def test_srt_unicode_bom_multiline_roundtrip(self):
        source = '\ufeff1\r\n00:00:01,125 --> 00:00:03,500\r\n한글 자막\r\n둘째 줄\r\n'
        segments = core.parse_srt(source)
        self.assertEqual(core.parse_srt(core.to_srt(segments)), segments)

    def test_reject_invalid_edit(self):
        for updates in [dict(start=-1), dict(end=30), dict(speed=0), dict(speed=float('nan')),
                        dict(start=7.9), dict(theme='invalid'), dict(layout='invalid'), dict(title='가'*57)]:
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                core.validate_edit(self.edit | updates, 12)

    def test_reject_bad_captions_and_identifier(self):
        for item in [dict(start=3,end=2,text='x'), dict(start=0,end=13,text='x'),dict(start=0,end=math.inf,text='x')]:
            with self.assertRaises(ValueError):
                core.validate_segments([item], 12)
        with self.assertRaises(ValueError): core.project_dir('../outside')
        with self.assertRaises(ValueError): core.parse_srt('1\n00:70:00,000 --> 00:71:00,000\nx')

    def test_ass_control_characters_are_literal(self):
        result = core.make_ass([dict(start=0,end=1,text=r'{\pos(0,0)}테스트\N')])
        self.assertNotIn(r'{\pos', result)
        self.assertIn('｛＼pos', result)

    def test_recommendations_have_valid_nonduplicate_ranges(self):
        segments=[dict(start=i*3,end=i*3+3,text=f'중요한 자동 편집 방법 {i}') for i in range(40)]
        candidates=core.recommend(segments,120,20)
        self.assertGreaterEqual(len(candidates),2)
        self.assertLessEqual(len(candidates),5)
        for c in candidates:
            self.assertTrue(0<=c['start']<c['end']<=120)

if __name__ == '__main__': unittest.main()
