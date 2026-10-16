"""Launch cached official REA 6.5.0 without changing client configuration."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

def locate():
    local = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    for root in [local / 'npm-cache' / '_npx', Path.home() / '.npm' / '_npx']:
        for package in sorted(root.glob('*/node_modules/rea-agents/package.json')):
            try:
                info = json.loads(package.read_text(encoding='utf-8'))
                launcher = package.parent / 'scripts' / 'rea.mjs'
                if info.get('name') == 'rea-agents' and info.get('version') == '6.5.0' and launcher.is_file():
                    return launcher
            except (OSError, ValueError):
                continue
    raise SystemExit('REA cache not found. Acquire official package: npx --yes rea-agents@6.5.0 --help')

if __name__ == '__main__':
    node = shutil.which('node')
    if not node:
        raise SystemExit('Node.js is required.')
    raise SystemExit(subprocess.call([node, str(locate()), *(sys.argv[1:] or ['--help'])], shell=False))
