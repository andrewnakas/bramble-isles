// DEV ONLY (never shipped): level test bot. Page query: ?bot=devbot.js&levels=105.106.0A...
// Waits for the overworld, fills the overworld level-number table so the tile under the player
// enters the next level, runs right holding run, jumps at walls/pits/ledges, keeps star power on
// (layout test, not an enemy test) and logs one line per level: BOT <level> GOAL|DEAD|TIMEOUT|EXIT x=<max px>.
(function () {
  var Q = new URLSearchParams(location.search);
  var list = (Q.get('levels') || '').split('.').filter(Boolean).map(function (s) { return parseInt(s, 16); });
  var TIMEOUT = +(Q.get('bottime') || 7200);
  function R(a) { return Module.HEAPU8[Module._web_ram() + a]; }
  function W(a, v) { Module.HEAPU8[Module._web_ram() + a] = v; }
  var keys = {};
  function key(c, d) { if (!!keys[c] !== d) { keys[c] = d; sendKey(c, d); } }
  function solid(px, py) {
    if (py < 0) return false;
    var col = px >> 4, row = py >> 4;
    if (row > 26 || col < 0) return false;
    var a = 0xC800 + (col >> 4) * 0x1B0 + row * 16 + (col & 15);
    var lo = R(a), hi = R(a + 0x10000);
    return hi !== 0;                 // page 1 = ledges, blocks, pipes, ground edges, slopes
  }
  var idx = -1, state = 'boot', since = 0, t0 = 0, maxx = 0, lastx = 0, still = 0, jt = 0, cur = 0, back = 0;
  function dumpRam(k) {
    var p = Module._web_ram(), b = '', h = Module.HEAPU8;
    for (var i = 0; i < 0x20000; i++) b += String.fromCharCode(h[p + i]);
    b = btoa(b);
    for (var j = 0; j < b.length; j += 4000) console.log('RAM:' + k + ':' + b.slice(j, j + 4000));
    console.log('RAM:' + k + ':END');
  }
  function finish(res) {
    if (Q.has('botram') && res !== 'GOAL') dumpRam(90 + idx);
    console.log('BOT ' + cur.toString(16) + ' ' + res + ' x=' + maxx + ' t=' + (since - t0));
    key('ArrowRight', false); key('KeyA', false); key('KeyZ', false); key('ArrowLeft', false);
    state = 'out';
  }
  Module.devBot = function (n) {
    since = n;
    var gm = R(0x100);
    W(0xDBE, 0x50);                                     // lives
    if (Q.has('botgm') && gm !== Module.__lastgm) { console.log('BOTGM f=' + n + ' gm=' + gm.toString(16) + ' st=' + state); Module.__lastgm = gm; }
    if (state === 'boot' || state === 'out') {
      if (gm === 0x0E && n > 2100) { state = 'ow'; t0 = n; }
      return;
    }
    if (state === 'ow') {
      if (n - t0 < 60) return;
      idx++;
      if (idx >= list.length) { console.log('BOT DONE'); state = 'done'; return; }
      cur = list[idx];
      if (cur >= 0x100) W(0x1F11, R(0x1F11) || 1);
      else W(0x1F11, 0);
      var tv = (cur >= 0x100) ? (cur & 0xFF) + 0x24 : cur;
      Module.HEAPU8.fill(tv & 0xFF, Module._web_ram() + 0xD000, Module._web_ram() + 0xD800);
      state = 'enter'; t0 = n; maxx = 0; still = 0;
      return;
    }
    if (state === 'enter') {
      var d = n - t0;
      key('KeyZ', d >= 10 && d < 20);
      if (gm === 0x14) { state = 'play'; t0 = n; lastx = 0; }
      if (d > 900) finish('NOENTRY gm=' + gm.toString(16));
      return;
    }
    if (state === 'play') {
      if (gm !== 0x14) {
        if (gm >= 0x0B && gm <= 0x0E) { finish(R(0x1493) ? 'GOAL' : 'EXIT gm=' + gm.toString(16)); return; }
        lastx = 0; maxx = Math.max(maxx, 0); return;              // sub-area / entrance-scene transition
      }
      W(0x1490, 0xF0);                                  // star power: layout test only
      var x = R(0x94) | R(0x95) << 8, y = R(0x96) | R(0x97) << 8;
      if (y & 0x8000) y -= 0x10000;
      if (x > maxx) maxx = x;
      if (R(0x71) === 9) { finish('DEAD'); return; }
      if (R(0x1493)) { finish('GOAL'); return; }
      if (n - t0 > TIMEOUT) { finish('TIMEOUT'); return; }
      if (Q.has('botlog') && (n - t0) % 8 === 0) console.log('BOTLOG t=' + (n - t0) + ' x=' + x + ' y=' + y + ' s71=' + R(0x71) + ' air=' + R(0x72) + ' blk=' + R(0x77) + ' jt=' + jt);
      var ground = R(0x72) === 0;
      var feet = y + 32;
      var LA = +(Q.get('botahead') || 40);
      var wall = solid(x + LA - 8, y + 24) || solid(x + LA - 8, y + 16) || (R(0x77) & 1);
      var pit = true;
      for (var dy = 0; dy < 96; dy += 16) if (solid(x + LA, feet + dy) || solid(x + LA - 12, feet + dy)) { pit = false; break; }
      if (x > lastx + 1) { still = 0; lastx = x; } else still++;
      if (back > 0) { back--; key('ArrowRight', false); key('ArrowLeft', true); key('KeyZ', false); return; }
      key('ArrowLeft', false);
      key('ArrowRight', true);
      key('KeyA', true);
      if (still > 90) { still = 0; back = 25; return; }
      if (jt > 0) { jt--; key('KeyZ', true); return; }
      key('KeyZ', false);
      if (ground && (wall || pit || still > 20)) jt = +(Q.get('botjump') || 32);
    }
  };
})();
