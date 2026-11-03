#!/usr/bin/env python3
"""Run interactively in the user's own terminal, never through a logged chat input."""
import argparse
import getpass
import os
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', default='~/.config/canvas-study-companion/canvas.env')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit('Run this command directly in your own interactive terminal.')
    path = Path(args.path).expanduser()
    if path.is_symlink():
        raise SystemExit('Refusing a symlink as a secrets file.')
    token = getpass.getpass('Canvas token (hidden; never paste into chat): ').strip()
    if not token or any(c.isspace() for c in token):
        raise SystemExit('Nothing saved: token was empty or contained whitespace.')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != 'nt':
        path.parent.chmod(0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    if os.name != 'nt':
        os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write('CANVAS_ACCESS_TOKEN=' + token + '\n')
    print('Token saved outside the project. Its value has not been printed.')
    if os.name == 'nt':
        print('Check that this file inherits only your user-account permissions, or use an OS credential store.')

if __name__ == '__main__':
    main()
