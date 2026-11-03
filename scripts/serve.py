#!/usr/bin/env python3
"""Serve the generated reader on loopback only, with a stable localStorage origin."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--directory', type=Path, default=Path('site'))
    p.add_argument('--port', type=int, default=8765)
    args = p.parse_args()
    directory = args.directory.resolve()
    if not directory.is_dir():
        raise SystemExit('Build a reader first.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(SimpleHTTPRequestHandler, directory=str(directory)))
    print(f'Open http://127.0.0.1:{args.port}/ — keep this port for your saved progress.', flush=True)
    server.serve_forever()
