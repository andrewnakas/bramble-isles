"""Write index.html for the web build from shell.html.

    python games/smw/web/make_page.py <site> [--publish]

--publish drops the dev hooks (the DEV-BEGIN..DEV-END block: frame dumps, RAM pokes, ?bot= script loading) and the
dev comment line, and copies THIRD_PARTY.md + LICENSE.smw.txt next to the page.
"""
import os, re, shutil, sys
here = os.path.dirname(os.path.abspath(__file__))
site = sys.argv[1]
publish = '--publish' in sys.argv
s = open(os.path.join(here, 'shell.html'), encoding='utf-8').read()
if publish:
    s, n = re.subn(r'// DEV-BEGIN.*?// DEV-END\n', 'function devHooks() {}\n', s, flags=re.S)
    assert n == 1, 'DEV-BEGIN/DEV-END block not found'
    s = re.sub(r'\A<!-- Dev hooks:[^\n]*-->\n', '', s)
    s = s.replace("if (Q.has('autostart') || Q.has('dump') || Q.has('fdump')) start();",
                  "if (Q.has('autostart')) start();")
    for bad in ('_web_ram', '_web_ppu_dump', 'devBot', 'PW64PNG'):
        assert bad not in s, bad
    for f in ('THIRD_PARTY.md', 'LICENSE.smw.txt'):
        shutil.copyfile(os.path.join(here, f), os.path.join(site, f))
open(os.path.join(site, 'index.html'), 'w', encoding='utf-8', newline='\n').write(s)
open(os.path.join(site, '.nojekyll'), 'w').close()
print('page ->', os.path.join(site, 'index.html'), '(publish)' if publish else '(dev hooks on)')
