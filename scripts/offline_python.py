"""Verification wrapper: reject Python network connections while running a script.

This proves our Python adapter needs no HTTP connection; it is not an OS sandbox.
FFmpeg remains a separate local process and receives local file paths in these tests.
"""
from pathlib import Path
import runpy
import socket
import sys


def denied(*args, **kwargs):
    raise RuntimeError('Network connections disabled for standalone verification')


original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex
original_pair = socket.socketpair


def local_pair(*args, **kwargs):
    # Windows asyncio creates its internal self-pipe via socketpair. Permit only
    # construction of that private pair, then immediately reinstate the guard.
    socket.socket.connect = original_connect
    socket.socket.connect_ex = original_connect_ex
    try:
        return original_pair(*args, **kwargs)
    finally:
        socket.socket.connect = denied
        socket.socket.connect_ex = denied


socket.socketpair = local_pair
socket.socket.connect = denied
socket.socket.connect_ex = denied
socket.create_connection = denied
script = Path(sys.argv[1]).resolve()
sys.argv = sys.argv[1:]
sys.path.insert(0, str(script.parent))
runpy.run_path(str(script), run_name='__main__')
