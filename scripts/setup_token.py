#!/usr/bin/env python3
"""Run interactively in the user's own terminal, never through a logged chat input."""
import argparse
import getpass
import os
from pathlib import Path
import sys
import tempfile

def secret_destination(value):
    path = Path(value).expanduser()
    if path.is_symlink():
        raise ValueError('Refusing a symlink as a secrets file.')
    path = path.resolve()
    project = Path(__file__).resolve().parents[1]
    if path.is_relative_to(project) or any((p / '.git').exists() for p in path.parents):
        raise ValueError('Credentials must be stored outside every Git repository.')
    return path

def save_token(path, token):
    path = secret_destination(path)
    if not token or any(c.isspace() for c in token):
        raise ValueError('Nothing saved: token was empty or contained whitespace.')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != 'nt':
        path.parent.chmod(0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write('CANVAS_ACCESS_TOKEN=' + token + '\n')
        # Atomic replacement avoids truncating a file reached through a link.
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', default='~/.config/canvas-study-companion/canvas.env')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit('Run this command directly in your own interactive terminal.')
    path = secret_destination(args.path)
    token = getpass.getpass('Canvas token (hidden; never paste into chat): ').strip()
    save_token(path, token)
    print('Token saved outside the project. Its value has not been printed.')
    if os.name == 'nt':
        print('Check that this file inherits only your user-account permissions, or use an OS credential store.')

if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        raise SystemExit(str(error)) from None
