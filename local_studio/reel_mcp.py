"""Local stdio MCP. Direct rendering by default; --port opts into legacy HTTP."""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from mcp.server.fastmcp import FastMCP

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, help='Optional legacy studio HTTP port')
parser.add_argument('--data-dir', type=Path, help='Standalone project storage; no HTTP server needed')
args = parser.parse_args()
if args.port is not None and not 1024 <= args.port <= 65535:
    parser.error('port must be 1024..65535')
if args.port is not None and args.data_dir is not None:
    parser.error('--data-dir cannot be combined with legacy --port')
BASE = f'http://127.0.0.1:{args.port}'
mcp = FastMCP('Goni Reel Engine')
engine = None
if args.port is None:
    import core
    import reel
    from reel_direct import Engine
    engine = Engine(args.data_dir)


def request(path, data=None):
    req = Request(BASE + path, data=json.dumps(data, ensure_ascii=False).encode('utf-8') if data is not None else None,
                  headers={'Content-Type': 'application/json', 'X-Studio-Request': '1'})
    try:
        with urlopen(req, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise ValueError(error.read().decode('utf-8')) from error


def identifier(value):
    import re
    if not re.fullmatch('[a-f0-9]{32}', value):
        raise ValueError('Invalid project/job id')
    return value


@mcp.tool()
def studio_status() -> dict:
    """Check mode and FFmpeg. Default standalone mode needs no editor/server/browser."""
    if engine:
        return engine.status()
    return request('/api/config')


@mcp.tool()
def list_projects() -> dict:
    """List imported local projects."""
    if engine:
        return engine.list_projects()
    return {'projects': request('/api/projects')}


@mcp.tool()
def import_video(path: str) -> dict:
    """Import the user-selected local video (copies it). Returns a job id; poll job_status."""
    if engine:
        return engine.import_video(path)
    return request('/api/import', {'path': path})


@mcp.tool()
def get_project(project_id: str) -> dict:
    """Read source metadata, saved reel plan and verified render paths."""
    if engine:
        return core.read_project(identifier(project_id))
    return request('/api/projects/' + identifier(project_id))


@mcp.tool()
def reel_preset(project_id: str) -> dict:
    """Get an evenly sampled four-cut draft. Does NOT analyze semantics or music beats."""
    if engine:
        return reel.preset(core.read_project(identifier(project_id))['meta']['duration'])
    return request('/api/reel/preset', {'id': identifier(project_id)})


@mcp.tool()
def save_reel(project_id: str, plan: dict) -> dict:
    """Validate/save a multi-cut plan. ratio landscape/portrait, layout fit/crop, audio source/continuous/mute.
    clips: start/end source seconds, speed .5..2, contrast .5..1.8, brightness -.2...2,
    saturation 0..2, zoom 1..1.3, invert/flash arrays of [start,end] in clip OUTPUT seconds.
    Effects use half-open windows. New renders never overwrite old versions.
    """
    if engine:
        return engine.save(identifier(project_id), plan)
    return request('/api/reel/save', {'id': identifier(project_id), 'plan': plan})


@mcp.tool()
def render_reel(project_id: str) -> dict:
    """Render saved plan locally. Returns job id, not completion. Poll job_status until done/error."""
    if engine:
        return engine.render(identifier(project_id))
    return request('/api/reel/render', {'id': identifier(project_id)})


@mcp.tool()
def job_status(job_id: str) -> dict:
    """Return queued/running/done/error with result. Done includes file path and decode verification."""
    if engine:
        return engine.job_status(identifier(job_id))
    return request('/api/jobs/' + identifier(job_id))


if __name__ == '__main__':
    try:
        mcp.run(transport='stdio')
    finally:
        if engine:
            engine.close()
