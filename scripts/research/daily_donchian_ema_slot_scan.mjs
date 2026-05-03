#!/usr/bin/env node
/**
 * Daily compact scan: Donchian+EMA buy buckets + CH/MAE sell (Either) per AFL defaults.
 * Usage: node scripts/research/daily_donchian_ema_slot_scan.mjs --slot=AM_OPEN|AM_MID|PM_CLOSE
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "..", "..");

const UNI = path.join(REPO, "data/research/ema_cloud/donchian_signals_full.csv");
const CACHE = path.join(REPO, "data/research/cache/fireant_ohlcv");
const VN = path.join(REPO, "minervini_backtest/data/raw/VNINDEX.csv");

const BUFFER = 1.003;
const DON = 20;
const WARM = 61;
const CH_K = 3.0;
const CH_ACT = 0.1;
const MAE_HOLD = 10;
const ATR_N = 14;

function parseArgs() {
  const a = process.argv.slice(2);
  let slot = "RUN";
  for (const x of a) {
    if (x.startsWith("--slot=")) slot = x.slice(7).toUpperCase();
  }
  return { slot };
}

function readCsvLines(p) {
  return fs.readFileSync(p, "utf8").trim().split(/\r?\n/);
}

function parseOhlcv(file) {
  const lines = readCsvLines(file);
  return lines.slice(1).map((ln) => {
    const [d, o, h, lo, c, v] = ln.split(",");
    return {
      date: d,
      open: +o,
      high: +h,
      low: +lo,
      close: +c,
      vol: +v,
    };
  });
}

function ema(arr, span) {
  const a = 2 / (span + 1);
  const out = new Array(arr.length).fill(NaN);
  let p = NaN;
  for (let i = 0; i < arr.length; i++) {
    const x = arr[i];
    if (!Number.isFinite(x)) continue;
    p = Number.isFinite(p) ? a * x + (1 - a) * p : x;
    out[i] = p;
  }
  return out;
}

function wilderAtr(h, l, c) {
  const n = c.length;
  const tr = new Array(n);
  tr[0] = h[0] - l[0];
  for (let i = 1; i < n; i++) {
    tr[i] = Math.max(
      h[i] - l[i],
      Math.abs(h[i] - c[i - 1]),
      Math.abs(l[i] - c[i - 1]),
    );
  }
  const atr = new Array(n).fill(NaN);
  let sum = 0;
  for (let i = 0; i < ATR_N; i++) sum += tr[i];
  atr[ATR_N - 1] = sum / ATR_N;
  for (let i = ATR_N; i < n; i++) {
    atr[i] = (atr[i - 1] * (ATR_N - 1) + tr[i]) / ATR_N;
  }
  return atr;
}

function donTrigger(h, i) {
  let m = -Infinity;
  for (let j = i - DON; j <= i - 1; j++) m = Math.max(m, h[j]);
  return m * BUFFER;
}

function loadUniverse() {
  const lines = readCsvLines(UNI);
  const s = new Set();
  for (let i = 1; i < lines.length; i++) {
    const sym = lines[i].split(",")[0];
    if (sym && sym !== "VPL") s.add(sym);
  }
  return [...s].sort();
}

function loadVnMap() {
  const rows = parseOhlcv(VN);
  const c = rows.map((r) => r.close);
  const e50 = ema(c, 50);
  const m = new Map();
  for (let i = 0; i < rows.length; i++) {
    m.set(rows[i].date, {
      reg: Number.isFinite(c[i]) && Number.isFinite(e50[i]) && c[i] > e50[i],
    });
  }
  return m;
}

function simulateSym(rows, vnByDate) {
  const n = rows.length;
  if (n < WARM + 2) return null;
  const c = rows.map((r) => r.close);
  const h = rows.map((r) => r.high);
  const o = rows.map((r) => r.open);
  const e10 = ema(c, 10);
  const e50 = ema(c, 50);
  const atr = wilderAtr(
    rows.map((r) => r.high),
    rows.map((r) => r.low),
    c,
  );

  const rawBuy = new Array(n).fill(0);
  const dcBuy = new Array(n).fill(0);
  const greenPulse = new Array(n).fill(0);
  const prod = new Array(n).fill(0);
  const chX = new Array(n).fill(0);
  const maeX = new Array(n).fill(0);
  const eitherX = new Array(n).fill(0);

  let dcIn = false;
  let dcEnt = -1;

  let pos = false;
  let entB = -1;
  let entPx = 0;
  let chHc = 0;
  let chAct = false;
  let mVio = false;
  let mVioC = 0;

  for (let i = WARM; i < n; i++) {
    const d = rows[i].date;
    const reg = vnByDate.get(d)?.reg === true;
    const trig = donTrigger(h, i);
    const bull = e10[i] > e50[i];
    const aboveF = c[i] > e10[i];
    const rb = c[i] > trig && bull && aboveF ? 1 : 0;
    rawBuy[i] = rb;

    if (dcIn && i - dcEnt >= 63) {
      dcIn = false;
      dcEnt = -1;
    }
    if (!dcIn && rb) {
      dcBuy[i] = 1;
      greenPulse[i] = 1;
      dcIn = true;
      dcEnt = i;
    }

    const pr = dcBuy[i] === 1 && reg ? 1 : 0;
    prod[i] = pr;

    if (!pos) {
      if (pr) {
        pos = true;
        entB = i < n - 1 ? i + 1 : i;
        entPx = i < n - 1 ? o[i + 1] : c[i];
        chHc = entPx;
        chAct = false;
        mVio = false;
        mVioC = 0;
      }
    } else if (i >= entB) {
      chHc = Math.max(chHc, c[i]);
      if (!chAct && c[i] >= entPx * (1 + CH_ACT)) chAct = true;

      let chHit = false;
      if (chAct && Number.isFinite(atr[i])) {
        const trail = chHc - CH_K * atr[i];
        if (c[i] < trail) chHit = true;
      }

      let maeHit = false;
      const hold = i - entB;
      if (hold >= MAE_HOLD) {
        if (c[i] >= e10[i]) {
          mVio = false;
          mVioC = 0;
        } else if (!mVio) {
          mVio = true;
          mVioC = c[i];
        } else if (c[i] < mVioC) {
          maeHit = true;
        }
      }

      if (chHit || maeHit) {
        eitherX[i] = 1;
        if (chHit) chX[i] = 1;
        if (maeHit) maeX[i] = 1;
        pos = false;
        entB = -1;
        entPx = 0;
        chHc = 0;
        chAct = false;
        mVio = false;
        mVioC = 0;
      }
    }
  }

  const L = n - 1;
  const trig = donTrigger(h, L);
  const distPct = 100 * (c[L] / trig - 1);
  const bull = e10[L] > e50[L];
  const aboveF = c[L] > e10[L];
  const absD = Math.abs(distPct);
  const regL = vnByDate.get(rows[L].date)?.reg === true;

  return {
    lastDate: rows[L].date,
    distPct,
    absD,
    bull,
    aboveF,
    rawL: rawBuy[L],
    dcL: dcBuy[L],
    gL: greenPulse[L],
    regL,
    chXL: chX[L],
    maeXL: maeX[L],
    eitherL: eitherX[L],
    posOpen: pos,
  };
}

function bucket(sym, o) {
  if (!o.bull || !o.aboveF) return null;
  if (o.absD > 10) return null;
  if (o.absD < 3) return 1;
  if (o.absD < 7) return 2;
  return 3;
}

function main() {
  const { slot } = parseArgs();
  const uni = loadUniverse();
  const vnByDate = loadVnMap();

  const L1 = [],
    L2 = [],
    L3 = [];
  const rb = [],
    gr = [];
  const nk = [];
  const sellE = [];
  let lastDate = "?";

  for (const sym of uni) {
    const f = path.join(CACHE, `${sym}.csv`);
    if (!fs.existsSync(f)) continue;
    const rows = parseOhlcv(f);
    const o = simulateSym(rows, vnByDate);
    if (!o) continue;
    lastDate = o.lastDate;
    const b = bucket(sym, o);
    if (b === 1) L1.push(sym);
    else if (b === 2) L2.push(sym);
    else if (b === 3) L3.push(sym);
    if (o.rawL) rb.push(sym);
    if (o.gL) gr.push(sym);
    if (o.rawL && !o.gL) nk.push(sym);
    if (o.eitherL) sellE.push(sym);
  }

  const dateGuess = lastDate;

  const regHead = vnByDate.get(dateGuess)?.reg;
  const line = [
    `SLOT=${slot}`,
    `DATE=${dateGuess}`,
    `REG=${regHead === true ? 1 : regHead === false ? 0 : "?"}`,
    `BUY|L1=${L1.join(",")}`,
    `L2=${L2.join(",")}`,
    `L3=${L3.join(",")}`,
    `RB=${rb.join(",")}`,
    `G=${gr.join(",")}`,
    `NK=${nk.join(",")}`,
    `SELL|E=${sellE.join(",")}`,
  ].join(" ");
  console.log(line);
}

main();
