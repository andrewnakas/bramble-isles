"""DIRTY ROOM: structural facts of the music banks + SFX tables -> games/smw/spec/music.json.

    python -m games.smw.extract_music_spec D:/n64work/smw/dirty/smw_assets.dat

Keeps only: slot counts, which slots share a song, byte budgets / ARAM ranges, tempo,
length + loop point in ticks, active channels, per channel a coarse role (drums / bass /
mid / high from the median register, plus a density class), echo use; for SFX: per id the
duration in SFX ticks, whether it uses noise / a pitch sweep / loops, and a note count class.
No notes, intervals, rhythms, instrument settings or sample bytes are written.
"""
import json
import os
import sys
import statistics

from games.smw import assetfile as A
from cleanroom.audio import nspc

BANKS = {'kSpcLevelMusicBank': 29, 'kSpcOverworldMusicBank': 9, 'kSpcCreditsMusicBank': 12}
TABLE = 0x1360
SFX_P3, SFX_P0 = 0x5619, 0x5681
N_P3, N_P0 = 51, 42


def _cls(n, edges):
    for i, e in enumerate(edges):
        if n < e:
            return i
    return len(edges)


def song_facts(ram, ptr):
    s = nspc.read_song(ram, ptr)
    chans = {}
    for ch in range(8):
        ev = [e for e in s.events if e.ch == ch and e.kind in ('note', 'perc')]
        if not ev:
            continue
        perc = sum(e.kind == 'perc' for e in ev) / len(ev)
        keys = [e.key for e in ev if e.kind == 'note']
        med = statistics.median(keys) if keys else 0
        per_bar = len(ev) / max(1, s.length / 192)
        if perc > 0.5:
            reg = 'drums'
        else:
            reg = ['low', 'mid', 'high'][_cls(med, (30, 44))]
        chans[ch] = {'reg': reg, 'density': ['sparse', 'medium', 'busy'][_cls(per_bar, (3, 9))], '_m': med}
    mel = sorted((v['_m'], ch) for ch, v in chans.items() if v['reg'] != 'drums')
    for r, (_, ch) in enumerate(mel):
        chans[ch]['rank'] = r
    for v in chans.values():
        del v['_m']
    return {'tempo': s.tempo, 'length': s.length, 'loop': s.loop, 'channels': chans,
            'echo': bool(s.echo), 'errors': len(s.errors)}


def sfx_facts(ram, ptr, port):
    """Walk an SFX stream (the format of Sfx0_Process / Sfx3_Process) counting ticks."""
    p, t, notes, noise, sweep, loops = ptr, 0, 0, False, False, False
    length = 0
    for _ in range(400):
        c = ram[p]
        if c == 0:
            break
        if c < 0x80:
            length = c
            p += 1
            c = ram[p]
            if c < 0x80:
                p += 1
                c = ram[p]
                if c < 0x80:
                    p += 1
                    c = ram[p]
        if c == 0xda:
            p += 1
            while port == 3 and ram[p] >= 0x80:
                noise = True
                p += 1
            p += 1
            continue
        if c == 0xdd:
            notes += 1
            sweep = True
            p += 5
            t += length
            continue
        if c == 0xeb:
            sweep = True
            p += 4
            t += length
            continue
        if c == 0xff:
            loops = True
            break
        notes += 1
        t += length
        p += 1
    return {'ticks': t, 'notes': ['1', '2-3', '4-8', 'many'][_cls(notes, (2, 4, 9))],
            'noise': noise, 'sweep': sweep, 'loops': loops}


def main(dat, out=os.path.join(os.path.dirname(__file__), 'spec', 'music.json')):
    items = dict(A.read(dat))
    spec = {'banks': {}, 'sfx': {}}
    for name, n in BANKS.items():
        blob = items[name]
        ram = nspc.load(blob)
        ptrs = [nspc.word(ram, TABLE + 2 * i) for i in range(n)]
        first = {}
        slots = {}
        for i, ptr in enumerate(ptrs, 1):
            if ptr in first:
                slots[str(i)] = {'alias': first[ptr]}
                continue
            first[ptr] = i
            slots[str(i)] = song_facts(ram, ptr)
        size = nspc.word(blob, 0)
        spec['banks'][name] = {'base': TABLE, 'slots': n, 'budget': size, 'songs': slots}
    ram = nspc.load(items['kSpcEngine'])
    for port, base, n in ((0, SFX_P0, N_P0), (3, SFX_P3, N_P3)):
        spec['sfx']['port%d' % port] = {str(i): sfx_facts(ram, nspc.word(ram, base + 2 * i), port)
                                        for i in range(1, n + 1)}
    spec['engine_block'] = {'addr': 0x5570, 'end': 0x5570 + nspc.word(items['kSpcEngine'], 3646 + 4)}
    json.dump(spec, open(out, 'w'), indent=1)
    nb = {k: (v['slots'], v['budget'], sum('alias' in s for s in v['songs'].values())) for k, v in spec['banks'].items()}
    print('music.json: banks (slots, budget, aliases)', nb)
    print('  sfx ids: port0 %d, port3 %d; engine data block %04X-%04X' % (
        N_P0, N_P3, spec['engine_block']['addr'], spec['engine_block']['end']))


if __name__ == '__main__':
    main(*sys.argv[1:])
