"""Which entries of smw_assets.dat are regenerated (assets) and how they are stored."""
BPP = {i: 3 for i in range(0x34)}
BPP.update({0x28: 2, 0x29: 2, 0x2A: 2, 0x2B: 2, 0x2F: 2, 0x32: 4})   # 0x32 = player sheet, uploaded as 4bpp
GFX32, GFX33 = 0x32, 0x33          # stored uncompressed as their own entries
NSHEETS = 0x34

SAMPLE_BASE = 0x8100               # ARAM address of the BRR block
SAMPLE_DIR = 0x8000
RATE = 32000                       # nominal DSP rate used for descriptors


def is_palette(name):
    return name.startswith('kGlobalPalettes_') or name == 'kPlayerPalettes'


def is_regenerated(name):
    return is_palette(name) or name in ('kGraphicsPtrs', 'kGfx32', 'kGfx33', 'kSpcSamples', 'kRom')
