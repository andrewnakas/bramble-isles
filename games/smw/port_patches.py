"""Patch list for the web build of the snesrev port (applied to a copy of pristine).

    python -m games.smw.port_patches D:/n64work/smw/build/src
"""
import sys, os

WEB_C = r'''// Web glue for the Emscripten build (our own code).
#include <emscripten.h>
#include <string.h>
#include "types.h"
struct RendererFuncs;
void OpenGLRenderer_Create(struct RendererFuncs *funcs) { (void)funcs; }

// Wait for the next 60.1 Hz game frame on the browser's animation clock.
EM_ASYNC_JS(void, web_frame_wait, (void), {
  var P = 1000 / 60.0988, w = Module.__fw || (Module.__fw = { next: performance.now(), run: 0 });
  w.n = (w.n || 0) + 1;
  if (Module.onGameFrame) Module.onGameFrame(w.n);      // dev hooks: keys and dumps by frame number
  if (Module.__turbo && w.n % Module.__turbo) return;   // dev: run several frames per browser frame
  w.next += P;
  var now = performance.now();
  if (now - w.next > 120) w.next = now;
  if (now > w.next + P && w.run < 3) { w.run++; return; }   // behind: catch up without yielding
  w.run = 0;
  do { await new Promise(function (r) { requestAnimationFrame(r); }); } while (performance.now() < w.next - 2);
});

// Dev: snapshot of the PPU (registers, VRAM, CGRAM, OAM) for the offline scene tools.
#include "src/snes/ppu.h"
extern Ppu *g_my_ppu;
static uint8 g_web_ppu_dump[32 + 0x10000 + 0x200 + 0x220];
EMSCRIPTEN_KEEPALIVE uint8 *web_ppu_dump(void) {
  Ppu *p = g_my_ppu;
  uint8 *o = g_web_ppu_dump;
  o[0] = p->bgmode; o[1] = p->obsel;
  memcpy(o + 2, p->bgXsc, 4);
  memcpy(o + 6, &p->bgTileAdr, 2);
  memcpy(o + 8, p->hScroll, 8);
  memcpy(o + 16, p->vScroll, 8);
  memcpy(o + 24, p->screenEnabled, 2);
  memcpy(o + 32, p->vram, 0x10000);
  memcpy(o + 32 + 0x10000, p->cgram, 0x200);
  memcpy(o + 32 + 0x10200, p->oam, 0x220);
  return o;
}

// Dev: the game's work RAM (level Map16 at 0xC800 / 0x1C800, overworld tables) for level tests.
extern uint8 g_ram[0x20000];
EMSCRIPTEN_KEEPALIVE uint8 *web_ram(void) { return g_ram; }

// Persist saves/ (battery save + save states) to IndexedDB.
EM_JS(void, web_sync_saves, (void), {
  if (Module.__syncing) return;
  Module.__syncing = 1;
  FS.syncfs(false, function () { Module.__syncing = 0; });
});

EM_ASYNC_JS(void, web_mount_saves, (void), {
  try { FS.mkdir('/saves'); } catch (e) {}
  try {
    FS.mount(IDBFS, {}, '/saves');
    await new Promise(function (r) { FS.syncfs(true, function () { r(); }); });
  } catch (e) { console.log('saves: no persistent storage'); }
});
'''

PATCHES = {
    'src/main.c': [
        ('#undef main\nint main(int argc, char** argv) {',
         '#ifdef __EMSCRIPTEN__\nvoid web_frame_wait(void);\nvoid web_sync_saves(void);\nvoid web_mount_saves(void);\n#endif\n'
         '#undef main\nint main(int argc, char** argv) {\n#ifdef __EMSCRIPTEN__\n  web_mount_saves();\n#endif'),
        ('    // if vsync isn\'t working, delay manually\n    curTick = SDL_GetTicks();\n',
         '    // if vsync isn\'t working, delay manually\n    curTick = SDL_GetTicks();\n'
         '#ifdef __EMSCRIPTEN__\n    if ((frameCtr & 255) == 0)\n      web_sync_saves();\n'
         '    if (!g_snes->disableRender)\n      web_frame_wait();\n    continue;\n#endif\n'),
        # SDL's own asyncify sleeps (swap, delay) sit behind indirect calls we do not instrument: turn them off
        ('  // set up SDL\n',
         '#ifdef __EMSCRIPTEN__\n  SDL_SetHint("SDL_EMSCRIPTEN_ASYNCIFY", "0");\n#endif\n  // set up SDL\n'),
        ('    if (g_paused) {\n      SDL_Delay(16);',
         '    if (g_paused) {\n#ifdef __EMSCRIPTEN__\n      web_frame_wait();\n      continue;\n#endif\n      SDL_Delay(16);'),
    ],
}


def main(root):
    n = 0
    for rel, lst in PATCHES.items():
        p = os.path.join(root, rel)
        s = open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')   # upstream stores CRLF
        for old, new in lst:
            if new in s:
                continue
            assert s.count(old) == 1, 'patch anchor not found in %s: %r' % (rel, old[:50])
            s = s.replace(old, new)
            n += 1
        open(p, 'w', encoding='utf-8', newline='').write(s)
    open(os.path.join(root, 'src', 'web_glue.c'), 'w', newline='\n').write(WEB_C)
    print('port patches applied: %d new' % n)


if __name__ == '__main__':
    main(sys.argv[1])
