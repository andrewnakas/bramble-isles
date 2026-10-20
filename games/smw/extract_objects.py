"""CODE ONLY (no retail data): static scan of the snesrev/smw object routines (smw_0d.c)
for the Map16 block numbers each level object writes.

    python -m games.smw.extract_objects [src_dir]  ->  games/smw/spec/objects.json

Approximate by design: a routine's writes are found by looking at the arguments of
SetMap16LowByte / HandleHorizontalSubScreenCrossingForCurrentObject and the nearest
SetMap16HighByte..._Page00/01 call; table arguments contribute all their values unless
they are indexed by the object number (k - N), in which case each object gets its entry.
Callees inside smw_0d.c are followed. Good enough to tell "which blocks does object X put
down" for drawing and for the level generator; not a substitute for running the code."""
import re, os, sys, json

SRC = 'D:/n64work/smw/pristine/src'
OUT = os.path.join(os.path.dirname(__file__), 'spec', 'objects.json')
ptrs = {}
GROUPS = {'grassland': 'kProcessGrasslandObjects_GrasslandPtrs', 'castle': 'kProcessCastleObjects_CastlePtrs',
          'rope': 'kProcessRopeObjects_RopePtrs', 'underground': 'kProcessUndergroundObjects_UndergroundPtrs',
          'ghosthouse': 'kProcessGhostHouseObjects_GhostHousePtrs'}
WRITE = re.compile(r'(SetMap16LowByte|HandleHorizontalSubScreenCrossingForCurrentObject)\s*\(')


def split_args(s, i):
    """s[i] is just after '(' -> (list of args, index after ')')."""
    depth, cur, args = 0, '', []
    while i < len(s):
        c = s[i]
        if c == '(':
            depth += 1
        elif c == ')':
            if depth == 0:
                args.append(cur.strip())
                return args, i + 1
            depth -= 1
        elif c == ',' and depth == 0:
            args.append(cur.strip()); cur = ''; i += 1; continue
        cur += c
        i += 1
    return args, i


def load(src):
    txt = open(os.path.join(src, 'smw_0d.c'), encoding='latin-1').read().replace('\r\n', '\n')
    tables = {}
    for m in re.finditer(r'const uint(8|16) (k\w+)\[\d*\]\s*=\s*\{([^}]*)\}', txt):
        tables[m.group(2)] = [int(x, 0) for x in re.findall(r'0x[0-9a-fA-F]+|\d+', m.group(3))]
    funcs = {}
    for m in re.finditer(r'^(?:void|uint8|uint16|int8|bool) (\w+)\(([^)]*)\) \{', txt, re.M):
        start = m.end()
        depth, i = 1, start
        while depth:
            depth += {'{': 1, '}': -1}.get(txt[i], 0)
            i += 1
        funcs[m.group(1)] = txt[start:i - 1]
    ptrs = {}
    for m in re.finditer(r'\(\*(k\w+)\[(\d+)\]\)\([^)]*\)\s*=\s*\{([^}]*)\}', txt):
        ptrs[m.group(1)] = [None if x.strip() == 'NULL' else x.strip().lstrip('&') for x in m.group(3).split(',') if x.strip()]
    return tables, funcs, ptrs


def resolve(arg, body, tables, objnum, kconst):
    """-> list of ints this argument can take, or None if unknown."""
    arg = re.sub(r'\(uint8\)', '', arg).strip()
    if re.fullmatch(r'0x[0-9a-fA-F]+|\d+', arg):
        return [int(arg, 0)]
    m = re.fullmatch(r'(k\w+)\[(.*)\]', arg)
    if m and m.group(1) in tables:
        tab, idx = tables[m.group(1)], m.group(2).strip().strip('()')
        if idx.startswith('(') and idx.endswith(')'):
            idx = idx[1:-1]
        var = re.fullmatch(r'(\w+)', idx)
        if var:      # a variable set from k - N earlier in the body
            a = re.search(r'\b%s = \(?(?:uint8\))?\(?k - (\d+)\)?;' % var.group(1), body)
            if a:
                idx = 'k - ' + a.group(1)
            elif var.group(1) == 'k':
                idx = 'k - 0'
        km = re.fullmatch(r'\(?k - (\d+)\)?', idx.strip())
        if km and objnum is not None:
            j = objnum - kconst - int(km.group(1))
            return [tab[j]] if 0 <= j < len(tab) else None
        return sorted(set(tab))
    for name in re.findall(r'k\w+', arg):     # expression over a table
        if name in tables:
            return sorted(set(tables[name]))
    return None


def scan(fn, funcs, tables, objnum, kconst, seen, depth=0):
    global ptrs
    if fn not in funcs or fn in seen or depth > 4:
        return set(), False
    seen = seen | {fn}
    body = funcs[fn]
    out, unknown = set(), False
    lines = body.split('\n')
    pages = []
    for li, ln in enumerate(lines):
        if 'Page01' in ln:
            pages.append((li, 1))
        elif 'Page00' in ln:
            pages.append((li, 0))
    flat = body
    fpages = sorted({p for _, p in pages}) or [0, 1]
    for m in WRITE.finditer(flat):
        args, _ = split_args(flat, m.end())
        if len(args) < 2:
            continue
        li = flat[:m.start()].count('\n')
        near = sorted(pages, key=lambda p: (abs(p[0] - li), p[0] > li))
        page = near[0][1] if near and abs(near[0][0] - li) <= 3 else None
        vals = resolve(args[1], body, tables, objnum, kconst)
        if vals is None:
            unknown = True
            continue
        for v in vals:
            for p in ([page] if page is not None else fpages):
                for b in ([v] if v < 256 else [v & 0xFF, v >> 8]):
                    out.add(p << 8 | b)
    # tables handed to helper routines (their result is written later): all values, function's pages
    for name in set(re.findall(r'\b(k\w*Tiles\w*)\[', body)):
        if name in tables:
            for v in tables[name]:
                for p in fpages:
                    for b in ([v] if v < 256 else [v & 0xFF, v >> 8]):
                        out.add(p << 8 | b)
    for name in set(re.findall(r'\b(k\w+Ptrs)\[', body)):      # sub-routine pointer tables
        for sub in ptrs.get(name, []):
            if sub:
                o, u = scan(sub, funcs, tables, None, kconst, seen, depth + 1)
                out |= o
                unknown |= u
    for callee in set(re.findall(r'\b([A-Z]\w+)\(', body)):
        if callee in funcs and callee != fn and not callee.startswith(('SetMap16', 'HandleHorizontal', 'Handle')):
            o, u = scan(callee, funcs, tables, objnum, kconst, seen, depth + 1)
            out |= o
            unknown |= u
    return out, unknown


def main(src=SRC):
    global ptrs
    tables, funcs, ptrs = load(src)
    res = {'standard': {}, 'extended': {}}
    for g, tab in GROUPS.items():
        for i, fn in enumerate(ptrs[tab]):
            if not fn:
                continue
            b, unk = scan(fn, funcs, tables, i, 0, frozenset())
            res['standard'].setdefault('%02X' % (i + 1), {})[g] = {'routine': fn, 'blocks': ['%03X' % x for x in sorted(b)], 'partial': unk}
    for i, fn in enumerate(ptrs['kProcessExtendedObjects_ExtendedObjectPtrs']):
        if not fn:
            continue
        b, unk = scan(fn, funcs, tables, i, 0, frozenset())
        res['extended']['%02X' % i] = {'routine': fn, 'blocks': ['%03X' % x for x in sorted(b)], 'partial': unk}
    # the generic one-tile objects resolve through a table indexed by k-16 with a page switch at 19
    gt = tables['kExtObjXX_Generic1TileObject_Tiles']
    for i, fn in enumerate(ptrs['kProcessExtendedObjects_ExtendedObjectPtrs']):
        if fn == 'ExtObj18_3upMoon' and 0 <= i - 16 < len(gt):
            v = i - 16
            res['extended']['%02X' % i] = {'routine': fn, 'blocks': ['%03X' % ((1 if v >= 19 else 0) << 8 | gt[v])], 'partial': False}
        elif fn == 'ExtObjXX_Generic1TileObject_GreenStarBlockEntry':
            res['extended']['%02X' % i] = {'routine': fn, 'blocks': ['%03X' % (0x100 | gt[0x32])], 'partial': False}
    # slope collision tables (smw_00.c): surface height per x for each slope kind
    t00 = open(os.path.join(src, 'smw_00.c'), encoding='latin-1').read()
    for nm in ('kSlopeDataTables_ShapeOfSlope', 'kSlopeSteepness_e55e', 'kSlopeSteepness_e5c8', 'kSlopeDataTables_SlopeType'):
        m = re.search(r'%s\[\d+\]\s*=\s*\{([^}]*)\}' % nm, t00)
        res.setdefault('slopes', {})[nm] = [int(x, 0) for x in re.findall(r'0x[0-9a-fA-F]+|\d+', m.group(1))]
    json.dump(res, open(OUT, 'w'), indent=0)
    nstd = sum(len(v) for v in res['standard'].values())
    print('objects.json: %d standard (object, group) routines, %d extended; %d partial' % (
        nstd, len(res['extended']), sum(e['partial'] for v in res['standard'].values() for e in v.values()) +
        sum(e['partial'] for e in res['extended'].values())))


if __name__ == '__main__':
    main(*sys.argv[1:])
