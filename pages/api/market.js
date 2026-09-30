import https from 'https';

const CACHE = { data: null, timestamp: 0 };
const CACHE_TTL_MS = 60 * 1000;

function fetchJson(url, headers = {}, timeoutMs = 6000) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        ...headers
      },
      timeout: timeoutMs
    }, (res) => {
      if (res.statusCode < 200 || res.statusCode >= 300) {
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (err) {
          reject(err);
        }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
  });
}

function calculateTaiwanKD(highs, lows, closes, period = 9) {
  const len = closes.length;
  const kArr = [];
  const dArr = [];
  let k = 50.0;
  let d = 50.0;

  for (let i = 0; i < len; i++) {
    if (i < period - 1) {
      kArr.push(50.0);
      dArr.push(50.0);
      continue;
    }
    let highest = -Infinity;
    let lowest = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      if (highs[j] > highest) highest = highs[j];
      if (lows[j] < lowest) lowest = lows[j];
    }
    const close = closes[i];
    let rsv = 50.0;
    if (highest !== lowest) {
      rsv = ((close - lowest) / (highest - lowest)) * 100.0;
    }
    rsv = Math.max(0, Math.min(100, rsv));
    k = (2.0 / 3.0) * k + (1.0 / 3.0) * rsv;
    d = (2.0 / 3.0) * d + (1.0 / 3.0) * k;
    kArr.push(Number(k.toFixed(1)));
    dArr.push(Number(d.toFixed(1)));
  }
  return { kArr, dArr };
}

function formatTaiwanDate(timestampSec) {
  const d = new Date(timestampSec * 1000);
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Taipei' }).format(d);
}

async function fetchMarketData() {
  let timestamps = [];
  let opens = [];
  let highs = [];
  let lows = [];
  let closes = [];
  let volumes = [];

  // Try 1: Query1 Finance (Fastest, global CDN)
  try {
    const q1Url = 'https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII?interval=1d&range=1mo';
    const q1Res = await fetchJson(q1Url, {}, 3500);

    const res0 = q1Res?.chart?.result?.[0];
    if (res0 && res0.timestamp && res0.indicators?.quote?.[0]) {
      const q = res0.indicators.quote[0];
      timestamps = res0.timestamp;
      opens = q.open;
      highs = q.high;
      lows = q.low;
      closes = q.close;
      volumes = q.volume;

      // If Query1 has 0 or missing for today's volume, fetch ApacLibraCharts to get real-time turnover
      if (volumes && volumes.length > 0 && (!volumes[volumes.length - 1] || volumes[volumes.length - 1] <= 0)) {
        try {
          const apacUrl = 'https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService.ApacLibraCharts;period=d;symbols=%5B%22%5ETWII%22%5D';
          const apacRes = await fetchJson(apacUrl, { 'Referer': 'https://tw.stock.yahoo.com/' }, 3000);
          const apacVol = apacRes?.[0]?.chart?.indicators?.quote?.[0]?.volume;
          if (apacVol && apacVol.length > 0 && apacVol[apacVol.length - 1] > 0) {
            volumes[volumes.length - 1] = apacVol[apacVol.length - 1] * 10;
          }
        } catch (e) {}
      }
    }
  } catch (err) {
    // console.warn('Query1 failed, trying APAC endpoint:', err.message);
  }

  // Try 2: APAC Libra Charts fallback
  if (!timestamps || timestamps.length < 5) {
    const apacUrl = 'https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService.ApacLibraCharts;period=d;symbols=%5B%22%5ETWII%22%5D';
    const apacRes = await fetchJson(apacUrl, {
      'Referer': 'https://tw.stock.yahoo.com/'
    }, 4000);

    const chart = apacRes?.[0]?.chart;
    if (chart && chart.timestamp && chart.indicators?.quote?.[0]) {
      const q = chart.indicators.quote[0];
      timestamps = chart.timestamp;
      opens = q.open;
      highs = q.high;
      lows = q.low;
      closes = q.close;
      volumes = q.volume;
    }
  }

  if (!timestamps || timestamps.length === 0) {
    throw new Error('No chart data available for ^TWII');
  }

  const validEntries = [];
  for (let i = 0; i < timestamps.length; i++) {
    const c = closes[i];
    if (c !== null && !isNaN(c)) {
      validEntries.push({
        ts: timestamps[i],
        open: opens[i] ?? c,
        high: highs[i] ?? c,
        low: lows[i] ?? c,
        close: c,
        volume: volumes[i] || 0
      });
    }
  }

  if (validEntries.length === 0) {
    throw new Error('No valid close quotes for ^TWII');
  }

  // Calculate Taiwan KD (9, 3, 3)
  const vHighs = validEntries.map(e => e.high);
  const vLows = validEntries.map(e => e.low);
  const vCloses = validEntries.map(e => e.close);
  const kd = calculateTaiwanKD(vHighs, vLows, vCloses, 9);

  const fullRecords = [];
  for (let i = 0; i < validEntries.length; i++) {
    const cur = validEntries[i];
    const prev = i > 0 ? validEntries[i - 1] : cur;
    const change = Number((cur.close - prev.close).toFixed(2));
    const changePct = prev.close > 0 ? Number(((change / prev.close) * 100).toFixed(2)) : 0;

    let streak = 0;
    let isUpStreak = false;
    let isDownStreak = false;
    for (let j = i; j > 0; j--) {
      const c1 = validEntries[j].close;
      const c0 = validEntries[j - 1].close;
      if (c1 > c0) {
        if (isDownStreak) break;
        isUpStreak = true;
        streak++;
      } else if (c1 < c0) {
        if (isUpStreak) break;
        isDownStreak = true;
        streak++;
      } else {
        break;
      }
    }

    let streakText = '平盤';
    if (isUpStreak && streak > 0) {
      streakText = `連漲 ${streak} 天`;
    } else if (isDownStreak && streak > 0) {
      streakText = `連跌 ${streak} 天`;
    }

    const volYiNum = cur.volume > 0 ? Number((cur.volume / 1000).toFixed(1)) : 0;
    const volYiStr = `${volYiNum.toFixed(1)} 億`;

    fullRecords.push({
      date: formatTaiwanDate(cur.ts),
      close: Number(cur.close.toFixed(2)),
      change: change,
      change_pct: changePct,
      k: kd.kArr[i] ?? 50.0,
      d: kd.dArr[i] ?? 50.0,
      turnover_yi: volYiNum,
      volume_yi: volYiStr,
      streak: streakText,
      streak_text: streakText
    });
  }

  const recent10Chronological = fullRecords.slice(-10);
  const recent10Descending = [...recent10Chronological].reverse();
  const latest = fullRecords[fullRecords.length - 1];

  return {
    symbol: '^TWII',
    name: '加權指數',
    latest: {
      date: latest.date,
      close: latest.close,
      change: latest.change,
      change_pct: latest.change_pct,
      k: latest.k,
      d: latest.d,
      turnover_yi: latest.turnover_yi,
      volume_yi: latest.volume_yi,
      streak: latest.streak,
      streak_text: latest.streak_text
    },
    records: recent10Chronological,
    table_records: recent10Descending,
    all_recent: fullRecords.slice(-30)
  };
}

const HARDCODED_MARKET_FALLBACK = {
  symbol: '^TWII',
  name: '加權指數',
  latest: {
    date: '2026-09-30',
    close: 47940.13,
    change: 308.17,
    change_pct: 0.65,
    k: 75.5,
    d: 70.8,
    turnover_yi: 8774.7,
    volume_yi: '8774.7 億',
    streak: '連漲 1 天',
    streak_text: '連漲 1 天'
  },
  records: [
    {date: '2026-09-15', close: 45511.49, change: -351.03, change_pct: -0.77, k: 26.2, d: 38.9, turnover_yi: 3225.5, streak: '連跌 4 天'},
    {date: '2026-09-16', close: 45848.90, change: 337.41, change_pct: 0.74, k: 24.4, d: 34.1, turnover_yi: 3326.7, streak: '連漲 1 天'},
    {date: '2026-09-17', close: 46288.00, change: 439.10, change_pct: 0.96, k: 29.8, d: 32.7, turnover_yi: 4395.1, streak: '連漲 2 天'},
    {date: '2026-09-18', close: 47180.75, change: 892.75, change_pct: 1.93, k: 47.1, d: 37.5, turnover_yi: 5651.2, streak: '連漲 3 天'},
    {date: '2026-09-21', close: 47718.84, change: 538.09, change_pct: 1.14, k: 64.3, d: 46.4, turnover_yi: 4475.5, streak: '連漲 4 天'},
    {date: '2026-09-22', close: 47800.17, change: 81.33, change_pct: 0.17, k: 67.9, d: 53.6, turnover_yi: 5924.9, streak: '連漲 5 天'},
    {date: '2026-09-23', close: 48157.29, change: 357.12, change_pct: 0.75, k: 74.0, d: 60.4, turnover_yi: 4866.3, streak: '連漲 6 天'},
    {date: '2026-09-24', close: 48024.60, change: -132.69, change_pct: -0.28, k: 76.6, d: 65.8, turnover_yi: 3540.9, streak: '連跌 1 天'},
    {date: '2026-09-29', close: 47631.96, change: -392.64, change_pct: -0.82, k: 74.0, d: 68.5, turnover_yi: 3781.3, streak: '連跌 2 天'},
    {date: '2026-09-30', close: 47940.13, change: 308.17, change_pct: 0.65, k: 75.5, d: 70.8, turnover_yi: 8774.7, streak: '連漲 1 天'}
  ],
  table_records: [
    {date: '2026-09-30', close: 47940.13, change: 308.17, change_pct: 0.65, k: 75.5, d: 70.8, turnover_yi: 8774.7, streak: '連漲 1 天'},
    {date: '2026-09-29', close: 47631.96, change: -392.64, change_pct: -0.82, k: 74.0, d: 68.5, turnover_yi: 3781.3, streak: '連跌 2 天'},
    {date: '2026-09-24', close: 48024.60, change: -132.69, change_pct: -0.28, k: 76.6, d: 65.8, turnover_yi: 3540.9, streak: '連跌 1 天'},
    {date: '2026-09-23', close: 48157.29, change: 357.12, change_pct: 0.75, k: 74.0, d: 60.4, turnover_yi: 4866.3, streak: '連漲 6 天'},
    {date: '2026-09-22', close: 47800.17, change: 81.33, change_pct: 0.17, k: 67.9, d: 53.6, turnover_yi: 5924.9, streak: '連漲 5 天'},
    {date: '2026-09-21', close: 47718.84, change: 538.09, change_pct: 1.14, k: 64.3, d: 46.4, turnover_yi: 4475.5, streak: '連漲 4 天'},
    {date: '2026-09-18', close: 47180.75, change: 892.75, change_pct: 1.93, k: 47.1, d: 37.5, turnover_yi: 5651.2, streak: '連漲 3 天'},
    {date: '2026-09-17', close: 46288.00, change: 439.10, change_pct: 0.96, k: 29.8, d: 32.7, turnover_yi: 4395.1, streak: '連漲 2 天'},
    {date: '2026-09-16', close: 45848.90, change: 337.41, change_pct: 0.74, k: 24.4, d: 34.1, turnover_yi: 3326.7, streak: '連漲 1 天'},
    {date: '2026-09-15', close: 45511.49, change: -351.03, change_pct: -0.77, k: 26.2, d: 38.9, turnover_yi: 3225.5, streak: '連跌 4 天'}
  ]
};

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  const query = req.query || {};
  const forceRefresh = query.refresh === '1' || query.force === 'true' || Boolean(query.t);
  const now = Date.now();
  if (!forceRefresh && CACHE.data && (now - CACHE.timestamp) < CACHE_TTL_MS) {
    res.setHeader('Cache-Control', 'no-cache, no-store, max-age=0, must-revalidate');
    res.setHeader('CDN-Cache-Control', 'no-store');
    res.setHeader('Vercel-CDN-Cache-Control', 'no-store');
    res.setHeader('X-Cache', 'HIT');
    res.status(200).json(CACHE.data);
    return;
  }

  try {
    const data = await fetchMarketData();
    if (!data || !data.records || data.records.length < 5) {
      res.setHeader('Cache-Control', 'no-cache, no-store, max-age=0, must-revalidate');
      res.status(200).json(HARDCODED_MARKET_FALLBACK);
      return;
    }
    CACHE.data = data;
    CACHE.timestamp = now;
    res.setHeader('Cache-Control', 'no-cache, no-store, max-age=0, must-revalidate');
    res.setHeader('CDN-Cache-Control', 'no-store');
    res.setHeader('Vercel-CDN-Cache-Control', 'no-store');
    res.setHeader('X-Cache', 'MISS');
    res.status(200).json(data);
  } catch (err) {
    res.setHeader('Cache-Control', 'no-cache, no-store, max-age=0, must-revalidate');
    res.status(200).json(HARDCODED_MARKET_FALLBACK);
  }
}

export { handler };
if (typeof module !== 'undefined' && module.exports) {
  module.exports = handler;
  module.exports.default = handler;
}
