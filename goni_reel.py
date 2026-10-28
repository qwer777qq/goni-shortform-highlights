"""Single-command local video render; no editor, web server or MCP required."""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'local_studio'))
import core
import reel


def main():
    parser = argparse.ArgumentParser(description='고니 독립 영상 엔진: 원본 + 편집 JSON → MP4')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New output folder; never overwrites')
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists():
        parser.error('출력 폴더가 이미 있습니다. 새 폴더 이름을 입력하세요.')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        parser.error('FFmpeg와 ffprobe를 PATH에 설치하세요.')
    # Validate before creating the output directory or copying source media.
    plan = reel.validate(json.loads(args.plan.read_text(encoding='utf-8-sig')),
                         core.probe(args.input.expanduser().resolve())['duration'])
    output.mkdir(parents=True)
    core.DATA = output / 'projects'
    try:
        project = core.import_file(args.input, preview=False)
        reel.save(project['id'], plan)
        result = reel.render(project['id'], plan,
                             lambda percent, message: print(f'{percent:.0f}% {message}', file=sys.stderr))
        rendered = Path(result['path']).parent
        for name in ('reel.mp4', 'edit.json', 'poster.jpg', 'verification.json', 'commands.json'):
            shutil.copy2(rendered / name, output / name)
        report = {'mode': 'standalone', 'server_required': False, 'project_id': project['id'],
                  'video': str(output / 'reel.mp4'), 'render': result}
        (output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as error:
        (output / 'failure.json').write_text(json.dumps({'error': str(error)}, ensure_ascii=False), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
