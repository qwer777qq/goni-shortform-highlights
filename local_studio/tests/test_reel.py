import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
import reel


class Validation(unittest.TestCase):
    def plan(self):
        return dict(clips=[dict(start=0, end=1, speed=1, invert=[[0,.067]])])

    def test_reject_invalid_and_nonfinite(self):
        for key, value in [('start', -1), ('end', 4), ('speed', 0), ('speed', float('nan')),
                           ('zoom', 2), ('invert', [[.2,.1]]), ('flash', [[0,2]]),
                           ('contrast', "1; injected"), ('brightness', float('inf'))]:
            plan = self.plan(); plan['clips'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                reel.validate(plan, 2)

    def test_silence_short_music_and_empty(self):
        for patch in [dict(clips=[]), dict(ratio='square'), dict(layout='unknown'),
                      dict(audio='continuous', audio_start=1.5)]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                reel.validate(self.plan() | patch, 2)

    def test_speed_frame_math_and_half_open_effect(self):
        plan = self.plan(); plan['clips'][0]['speed'] = 2
        checked = reel.validate(plan, 2)
        self.assertEqual(checked['duration'], .5)
        self.assertIn('lt(t,0.067000)', reel.filters(checked['clips'][0], checked))


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
class Render(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.old_data = core.DATA
        core.DATA = Path(cls.temp.name) / 'data'
        cls.input = Path(cls.temp.name) / 'colors.mp4'
        core.run(['ffmpeg','-v','error','-f','lavfi','-i','color=red:s=320x180:r=30:d=1',
                  '-f','lavfi','-i','color=blue:s=320x180:r=30:d=1',
                  '-f','lavfi','-i','sine=frequency=440:duration=2:sample_rate=48000',
                  '-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map','[v]','-map','2:a',
                  '-c:v','libx264','-c:a','aac', str(cls.input)])
        cls.project = core.import_file(cls.input)

    @classmethod
    def tearDownClass(cls):
        core.DATA = cls.old_data
        cls.temp.cleanup()

    def pixel(self, file, time):
        cmd=['ffmpeg','-v','error','-ss',str(time),'-i',str(file),'-frames:v','1',
             '-vf','scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-']
        return tuple(subprocess.check_output(cmd))

    def test_reordered_effects_audio_and_versioning(self):
        plan=dict(audio='continuous', clips=[dict(start=1,end=2,invert=[[0,.2]]),dict(start=0,end=1,speed=2)])
        reel.save(self.project['id'], plan)
        a=reel.render(self.project['id']); b=reel.render(self.project['id'])
        self.assertNotEqual(a['path'], b['path'])
        self.assertTrue(Path(a['path']).is_file())
        r,g,blue=self.pixel(a['path'],.1)
        self.assertGreater(r,180); self.assertGreater(g,180); self.assertLess(blue,80)
        r,g,blue=self.pixel(a['path'],.5)
        self.assertGreater(blue,180); self.assertLess(r,80)
        r,g,blue=self.pixel(a['path'],1.2)
        self.assertGreater(r,180); self.assertLess(blue,80)
        meta=core.probe(a['path'])
        self.assertTrue(meta['has_audio']); self.assertAlmostEqual(meta['duration'],1.5,delta=.1)
        project=core.read_project(self.project['id'])
        self.assertEqual(len(project['reel_exports']),2)
        self.assertEqual(project['reel']['clips'][0]['start'],1)

    def test_portrait_silent_input(self):
        silent=Path(self.temp.name)/'silent.mp4'
        core.run(['ffmpeg','-v','error','-i',str(self.input),'-an','-c:v','copy',str(silent)])
        p=core.import_file(silent)
        result=reel.render(p['id'],dict(ratio='portrait',audio='source',clips=[dict(start=0,end=.25,flash=[[0,.067]])]))
        meta=core.probe(result['path'])
        self.assertEqual((meta['width'],meta['height']),(1080,1920))
        self.assertTrue(meta['has_audio'])  # silence track keeps concatenation deterministic


if __name__=='__main__':
    unittest.main()
