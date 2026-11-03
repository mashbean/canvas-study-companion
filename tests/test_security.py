import functools
import http.client
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

serve, setup, canvas = module('serve'), module('setup_token'), module('collect_canvas')


class ServerSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name) / 'site'
        cls.root.mkdir()
        (cls.root / 'index.html').write_text('Synthetic reader', encoding='utf-8')
        (cls.root / 'pack.js').write_text('window.PACK = {};', encoding='utf-8')
        (cls.root / '.env').write_text('fictional local value', encoding='utf-8')
        (cls.root / 'credentials.env').write_text('fictional local value', encoding='utf-8')
        (cls.root / 'empty').mkdir()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(serve.ReaderHandler, directory=str(cls.root)))
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temp.cleanup()

    def request(self, path='/', headers=None, method='GET'):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_local_reader_and_protective_headers(self):
        status, headers, body = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(body, b'Synthetic reader')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(headers['Referrer-Policy'], 'no-referrer')
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertEqual(self.request('/pack.js', {'Host': f'localhost:{self.port}'})[0], 200)

    def test_foreign_host_is_rejected_before_serving(self):
        for host in ['untrusted.example', f'localhost.evil.example:{self.port}', '127.0.0.1:1', f'evil@127.0.0.1:{self.port}']:
            status, _, body = self.request('/pack.js', {'Host': host})
            self.assertEqual(status, 403)
            self.assertNotIn(b'window.PACK', body)

    def test_foreign_origin_and_cross_site_requests(self):
        for headers in [{'Origin': 'https://untrusted.example'}, {'Origin': 'null'}, {'Sec-Fetch-Site': 'cross-site'}]:
            self.assertEqual(self.request('/pack.js', headers)[0], 403)
        self.assertEqual(self.request('/pack.js', {'Origin': f'http://127.0.0.1:{self.port}'})[0], 200)

    def test_hidden_files_directory_listing_and_non_reader_types(self):
        for path in ['/.env', '/%2eenv', '/credentials.env', '/empty/']:
            self.assertEqual(self.request(path)[0], 403)

    def test_symlink_escape_in_files_and_directory_indexes(self):
        outside = Path(self.temp.name) / 'outside.txt'
        outside.write_text('Synthetic outside value', encoding='utf-8')
        try:
            (self.root / 'escape.txt').symlink_to(outside)
            folder = self.root / 'linked-index'
            folder.mkdir()
            (folder / 'index.html').symlink_to(outside)
        except OSError:
            self.skipTest('Platform does not allow test symlinks')
        for path in ['/escape.txt', '/linked-index/']:
            status, _, body = self.request(path)
            self.assertEqual(status, 403)
            self.assertNotIn(b'Synthetic outside value', body)

    def test_head_has_the_same_protection(self):
        self.assertEqual(self.request('/pack.js', {'Host': 'untrusted.example'}, method='HEAD')[0], 403)


class CredentialSecurityTests(unittest.TestCase):
    def test_current_and_other_repositories_are_rejected(self):
        with self.assertRaises(ValueError):
            setup.secret_destination(ROOT / '.env.example')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.git').mkdir()
            with self.assertRaises(ValueError):
                setup.secret_destination(root / 'ignored' / 'token.env')

    def test_refusal_happens_before_requesting_the_token(self):
        with patch('sys.argv', ['setup_token.py', '--path', str(ROOT / '.env.example')]), patch('sys.stdin.isatty', return_value=True), patch.object(setup.getpass, 'getpass') as prompt:
            with self.assertRaises(ValueError):
                setup.main()
            prompt.assert_not_called()

    def test_private_atomic_storage_and_no_target_truncation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / 'unrelated.txt'
            original.write_text('unchanged', encoding='utf-8')
            destination = root / 'token.env'
            os.link(original, destination)
            setup.save_token(destination, 'fake-test-value')
            self.assertEqual(original.read_text(), 'unchanged')
            self.assertEqual(destination.read_text(), 'CANVAS_ACCESS_TOKEN=fake-test-value\n')
            if os.name != 'nt':
                self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)

    def test_symlink_destination_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'target.txt'
            target.write_text('unchanged', encoding='utf-8')
            link = root / 'token.env'
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest('Platform does not allow test symlinks')
            with self.assertRaises(ValueError):
                setup.save_token(link, 'fake-test-value')
            self.assertEqual(target.read_text(), 'unchanged')


class ResponseLimitTests(unittest.TestCase):
    def response(self, body, headers=None):
        response = io.BytesIO(body)
        response.headers = headers or {}
        return response

    def test_oversized_header_is_refused_without_reading(self):
        response = self.response(b'anything', {'Content-Length': '9000'})
        with self.assertRaises(canvas.CollectionError):
            canvas.read_limited(response, 8)
        self.assertEqual(response.tell(), 0)

    def test_missing_or_lying_length_cannot_bypass_limit(self):
        for headers in [{}, {'Content-Length': '1'}]:
            response = self.response(b'x' * 1000, headers)
            with self.assertRaises(canvas.CollectionError):
                canvas.read_limited(response, 8)
            self.assertEqual(response.tell(), 9)

    def test_normal_response_and_invalid_length(self):
        self.assertEqual(canvas.read_limited(self.response(b'12345678'), 8), b'12345678')
        for value in ['-1', 'not-a-size']:
            with self.assertRaises(canvas.CollectionError):
                canvas.read_limited(self.response(b'', {'Content-Length': value}), 8)


if __name__ == '__main__':
    unittest.main()
