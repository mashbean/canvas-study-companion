import importlib.util
import io
import json
from pathlib import Path
import unittest
import tempfile
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('canvas', Path(__file__).parents[1] / 'scripts/collect_canvas.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class Response(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(json.dumps(data).encode() if not isinstance(data, bytes) else data)
        self.headers = headers or {}


class FakeOpener:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []

    def open(self, request, timeout):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class CanvasTests(unittest.TestCase):
    def test_custom_institution_origin_and_link_scope(self):
        opener = FakeOpener([Response({'id': 1})])
        client = c.Client('fake-test-secret', opener, base_url='https://learning.example.edu')
        self.assertEqual(client.get('courses/1')[0]['id'], 1)
        self.assertEqual(opener.requests[0].full_url, 'https://learning.example.edu/api/v1/courses/1')
        files, _, external = c.content_links('<a href="/courses/1/files/8">A</a><a href="https://other.example.edu/courses/1/files/9">B</a>', '1', client.origin)
        self.assertEqual(files, {8})
        self.assertEqual(len(external), 1)
        for bad in ['http://learning.example.edu', 'https://token@learning.example.edu', 'https://learning.example.edu/path']:
            with self.assertRaises(c.CollectionError): c.Client('fake-test-secret', base_url=bad)

    def test_pagination_follows_link_even_when_first_page_short(self):
        opener = FakeOpener([Response([1], {'Link': '<https://canvas.example.edu/api/v1/courses?page=opaque>; rel="next"'}), Response([2])])
        self.assertEqual(c.Client('fake-test-secret', opener).listing('courses'), [1, 2])
        self.assertIn('page=opaque', opener.requests[1].full_url)

    def test_foreign_pagination_does_not_receive_token(self):
        opener = FakeOpener([Response([], {'Link': '<https://example.org/api/v1/courses>; rel="next"'})])
        with self.assertRaises(c.CollectionError):
            c.Client('fake-test-secret', opener).listing('courses')
        self.assertEqual(len(opener.requests), 1)

    def test_retry_after_429(self):
        waits = []
        opener = FakeOpener([HTTPError(c.ORIGIN, 429, 'retry', {'Retry-After': '3'}, None), Response({'ok': True})])
        self.assertEqual(c.Client('fake-test-secret', opener, waits.append).get('courses/1')[0], {'ok': True})
        self.assertEqual(waits, [3])

    def test_redirect_and_login_html_never_count_as_json(self):
        for response in [HTTPError(c.ORIGIN, 302, 'redirect', {'Location': 'https://login.microsoftonline.com'}, None), Response(b'<html>Login</html>')]:
            with self.assertRaises(c.CollectionError):
                c.Client('fake-test-secret', FakeOpener([response])).get('courses')

    def test_download_redirect_never_carries_authorization(self):
        opener = FakeOpener([HTTPError(c.ORIGIN, 302, 'redirect', {'Location': 'https://files.example.org/a.pdf?signature=private'}, None), Response(b'%PDF-1.4')])
        self.assertEqual(c.Client('fake-test-secret', opener).download('https://canvas.example.edu/files/1/download'), b'%PDF-1.4')
        self.assertTrue(all(r.get_header('Authorization') is None for r in opener.requests))

    def test_download_rejects_html(self):
        with self.assertRaises(c.CollectionError):
            c.Client('', FakeOpener([Response(b'<html>login</html>', {'Content-Type': 'text/html'})])).download(c.ORIGIN + '/file')

    def test_redacts_signed_links_and_tokens_from_nested_html(self):
        raw = {'secure_params': 'hidden', 'body': '<a href="https://canvas.example.edu/files/4?verifier=hidden&access_token=fake-test-secret">A</a>', 'items': [{'note': 'Bearer fake-test-secret'}]}
        saved = json.dumps(c.scrub(raw, 'fake-test-secret'))
        for secret in ['fake-test-secret', 'hidden', 'secure_params', 'verifier', 'access_token']:
            self.assertNotIn(secret, saved)

    def test_lti_is_not_inferred_missing_assignment(self):
        data = c.normalize('assignments', {'id': 1, 'name': 'Sign-up: Office Hours', 'submission_types': ['external_tool'], 'submission': {'workflow_state': 'unsubmitted', 'missing': False, 'preview_url': 'private'}})
        self.assertEqual(data['kind_hint'], 'registration')
        self.assertNotIn('preview_url', data['submission'])
        self.assertFalse(data['submission']['missing'])

    def test_absence_is_never_automatic_deletion(self):
        result = c.difference([{'key': '1', 'data': {}}], [], complete=False)
        self.assertEqual(result['not_observed'], ['1'])
        self.assertFalse(result['absence_is_deletion'])

    def test_dates_around_uk_clock_change(self):
        self.assertEqual(c.week_start('2026-10-25', True), '2026-10-26')
        self.assertEqual(c.week_start('2026-11-02'), '2026-11-02')

    def test_collection_fetches_omitted_module_items_and_deduplicates_files(self):
        class FakeClient:
            token = 'fake-test-secret'
            def listing(self, endpoint):
                if '/modules?' in endpoint:return [{'id': 7, 'name': 'Week 4', 'items_count': 1}]
                if '/modules/7/items?' in endpoint:return [{'id': 8, 'title': 'Reading', 'type': 'File', 'content_id': 9}]
                return []
            def get(self, endpoint):
                if '/files/9' in endpoint:return {'id':9,'filename':'case.pdf','display_name':'case','url':'https://files.example.org/case.pdf?signature=private'}, {}
                return {'id':1,'name':'Test course','syllabus_body':None}, {}
            def download(self, url):return b'%PDF-1.4 test'
        plan={'teaching_week':4,'announcements_from':'2026-10-26','announcements_to':'2026-11-09','courses':[{'id':1,'folder':'Test','module_ids':[7]}]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            first=c.collect(plan,FakeClient(),root,root)
            second=c.collect(plan,FakeClient(),root,root)
            self.assertEqual(first[1],[])
            self.assertTrue(any(r['kind']=='items' for r in first[0]))
            self.assertEqual(first[2],second[2])
            self.assertEqual(len(list(root.rglob('*.pdf'))),1)
            self.assertNotIn('signature=private',json.dumps(first))

    def test_content_links_scope_and_html_entities(self):
        files, pages, external = c.content_links('''
          <a href="/courses/1/files/10/download?verifier=private&amp;download=1">A</a>
          <img src="/files/11/preview">
          <a data-api-endpoint="https://canvas.example.edu/api/v1/courses/1/pages/reading">B</a>
          <a href="https://publisher.example/files/999">External</a>
          <a href="/courses/2/files/12">Different course</a>
          <a href="mailto:example@example.org">Email</a>
        ''', '1')
        self.assertEqual(files, {10, 11})
        self.assertEqual(pages, {'reading'})
        self.assertEqual(external, {'https://publisher.example/files/999', c.ORIGIN + '/courses/2/files/12'})

    def test_collect_follows_assignment_announcement_and_recursive_page_links(self):
        class FakeClient:
            token = 'fake-test-secret'
            def listing(self, endpoint):
                if endpoint.startswith('announcements?'):
                    return [{'id':50, 'html_url':c.ORIGIN+'/courses/1/discussion_topics/50',
                             'message':'<a href="/courses/1/pages/a">Prep</a>'}]
                if '/modules?' in endpoint:
                    return [{'id':7, 'items_count':1, 'items':[{'id':8, 'type':'Assignment', 'content_id':20}]}]
                if '/assignments?' in endpoint:
                    return [{'id':20,'description':'<a href="/courses/1/files/21">Questions</a>'},
                            {'id':30,'description':'<img src="/files/31/preview">'},
                            {'id':40,'description':'<a href="/files/41">Unselected old assignment</a>'}]
                return []
            def get(self, endpoint):
                if '/pages/a' in endpoint:
                    return {'body':'<a href="/courses/1/pages/b">Next</a>'}, {}
                if '/pages/b' in endpoint:
                    return {'body':'<a href="/courses/1/pages/a">Cycle</a><a href="/files/61">Reading</a>'}, {}
                if '/files/' in endpoint:
                    fid=int(endpoint.rsplit('/',1)[1])
                    return {'id':fid,'filename':str(fid)+'.pdf','url':c.ORIGIN+'/files/'+str(fid)}, {}
                return {'syllabus_body':'<a href="/files/71">Syllabus attachment</a>'}, {}
            def download(self, url):
                return b'%PDF-1.4 ' + url.encode()
        plan={'teaching_week':4,'announcements_from':'2026-10-26','announcements_to':'2026-11-09',
              'courses':[{'id':1,'folder':'Test','module_ids':[7],'assignment_ids':[30,99]}]}
        with tempfile.TemporaryDirectory() as folder:
            records, errors, files, _ = c.collect(plan,FakeClient(),Path(folder),Path(folder))
        self.assertEqual({f['id'] for f in files}, {21,31,61,71})
        self.assertEqual([r['key'] for r in records if r['kind']=='page'], ['1:page:a','1:page:b'])
        self.assertEqual([e['key'] for e in errors], ['1:assignment:99'])
        saved_b = next(r['data']['body'] for r in records if r['key']=='1:page:b')
        self.assertIn('Cycle', saved_b)
        self.assertIn('Reading', saved_b)


if __name__ == '__main__':
    unittest.main()
