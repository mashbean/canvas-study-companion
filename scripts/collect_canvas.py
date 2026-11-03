#!/usr/bin/env python3
"""Read-only Canvas collection. No submission, enrolment or browser-cookie access.

The collector stages evidence; it never rewrites the reviewed bilingual reader.
"""
import argparse
import datetime as dt
import email.utils
try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo

ORIGIN = 'https://canvas.example.edu'
SECRET_KEYS = re.compile(r'token|secret|password|authorization|cookie|secure_params|preview_url|verifier|signature|credential', re.I)
SAFE_QUERY = {'page', 'per_page', 'include[]', 'context_codes[]', 'start_date', 'end_date', 'section', 'idpCode', 'module_item_id', 'docID', 'pq-origsite', 'chapter', 'id', 'list', 'doi', 'lang', 'tab', 'usp', 'wrap'}


def validate_origin(value):
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.path not in ('', '/') or p.query or p.fragment:
        raise CollectionError('Canvas URL must be an HTTPS origin without a path, credentials or query')
    return value.rstrip('/')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def week_start(value=None, next_week=False):
    day = dt.date.fromisoformat(value) if value else dt.datetime.now(ZoneInfo('Europe/London')).date()
    monday = day - dt.timedelta(days=day.weekday())
    return (monday + dt.timedelta(days=7 if next_week else 0)).isoformat()


def safe_url(value):
    p = urlsplit(html.unescape(value))
    if p.scheme not in ('http', 'https'):
        return value if not p.scheme else '[non-web link]'
    query = [(k, v) for k, v in parse_qsl(p.query) if k in SAFE_QUERY]
    # Never retain credentials in URL userinfo.
    host = p.hostname or ''
    if p.port:
        host += ':' + str(p.port)
    return urlunsplit((p.scheme, host, p.path, urlencode(query), p.fragment))


def scrub(value, token=''):
    if isinstance(value, dict):
        return {k: scrub(v, token) for k, v in value.items() if not SECRET_KEYS.search(k)}
    if isinstance(value, list):
        return [scrub(v, token) for v in value]
    if isinstance(value, str):
        if token:
            value = value.replace(token, '[redacted]')
        value = re.sub(r'https?://[^\s<>"\']+', lambda m: safe_url(m.group()), value)
        value = re.sub(r'(?i)Bearer\s+[^\s<>"\']+', 'Bearer [redacted]', value)
        value = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[redacted-signed-value]', value)
    return value


def select(data, keys):
    return {k: data[k] for k in keys.split() if k in data}


def normalize(kind, x):
    if isinstance(x, list):
        return [normalize(kind, v) for v in x]
    if kind == 'assignments':
        result = select(x, 'id name description due_at lock_at unlock_at updated_at html_url submission_types points_possible omit_from_final_grade')
        result['submission'] = select(x.get('submission') or {}, 'workflow_state submitted_at late missing graded_at')
        result['kind_hint'] = ('registration' if re.search(r'office hours|sign.up', x.get('name', ''), re.I)
                               else 'self_check' if 'checklist' in x.get('name', '').lower()
                               else 'external_tool_review' if 'external_tool' in x.get('submission_types', [])
                               else 'assessment_review')
        result['hint_is_not_teacher_requirement'] = True
        return result
    if kind == 'modules':
        result = select(x, 'id name items_count position')
        result['items'] = [select(i, 'id title type content_id page_url external_url html_url url position') for i in x.get('items', [])]
        return result
    if kind == 'items':
        return select(x, 'id title type content_id page_url external_url html_url url position')
    if kind in ('pages', 'page'):
        return select(x, 'page_id url title body updated_at html_url published')
    if kind == 'course':
        return select(x, 'id name course_code syllabus_body time_zone')
    if kind == 'announcements':
        return select(x, 'id title message posted_at html_url context_code')
    if kind == 'file':
        return select(x, 'id display_name filename content-type size updated_at modified_at locked_for_user hidden_for_user')
    raise ValueError('Unsupported evidence kind')


class CollectionError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, token, opener=None, sleeper=time.sleep, base_url=ORIGIN):
        self.origin = validate_origin(base_url)
        self.token = token
        self.opener = opener or build_opener(NoRedirect())
        self.sleeper = sleeper

    def request(self, url, authenticated=True):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.username or parsed.password:
            raise CollectionError('Unsafe request URL')
        if authenticated and (parsed.netloc != urlsplit(self.origin).netloc or not parsed.path.startswith('/api/v1/')):
            raise CollectionError('Authenticated request outside Canvas API rejected')
        for attempt in range(4):
            headers = {'Accept': 'application/json' if authenticated else '*/*', 'User-Agent': 'Canvas-Study-Companion/1'}
            if authenticated:
                headers['Authorization'] = 'Bearer ' + self.token
            try:
                with self.opener.open(Request(url, headers=headers, method='GET'), timeout=30) as response:
                    return response.read(), response.headers
            except HTTPError as error:
                if error.code in (301, 302, 303, 307, 308):
                    # API redirects normally mean login; never forward a token.
                    raise CollectionError('API redirected; authentication or endpoint requires review') from None
                if error.code in (429, 500, 502, 503, 504) and attempt < 3:
                    retry = error.headers.get('Retry-After', '')
                    try:
                        wait = float(retry)
                    except ValueError:
                        try:
                            wait = (email.utils.parsedate_to_datetime(retry) - dt.datetime.now(dt.timezone.utc)).total_seconds()
                        except (TypeError, ValueError):
                            wait = 2 ** attempt
                    if wait > 60:
                        raise CollectionError('Rate limit requires a later retry') from None
                    self.sleeper(max(0, wait))
                    continue
                raise CollectionError('HTTP ' + str(error.code)) from None
            except (URLError, TimeoutError, OSError):
                raise CollectionError('Network request failed; details withheld to protect credentials') from None
        raise CollectionError('Retry budget exhausted')

    def get(self, path):
        url = path if path.startswith('https://') else self.origin + '/api/v1/' + path
        body, headers = self.request(url)
        try:
            return json.loads(body.decode('utf-8').removeprefix('while(1);')), headers
        except (ValueError, UnicodeError):
            raise CollectionError('Expected JSON; possible sign-in page') from None

    def listing(self, path):
        url, seen, values = path, set(), []
        while url:
            if url in seen or len(seen) >= 500:
                raise CollectionError('Pagination loop or excessive page count')
            seen.add(url)
            data, headers = self.get(url)
            if not isinstance(data, list):
                raise CollectionError('Expected paginated array')
            values.extend(data)
            links = headers.get('Link', '') or headers.get('link', '')
            match = re.search(r'<([^>]+)>\s*;\s*rel="?next"?', links)
            url = match.group(1) if match else None
        return values

    def download(self, url):
        # URL comes only from Canvas file metadata. Never forward bearer credentials.
        for _ in range(8):
            p = urlsplit(url)
            if p.scheme != 'https' or p.username or p.password:
                raise CollectionError('Unsafe file download URL')
            try:
                with self.opener.open(Request(url, headers={'User-Agent': 'Canvas-Study-Companion/1'}, method='GET'), timeout=30) as response:
                    body = response.read()
                    content_type = response.headers.get('Content-Type', '')
                    if 'text/html' in content_type or body.lstrip().lower().startswith((b'<!doctype html', b'<html')):
                        raise CollectionError('Download returned HTML; use original-site login')
                    return body
            except HTTPError as error:
                if error.code in (301, 302, 303, 307, 308) and error.headers.get('Location'):
                    url = urljoin(url, error.headers['Location'])
                    continue
                raise CollectionError('File HTTP ' + str(error.code)) from None
            except (URLError, TimeoutError, OSError):
                raise CollectionError('File download failed') from None
        raise CollectionError('File redirect limit exceeded')


def load_token(path):
    token = os.environ.get('CANVAS_ACCESS_TOKEN', '').strip()
    if token:
        return token
    p = Path(path).expanduser()
    if not p.exists():
        return ''
    if os.name != 'nt' and p.stat().st_mode & 0o077:
        raise CollectionError('Secret file must have mode 600 or stricter')
    for line in p.read_text(encoding='utf-8').splitlines():
        if line.startswith('CANVAS_ACCESS_TOKEN='):
            return line.partition('=')[2].strip().strip('\"\'')
    return ''


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def difference(old, new, complete=False):
    before = {r['key']: r for r in old}
    after = {r['key']: r for r in new}
    return {'added': sorted(after.keys() - before.keys()),
            'changed': sorted(k for k in after.keys() & before.keys() if digest(after[k]['data']) != digest(before[k]['data'])),
            'not_observed': sorted(before.keys() - after.keys()),
            'absence_is_deletion': False,
            'coverage_complete': complete}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def content_links(body, cid, origin=ORIGIN):
    """Discover files/pages from actual HTML attributes, scoped to this course."""
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = []
        def handle_starttag(self, tag, attrs):
            self.urls.extend(value for key, value in attrs
                             if key in ('href', 'src', 'data-api-endpoint') and value)
    parser = Links()
    parser.feed(body or '')
    files, pages, external = set(), set(), set()
    for value in parser.urls:
        url = urljoin(origin + '/courses/' + str(cid) + '/', value)
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https'):
            continue
        if parts.netloc != urlsplit(origin).netloc:
            external.add(safe_url(url))
            continue
        path = re.sub(r'^/api/v1', '', parts.path)
        match = re.match(r'^/courses/(\d+)/(files|pages)/([^/]+)(?:/|$)', path)
        if match:
            course, kind, item = match.groups()
            if course != str(cid):
                external.add(safe_url(url))
            elif kind == 'files' and item.isdigit():
                files.add(int(item))
            elif kind == 'pages':
                pages.add(item)
        else:
            match = re.match(r'^/files/(\d+)(?:/|$)', path)
            if match:
                files.add(int(match.group(1)))
    return files, pages, external


def collect(plan, client, run_dir, week_dir):
    records, errors, files, external = [], [], [], []
    origin = getattr(client, 'origin', ORIGIN)
    existing_files = {}
    for folder in ('sources', 'originals'):
        for path in (week_dir / folder).rglob('*'):
            if path.is_file() and path.suffix.lower() in ('.pdf', '.pptx', '.docx', '.xlsx', '.png', '.jpg'):
                existing_files[hashlib.sha256(path.read_bytes()).hexdigest()] = path

    def capture(key, endpoint, kind, listing=False):
        try:
            raw = client.listing(endpoint) if listing else client.get(endpoint)[0]
            record = {'key': key, 'endpoint': origin + '/api/v1/' + endpoint, 'kind': kind,
                      'checked_at': now(), 'pagination_complete': True,
                      'data': scrub(normalize(kind, raw), client.token)}
            records.append(record)
            return raw
        except CollectionError as error:
            errors.append({'key': key, 'error': str(error)})
            return None

    query = [('context_codes[]', 'course_' + str(c['id'])) for c in plan['courses']]
    query += [('start_date', plan['announcements_from']), ('end_date', plan['announcements_to']), ('per_page', 100)]
    announcements = capture('announcements', 'announcements?' + urlencode(query), 'announcements', True) or []

    for course in plan['courses']:
        cid, slug = str(course['id']), course['folder']
        prefix = 'courses/' + cid
        course_data = capture(cid + ':course', prefix + '?include[]=syllabus_body', 'course') or {}
        modules = capture(cid + ':modules', prefix + '/modules?include[]=items&per_page=100', 'modules', True)
        assignments = capture(cid + ':assignments', prefix + '/assignments?include[]=submission&per_page=100', 'assignments', True) or []
        capture(cid + ':pages', prefix + '/pages?per_page=100', 'pages', True)
        file_ids = set(course.get('file_ids', []))
        page_slugs = set(course.get('pages', []))
        assignment_ids = set(course.get('assignment_ids', []))

        def discover(body, source):
            linked_files, linked_pages, links = content_links(body, cid, origin)
            file_ids.update(linked_files)
            page_slugs.update(linked_pages)
            for link in sorted(links):
                external.append({'course': cid, 'source': source, 'url': link, 'status': 'manual_review'})

        discover(course_data.get('syllabus_body'), 'syllabus_body')
        for announcement in announcements:
            path = urlsplit(announcement.get('html_url', '')).path
            if path.startswith('/courses/' + cid + '/') or announcement.get('context_code') == 'course_' + cid:
                discover(announcement.get('message'), 'announcement:' + str(announcement['id']))
        selected = []
        for module in modules or []:
            if module['id'] not in course['module_ids']:
                continue
            selected.append(module['id'])
            items = module.get('items', [])
            if len(items) != module.get('items_count'):
                items = capture(cid + ':module-items:' + str(module['id']), prefix + '/modules/' + str(module['id']) + '/items?per_page=100', 'items', True) or []
                if len(items) != module.get('items_count'):
                    errors.append({'key': cid + ':module:' + str(module['id']), 'error': 'Module item count mismatch'})
            for item in items:
                if item['type'] == 'File':
                    file_ids.add(item['content_id'])
                elif item['type'] == 'Page':
                    page_slugs.add(item['page_url'])
                elif item['type'] == 'Assignment':
                    assignment_ids.add(item['content_id'])
                elif item['type'] == 'ExternalUrl':
                    external.append({'course': cid, 'title': item['title'], 'url': safe_url(item['external_url']), 'status': 'manual_review'})
        for mid in set(course['module_ids']) - set(selected):
            errors.append({'key': cid + ':module:' + str(mid), 'error': 'Selected module not found; recheck plan'})
        for assignment in assignments:
            if assignment['id'] in assignment_ids:
                discover(assignment.get('description'), 'assignment:' + str(assignment['id']))
        for aid in assignment_ids - {a['id'] for a in assignments}:
            errors.append({'key': cid + ':assignment:' + str(aid), 'error': 'Selected assignment not found; recheck plan'})
        visited_pages = set()
        while page_slugs - visited_pages:
            if len(visited_pages) >= 100:
                errors.append({'key': cid + ':linked-pages', 'error': 'Linked-page limit reached; manual review required'})
                break
            page = sorted(page_slugs - visited_pages)[0]
            visited_pages.add(page)
            data = capture(cid + ':page:' + page, prefix + '/pages/' + page, 'page')
            if not data:
                continue
            discover(data.get('body'), 'page:' + page)
        for fid in sorted(file_ids):
            meta = capture(cid + ':file:' + str(fid), prefix + '/files/' + str(fid), 'file')
            if not meta:
                continue
            canonical = origin + '/courses/' + cid + '/files/' + str(fid)
            if meta.get('locked_for_user') or meta.get('hidden_for_user') or not meta.get('url'):
                errors.append({'key': cid + ':file:' + str(fid), 'error': 'File unavailable to current user'})
                continue
            try:
                body = client.download(meta['url'])
                sha = hashlib.sha256(body).hexdigest()
                name = re.sub(r'[^\w. -]', '_', Path(meta.get('filename') or str(fid)).name)
                if name.lower().endswith('.pdf') and not body.startswith(b'%PDF-'):
                    raise CollectionError('Expected PDF signature')
                destination = existing_files.get(sha) or week_dir / 'originals' / slug / ('Week-' + str(plan['teaching_week'])) / (str(fid) + '-' + sha[:12] + '-' + name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    destination.write_bytes(body)
                existing_files[sha] = destination
                files.append({'course': cid, 'id': fid, 'title': meta.get('display_name'), 'source_url': canonical,
                              'path': str(destination.relative_to(week_dir)), 'sha256': sha, 'bytes': len(body)})
            except CollectionError as error:
                errors.append({'key': cid + ':download:' + str(fid), 'error': str(error)})
    return records, errors, files, external


def validate_plan(plan):
    if week_start(plan['week']) != plan['week']:
        raise CollectionError('Week must be an ISO Monday in the selected timetable timezone')
    if not plan.get('schedule_verified_at') or not plan.get('schedule_source'):
        raise CollectionError('Verify calendar and teaching week before collection')
    try:
        checked = dt.datetime.fromisoformat(plan['schedule_verified_at'].replace('Z', '+00:00'))
        ZoneInfo(plan['timezone'])
        if not checked.tzinfo or not plan['courses']:
            raise ValueError('Missing timezone or courses')
    except (ValueError, KeyError):
        raise CollectionError('Replace example settings with verified dates, timezone and selected courses') from None
    for course in plan['courses']:
        if not course['module_ids'] or not re.fullmatch(r'[A-Za-z0-9_-]+', course['folder']):
            raise CollectionError('Explicit module IDs and a safe course folder are required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, default=Path('data'))
    parser.add_argument('--secret-file', default='~/.config/canvas-study-companion/canvas.env')
    parser.add_argument('--import-browser', type=Path, help='Sanitized browser API evidence, never cookies or access tokens')
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    validate_origin(plan['canvas_url'])
    validate_plan(plan)
    week_dir = args.output_root / 'weeks' / plan['week']
    runs = week_dir / 'runs'
    runs.mkdir(parents=True, exist_ok=True)
    ignore = runs / '.gitignore'
    ignored = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
    if '.collector.lock' not in ignored.splitlines():
        ignore.write_text(ignored.rstrip() + '\n.collector.lock\n', encoding='utf-8')
    lock = open(runs / '.collector.lock', 'a+b')
    try:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            if lock.seek(0, 2) == 0:
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        raise CollectionError('Another collector is running') from None
    previous = sorted(runs.glob('*/snapshot.json'))
    run_dir = runs / dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run_dir.mkdir()
    records, errors, files, external = [], [], [], []
    auth_mode = 'bearer_token'
    if args.import_browser:
        evidence = json.loads(args.import_browser.read_text(encoding='utf-8'))
        records = scrub(evidence['records'])
        files = evidence.get('files', [])
        for entry in files:
            target = (week_dir / entry['path']).resolve()
            if not target.is_relative_to(week_dir.resolve()) or not target.is_file():
                raise CollectionError('Imported file must exist inside the target week')
            if hashlib.sha256(target.read_bytes()).hexdigest() != entry['sha256']:
                raise CollectionError('Imported file hash mismatch')
        auth_mode = 'browser_session_api'
        for record in records:
            record['pagination_complete'] = False
        errors = [{'key': 'coverage', 'error': 'Browser API cannot verify Link headers; partial evidence, not unattended token validation'}]
    else:
        token = load_token(args.secret_file)
        if not token:
            auth_mode = 'unavailable'
            errors = [{'key': 'authentication', 'error': 'Canvas token not configured; use browser fallback and retain gaps'}]
        else:
            records, errors, files, external = collect(plan, Client(token, base_url=plan['canvas_url']), run_dir, week_dir)
    status = 'complete' if not errors else 'partial' if records else 'blocked'
    old = json.loads(previous[-1].read_text(encoding='utf-8')) if previous else None
    # Do not let a blocked/empty run conceal the last evidence-bearing baseline.
    for candidate in reversed(previous):
        content = json.loads(candidate.read_text(encoding='utf-8'))
        if content.get('records'):
            old = content
            break
    changes = difference(old.get('records', []) if old else [], records, status == 'complete')
    changes['files'] = difference(
        [{'key': str(f['course']) + ':' + str(f['id']), 'data': {'sha256': f['sha256']}} for f in old.get('files', [])] if old else [],
        [{'key': str(f['course']) + ':' + str(f['id']), 'data': {'sha256': f['sha256']}} for f in files],
        status == 'complete')
    changes['baseline'] = 'prior_snapshot' if old and old.get('records') else 'first_api_baseline_not_proof_of_new_publication'
    changes['comparison_note'] = 'Browser captures may contain selected fields only; review source coverage before treating a schema or capture difference as a source change.'
    snapshot = {'schema': 1, 'week': plan['week'], 'checked_at': now(), 'auth_mode': auth_mode, 'status': status,
                'scope': 'Canvas only; timetable, optional email, external library and reader review are separate checks',
                'records': records, 'errors': errors, 'files': files, 'external_links': external, 'changes': changes}
    write_json(run_dir / 'snapshot.json', snapshot)
    write_json(run_dir / 'plan.json', plan)
    report = f"# Canvas collection report\n\nWeek: {plan['week']}; status: {status}; authentication: {auth_mode}\n\n"
    report += f"Collected {len(records)} evidence records and {len(files)} files. A first snapshot is not proof of new publication.\n\n"
    report += '\n'.join('- ' + e['key'] + ': ' + e['error'] for e in errors)
    report += '\n\nReview timetable, external readings, source classification and translations separately. No submissions or enrolments are performed.\n'
    (run_dir / 'report.md').write_text(report, encoding='utf-8')
    print(json.dumps({'status': status, 'auth_mode': auth_mode, 'records': len(records), 'files': len(files), 'run': str(run_dir)}, ensure_ascii=False))
    return 0 if status == 'complete' else 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (CollectionError, ValueError, KeyError) as error:
        # Validation errors are fixed strings; never emit API payloads or credentials.
        print('Collection stopped: ' + (str(error) if isinstance(error, CollectionError) else 'Invalid plan or evidence'), file=sys.stderr)
        sys.exit(2)
