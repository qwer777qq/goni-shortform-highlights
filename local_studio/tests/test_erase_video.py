import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from erase_video import clean_video


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class Cleanup(unittest.TestCase):
    def test_region_and_mute_on_real_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / 'input.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=blue:s=320x180:r=10:d=1',
                            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-vf',
                            'drawbox=x=90:y=100:w=100:h=25:color=white:t=fill',
                            '-c:v', 'libx264', '-c:a', 'aac', str(source)], check=True)
            result = clean_video(str(source), str(folder / 'result'), [85, 95, 110, 35], 'mute')
            info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                                       '-of', 'json', result['output']]))
            self.assertEqual([x['codec_type'] for x in info['streams']], ['video'])
            self.assertEqual(result['method'], 'ffmpeg delogo spatial interpolation')
            def pixel(path):
                return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-frames:v', '1',
                                                '-vf', 'crop=2:2:120:110,scale=1:1', '-pix_fmt', 'rgb24',
                                                '-f', 'rawvideo', '-'])
            before, after = pixel(source), pixel(result['output'])
            self.assertGreater(before[0], 200)
            self.assertLess(after[0], 100)
            self.assertGreater(after[2], 150)
            with self.assertRaises(ValueError):
                clean_video(str(source), str(folder / 'result'))


if __name__ == '__main__':
    unittest.main()
