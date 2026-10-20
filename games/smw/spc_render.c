// Offline renderer for the snesrev/smw C SPC player (src/smw_spc_player.c + snes/dsp.c).
// Built by games/smw/spc_render.py; renders what the web build would play, no browser needed.
//   spc_render out.raw frames upload1.bin [upload2.bin ...] -- frame:port:value ...
// Uploads are applied in order (like the game: engine, samples, bank). Each event sets an
// input port for one frame (the game clears its sound registers after one frame, music too).
// Output: int16 stereo 32 kHz raw. Exit 3 if the player asserted (abort is trapped).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include "smw_spc_player.h"
#include "snes/dsp.h"

static void on_abort(int s) { fprintf(stderr, "ASSERT in SPC player\n"); fflush(stderr); _exit(3); }

int main(int argc, char **argv) {
  signal(SIGABRT, on_abort);
  if (argc < 4) return 2;
  FILE *fo = fopen(argv[1], "wb");
  int frames = atoi(argv[2]);
  SpcPlayer *p = SmwSpcPlayer_Create();
  p->initialize(p);
  int i = 3;
  for (; i < argc && strcmp(argv[i], "--"); i++) {
    FILE *f = fopen(argv[i], "rb");
    if (!f) return 4;
    static uint8 buf[70000];
    size_t n = fread(buf, 1, sizeof(buf), f);
    fclose(f);
    buf[n] = buf[n + 1] = 0;
    p->upload(p, buf);
  }
  int nev = 0, ev[512][3];
  for (i++; i < argc && nev < 512; i++)
    if (sscanf(argv[i], "%d:%d:%d", &ev[nev][0], &ev[nev][1], &ev[nev][2]) == 3) nev++;
  int16_t out[534 * 2];
  for (int f = 0; f < frames; f++) {
    for (int k = 0; k < 4; k++) p->input_ports[k] = 0;
    for (int e = 0; e < nev; e++)
      if (ev[e][0] == f) p->input_ports[ev[e][1]] = (uint8)ev[e][2];
    p->gen_samples(p);
    dsp_getSamples(p->dsp, out, 534);
    fwrite(out, 4, 534, fo);
  }
  fclose(fo);
  return 0;
}
