"""SNES planar tile codecs (2bpp / 3bpp / 4bpp, 8x8) and BGR555 palettes."""
import numpy as np

TILE_BYTES = {2: 16, 3: 24, 4: 32}


def decode(data, bpp):
    """bytes -> uint8 array (ntiles, 8, 8) of colour indices."""
    tb = TILE_BYTES[bpp]
    n = len(data) // tb
    a = np.frombuffer(bytes(data[:n * tb]), np.uint8).reshape(n, tb)
    bits = np.unpackbits(a, axis=1).reshape(n, tb, 8)
    out = np.zeros((n, 8, 8), np.uint8)
    for y in range(8):
        out[:, y] |= bits[:, 2 * y] | bits[:, 2 * y + 1] << 1
        if bpp == 3:
            out[:, y] |= bits[:, 16 + y] << 2
        elif bpp == 4:
            out[:, y] |= bits[:, 16 + 2 * y] << 2 | bits[:, 17 + 2 * y] << 3
    return out


def encode(tiles, bpp):
    tiles = np.asarray(tiles, np.uint8)
    n = len(tiles)
    tb = TILE_BYTES[bpp]
    bits = np.zeros((n, tb, 8), np.uint8)
    for y in range(8):
        bits[:, 2 * y] = tiles[:, y] & 1
        bits[:, 2 * y + 1] = tiles[:, y] >> 1 & 1
        if bpp == 3:
            bits[:, 16 + y] = tiles[:, y] >> 2 & 1
        elif bpp == 4:
            bits[:, 16 + 2 * y] = tiles[:, y] >> 2 & 1
            bits[:, 17 + 2 * y] = tiles[:, y] >> 3 & 1
    return np.packbits(bits.reshape(n, tb * 8), axis=1).tobytes()


def sheet(tiles, cols=16):
    """(n,8,8) -> 2D index image, `cols` tiles per row."""
    n = len(tiles)
    rows = -(-n // cols)
    t = np.zeros((rows * cols, 8, 8), tiles.dtype)
    t[:n] = tiles
    return t.reshape(rows, cols, 8, 8).transpose(0, 2, 1, 3).reshape(rows * 8, cols * 8)


def unsheet(img, cols=16):
    h, w = img.shape
    return img.reshape(h // 8, 8, w // 8, 8).transpose(0, 2, 1, 3).reshape(-1, 8, 8)


def bgr555_to_rgb(words):
    w = np.asarray(words, np.uint16).astype(np.int32)
    c = np.stack([w & 31, w >> 5 & 31, w >> 10 & 31], -1)
    return (c * 255 // 31).astype(np.uint8)


def rgb_to_bgr555(rgb):
    c = (np.asarray(rgb, np.int32) * 31 + 127) // 255
    return (c[..., 0] | c[..., 1] << 5 | c[..., 2] << 10).astype(np.uint16)
