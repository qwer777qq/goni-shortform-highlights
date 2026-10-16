"""Local adapter: transcript preparation and agent-selected highlight export."""
import argparse
import importlib.util
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='local_studio directory')
    parser.add_argument('--port', type=int, default=8767)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare')
    source = prepare.add_mutually_exclusive_group(required=True)
    source.add_argument('--video', type=Path)
    source.add_argument('--url')
    prepare.add_argument('--srt', type=Path)
    prepare.add_argument('--model', choices=['tiny','base','small','medium'], default='small')
    export = sub.add_parser('export')
    export.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    base = f'http://127.0.0.1:{args.port}'
    def api(route, body=None):
        data = None if body is None else json.dumps(body).encode('utf-8')
        request = Request(base + route, data=data, headers={'Content-Type':'application/json','X-Studio-Request':'1'})
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(error.read().decode('utf-8', errors='replace')) from error
    def wait(job):
        deadline = time.monotonic() + 14400
        while job['status'] in ('queued','running'):
            if time.monotonic() > deadline:
                raise TimeoutError(f'Job {job["id"]} still running; inspect before retrying.')
            time.sleep(1)
            job = api('/api/jobs/' + job['id'])
        if job['status'] != 'done':
            raise RuntimeError(job['message'])
        return job['result']
    config = api('/api/config')
    if Path(config['data_dir']).resolve() != root / 'data':
        raise RuntimeError('Running server data directory does not match --root; no write performed.')
    if args.action == 'prepare':
        srt = args.srt.read_text(encoding='utf-8-sig') if args.srt else None
        job = api('/api/import', {'path':str(args.video.resolve())}) if args.video else api('/api/youtube', {'url':args.url})
        project = wait(job)['project']
        print(json.dumps({'imported_project_id':project['id']},ensure_ascii=False),flush=True)
        if srt is not None:
            project = api('/api/srt', {'id':project['id'],'text':srt})
        else:
            project = wait(api('/api/transcribe', {'id':project['id'],'model':args.model}))['project']
        transcript = root / 'data' / project['id'] / 'transcript.json'
        transcript.write_text(json.dumps({'project_id':project['id'],'duration':project['meta']['duration'],
                                           'segments':project['segments']},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'project_id':project['id'],'transcript':str(transcript),'next':'Read complete transcript and choose grounded clips.'},ensure_ascii=False))
        return
    plan = json.loads(args.plan.read_text(encoding='utf-8-sig'))
    # Load the project's own validator so export and UI have the same contract.
    spec = importlib.util.spec_from_file_location('studio_core', root / 'core.py')
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    project_id = plan['project_id']
    core.project_dir(project_id)
    project = api('/api/projects/' + project_id)
    clips = plan.get('clips')
    if not isinstance(clips,list) or not 1 <= len(clips) <= 10:
        raise ValueError('Provide 1 to 10 selected clips.')
    edits = [core.validate_edit(project['edit'] | clip,project['meta']['duration']) for clip in clips]
    report = {'project_id':project_id,'brief':plan.get('brief',''),'completed':[],'status':'running'}
    result_path = root / 'data' / project_id / ('export-result-' + str(time.time_ns()) + '.json')
    def record():
        result_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    record()
    try:
        for clip, edit in zip(clips,edits):
            api('/api/save',{'id':project_id,'edit':edit})
            result = wait(api('/api/render',{'id':project_id}))
            folder = root / 'data' / project_id / 'exports' / result['export']['id']
            report['completed'].append({'reason':clip.get('reason',''),'edit':edit,'output':str(folder / 'short.mp4'),
                                         'captions':str(folder/'captions.srt'),'preview_thumbnail':str(folder/'thumbnail.jpg')})
            record()
        report['status'] = 'done'
    except Exception as error:
        report.update(status='error',error=str(error))
        raise
    finally:
        record()
        print(json.dumps({'status':report['status'],'report':str(result_path),'completed':len(report['completed'])},ensure_ascii=False))

if __name__ == '__main__':
    main()
