#!/usr/bin/env python3
"""Save course/module discovery privately; never guess another student's course IDs."""
import argparse
from pathlib import Path
import sys
from collect_canvas import Client, CollectionError, load_token, normalize, scrub, now, write_json

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base-url', required=True)
    p.add_argument('--course', type=int, action='append', default=[])
    p.add_argument('--secret-file', default='~/.config/canvas-study-companion/canvas.env')
    p.add_argument('--output', type=Path, default=Path('data/discovery.json'))
    args = p.parse_args()
    token = load_token(args.secret_file)
    if not token:
        raise CollectionError('No token configured; run setup_token.py in your terminal')
    client = Client(token, base_url=args.base_url)
    result = {'checked_at': now(), 'auth_mode': 'bearer_token', 'courses': [], 'errors': []}
    courses = ([{'id': cid} for cid in args.course] if args.course else
               client.listing('courses?enrollment_state=active&per_page=100'))
    for entry in courses:
        cid = entry['id']
        try:
            meta = client.get(f'courses/{cid}?include[]=syllabus_body')[0]
            modules = client.listing(f'courses/{cid}/modules?per_page=100')
            result['courses'].append({'course': normalize('course', meta), 'modules': normalize('modules', modules)})
        except CollectionError as error:
            result['errors'].append({'course': cid, 'error': str(error)})
    result['status'] = ('complete' if result['courses'] and not result['errors'] else
                        'partial' if result['courses'] else 'blocked')
    write_json(args.output, scrub(result, token))
    print(f"{result['status']}: {len(result['courses'])} courses; saved to {args.output}")
    return 0 if result['status'] == 'complete' else 2

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (CollectionError, ValueError) as error:
        print('Discovery stopped: ' + (str(error) if isinstance(error, CollectionError) else 'Invalid configuration'), file=sys.stderr)
        sys.exit(2)
