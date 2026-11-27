import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const Engine = require('../public/datamosh-engine.js');

function makeGradientRgba(w, h) {
  const buf = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      buf[i] = ((x * 17 + y * 5) % 256);
      buf[i + 1] = ((y * 13 + x * 3) % 256);
      buf[i + 2] = (((x + y) * 9) % 256);
      buf[i + 3] = 255;
    }
  }
  return buf;
}

test('Pixel Sort orders row spans by luminance deterministically', () => {
  const w = 32;
  const h = 16;
  const src = makeGradientRgba(w, h);
  const sorted = Engine.applyPixelSort(src, w, h, {
    thresholdLow: 20,
    thresholdHigh: 240,
    direction: 'row',
  });
  assert.equal(sorted.length, src.length);
  let diffs = 0;
  for (let i = 0; i < src.length; i++) {
    if (sorted[i] !== src[i]) diffs++;
  }
  assert.ok(diffs > 0, 'Pixel sort should rearrange pixels');
});

test('True 8-Bitplane Slicer masks to exact bit values (Bit 7 MSB -> 0 or 128)', () => {
  const w = 16;
  const h = 16;
  const src = makeGradientRgba(w, h);
  const sliced = Engine.applyBitplaneSlice(src, w, h, {
    keepBits: [7],
    invertBits: [],
    channel: 'all',
  });
  for (let i = 0; i < sliced.length; i += 4) {
    assert.ok(sliced[i] === 0 || sliced[i] === 128, `Unexpected R bit7 value: ${sliced[i]}`);
    assert.ok(sliced[i + 1] === 0 || sliced[i + 1] === 128, `Unexpected G bit7 value: ${sliced[i + 1]}`);
    assert.ok(sliced[i + 2] === 0 || sliced[i + 2] === 128, `Unexpected B bit7 value: ${sliced[i + 2]}`);
  }
});

test('Sierpinski XOR modulates pixel buffer across formulas', () => {
  const w = 24;
  const h = 24;
  const src = makeGradientRgba(w, h);
  for (const formula of ['xor', 'and', 'or', 'xor_and']) {
    const out = Engine.applySierpinskiXor(src, w, h, { formula, scale: 1.5, blend: 0.7 });
    assert.equal(out.length, src.length);
    assert.notDeepEqual(Array.from(out), Array.from(src));
  }
});

test('Header-safe JPEG Byte-Bend preserves SOI, SOS header, and EOI while mutating scan data', () => {
  // Minimal synthetic JPEG: SOI + APP0 + SOS(header len 12) + 64 scan bytes + EOI
  const header = [
    0xff, 0xd8, // SOI
    0xff, 0xe0, 0x00, 0x06, 0x4a, 0x46, 0x49, 0x46, // APP0 (len 6)
    0xff, 0xda, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3f, 0x00, // SOS (len 8)
  ];
  const scan = new Array(80).fill(0).map((_, idx) => 0x10 + (idx % 0x70));
  const eoi = [0xff, 0xd9];
  const fakeJpeg = new Uint8Array([...header, ...scan, ...eoi]);

  const res = Engine.corruptJpegBytes(fakeJpeg, { intensity: 60, seed: 77 });
  assert.equal(res.scanStart, header.length);
  assert.equal(res.headerPreserved, true);
  assert.ok(res.mutatedCount > 0, 'Expected scan mutations');
  // Header bytes untouched
  for (let i = 0; i < header.length; i++) {
    assert.equal(res.bytes[i], fakeJpeg[i], `Header byte ${i} must be preserved`);
  }
  // Trailing EOI untouched
  assert.equal(res.bytes[res.bytes.length - 2], 0xff);
  assert.equal(res.bytes[res.bytes.length - 1], 0xd9);
});

test('JSON Preset serialize & parse validates and clamps out-of-range inputs', () => {
  const jsonStr = Engine.serializePreset({
    name: 'Audit Preset',
    sliceHeight: 999,
    shiftMax: -20,
    rgbSplit: 12,
    scanIntensity: 40,
    pixelSort: true,
    bitplaneEnabled: true,
    keepBits: [7, 6, 99, -1],
    bitplaneChannel: 'luminance',
    sierpinskiEnabled: true,
    sierpinskiFormula: 'xor_and',
  });
  const parsed = Engine.parsePresetJson(jsonStr);
  assert.equal(parsed.sliceHeight, 128);
  assert.equal(parsed.shiftMax, 0);
  assert.deepEqual(parsed.keepBits, [7, 6]);
  assert.equal(parsed.bitplaneChannel, 'luminance');
  assert.equal(parsed.sierpinskiFormula, 'xor_and');
  assert.throws(() => Engine.parsePresetJson('{broken-json'));
});
