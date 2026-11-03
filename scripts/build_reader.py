#!/usr/bin/env python3
"""Build a static reader from reviewed content; no API calls or automatic translation."""
import argparse
import copy
from datetime import date
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
TAGS = set('p br em strong b i u s blockquote pre code sup sub span a ul ol li table thead tbody tfoot tr td th caption figure img figcaption details summary h2 h3 h4 math mrow mi mn mo msup msub msubsup mfrac msqrt mroot mtext mtable mtr mtd'.split())
VOID = {'br', 'img'}

def safe_url(value, local_only=False):
    value = str(value).strip()
    if not value or any(ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError('Unsafe or empty resource URL')
    p = urlsplit(value)
    if p.username or p.password or value.startswith('//'):
        raise ValueError('Credentials or protocol-relative URL are not allowed')
    if p.scheme:
        if local_only or p.scheme not in ('https', 'http') or not p.hostname:
            raise ValueError('Unsupported resource URL')
    elif value.startswith('/') or '..' in Path(unquote(p.path)).parts:
        raise ValueError('Resource must remain inside the reader folder')
    return value

class Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag not in TAGS:
            return
        kept = []
        for key, value in attrs:
            if value is None:
                continue
            if key in ('href', 'src') and ((key == 'href' and tag == 'a') or (key == 'src' and tag == 'img')):
                try:
                    value = safe_url(value, local_only=(tag == 'img'))
                except ValueError:
                    continue
            elif key not in ('alt', 'title', 'lang', 'dir', 'colspan', 'rowspan', 'display'):
                continue
            kept.append(f' {key}="{html.escape(value, quote=True)}"')
        self.parts.append('<' + tag + ''.join(kept) + '>')
    def handle_endtag(self, tag):
        if tag in TAGS and tag not in VOID:
            self.parts.append('</' + tag + '>')
    def handle_data(self, data):
        self.parts.append(html.escape(data))

def clean(value):
    parser = Cleaner()
    parser.feed(str(value))
    return ''.join(parser.parts)

def prepare(pack):
    pack = copy.deepcopy(pack)
    if date.fromisoformat(pack['week']).weekday() != 0:
        raise ValueError('week must be an ISO Monday')
    for key in ('project_id', 'title', 'language', 'documents', 'guide'):
        if not pack.get(key):
            raise ValueError('Missing field: ' + key)
    if pack['language'].get('direction', 'ltr') not in ('ltr', 'rtl'):
        raise ValueError('Invalid language direction')
    if pack['language'].get('mode') not in ('english-only', 'bilingual-summaries', 'bilingual-full'):
        raise ValueError('Invalid translation mode')
    ids = set()
    for doc in pack['documents']:
        if not doc.get('id') or doc['id'] in ids:
            raise ValueError('Duplicate or missing document ID')
        ids.add(doc['id'])
        for key in ('source_url', 'download'):
            if doc.get(key):
                doc[key] = safe_url(doc[key])
        if not doc.get('units'):
            raise ValueError('Each document needs units, including an explicit gap unit if unavailable')
        pairs = set()
        for unit in doc['units']:
            if not unit.get('flow'):
                raise ValueError('Each unit needs reviewed paragraph pairs')
            for pair in unit['flow']:
                if not pair.get('id') or pair['id'] in pairs or not pair.get('en'):
                    raise ValueError('Stable unique paragraph IDs and English content are required')
                pairs.add(pair['id'])
                pair['en'] = clean(pair['en'])
                pair['translation'] = clean(pair.get('translation', ''))
                if pack['language']['mode'] != 'english-only' and not pair['translation'] and not pair.get('translation_gap'):
                    raise ValueError('Missing translation must have an explicit translation_gap')
    return pack

def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == ROOT or source.parent == output or source.is_relative_to(output):
        raise ValueError('Use a separate generated output folder')
    pack = prepare(json.loads(source.read_text(encoding='utf-8')))
    assets = []
    for resource in pack.get('assets', []):
        safe_url(resource, local_only=True)
        if Path(resource).parts[0] not in ('assets', 'sources') or Path(resource).suffix.lower() not in ('.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.pptx', '.docx', '.xlsx', '.txt'):
            raise ValueError('Assets must be documents or images under assets/ or sources/')
        if urlsplit(resource).query or urlsplit(resource).fragment:
            raise ValueError('Asset paths cannot have a query or fragment')
        path = (source.parent / resource).resolve()
        if not path.is_relative_to(source.parent) or not path.is_file():
            raise ValueError('Asset is missing or outside the pack directory')
        assets.append((path, resource))
    output.mkdir(parents=True, exist_ok=True)
    for name in ('index.html', 'app.js', 'style.css'):
        shutil.copy2(ROOT / 'templates' / name, output / name)
    for path, resource in assets:
        target = (output / resource).resolve()
        if not target.is_relative_to(output):
            raise ValueError('Unsafe output asset path')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    # Escape every '<' so source strings can never terminate a script element.
    serialized = json.dumps(pack, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    (output / 'pack.js').write_text('window.PACK = ' + serialized + ';\n', encoding='utf-8')
    manifest = [{k: v for k, v in d.items() if k not in ('units', 'questions')} for d in pack['documents']]
    (output / 'reading-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pack', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(build(args.pack, args.output))
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit('Build failed: ' + str(error))
