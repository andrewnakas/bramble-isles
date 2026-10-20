"""Render every song slot and SFX id of a .dat (or of a fresh music build) with the port's C
player and print one screen: crashes (player asserts), silent slots, levels.

    python -m games.smw.check_music [assets.dat] [--fresh] [--wav DIR]
--fresh rebuilds the music entries with games.smw.music first (on top of the given .dat).
"""
import json
import os
import sys

from games.smw import assetfile as A, spc_render as R

SPEC = os.path.join(os.path.dirname(__file__), 'spec', 'music.json')


def main(argv):
    wav = argv[argv.index('--wav') + 1] if '--wav' in argv else None
    args = [a for a in argv[1:] if not a.startswith('--') and a != wav]
    dat = args[0] if args else 'D:/n64work/smw/clean/smw_assets.dat'
    items = dict(A.read(dat))
    if '--fresh' in argv:
        from games.smw import music
        items.update(music.build(items, None, os.path.dirname(SPEC)))
    if wav:
        os.makedirs(wav, exist_ok=True)
    spec = json.load(open(SPEC))
    bad, rows = [], []
    for bank, short in (('kSpcLevelMusicBank', 'level'), ('kSpcOverworldMusicBank', 'overworld'),
                        ('kSpcCreditsMusicBank', 'credits')):
        n = spec['banks'][bank]['slots']
        cells = []
        for s in range(1, n + 1):
            try:
                x = R.render(items, bank, [(5, 2, s)], 60 * 12)
            except RuntimeError as e:
                bad.append('%s %d: %s' % (short, s, e))
                cells.append('%d:X' % s)
                continue
            db = R.level_db(x[32000 // 6:])
            cells.append('%d:%.0f' % (s, db))
            if db < -50:
                bad.append('%s %d silent (%.0f dB)' % (short, s, db))
            if wav:
                R.save_wav(os.path.join(wav, '%s_%02d.wav' % (short, s)), x)
        rows.append('%-9s %s' % (short, ' '.join(cells)))
    for port, n in ((0, 42), (3, 51), (1, 4)):
        cells = []
        for i in range(1, n + 1):
            try:
                x = R.render(items, 'level', [(5, port, i)], 240)
            except RuntimeError as e:
                bad.append('sfx p%d #%d: %s' % (port, i, e))
                cells.append('%d:X' % i)
                continue
            db = R.level_db(x)
            cells.append('%d:%.0f' % (i, db))
            if wav:
                R.save_wav(os.path.join(wav, 'sfx%d_%02d.wav' % (port, i)), x)
        rows.append('sfx p%d  %s' % (port, ' '.join(cells)))
    for r in rows:
        print(r)
    print('%d problems' % len(bad))
    for b in bad[:20]:
        print('  ' + b)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
