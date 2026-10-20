"""CLEAN ROOM. Builds smw_assets.dat from games/smw/spec (tables.dat = kept structural tables + shape
placeholders, plus structure/anchor JSON) and the module generators. Never reads the ROM or the dirty tree."""
import sys, os, json, struct
import numpy as np
from scipy.ndimage import uniform_filter
from games.smw import assetfile as A, layout as L
from cleanroom.snes import lz2, tiles, brr
from cleanroom.audio import descriptor

SPEC = os.path.join(os.path.dirname(__file__), 'spec')


# ---------------------------------------------------------------- main
# Originality rebuild (2026-10): each module below returns {entry name: bytes} that
# replaces the old kept/derived entry. A module that is missing or raises is skipped
# with a warning (several people work on them at once); SMW_STRICT=1 makes it fatal.
MODULES = ['tiles', 'sprites', 'overworld', 'text_gen', 'levels', 'music']


def apply_modules(items, kept, only=None):
    import importlib, traceback
    done = {}
    for m in MODULES:
        if only and m not in only:
            continue
        try:
            mod = importlib.import_module('games.smw.' + m)
        except ModuleNotFoundError as e:
            if e.name == 'games.smw.' + m:
                continue
            raise
        except Exception:
            if os.environ.get('SMW_STRICT'):
                raise
            print('WARNING: module %s failed to import, kept old entries:\n%s' % (m, traceback.format_exc(limit=3)))
            continue
        try:
            out = mod.build(dict(items), kept, SPEC)
        except Exception:
            if os.environ.get('SMW_STRICT'):
                raise
            print('WARNING: module %s failed, kept old entries:\n%s' % (m, traceback.format_exc(limit=4)))
            continue
        for n, v in out.items():
            assert n in items, '%s returned unknown entry %s' % (m, n)
            items[n] = bytes(v)
        done[m] = sorted(out)
    return done


def base_items(kept):
    """Start values: the kept structural tables, blank sheets / palettes of the kept sizes, and empty
    entries for everything the modules regenerate."""
    sizes = json.load(open(os.path.join(SPEC, 'sizes.json')))
    sheet = {int(k, 16): n for k, n in sizes['sheets'].items()}
    items = []
    for n, v in kept:
        if n == 'kGraphicsPtrs':
            v = A.pack_array([lz2.compress(bytes(sheet[i])) for i in range(0x32)])
        elif n == 'kGfx32':
            v = bytes(sheet[0x32])
        elif n == 'kGfx33':
            v = bytes(sheet[0x33])
        elif L.is_palette(n):
            v = bytes(sizes['palettes'][n])
        items.append((n, v))
    return items


def main(out, only=None):
    kept = A.read(os.environ.get('SMW_KEPT') or os.path.join(SPEC, 'tables.dat'))
    items = base_items(kept)
    order = [n for n, _ in items]
    d = dict(items)
    done = apply_modules(d, dict(kept), only)
    items = [(n, d[n]) for n in order]
    A.write(out, items)
    print('wrote %s: %d entries, %d bytes (kRom %d bytes)' % (out, len(items), os.path.getsize(out), len(d['kRom'])))
    for m, names in done.items():
        print('  %-10s replaced %d entries' % (m, len(names)))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--only=')]
    only = [a[7:] for a in sys.argv[1:] if a.startswith('--only=')]
    only = only[0].split(',') if only else None
    main(args[0] if args else 'D:/n64work/smw/clean/smw_assets.dat', only)
