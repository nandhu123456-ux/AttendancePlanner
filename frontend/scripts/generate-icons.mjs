// Generates TRACK_75 PWA icons (PNG) using only Node built-ins.
// Branding matches the existing app: teal palette (#1e4d4d / #2a7373 / #328888)
// and the cube wireframe motif from the original favicon.
// Run: node scripts/generate-icons.mjs
import zlib from "node:zlib";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "..", "public", "icons");
fs.mkdirSync(outDir, { recursive: true });

/* ---------- PNG encoding ---------- */
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

function encodePNG(width, height, rgba) {
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // RGBA
  const raw = Buffer.alloc(height * (width * 4 + 1));
  for (let y = 0; y < height; y++) {
    raw[y * (width * 4 + 1)] = 0; // filter: none
    rgba.copy(raw, y * (width * 4 + 1) + 1, y * width * 4, (y + 1) * width * 4);
  }
  const idat = zlib.deflateSync(raw, { level: 9 });
  return Buffer.concat([sig, chunk("IHDR", ihdr), chunk("IDAT", idat), chunk("IEND", Buffer.alloc(0))]);
}

/* ---------- Drawing helpers (RGBA buffer) ---------- */
function hex(c) {
  return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)];
}

function px(buf, N, x, y, c) {
  if (x < 0 || y < 0 || x >= N || y >= N) return;
  const i = (y * N + x) * 4;
  buf[i] = c[0]; buf[i + 1] = c[1]; buf[i + 2] = c[2]; buf[i + 3] = 255;
}

function insideRoundedRect(x, y, N, r) {
  const half = N / 2;
  const dx = Math.max(Math.abs(x - half) - (half - r), 0);
  const dy = Math.max(Math.abs(y - half) - (half - r), 0);
  return dx * dx + dy * dy <= r * r;
}
function drawBackground(buf, N, top, bottom, rounded) {
  const radius = rounded ? N * 0.22 : 0;
  for (let y = 0; y < N; y++) {
    const t = y / (N - 1);
    const c = [
      Math.round(top[0] + (bottom[0] - top[0]) * t),
      Math.round(top[1] + (bottom[1] - top[1]) * t),
      Math.round(top[2] + (bottom[2] - top[2]) * t),
    ];
    for (let x = 0; x < N; x++) {
      if (!rounded || insideRoundedRect(x, y, N, radius)) px(buf, N, x, y, c);
    }
  }
}

function drawLine(buf, N, x1, y1, x2, y2, width, c) {
  const half = width / 2;
  const minX = Math.floor(Math.min(x1, x2) - width - 1), maxX = Math.ceil(Math.max(x1, x2) + width + 1);
  const minY = Math.floor(Math.min(y1, y2) - width - 1), maxY = Math.ceil(Math.max(y1, y2) + width + 1);
  const dx = x2 - x1, dy = y2 - y1;
  const lenSq = dx * dx + dy * dy || 1;
  for (let y = Math.max(0, minY); y < Math.min(N, maxY); y++) {
    for (let x = Math.max(0, minX); x < Math.min(N, maxX); x++) {
      const t = Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / lenSq));
      const ex = x1 + t * dx - x, ey = y1 + t * dy - y;
      if (ex * ex + ey * ey <= half * half) px(buf, N, x, y, c);
    }
  }
}

function drawCircle(buf, N, cx, cy, r, c) {
  for (let y = Math.floor(cy - r); y <= Math.ceil(cy + r); y++) {
    for (let x = Math.floor(cx - r); x <= Math.ceil(cx + r); x++) {
      const dx = x - cx, dy = y - cy;
      if (dx * dx + dy * dy <= r * r) px(buf, N, x, y, c);
    }
  }
}

/* ---------- Cube motif (matches existing favicon) ---------- */
const CUBE_EDGES_LIGHT = hex("#cfeded");
const CUBE_DOT = hex("#4a9e9e");
const BG_TOP = hex("#2a7373");
const BG_BOTTOM = hex("#1a3a3a");

function drawCube(buf, N, radiusFrac) {
  const cx = N / 2, cy = N / 2;
  const R = N * radiusFrac;
  const w = N * 0.045;
  // Pointy-top hexagon vertices (iso cube)
  const v = [];
  for (let i = 0; i < 6; i++) {
    const a = Math.PI / 2 + (i * Math.PI) / 3;
    v.push([cx + R * Math.cos(a), cy - R * Math.sin(a)]);
  }
  // Hexagon outline
  for (let i = 0; i < 6; i++) drawLine(buf, N, v[i][0], v[i][1], v[(i + 1) % 6][0], v[(i + 1) % 6][1], w, CUBE_EDGES_LIGHT);
  // Spokes from center to alternating vertices (top, lower-left, lower-right)
  for (const i of [0, 2, 4]) drawLine(buf, N, cx, cy, v[i][0], v[i][1], w, CUBE_EDGES_LIGHT);
  // Center dot
  drawCircle(buf, N, cx, cy, N * 0.075, CUBE_DOT);
}


function render(size, maskable) {
  const SS = 4; // supersample factor for smooth edges
  const N = size * SS;
  const buf = Buffer.alloc(N * N * 4);
  drawBackground(buf, N, BG_TOP, BG_BOTTOM, !maskable);
  // Maskable: keep motif within the 80% safe zone
  drawCube(buf, N, maskable ? 0.28 : 0.30);
  // Box-downsample
  const out = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let r = 0, g = 0, b = 0, a = 0;
      for (let sy = 0; sy < SS; sy++) {
        for (let sx = 0; sx < SS; sx++) {
          const i = ((y * SS + sy) * N + x * SS + sx) * 4;
          r += buf[i]; g += buf[i + 1]; b += buf[i + 2]; a += buf[i + 3];
        }
      }
      const o = (y * size + x) * 4;
      out[o] = Math.round(r / (SS * SS));
      out[o + 1] = Math.round(g / (SS * SS));
      out[o + 2] = Math.round(b / (SS * SS));
      out[o + 3] = Math.round(a / (SS * SS));
    }
  }
  return encodePNG(size, size, out);
}

const icons = [
  ["icon-192.png", 192, false],
  ["icon-512.png", 512, false],
  ["icon-maskable-512.png", 512, true],
  ["apple-touch-icon.png", 180, true],
];

for (const [name, size, maskable] of icons) {
  fs.writeFileSync(path.join(outDir, name), render(size, maskable));
  console.log(`wrote public/icons/${name}`);
}

