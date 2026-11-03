#!/usr/bin/env python3
"""Serve a generated reader on loopback; reject foreign hosts and file escapes."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
EXTENSIONS = {'.html', '.htm', '.js', '.css', '.json', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.pptx', '.docx', '.xlsx', '.txt'}


class ReaderHandler(SimpleHTTPRequestHandler):
    def parse_request(self):
        if not super().parse_request():
            return False
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if port == 80:
            hosts.update({'127.0.0.1', 'localhost'})
        supplied = self.headers.get_all('Host', [])
        origins = self.headers.get_all('Origin', [])
        if (len(supplied) != 1 or supplied[0].lower() not in hosts
                or len(origins) > 1
                or (origins and origins[0].lower() not in {'http://' + h for h in hosts})
                or self.headers.get('Sec-Fetch-Site') == 'cross-site'):
            self.send_error(403, 'Only direct local reader access is allowed')
            return False
        return True

    def checked_path(self, path):
        root = Path(self.directory).resolve()
        path = Path(path).resolve()
        if not path.is_relative_to(root) or any(p.startswith('.') for p in path.relative_to(root).parts):
            raise PermissionError('Outside the reader directory')
        return path

    def send_head(self):
        try:
            path = self.checked_path(self.translate_path(self.path))
            if path.is_dir():
                for name in ('index.html', 'index.htm'):
                    candidate = path / name
                    if candidate.exists():
                        self.checked_path(candidate)
                        break
            elif path.suffix.lower() not in EXTENSIONS:
                raise PermissionError('Unsupported file type')
        except (PermissionError, OSError, ValueError, RuntimeError):
            self.send_error(403, 'File is not available in this reader')
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(403, 'Open a generated reader folder, for example /demo/')
        return None

    def end_headers(self):
        for name, value in {
            'Content-Security-Policy': CSP,
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'Cross-Origin-Resource-Policy': 'same-origin',
            'X-Frame-Options': 'DENY',
            'Cache-Control': 'no-store',
        }.items():
            self.send_header(name, value)
        super().end_headers()

    def log_message(self, format, *args):
        # Reading filenames and query strings should not end up in terminal logs.
        pass

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--directory', type=Path, default=Path('site'))
    p.add_argument('--port', type=int, default=8765)
    args = p.parse_args()
    directory = args.directory.resolve()
    if not directory.is_dir() or (directory / '.git').exists():
        raise SystemExit('Choose a generated reader directory, not a repository root.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(ReaderHandler, directory=str(directory)))
    print(f'Open a reader under http://127.0.0.1:{args.port}/ (for example /demo/); keep this port for saved progress.', flush=True)
    server.serve_forever()
