"""Inject the global Yetka maintenance alert into a built Lina index."""

import argparse
from pathlib import Path


SCRIPT_TAG = '<script src="/static/js/yetka-maintenance-alert.js?v=1" defer></script>'


def inject(index_path):
    path = Path(index_path)
    if not path.is_file():
        print(f'Yetka Lina index not found; alert injection skipped: {path}')
        return False
    content = path.read_text(encoding='utf-8')
    if SCRIPT_TAG in content:
        print(f'Yetka maintenance alert already installed: {path}')
        return True
    if '</body>' not in content:
        raise RuntimeError(f'Lina index has no closing body tag: {path}')
    path.write_text(content.replace('</body>', f'{SCRIPT_TAG}</body>', 1), encoding='utf-8')
    print(f'Installed Yetka maintenance alert: {path}')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', default='/opt/lina/index.html')
    args = parser.parse_args()
    inject(args.index)


if __name__ == '__main__':
    main()
