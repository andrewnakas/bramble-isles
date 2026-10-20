// Offline level renderer: runs the port's own level loader (LoadLevelHeader + object routines)
// on an smw_assets.dat and writes the resulting Map16 grid of layer 1 (and layer 2 when it is
// object data). Built by games/smw/lvl_render.py against the pristine port source.
//   lvl_render <assets.dat> <out.bin> <kind> <index>...
//   kind: level (kLevelData_Layer1/2 index 0-511), entrance, choco2, rollcall
// Output per index: u16 index, u8 mode, u8 screens, then 0x3800 bytes lo + 0x3800 hi (RAM 0xC800..)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "types.h"
#include "variables.h"
#include "funcs.h"
#include "smw_rtl.h"
#include "common_rtl.h"
#include "assets/smw_assets.h"
#include "util.h"
#include "config.h"
#include "common_cpu_infra.h"
const RtlGameInfo kSmb1GameInfo, kSmbllGameInfo;

const uint8 *g_asset_ptrs[kNumberOfAssets];
uint32 g_asset_sizes[kNumberOfAssets];
bool g_debug_flag, g_want_dump_memmap_flags, g_new_ppu = true, g_other_image = true;
struct SpcPlayer *g_spc_player;
int g_got_mismatch_count;
Config g_config;

void NORETURN Die(const char *error) { fprintf(stderr, "Die: %s\n", error); exit(5); }
void Warning(const char *error) { fprintf(stderr, "Warning: %s\n", error); }
void ChangeWindowScale(int s) {}
void RtlDrawPpuFrame(uint8 *pixel_buffer, size_t pitch, uint32 render_flags) {}
void RtlApuLock(void) {}
void RtlApuUnlock(void) {}
void MkDir(const char *s) {}
MemBlk FindInAssetArray(int asset, int idx) { return FindIndexInMemblk((MemBlk){g_asset_ptrs[asset], g_asset_sizes[asset]}, idx); }
const uint8 *FindPtrInAsset(int asset, uint32 addr) { return FindAddrInMemblk((MemBlk){g_asset_ptrs[asset], g_asset_sizes[asset]}, addr); }

static uint8 *load(const char *path) {
  FILE *f = fopen(path, "rb");
  if (!f) Die("open");
  fseek(f, 0, SEEK_END);
  long n = ftell(f);
  fseek(f, 0, SEEK_SET);
  uint8 *d = malloc(n);
  fread(d, 1, n, f);
  fclose(f);
  uint32 offset = 88 + kNumberOfAssets * 4 + *(uint32 *)(d + 84);
  for (size_t i = 0; i < kNumberOfAssets; i++) {
    uint32 size = *(uint32 *)(d + 88 + i * 4);
    offset = (offset + 3) & ~3;
    g_asset_sizes[i] = size;
    g_asset_ptrs[i] = d + offset;
    offset += size;
  }
  return d;
}

int main(int argc, char **argv) {
  if (argc < 5) return 2;
  load(argv[1]);
  FILE *fo = fopen(argv[2], "wb");
  const char *kind = argv[3];
  for (int a = 4; a < argc; a++) {
    int idx = strtol(argv[a], 0, 0);
    memset(g_ram, 0, sizeof(g_ram));
    for (int i = 0; i < 0x3800; i++) { g_ram[0xC800 + i] = 0x25; g_ram[0x1C800 + i] = 0; }
    if (!strcmp(kind, "level")) {
      ptr_layer1_data = kLevelData_Layer1(idx).ptr;
      ptr_layer2_data = kLevelData_Layer2(idx).ptr;
      ptr_layer2_is_bg = kLevelData_Layer2_IsBg[idx];
    } else if (!strcmp(kind, "entrance")) {
      ptr_layer1_data = kEntranceData_Layer1(idx).ptr;
      ptr_layer2_data = kEntranceData_Layer2(idx).ptr;
      ptr_layer2_is_bg = kEntranceData_Layer2_IsBg[idx];
    } else if (!strcmp(kind, "choco2")) {
      ptr_layer1_data = kChoclateIsland2_Layer1(idx).ptr;
      ptr_layer2_data = kChoclateIsland2_Layer2(idx).ptr;
      ptr_layer2_is_bg = kChoclateIsland2_Layer2_IsBg[idx];
    } else {
      ptr_layer1_data = kRollCallData_Layer1(idx).ptr;
      ptr_layer2_data = kRollCallData_Layer2(idx).ptr;
      ptr_layer2_is_bg = kRollCallData_Layer2_IsBg[idx];
    }
    uint8 hdr1 = ptr_layer1_data[1];
    uint8 screens = (ptr_layer1_data[0] & 0x1F) + 1;
    if (!ptr_layer2_is_bg) {
      BeginLoadingLevelData();
    } else {
      LoadLevelHeader();
      InitializeMap16Pointers();
      int m = misc_level_mode_setting;
      if (!(m == 9 || m == 11 || m == 16) && *ptr_layer1_data != 0xFF)
        LoadLevelDataObject();
    }
    uint16 i16 = idx;
    fwrite(&i16, 2, 1, fo);
    uint8 m = hdr1 & 0x1F;
    fwrite(&m, 1, 1, fo);
    fwrite(&screens, 1, 1, fo);
    fwrite(g_ram + 0xC800, 1, 0x3800, fo);
    fwrite(g_ram + 0x1C800, 1, 0x3800, fo);
  }
  fclose(fo);
  return 0;
}
