from pathlib import Path
import sys,unittest,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core
from template_styles import CATALOG,word_cues,timed_text

class TemplateTests(unittest.TestCase):
    def test_all_seven_types_validate_and_make_distinct_overlays(self):
        from PIL import Image
        import hashlib
        presets=[x for x in CATALOG if not x['legacy']]
        self.assertEqual(len(presets),7)
        hashes={}
        with tempfile.TemporaryDirectory() as temp:
            for item in presets:
                edit=core.validate_edit(dict(start=0,end=3,speed=1,layout='fit',theme=item['id'],
                    title='긴 제목이 잘리지 않도록 두 줄로 자동 조절합니다',footer='샘플',captions=True,comment='직접 입력한 질문입니다'),3)
                out=Path(temp)/(item['id']+'.png');core.make_overlay(edit,out)
                with Image.open(out) as im:self.assertEqual(im.size,(1080,1920))
                hashes[item['id']]=hashlib.sha256(out.read_bytes()).hexdigest()
            self.assertNotEqual(hashes['white-yellow'],hashes['paper-story'])
            self.assertNotEqual(hashes['dark-red'],hashes['dark-minimal'])

    def test_timing_covers_segment_without_gaps(self):
        cues=word_cues(dict(start=.2,end=1.7,text='첫째 둘째 셋째'))
        self.assertEqual(cues[0]['start'],.2)
        self.assertAlmostEqual(cues[-1]['end'],1.7)
        self.assertEqual(len(cues),3)
        for a,b in zip(cues,cues[1:]):self.assertAlmostEqual(a['end'],b['start'])

    def test_effects_and_ass_escaping(self):
        seg=dict(start=0,end=2,text=r'첫째 {\pos(0,0)} 둘째')
        for mode in ('pop','highlight'):
            rows=timed_text(seg,mode)
            self.assertEqual(len(rows),3)
            self.assertNotIn(r'{\pos',''.join(x[2] for x in rows))
        self.assertIn(r'\t(0,110',core.make_ass([seg],'subtitle-pop'))
        self.assertIn(r'\c&HCBF580&',core.make_ass([seg],'subtitle-highlight'))

    def test_comment_length_and_preservation(self):
        e=dict(start=0,end=2,speed=1,layout='fit',theme='comment-capture',comment='가'*80)
        self.assertEqual(core.validate_edit(e,2)['comment'],e['comment'])
        with self.assertRaises(ValueError):core.validate_edit(e|{'comment':'가'*81},2)
