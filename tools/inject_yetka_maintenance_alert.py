"""Inject global Yetka UI policies into a built Lina index."""

import argparse
from pathlib import Path


SCRIPT_TAGS = (
    '<script src="/static/js/yetka-ui-policy.js?v=1" defer></script>',
    '<script src="/static/js/yetka-maintenance-alert.js?v=3" defer></script>',
)
LEGACY_SCRIPT_TAGS = (
    '<script src="/static/js/yetka-maintenance-alert.js?v=1" defer></script>',
    '<script src="/static/js/yetka-maintenance-alert.js?v=2" defer></script>',
)


def inject(index_path):
    path = Path(index_path)
    if not path.is_file():
        print(f'Yetka Lina index not found; alert injection skipped: {path}')
        return False
    content = path.read_text(encoding='utf-8')
    if '</body>' not in content:
        raise RuntimeError(f'Lina index has no closing body tag: {path}')
    for legacy_tag in LEGACY_SCRIPT_TAGS:
        content = content.replace(legacy_tag, '')
    missing_tags = [tag for tag in SCRIPT_TAGS if tag not in content]
    if not missing_tags:
        print(f'Yetka UI policy and maintenance alert already installed: {path}')
        return True
    injection = ''.join(missing_tags)
    path.write_text(content.replace('</body>', f'{injection}</body>', 1), encoding='utf-8')
    print(f'Installed Yetka UI policy and maintenance alert: {path}')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', default='/opt/lina/index.html')
    args = parser.parse_args()
    inject(args.index)


if __name__ == '__main__':
    main()
