"""CLEAN ROOM: all music, sound effects and samples of BRAMBLE ISLES.

build(items, kept, spec_dir) -> {kSpcEngine, kSpcSamples, kSpcLevelMusicBank,
                                 kSpcOverworldMusicBank, kSpcCreditsMusicBank}

Inputs are structure only (games/smw/spec/music.json + samples.json): slot counts and
aliases, byte budgets, tempo, length + loop point in ticks, active channels with a coarse
register rank, echo use; sample lengths + loop blocks; SFX ids with their durations.
Everything audible is ours:
  * samples   synthetic waves (additive square/pulse/saw/triangle/organ/strings/brass/flute,
              FM-ish bell, plucked string, marimba, e-piano, noise drums, timpani) laid out
              in the retail sample sizes so the ARAM map stays put; every loop holds a whole
              number of cycles and the instrument pitch multiplier makes keys land exactly
  * music     cleanroom.audio.compose material, arranged into N-SPC patterns per mood
              (cleanroom.audio.nspc writer), each bank inside its byte budget
  * SFX       designed per gameplay role (call sites of each id in the port's code)
  * engine    kSpcEngine carries only the tables + SFX streams the C player reads
              (0x5570..0x5FDB); no SPC700 program bytes
"""
import json
import os
import struct

import numpy as np

from cleanroom.audio import nspc
from cleanroom.audio import compose as C
from cleanroom.snes import brr

SAMPLE_DIR, SAMPLE_BASE = 0x8000, 0x8100
RATE = 32000
TABLE = 0x1360
SFX_INSTR, SFX_P3, SFX_P0, SFX_DATA = 0x5570, 0x5619, 0x5681, 0x56D7
MUS_INSTR, PERC, ENGINE_END = 0x5F46, 0x5FA5, 0x5FDB
N_P0, N_P3 = 42, 51
SFX_GAIN = 0.4                      # our SFX volumes are written loud, scaled into the mix here
BONGO_SLOTS = (1, 2, 3, 6)          # C player mutes channel 5 of these ids unless the hero rides ZEEP


def _period(pp):
    base = [4286, 4541, 4811, 5097, 5400, 5721, 6061, 6422, 6804, 7208, 7637, 8091]
    t = base[pp % 12]
    q = pp // 12
    while q < 6:
        t >>= 1
        q += 1
    return t


# ================================================================ samples
# sample index -> our timbre (chosen by sample length: loops vs one-shots, long attacks)
TIMBRE = {0: 'square', 1: 'pulse25', 2: 'bell', 3: 'organ', 4: 'triangle', 5: 'strings', 6: 'rim',
          7: 'epiano', 8: 'saw', 9: 'pluck', 10: 'crash', 11: 'kick', 12: 'reed', 13: 'brass',
          14: 'marimba', 15: 'hat', 16: 'bongo', 17: 'flute', 18: 'snare', 19: 'timpani'}


def pitch_plan(loop_blocks):
    """(cycles in loop, pitch multiplier, octave) with cycles*mult = blocks * 2^octave, so that
    key pp plays MIDI key pp + 24 + 12*octave exactly. Prefers long periods (more harmonics)."""
    best = None
    for k in (0, 1, 2):
        tot = loop_blocks * 2 ** k
        for b in range(1, 9):
            if tot % b:
                continue
            c = tot // b
            per = loop_blocks * 16 / c
            if per < 16 or per > 128:
                continue
            maxpp = max(pp for pp in range(70) if _period(pp) * b <= 0x3fff)
            score = min(per, 100) + 3 * min(maxpp, 62) - 10 * k
            if best is None or score > best[0]:
                best = (score, c, b, k, maxpp)
    return best[1:]


def _harm(kind, H):
    k = np.arange(1, H + 1, dtype=float)
    if kind == 'square':
        a = np.where(k % 2 == 1, 1 / k, 0)
    elif kind == 'pulse25':
        a = np.abs(np.sin(np.pi * k * 0.25)) / k
    elif kind == 'reed':
        a = np.abs(np.sin(np.pi * k * 0.125)) / k
    elif kind == 'saw':
        a = 1 / k
    elif kind == 'triangle':
        a = np.where(k % 2 == 1, 1 / k ** 2, 0)
    elif kind == 'organ':
        a = np.zeros(H)
        for h, v in ((1, 1), (2, .7), (3, .5), (4, .35), (6, .2), (8, .25)):
            if h <= H:
                a[h - 1] = v
    elif kind == 'strings':
        a = k ** -1.25 * np.exp(-k / 14)
    elif kind == 'brass':
        a = k ** -0.7 * np.exp(-k / 9)
    elif kind == 'flute':
        a = np.zeros(H)
        a[0], a[1:3] = 1, [.22, .08][:max(0, min(2, H - 1))] if H > 1 else []
    else:                                   # soft steady state of struck/plucked sounds
        a = np.exp(-(k - 1) * 1.3)
    a = a * np.exp(-((k / max(H, 1)) ** 4) * 3)      # gentle band edge
    return a


def _periodic(amps, n, per, phase0, t0=0):
    t = np.arange(t0, t0 + n, dtype=float)
    x = np.zeros(n)
    for h, a in enumerate(amps, 1):
        if a:
            x += a * np.sin(2 * np.pi * h * t / per + phase0[h - 1])
    return x


def _norm(x, peak=0.9):
    return x * (peak / (np.max(np.abs(x)) + 1e-9))


def synth_loop_sample(kind, blocks, loop_block, seed):
    n, ls = blocks * 16, loop_block * 16
    ln = n - ls
    c, b, k, _ = pitch_plan(blocks - loop_block)
    per = ln / c
    H = int(per // 2) - 1
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 2 * np.pi, 64)
    steady = _harm(kind, H)
    x = np.zeros(n)
    t = np.arange(n, dtype=float)
    struck = kind in ('bell', 'epiano', 'pluck', 'marimba')
    if struck:
        # attack: brighter spectrum whose upper partials die away by the loop start,
        # converging on the steady loop wave (so the seam is continuous)
        bright = {'bell': 0.25, 'epiano': 0.45, 'pluck': 0.8, 'marimba': 0.3}[kind]
        for h in range(1, H + 1):
            a_end = steady[h - 1]
            a0 = a_end + bright * h ** -0.9 * (h > 1)
            if ls:
                w = np.exp(-np.minimum(t, ls) / max(ls, 1) * (2 + h * 0.6))
                w = np.where(t < ls, (w - w[min(ls, n - 1)]) / (1 - w[min(ls, n - 1)] + 1e-9), 0)
            else:
                w = 0
            amp = a_end + (a0 - a_end) * w
            x += amp * np.sin(2 * np.pi * h * t / per + ph[h - 1])
        if kind in ('bell', 'marimba') and ls:
            ratio = 2.76 if kind == 'bell' else 3.93
            win = np.clip(1 - t / ls, 0, 1) ** 2
            x += 0.5 * win * np.sin(2 * np.pi * ratio * t / per)
        env = np.ones(n)
        if ls:
            env[:ls] = 1 + 1.6 * np.exp(-t[:ls] / (ls / 4)) - 1.6 * np.exp(-ls / (ls / 4))
        x *= env
        x[:16] *= np.linspace(0.3, 1, 16)
    else:
        x = _periodic(steady, n, per, ph)
        if kind == 'flute' and ls:
            noise = rng.standard_normal(n) * np.clip(1 - t / ls, 0, 1) ** 2 * 0.15
            x += np.convolve(noise, np.ones(4) / 4, 'same')
        if kind == 'brass' and ls:        # brass "blat": bright start settling to the loop
            x += np.clip(1 - t / ls, 0, 1) * _periodic(_harm('saw', H) * 0.4, n, per, ph)
        if ls:
            x[:24] *= np.linspace(0, 1, 24)
    return _norm(x, 0.85)


def synth_oneshot(kind, n, seed):
    rng = np.random.default_rng(seed)
    t = np.arange(n) / RATE
    noise = rng.standard_normal(n)

    def hp(x, k=1):
        for _ in range(k):
            x = np.diff(x, prepend=0)
        return x

    def lp(x, w):
        return np.convolve(x, np.ones(w) / w, 'same')
    if kind == 'kick':
        f = 48 + 110 * np.exp(-t / 0.025)
        x = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t / 0.07)
        x[:40] += noise[:40] * np.linspace(.6, 0, 40)
    elif kind == 'snare':
        x = 0.6 * hp(lp(noise, 2)) * np.exp(-t / 0.05) + 0.5 * np.sin(2 * np.pi * 196 * t) * np.exp(-t / 0.03)
    elif kind == 'rim':
        x = np.sin(2 * np.pi * 820 * t) * np.exp(-t / 0.008) + 0.4 * hp(noise) * np.exp(-t / 0.01)
        x += 0.3 * np.sin(2 * np.pi * 1730 * t) * np.exp(-t / 0.005)
    elif kind == 'hat':
        x = hp(noise, 2) * np.exp(-t / 0.012)
    elif kind == 'crash':
        x = hp(noise, 1) * (np.exp(-t / 0.12) * 0.8 + 0.2) * np.clip(1 - t / t[-1], 0, 1)
        x += 0.2 * hp(noise, 2) * np.exp(-t / 0.03)
    elif kind == 'bongo':
        f = 330 * (1 + 0.35 * np.exp(-t / 0.01))
        x = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t / 0.045)
        x += 0.25 * np.sin(2 * np.pi * np.cumsum(f * 1.58) / RATE) * np.exp(-t / 0.02)
    elif kind == 'timpani':
        f = 98 * (1 + 0.05 * np.exp(-t / 0.05))
        x = (np.sin(2 * np.pi * np.cumsum(f) / RATE) + 0.35 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / RATE)
             + 0.2 * np.sin(2 * np.pi * np.cumsum(f * 1.99) / RATE)) * np.exp(-t / 0.18)
        x += 0.3 * lp(noise, 6) * np.exp(-t / 0.02)
    else:
        x = noise * np.exp(-t / 0.05)
    x[-48:] *= np.linspace(1, 0, 48)
    return _norm(x, 0.9)


def build_samples(sp):
    blob = bytearray(sp['blob_bytes'])
    plans = {}
    for i, e in enumerate(sp['samples']):
        kind = TIMBRE[i]
        if e['loop']:
            x = synth_loop_sample(kind, e['blocks'], e['loop_block'], 500 + i)
            plans[i] = pitch_plan(e['blocks'] - e['loop_block'])
        else:
            x = synth_oneshot(kind, e['blocks'] * 16, 500 + i)
        pcm = np.round(np.clip(x, -1, 1) * 32000).astype(np.int16)
        b = brr.encode(pcm, e['loop_block'] if e['loop'] else None)
        assert len(b) == e['blocks'] * 9
        blob[e['offset']:e['offset'] + len(b)] = b
    dirb = bytearray()
    for k in sp['dir']:
        e = sp['samples'][k]
        s = SAMPLE_BASE + e['offset']
        dirb += struct.pack('<HH', s, s + e.get('loop_block', 0) * 9)
    assert len(dirb) == sp['dir_bytes']
    data = (struct.pack('<HH', len(dirb), SAMPLE_DIR) + dirb +
            struct.pack('<HH', len(blob), SAMPLE_BASE) + bytes(blob) + bytes.fromhex(sp['tail']))
    return data, plans


# ================================================================ instruments
def adsr(ar, dr, sl, sr):
    return 0x80 | dr << 4 | ar, sl << 5 | sr


ENV = {'sus': adsr(15, 7, 7, 0), 'pluck': adsr(15, 5, 3, 13), 'stac': adsr(15, 6, 2, 18),
       'pad': adsr(10, 2, 6, 6), 'bell': adsr(15, 4, 2, 12), 'drum': adsr(15, 7, 7, 0),
       'swell': adsr(11, 3, 6, 3), 'long': adsr(15, 3, 5, 8)}
S = {v: k for k, v in TIMBRE.items()}
# music instruments (DA argument = index - 1)
INSTR = [('square', 'sus'), ('pulse25', 'sus'), ('triangle', 'sus'), ('saw', 'sus'), ('reed', 'sus'),
         ('bell', 'bell'), ('organ', 'sus'), ('strings', 'pad'), ('epiano', 'pluck'), ('pluck', 'pluck'),
         ('brass', 'swell'), ('marimba', 'bell'), ('flute', 'sus'), ('triangle', 'pluck'), ('saw', 'stac'),
         ('bongo', 'drum'), ('timpani', 'drum'), ('square', 'stac'), ('strings', 'stac')]
IN = {'square': 1, 'pulse': 2, 'tri': 3, 'saw': 4, 'reed': 5, 'bell': 6, 'organ': 7, 'strings': 8,
      'epiano': 9, 'pluck': 10, 'brass': 11, 'marimba': 12, 'flute': 13, 'tribass': 14, 'sawbass': 15,
      'bongo': 16, 'timp': 17, 'sqstac': 18, 'pizz': 19}
# drum kit D0..D8: (sample, key that plays the sample near its own rate with multiplier 2)
PERC_KIT = [('kick', 60), ('snare', 60), ('hat', 62), ('crash', 60), ('rim', 60), ('bongo', 52),
            ('bongo', 57), ('timpani', 55), ('crash', 54)]
KICK, SNARE, HAT, CRASH, RIM, TOMLO, TOMHI, TIMP, CRASHLO = range(9)
# SFX instruments (9 bytes each): ids 7, 8, 9 are used by the player's fixed jump/double/ZEEP-drum code
SFX_INSTR_DEF = [('square', 'sus', 0x60), ('pulse25', 'sus', 0x60), ('triangle', 'sus', 0x70),
                 ('saw', 'sus', 0x50), ('bell', 'bell', 0x60), ('marimba', 'bell', 0x68), ('square', 'sus', 0x50),
                 ('marimba', 'bell', 0x60), ('pulse25', 'stac', 0x58), ('bongo', 'drum', 0x60),
                 ('kick', 'drum', 0x7f), ('snare', 'drum', 0x70), ('crash', 'drum', 0x60), ('timpani', 'drum', 0x7f),
                 ('pluck', 'pluck', 0x60), ('brass', 'swell', 0x58), ('flute', 'sus', 0x60), ('organ', 'sus', 0x58)]
SI = {n: i for i, n in enumerate(['sq', 'pulse', 'tri', 'saw', 'bell', 'mar', 'noise', 'double', 'jump', 'bongo',
                                  'kick', 'snare', 'crash', 'timp', 'pluck', 'brass', 'flute', 'organ'])}


class Tables:
    def __init__(self, plans):
        self.plans = plans

    def mult(self, sname):
        i = S[sname]
        return self.plans[i][1] if i in self.plans else 2

    def octave(self, sname):
        i = S[sname]
        return self.plans[i][2] if i in self.plans else None

    def maxpp(self, sname):
        i = S[sname]
        return self.plans[i][3] if i in self.plans else 69

    def music_instr(self):
        out = bytearray()
        for sname, env in INSTR:
            a1, a2 = ENV[env]
            out += bytes([S[sname], a1, a2, 0x7f, self.mult(sname)])
        return bytes(out)

    def perc(self):
        out = bytearray()
        for sname, key in PERC_KIT:
            a1, a2 = ENV['drum']
            out += bytes([S[sname], a1, a2, 0x7f, 2, 0x80 + key])
        return bytes(out)

    def sfx_instr(self):
        out = bytearray()
        for sname, env, vol in SFX_INSTR_DEF:
            a1, a2 = ENV[env]
            out += bytes([vol, vol, 0, 0, S[sname], a1, a2, 0x7f, self.mult(sname)])
        return bytes(out)

    def pp(self, inst, midi):
        """MIDI key -> N-SPC key for music instrument index (1-based), folded into range."""
        sname = INSTR[inst - 1][0]
        k = self.octave(sname)
        if k is None:               # one-shot drum used melodically: its own rate near key 60
            return int(np.clip(midi - 12, 30, 66))
        pp = midi - 24 - 12 * k
        top = self.maxpp(sname)
        while pp > top:
            pp -= 12
        while pp < 0:
            pp += 12
        return pp

    def sfx_pp(self, inst, midi):
        sname = SFX_INSTR_DEF[inst][0]
        k = self.octave(sname)
        if k is None:
            return int(np.clip(midi - 12, 20, 69))
        pp = midi - 24 - 12 * k
        top = self.maxpp(sname)
        while pp > top:
            pp -= 12
        while pp < 0:
            pp += 12
        return pp


# ================================================================ moods (our choice per slot)
# mood: (compose moods, instrument palette, echo, drums wanted)
PALETTE = {
    'meadow':   dict(lead='square', counter='pulse', arp='marimba', chords='pluck', bass='tribass', mood=['bright', 'happy']),
    'hills':    dict(lead='pulse', counter='square', arp='bell', chords='pizz', bass='tribass', mood=['heroic', 'fast']),
    'cave':     dict(lead='marimba', counter='pluck', arp='bell', chords='pluck', bass='sawbass', mood=['minor', 'calm']),
    'water':    dict(lead='flute', counter='epiano', arp='bell', chords='strings', bass='tri', mood=['calm', 'major'], pad=True),
    'castle':   dict(lead='organ', counter='brass', arp='organ', chords='strings', bass='sawbass', mood=['dark', 'tense'], pad=True),
    'ghost':    dict(lead='epiano', counter='flute', arp='bell', chords='strings', bass='pizz', mood=['eerie', 'slow'], pad=True),
    'boss':     dict(lead='brass', counter='saw', arp='sqstac', chords='strings', bass='sawbass', mood=['tense', 'fast']),
    'star':     dict(lead='square', counter='pulse', arp='sqstac', chords='pizz', bass='sawbass', mood=['bright', 'fast', 'busy']),
    'switch':   dict(lead='reed', counter='marimba', arp='sqstac', chords='pizz', bass='tribass', mood=['tense', 'fast', 'busy']),
    'bonus':    dict(lead='bell', counter='marimba', arp='pluck', chords='pizz', bass='tribass', mood=['happy', 'major']),
    'fanfare':  dict(lead='brass', counter='square', arp='pulse', chords='strings', bass='tribass', mood=['triumphant']),
    'sad':      dict(lead='flute', counter='epiano', arp='bell', chords='strings', bass='tri', mood=['sad', 'slow'], pad=True),
    'sting':    dict(lead='bell', counter='square', arp='pulse', chords='strings', bass='tri', mood=['major']),
    'map':      dict(lead='flute', counter='pulse', arp='marimba', chords='pluck', bass='tribass', mood=['calm', 'happy']),
    'plateau':  dict(lead='reed', counter='pluck', arp='marimba', chords='pizz', bass='tribass', mood=['bright']),
    'forest':   dict(lead='epiano', counter='flute', arp='bell', chords='strings', bass='tri', mood=['dorian'], pad=True),
    'valley':   dict(lead='brass', counter='organ', arp='sqstac', chords='strings', bass='sawbass', mood=['dark']),
    'credits':  dict(lead='flute', counter='epiano', arp='bell', chords='strings', bass='tribass', mood=['calm', 'major'], pad=True),
    'march':    dict(lead='brass', counter='square', arp='pluck', chords='pizz', bass='tribass', mood=['heroic']),
}
MOODS = {
    'kSpcLevelMusicBank': {1: 'water', 2: 'meadow', 3: 'hills', 4: 'boss', 5: 'castle', 6: 'cave', 7: 'ghost',
                           8: 'castle', 9: 'sad', 10: 'sad', 11: 'fanfare', 12: 'fanfare', 13: 'star', 14: 'switch',
                           15: 'sting', 16: 'sting', 17: 'sting', 18: 'bonus', 19: 'fanfare', 20: 'sting',
                           21: 'march', 22: 'boss', 23: 'boss', 24: 'boss', 25: 'boss', 26: 'boss', 27: 'fanfare',
                           28: 'sad', 29: 'boss'},
    'kSpcOverworldMusicBank': {1: 'map', 2: 'plateau', 3: 'forest', 4: 'valley', 5: 'map', 6: 'bonus', 7: 'valley',
                               8: 'fanfare', 9: 'map'},
    'kSpcCreditsMusicBank': {1: 'credits', 2: 'sting', 3: 'credits', 4: 'march'},
}
VOL = {'lead': 0xd8, 'counter': 0xa8, 'arp': 0x90, 'chords': 0x88, 'bass': 0xd0, 'drums': 0xc0, 'bongo': 0xb0}
PAN = {'lead': 10, 'counter': 13, 'arp': 7, 'chords': 12, 'bass': 10, 'drums': 9, 'bongo': 14}


# ================================================================ arrangement
def plan_roles(facts, slot, pal):
    chans = sorted(int(c) for c in facts['channels'])
    info = facts['channels']
    ndr = min(2, sum(info[str(c)]['reg'] == 'drums' for c in chans))
    bongo = slot in BONGO_SLOTS and 5 in chans
    free = [c for c in chans if not (bongo and c == 5)]
    nmel = len(free) - ndr
    roles = ['lead', 'bass', 'counter', 'arp', 'chords', 'chords', 'chords', 'chords'][:max(nmel, 0)]
    if nmel == 3:
        roles = ['lead', 'bass', 'arp' if pal.get('pad') is None else 'chords']
    roles += ['drums'] * ndr
    # sfx steal channels 4, 6, 7: give them accompaniment, keep lead/bass on 0..3/5
    prio = sorted(free, key=lambda c: (c in (4, 6, 7), c))
    order = [r for r in roles if r not in ('drums',)] + ['drums'] * ndr
    asg = {}
    mel = [c for c in prio]
    for r in order:
        if r == 'drums':
            c = max(mel)               # drums take the highest free channel
        else:
            c = mel[0]
        mel.remove(c)
        asg[c] = r
    if bongo:
        asg[5] = 'bongo'
    return asg


def timebase(tempo):
    rate = nspc.tick_rate(tempo)
    beat = 48 if rate * 60 / 48 >= 72 else 24
    return beat, rate * 60 / beat


def mono(notes, t0, t1, beat):
    """Monophonic note list (time, key, vel, dur) in [t0, t1) -> track events in MIDI keys."""
    ev = []
    t = t0
    notes = sorted(n for n in notes if t0 <= n[0] < t1)
    keep = []
    for n in notes:
        if keep and keep[-1][0] == n[0]:
            if n[1] > keep[-1][1]:
                keep[-1] = n
            continue
        keep.append(n)
    for i, (nt, key, vel, dur) in enumerate(keep):
        if nt > t:
            ev.append(['r', nt - t])
        nxt = keep[i + 1][0] if i + 1 < len(keep) else t1
        ioi = nxt - nt
        dur = max(1, min(dur, ioi))
        vi = int(np.clip(round(vel / 127 * 15), 4, 15))
        if ioi - dur >= beat:
            ev.append(['n', key, dur, vi, 7])
            ev.append(['r', ioi - dur])
        else:
            g = dur / ioi
            gi = 7 if g > 0.92 else 5 if g > 0.7 else 3
            ev.append(['n', key, ioi, vi, gi])
        t = nxt
    if t < t1:
        ev.append(['r', t1 - t])
    out = []
    for e in ev:                    # merge rests
        if e[0] == 'r' and out and out[-1][0] == 'r':
            out[-1][1] += e[1]
        else:
            out.append(e)
    return out


def drum_lines(notes, ndr):
    """compose drum notes -> one or two monophonic lines of (time, drum, vel, dur)."""
    mp = {36: KICK, 38: SNARE, 42: HAT, 46: HAT, 49: CRASH}
    by = {}
    for n in notes:
        by.setdefault(n.time, []).append(n)
    a, b = [], []
    for t in sorted(by):
        hits = sorted(by[t], key=lambda n: [36, 38, 49, 46, 42].index(n.key) if n.key in (36, 38, 49, 46, 42) else 9)
        main = [n for n in hits if n.key in (36, 38, 49)]
        hats = [n for n in hits if n.key in (42, 46)]
        if ndr >= 2:
            if main:
                a.append((t, mp[main[0].key], main[0].vel, main[0].dur))
            if hats:
                b.append((t, mp[hats[0].key], hats[0].vel, hats[0].dur))
        else:
            n = hits[0]
            a.append((t, mp.get(n.key, HAT), n.vel, n.dur))
    return [a, b][:max(1, ndr)]


class Arranger:
    def __init__(self, tabs):
        self.tabs = tabs

    def material(self, facts, slot, mood, seed, length, loop=None, cadence=False):
        """compose() output split per our channel -> {ch: [(t, key, vel, dur)]}, drum flags."""
        pal = PALETTE[mood]
        asg = plan_roles(facts, slot, pal)
        beat, bpm = timebase(facts['tempo'])
        croles = []
        for r in asg.values():
            if r in ('bongo',):
                continue
            if r == 'chords':
                r = 'pad' if pal.get('pad') else 'chords'
            if r not in croles:
                croles.append(r)
        song = C.compose(bpm=bpm, length=length, loop=loop, roles=croles, moods=pal['mood'],
                         seed=seed, division=beat)
        by_role = {}
        for n in song.notes:
            by_role.setdefault(song.roles[n.ch], []).append(n)
        lines = {}
        chord_chs = [c for c, r in asg.items() if r == 'chords']
        drum_chs = [c for c, r in asg.items() if r == 'drums']
        for c, r in asg.items():
            if r in ('lead', 'bass', 'counter', 'arp'):
                lines[c] = [(n.time, n.key, n.vel, n.dur) for n in by_role.get(r, [])]
        cr = 'pad' if pal.get('pad') else 'chords'
        if chord_chs:
            groups = {}
            for n in by_role.get(cr, []):
                groups.setdefault(n.time, []).append(n)
            for c in chord_chs:
                lines[c] = []
            for t, g in groups.items():
                g = sorted(g, key=lambda n: n.key)
                for i, c in enumerate(chord_chs):
                    n = g[(i + max(0, len(g) - len(chord_chs))) % len(g)]
                    lines[c].append((n.time, n.key, n.vel, n.dur))
        if drum_chs:
            dl = drum_lines(by_role.get('drums', []), len(drum_chs))
            for c, l in zip(sorted(drum_chs), dl):
                lines[c] = l
        if 5 in asg and asg[5] == 'bongo':
            lines[5] = self.bongo(length, beat, seed)
        if cadence:
            self.cadence(lines, asg, song, length, beat)
        return lines, asg, beat, song

    @staticmethod
    def bongo(length, beat, seed):
        rng = np.random.default_rng(seed + 77)
        step = beat // 2
        pat = []
        for i in range(8):
            if i == 0 or rng.uniform() < 0.55:
                pat.append((i * step, 57 + 12 if rng.uniform() < 0.4 else 52 + 12))
        out = []
        for b0 in range(0, length, 4 * beat):
            for t, k in pat:
                if b0 + t < length:
                    out.append((b0 + t, k, 100, step))
        return out

    @staticmethod
    def cadence(lines, asg, song, length, beat):
        cad = min(2 * beat, max(beat // 2, length // 3))
        t0 = length - cad
        scale = C.MODES[song.mode]
        tones = [0, scale[2], scale[4], 12]
        mels = [c for c, r in asg.items() if r in ('lead', 'counter', 'arp', 'chords', 'bass')]
        for i, c in enumerate(sorted(mels, key=lambda c: ['lead', 'counter', 'arp', 'chords', 'bass'].index(asg[c]))):
            r = asg[c]
            lines[c] = [n for n in lines[c] if n[0] < t0]
            base = song.root + (12 if r == 'lead' else -12 if r == 'bass' else 0)
            lines[c].append((t0, base + tones[i % 4] if r != 'bass' else base, 110, cad))
        for c, r in asg.items():
            if r == 'drums':
                lines[c] = [n for n in lines[c] if n[0] < t0] + [(t0, CRASH, 110, cad)]
                break

    def tracks(self, lines, asg, mood, t0, t1, beat, setup, facts):
        pal = PALETTE[mood]
        out = {}
        for c, r in asg.items():
            evs = []
            if r in ('drums',):
                raw = mono([(t, d, v, du) for t, d, v, du in lines.get(c, [])], t0, t1, beat)
                for e in raw:
                    if e[0] == 'n':
                        evs.append(('p', e[1], e[2], e[3], e[4]))
                    else:
                        evs.append(('r', e[1]))
                inst = None
            else:
                inst = IN['bongo'] if r == 'bongo' else IN[pal[r] if r in pal else pal['chords']]
                raw = mono(lines.get(c, []), t0, t1, beat)
                for e in raw:
                    if e[0] == 'n':
                        evs.append(('n', self.tabs.pp(inst, e[1]), e[2], e[3], e[4]))
                    else:
                        evs.append(('r', e[1]))
            if setup:
                pre = []
                if inst:
                    pre.append(('x', 0xda, inst - 1))
                pre += [('x', 0xe7, VOL[r]), ('x', 0xdb, PAN[r])]
                if r == 'lead' and mood in ('water', 'ghost', 'sad', 'forest', 'credits', 'castle'):
                    pre.append(('x', 0xde, 24, 18, 0x30))
                if c == min(asg):
                    pre.append(('x', 0xe2, facts['tempo'] - 1))
                    if facts.get('echo') or pal.get('pad') and mood in ('water', 'ghost'):
                        mask = sum(1 << k for k, rr in asg.items() if rr not in ('drums', 'bass'))
                        pre += [('x', 0xf1, 2, 0x50, 0), ('x', 0xef, mask, 0x28, 0x28)]
                    else:
                        pre.append(('x', 0xf0))
                evs = pre + evs
            out[c] = evs
        return out

    def song(self, facts, slot, mood, seed, mat_bars):
        """-> (patterns, loop index)."""
        beat, _ = timebase(facts['tempo'])
        bar = 4 * beat
        length, loop = facts['length'], facts['loop']
        pats = []
        ploop = None
        if length <= 2 * bar and loop is None:
            lines, asg, beat, _ = self.material(facts, slot, mood, seed, length, cadence=True)
            return [self.tracks(lines, asg, mood, 0, length, beat, True, facts)], None
        if loop is None:
            intro = 0
            body = length
        else:
            intro, body = loop, length - loop
        if intro:
            lines, asg, beat, _ = self.material(facts, slot, mood, seed + 1, intro)
            for a in range(0, intro, 2 * bar):
                pats.append(self.tracks(lines, asg, mood, a, min(intro, a + 2 * bar), beat, a == 0, facts))
            ploop = len(pats)
        else:
            ploop = 0
        mat = min(mat_bars * bar, body)
        sec_a = (mat // bar // 2) * bar if mat >= 4 * bar else None
        lines, asg, beat, _ = self.material(facts, slot, mood, seed, mat, loop=sec_a,
                                            cadence=(loop is None and mat >= body))
        win = [(a, min(mat, a + 2 * bar)) for a in range(0, mat, 2 * bar)]
        cache = {}
        t = 0
        k = 0
        while t < body:
            a, b = win[k % len(win)]
            n = min(b - a, body - t)
            key = (a, n, k == 0 and not intro)
            if key not in cache:
                cache[key] = self.tracks(lines, asg, mood, a, a + n, beat, a == 0, facts)
            pats.append(cache[key])
            t += n
            k += 1
        if loop is None:
            ploop = None
            # end on a held tonic: replace the final pattern with a cadenced copy
            if mat < body:
                last = pats[-1]
                ln = nspc.track_ticks(next(iter(last.values())))
                fac = dict(facts, length=ln, loop=None)
                lines2, asg2, beat2, _ = self.material(fac, slot, mood, seed + 5, ln, cadence=True)
                pats[-1] = self.tracks(lines2, asg2, mood, 0, ln, beat2, False, facts)
        return pats, ploop


# ================================================================ SFX
def sfx_stream(steps, tabs, port):
    """steps: ('i', inst[, noise]) | ('n', midi, ticks, vol) | ('s', midi, ticks, vol, target, slide[, delay])
    | ('b', target, ticks, slide[, delay]) | ('loop',). Ends with a short silent note (key off)."""
    out = bytearray()
    cur_len, cur_vol = None, None
    inst = 0
    last_key = 60
    steps = list(steps)
    if steps[-1][0] not in ('loop',) and not (steps[-1][0] == 'n' and steps[-1][3] == 0):
        steps.append(('n', last_key, 3, 0))
    for s in steps:
        k = s[0]
        if k == 'i':
            out.append(0xda)
            if len(s) > 2 and s[2]:
                assert port == 3
                out.append(0x80)
            out.append(s[1])
            inst = s[1]
            continue
        if k == 'loop':
            out.append(0xff)
            continue
        ticks = max(3, min(0x7f, s[2]))
        vol = s[3] if k in ('n', 's') else None
        if ticks != cur_len or (vol is not None and vol != cur_vol):
            out.append(ticks)
            cur_len = ticks
            if vol is not None and vol != cur_vol:
                out.append(min(0x7f, int(round(vol * SFX_GAIN))))
                cur_vol = vol
        if k == 'n':
            out.append(0x80 + tabs.sfx_pp(inst, s[1]))
            last_key = s[1]
        elif k == 's':
            d = s[6] if len(s) > 6 else 0
            out += bytes([0xdd, 0x80 + tabs.sfx_pp(inst, s[1]), d, max(1, s[5]), 0x80 + tabs.sfx_pp(inst, s[4])])
        elif k == 'b':
            d = s[4] if len(s) > 4 else 0
            out += bytes([0xeb, d, max(1, s[3]), 0x80 + tabs.sfx_pp(inst, s[1])])
    out.append(0)
    return bytes(out)


def _arp(inst, keys, step, vol, decay=0):
    out = [('i', SI[inst])]
    for i, k in enumerate(keys):
        out.append(('n', k, step, max(8, vol - decay * i)))
    return out


def _sweep(inst, a, b, ticks, vol, noise=False):
    return [('i', SI[inst], noise), ('s', a, ticks, vol, b, ticks)]


def _noise(ticks, vol, steps=4, key=60):
    out = [('i', SI['noise'], True)]
    per = max(3, ticks // steps)
    for i in range(steps):
        out.append(('n', key, per, max(6, int(vol * (1 - i / steps)))))
    return out


def sfx_designs(spec):
    """Our sound for every id; durations follow the kept tick counts. Roles from the port's call sites."""
    p0, p3 = {}, {}
    T = lambda port, i: max(6, spec['port%d' % port][str(i)]['ticks'])   # noqa: E731
    # ---------------- port 0 (channel 4)
    p0[1] = _sweep('sq', 50, 43, 7, 0x50)                                  # head bump
    p0[2] = [('i', SI['kick']), ('n', 60, 6, 0x60), ('i', SI['pulse']), ('s', 79, 28, 0x48, 67, 24)]   # hit enemy
    p0[3] = [('i', SI['kick']), ('n', 62, 4, 0x70), ('i', SI['sq']), ('n', 86, 8, 0x40)]   # kick shell
    p0[4] = [('i', SI['pulse'])] + [x for k in (72, 67, 63, 60, 55, 51) for x in [('s', k, 12, 0x48, k - 3, 10)]]  # pipe / shrink
    p0[5] = _arp('bell', [67, 71, 74, 79, 83, 86], 14, 0x50, 4)              # checkpoint
    p0[6] = _sweep('tri', 74, 50, 54, 0x60)                                # gulp
    p0[7] = [('i', SI['saw']), ('s', 60, 18, 0x40, 72, 16), ('s', 72, 21, 0x38, 58, 18)]      # throw
    p0[8] = [('i', SI['kick']), ('n', 55, 20, 0x7f), ('i', SI['tri']), ('s', 48, 37, 0x50, 36, 30)]  # thud
    p0[9] = [('i', SI['flute']), ('s', 62, 25, 0x48, 81, 22), ('s', 81, 26, 0x40, 70, 22)]   # cape swoop
    p0[10] = _arp('pulse', [60, 65, 63, 68, 66, 71, 69, 74, 72, 77], 9, 0x48)  # power-up appears
    p0[11] = _arp('mar', [76, 69], 13, 0x58)                               # switch / flip
    p0[12] = _arp('bell', [84, 79, 76, 72, 76, 79, 84, 88], 15, 0x50, 3)   # item to reserve box
    p0[13] = [('i', SI['flute'])] + [('n', k, 9, 0x48) for k in (72, 76, 74, 77, 76, 79, 77, 81, 79, 83, 84, 88)]  # feather
    p0[14] = _sweep('tri', 55, 67, 33, 0x48)                               # swim stroke
    p0[15] = _sweep('saw', 70, 46, 46, 0x48)                               # hurt / net flip
    p0[16] = [('i', SI['saw'])] + [('s', 48 + 4 * i, 12, 0x40, 52 + 4 * i, 10) for i in range(6)]   # magic / fire breath
    p0[17] = _arp('bell', [81, 76], 30, 0x50)                              # pause
    p0[18] = _arp('bell', [76, 81], 30, 0x50)                              # unpause
    for i, k in zip(range(19, 26), (64, 66, 68, 71, 73, 76, 78)):          # stomp combo 1..7
        p0[i] = [('i', SI['sq']), ('n', k, 6, 0x50), ('n', k + 7, 6, 0x48)]
    p0[26] = _arp('pulse', [72, 79], 12, 0x40)
    p0[27] = _arp('pulse', [79, 72], 12, 0x40)
    p0[28] = [('i', SI['mar']), ('n', 57, 18, 0x60), ('n', 64, 18, 0x50)]   # block "dong"
    p0[29] = [('i', SI['sq'])] + [('n', k, 9, 0x24) for _ in range(6) for k in (77, 82, 80, 84)]   # hurry (with port 3 #29)
    p0[30] = [('i', SI['timp']), ('n', 48, 25, 0x7f), ('n', 43, 25, 0x7f), ('n', 48, 25, 0x70)]   # key / door rumble
    p0[31] = [('i', SI['saw'])] + [('s', 84 - 8 * i, 57, 0x48 - 6 * i, 76 - 8 * i, 50) for i in range(5)]   # boss falls
    p0[32] = _sweep('pulse', 67, 79, 27, 0x50)                             # spit
    p0[33] = [('i', SI['kick'])] + [('n', 50 + (i % 2) * 2, 12, 0x60) for i in range(15)] + [('loop',)]  # rumble (loops)
    p0[34] = []
    p0[35] = _sweep('sq', 76, 64, 39, 0x50)                                # boss hurt
    p0[36] = []
    p0[37] = [('i', SI['snare']), ('n', 55, 24, 0x60), ('i', SI['tri']), ('s', 45, 48, 0x50, 60, 40)]   # lava splash
    p0[38] = p0[40] = _sweep('flute', 60, 96, 75, 0x48)                    # firework whistle
    p0[39] = p0[41] = [('i', SI['crash']), ('n', 55, 60, 0x7f), ('i', SI['timp']), ('n', 43, 60, 0x60), ('n', 40, 60, 0x40)]  # bang
    p0[42] = [('i', SI['brass']), ('s', 55, 54, 0x58, 43, 50), ('s', 50, 54, 0x50, 38, 50)]   # GRUMBOLT roar
    # ---------------- port 3 (channel 6)
    p3[1] = _arp('bell', [84, 91, 96], 7, 0x58) + [('n', 96, 23, 0x30)]    # coin
    p3[2] = _sweep('pulse', 60, 79, 48, 0x48)                              # item pops out
    p3[3] = [('i', SI['tri']), ('s', 60, 39, 0x50, 84, 30), ('s', 84, 39, 0x48, 60, 30)]   # tongue
    p3[4] = [('i', SI['pulse'])] + [('n', 72 + 5 * (i % 2), 4, 0x48) for i in range(12)]   # spin
    p3[5] = _arp('sq', [67, 72, 76, 79, 84, 88], 8, 0x58)                  # 1-up
    p3[6] = _sweep('sq', 84, 72, 9, 0x50)                                  # fireball
    p3[7] = _noise(64, 0x60, 5)                                            # bricks shatter
    p3[8] = [('i', SI['tri']), ('s', 48, 24, 0x60, 72, 20), ('s', 72, 24, 0x50, 64, 18), ('s', 64, 24, 0x40, 76, 18)]  # spring
    p3[9] = [('i', SI['kick']), ('n', 52, 12, 0x7f)] + _noise(27, 0x40, 3)  # cannon
    p3[10] = _arp('mar', [72, 76, 79, 76, 84], 11, 0x58)                   # egg hatch
    p3[11] = _sweep('pulse', 55, 74, 54, 0x48)                             # sprout
    p3[12] = _sweep('pulse', 86, 62, 90, 0x48)                             # reserve drop
    p3[13] = _arp('mar', [64, 67, 71], 12, 0x50)
    p3[14] = _arp('flute', [72, 67, 72], 16, 0x40)                         # screen scroll
    p3[15] = [('i', SI['timp']), ('n', 43, 36, 0x60), ('i', SI['saw']), ('s', 40, 72, 0x30, 46, 64)]   # door opens
    p3[16] = [('i', SI['kick']), ('n', 48, 39, 0x7f)]                      # door shuts
    p3[17] = [('i', SI['mar']), ('n', 88, 4, 0x48), ('loop',)]             # bonus tally (repeats)
    p3[18] = _arp('mar', [91, 88, 91, 88], 11, 0x48)                       # time tally
    p3[19] = _sweep('flute', 79, 60, 45, 0x48)                             # ZEEP runs off
    p3[20] = _arp('pulse', [60, 64], 12, 0x40)
    p3[21] = _arp('bell', [72, 79, 76, 84], 15, 0x48)                      # map path piece
    p3[22] = _arp('bell', [60, 67, 72, 79, 76, 84, 88, 91], 12, 0x48, 3)   # map path revealed
    p3[23] = _noise(96, 0x58, 6)                                           # fire / lightning
    p3[24] = _noise(240, 0x70, 10)                                         # thunder
    p3[25] = _noise(28, 0x50, 2)                                           # pop
    p3[26] = [('i', SI['crash']), ('n', 50, 48, 0x7f), ('i', SI['timp']), ('n', 40, 48, 0x7f)]   # explosion
    p3[27] = _noise(98, 0x70, 7)                                           # castle crumbles
    p3[28] = _arp('mar', [60, 67, 64, 71, 67, 74, 71, 79], 12, 0x50)       # switch blocks fly
    p3[29] = [('i', SI['sq'])] + [('n', k, 9, 0x1c) for _ in range(6) for k in (65, 70, 68, 72)]   # hurry (pair)
    p3[30] = [('i', SI['flute']), ('s', 84, 19, 0x48, 96, 16), ('s', 96, 19, 0x40, 84, 16)]   # whistle
    p3[31] = _sweep('tri', 76, 57, 57, 0x58)                               # baby ZEEP gulp
    p3[32] = _noise(84, 0x50, 6)                                           # Thornling falls
    p3[33] = _sweep('pulse', 72, 84, 30, 0x48)                             # ZEEP off
    p3[34] = _arp('bell', [72, 79, 84, 79, 76, 72], 14, 0x48, 2)           # message box
    p3[35] = _sweep('tri', 67, 72, 12, 0x40)                               # map step
    p3[36] = _arp('bell', [60, 66, 72, 78, 84, 90], 16, 0x50)              # keyhole
    p3[37] = _sweep('flute', 72, 91, 15, 0x48)                             # launch
    p3[38] = _noise(33, 0x40, 3)                                           # flapping
    p3[39] = _noise(14, 0x50, 2)                                           # lava ball
    p3[40] = [('i', SI['kick']), ('n', 57, 10, 0x7f), ('i', SI['sq']), ('s', 79, 27, 0x50, 67, 24)]   # boss stomp
    p3[41] = _sweep('tri', 69, 48, 44, 0x58)                               # swallow
    p3[42] = [('i', SI['mar']), ('n', 64, 30, 0x60)]                       # block hit
    p3[43] = _sweep('pulse', 60, 72, 75, 0x40)
    p3[44] = _noise(180, 0x48, 8)
    for i in range(45, 52):
        p3[i] = _noise(18, 0x38, 2)
    return p0, p3


# ================================================================ build
def build_engine(tabs, spec):
    p0, p3 = sfx_designs(spec['sfx'])
    data = bytearray()
    ptr0, ptr3 = {}, {}
    seen = {}
    end_only = None
    for port, table, ptrs in ((3, p3, ptr3), (0, p0, ptr0)):
        for i in sorted(table):
            steps = table[i]
            b = sfx_stream(steps, tabs, port) if steps else b'\0'
            if b == b'\0' and end_only is not None:
                ptrs[i] = end_only
                continue
            if (port, b) in seen:
                ptrs[i] = seen[(port, b)]
                continue
            a = SFX_DATA + len(data)
            seen[(port, b)] = a
            if b == b'\0':
                end_only = a
            ptrs[i] = a
            data += b
    blk = bytearray(ENGINE_END - SFX_INSTR)
    si = tabs.sfx_instr()
    blk[0:len(si)] = si
    for i in range(1, N_P3 + 1):
        struct.pack_into('<H', blk, SFX_P3 + 2 * i - SFX_INSTR, ptr3.get(i, end_only))
    for i in range(1, N_P0 + 1):
        struct.pack_into('<H', blk, SFX_P0 + 2 * i - SFX_INSTR, ptr0.get(i, end_only))
    assert SFX_DATA + len(data) <= MUS_INSTR, 'SFX data too big: %d' % len(data)
    blk[SFX_DATA - SFX_INSTR:SFX_DATA - SFX_INSTR + len(data)] = data
    mi, pc = tabs.music_instr(), tabs.perc()
    blk[MUS_INSTR - SFX_INSTR:MUS_INSTR - SFX_INSTR + len(mi)] = mi
    blk[PERC - SFX_INSTR:PERC - SFX_INSTR + len(pc)] = pc
    assert PERC + len(pc) == ENGINE_END
    return nspc.upload([(SFX_INSTR, bytes(blk))]), len(data)


SEEDS = {'kSpcLevelMusicBank': 1100, 'kSpcOverworldMusicBank': 2200, 'kSpcCreditsMusicBank': 3300}
# seed bumps picked after the originality gate flagged a chance overlap (a short loop shares a
# few interval 6-grams): (bank, slot) -> extra seed
RESEED = {('kSpcLevelMusicBank', 13): 1, ('kSpcLevelMusicBank', 12): 1, ('kSpcOverworldMusicBank', 5): 4}


def build_bank(name, bspec, tabs, log=None):
    arr = Arranger(tabs)
    songs = {int(k): v for k, v in bspec['songs'].items()}
    level = {s: 16 for s in songs if 'alias' not in songs[s]}
    budget = bspec['budget']

    def assemble():
        bank = nspc.Bank(TABLE, bspec['slots'])
        for s, f in songs.items():
            if 'alias' in f:
                bank.alias(s, f['alias'])
                continue
            pats, loop = arr.song(f, s, MOODS[name][s], SEEDS[name] + 17 * s + 1000 * RESEED.get((name, s), 0), level[s])
            bank.add_song(s, pats, loop)
        return bank.build()
    for _ in range(40):
        data, ptrs = assemble()
        if len(data) <= budget:
            break
        # shrink the longest-material song that can still shrink
        cand = [s for s in level if level[s] > 4]
        if not cand:
            raise RuntimeError('%s: cannot fit %d > %d' % (name, len(data), budget))
        big = max(cand, key=lambda s: (level[s], songs[s]['length']))
        level[big] -= 4
    assert TABLE + len(data) <= SFX_INSTR
    if log is not None:
        log.append('%s %d/%d bytes, material bars %s' % (name, len(data), budget, sorted(set(level.values()))))
    return nspc.upload([(TABLE, data)])


def build(items, kept, spec_dir):
    spec = json.load(open(os.path.join(spec_dir, 'music.json')))
    sp = json.load(open(os.path.join(spec_dir, 'samples.json')))
    samples, plans = build_samples(sp)
    tabs = Tables(plans)
    engine, nsfx = build_engine(tabs, spec)
    out = {'kSpcSamples': samples, 'kSpcEngine': engine}
    log = []
    for name, b in spec['banks'].items():
        out[name] = build_bank(name, b, tabs, log)
    print('  music: ' + '; '.join(log) + '; sfx data %d B' % nsfx)
    return out


if __name__ == '__main__':
    from games.smw import assetfile as A
    import sys
    it = dict(A.read(sys.argv[1] if len(sys.argv) > 1 else 'D:/n64work/smw/clean/smw_assets.dat'))
    res = build(it, None, os.path.join(os.path.dirname(__file__), 'spec'))
    print({k: len(v) for k, v in res.items()})
