"""Originality exporter for music: every song slot of the three banks as a MIDI file
music/<bank>_<slot>.mid (one pass up to the loop jump or the end; drums on channel ch+8).
Same code for the retail-derived (dirty) and the clean .dat. Slots that share a song with an
earlier slot are skipped."""
import os

from cleanroom.audio import midi, nspc

BANKS = (('kSpcLevelMusicBank', 'level', 29), ('kSpcOverworldMusicBank', 'overworld', 9),
         ('kSpcCreditsMusicBank', 'credits', 12))
TABLE = 0x1360


def export(items, outdir):
    n = 0
    for name, short, slots in BANKS:
        if not items.get(name):
            continue
        ram = nspc.load(items[name])
        seen = set()
        for s in range(1, slots + 1):
            ptr = nspc.word(ram, TABLE + 2 * (s - 1))
            if ptr in seen or ptr == 0:
                continue
            seen.add(ptr)
            song = nspc.read_song(ram, ptr)
            notes = nspc.to_notes(song)
            tempo = int(round(60e6 / (nspc.tick_rate(song.tempo) * 60 / 48)))
            loop = (song.loop, song.length) if song.loop is not None else None
            with open(os.path.join(outdir, '%s_%02d.mid' % (short, s)), 'wb') as f:
                f.write(midi.write(notes, 48, tempo, loop))
            n += 1
    return n
