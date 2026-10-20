// CODE-ONLY tool: runs the port's own level-object routines on synthetic one-object levels
// and prints the Map16 grid each object writes. No retail level data is read (the assets
// file is only needed because the port links against it; a clean one works).
// Build (zig cc / clang): compile the port's src/*.c (minus main/opengl/glsl/web_glue), src/snes,
// smb1, smbll with -Istub (stub/SDL_keycode.h: typedef int SDL_Keycode, SDL_Keymod), then link this.
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "types.h"
#include "variables.h"
#include "funcs.h"
#include "smw_rtl.h"
#include "common_rtl.h"
#include "config.h"
#include "assets/smw_assets.h"
bool g_debug_flag, g_want_dump_memmap_flags, g_new_ppu = true, g_other_image = true;
int g_got_mismatch_count;
struct SpcPlayer *g_spc_player;
Config g_config;
const uint8 *g_asset_ptrs[kNumberOfAssets];
uint32 g_asset_sizes[kNumberOfAssets];
void NORETURN Die(const char *e) { fprintf(stderr, "Die: %s\n", e); exit(1); }
void Warning(const char *e) { fprintf(stderr, "Warn: %s\n", e); }
void RtlDrawPpuFrame(uint8 *pixel_buffer, size_t pitch, uint32 render_flags) {}
void RtlApuLock(void) {}
void RtlApuUnlock(void) {}
void MkDir(const char *s) {}
MemBlk FindInAssetArray(int asset, int idx) { return FindIndexInMemblk((MemBlk){g_asset_ptrs[asset], g_asset_sizes[asset]}, idx); }
const uint8 *FindPtrInAsset(int asset, uint32 addr) { return FindAddrInMemblk((MemBlk){g_asset_ptrs[asset], g_asset_sizes[asset]}, addr); }

static volatile int g_job;
static DWORD WINAPI Watchdog(LPVOID a) {
  int last = -1;
  for (;;) {
    Sleep(1500);
    if (g_job == last && g_job >= 0) { printf("HANG\n"); fflush(stdout); ExitProcess(3); }
    last = g_job;
  }
}

static void LoadAssets(const char *fn) {
  FILE *f = fopen(fn, "rb"); fseek(f, 0, 2); long n = ftell(f); fseek(f, 0, 0);
  uint8 *data = malloc(n); fread(data, 1, n, f); fclose(f);
  uint32 offset = 88 + kNumberOfAssets * 4 + *(uint32 *)(data + 84);
  for (size_t i = 0; i < kNumberOfAssets; i++) {
    uint32 size = *(uint32 *)(data + 88 + i * 4);
    offset = (offset + 3) & ~3;
    g_asset_sizes[i] = size; g_asset_ptrs[i] = data + offset; offset += size;
  }
}

// usage: harness assets.dat < jobs   (each line: tileset obj size x y; obj >= 256 = extended object obj-256)
int main(int argc, char **argv) {
  LoadAssets(argv[1]);
  int ts, obj, size, x, y;
  CreateThread(NULL, 0, Watchdog, NULL, 0, NULL);
  while (scanf("%d %d %d %d %d", &ts, &obj, &size, &x, &y) == 5) {
    g_job++;
    printf("S %d %d %d\n", ts, obj, size); fflush(stdout);
    for (int i = 0; i < 0x1b0 * 32; i++) { g_ram[0xc800 + i] = 0x25; g_ram[0x1c800 + i] = 0; }
    misc_level_tileset_setting = ts;
    misc_level_mode_setting = 0; misc_level_layout_flags = 0;
    misc_current_layer_being_processed = 0;
    blocks_screen_to_place_current_object = 0;
    static uint8 buf[8];
    int num = obj >= 0x100 ? 0 : obj;     // b0 = N BB YYYYY, b1 = bbbb XXXX, b2 = size (ext: number)
    buf[0] = ((num >> 4) & 3) << 5 | (y & 0x1f);
    buf[1] = (num & 0xf) << 4 | (x & 0xf);
    buf[2] = obj >= 0x100 ? (obj & 0xff) : size;
    buf[3] = 0xff;
    ptr_layer1_data = buf;
    LoadLevelDataObject();
    printf("G %d %d %d\n", ts, obj, size);
    for (int yy = 0; yy < 27; yy++) {
      for (int s = 0; s < 3; s++) for (int xx = 0; xx < 16; xx++) {
        int k = 0xc800 + s * 0x1b0 + yy * 16 + xx;
        printf("%03X ", g_ram[k] | g_ram[k + 0x10000] << 8);
      }
      printf("\n");
    }
  }
  g_job = -1;
  fflush(stdout);
  return 0;
}
