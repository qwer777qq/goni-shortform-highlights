"""Independent template behaviours; no third-party code or media."""
import json, re
from pathlib import Path
CATALOG = json.loads((Path(__file__).with_name('template_catalog.json')).read_text(encoding='utf-8'))
PRESETS = {item['id']: item for item in CATALOG}

def escape_ass(text):
    return text.replace('\\', '＼').replace('{', '｛').replace('}', '｝')

def word_cues(segment):
    """Uniform word timing, NOT forced alignment or measured word timestamps."""
    words = re.findall(r'\S+', segment['text'])
    if not words:
        return []
    step = (segment['end'] - segment['start']) / len(words)
    return [dict(start=segment['start']+i*step, end=segment['start']+(i+1)*step,
                 word=word, index=i, words=words) for i,word in enumerate(words)]

def timed_text(segment, style):
    if style == 'standard':
        return [(segment['start'], segment['end'], escape_ass(segment['text']))]
    rows=[]
    for cue in word_cues(segment):
        if style == 'pop':
            # Shrink long single tokens rather than letting them leave the frame.
            size=min(88, max(24, int(860/max(1,len(cue['word'])))))
            text=r'{\an2\fs'+str(size)+r'\fscx92\fscy92\t(0,110,\fscx100\fscy100)}'+escape_ass(cue['word'])
        else:
            # Keep per-line width bounded and highlight the currently timed token.
            parts=[]; count=0
            for j, word in enumerate(cue['words']):
                for offset in range(0,len(word),14):
                    chunk=word[offset:offset+14]
                    if count and count+len(chunk)+1>14:
                        parts.append(r'\N'); count=0
                    elif count:
                        parts.append(' '); count+=1
                    parts.append((r'{\c&HCBF580&}' if j==cue['index'] else r'{\c&HFFFFFF&}')+escape_ass(chunk))
                    count+=len(chunk)
            text=''.join(parts)
        rows.append((cue['start'],cue['end'],text))
    return rows

def decorate(draw, edit, font_path):
    from PIL import ImageFont
    key=edit.get('theme','safe')
    if key=='dark-red':
        draw.rounded_rectangle((90,366,990,378),6,fill='#FF555B')
    elif key=='white-yellow':
        draw.rounded_rectangle((70,90,1010,360),28,fill='#FFE56B')
    elif key=='paper-story':
        draw.line((90,90,990,90),fill='#B8A286',width=3)
        draw.line((90,370,990,370),fill='#B8A286',width=3)
    elif key=='comment-capture':
        draw.rounded_rectangle((80,1510,1000,1800),28,fill='#FFFFFF')
        draw.text((120,1535),'작성 문구 · 댓글 형식',font=ImageFont.truetype(str(font_path),30),fill='#687080')
        content=edit.get('comment','').strip() or '댓글 문구를 입력하세요'
        for size in range(46,21,-2):
            f=ImageFont.truetype(str(font_path),size);lines=[];line=''
            for char in content.replace('\n',' '):
                if draw.textlength(line+char,font=f)>820:
                    lines.append(line);line=''
                line+=char
            lines.append(line)
            if len(lines)<=3:break
        for i,line in enumerate(lines):
            draw.text((120,1590+i*(size+12)),line,font=f,fill='#171C25')
