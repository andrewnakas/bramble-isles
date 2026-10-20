"""Export an smw_assets.dat into comparable files for the originality gate.

    python -m games.smw.export_orig <assets.dat> <outdir>

Run it on the retail-derived file (DIRTY, output stays in D:/n64work/smw/orig_dirty, never
committed) and on the clean build (D:/n64work/smw/orig_clean); then
    python -m cleanroom.originality D:/n64work/smw/orig_dirty D:/n64work/smw/orig_clean games/smw/spec
Each domain module games.smw.orig_<domain> exposes export(items: {name: bytes}, outdir) and
writes below outdir/<domain>/ (images/*.png, text/*.json, music/*.mid, levels/*.obj ...).
"""
import importlib
import os
import sys

from games.smw import assetfile as A

DOMAINS = ['images', 'text', 'music', 'levels', 'overworld', 'bg']


def main(dat, out):
    items = dict(A.read(dat))
    for d in DOMAINS:
        try:
            mod = importlib.import_module('games.smw.orig_' + d)
        except ModuleNotFoundError as e:
            if e.name == 'games.smw.orig_' + d:
                print('  %-10s (no exporter yet)' % d)
                continue
            raise
        sub = os.path.join(out, d)
        os.makedirs(sub, exist_ok=True)
        n = mod.export(items, sub)
        print('  %-10s %s files -> %s' % (d, n, sub))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
