const https = require('https');

const CACHE = { data: null, timestamp: 0 };
const CACHE_TTL_MS = 120 * 1000;

function fetchJson(url, headers = {}, timeoutMs = 4500) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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

  // Try 1: Query1 Finance
  try {
    const q1Url = 'https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII?interval=1d&range=1mo';
    const q1Res = await fetchJson(q1Url, {
      'Accept': 'application/json'
    }, 4000);

    const res0 = q1Res?.chart?.result?.[0];
    if (res0 && res0.timestamp && res0.indicators?.quote?.[0]) {
      const q = res0.indicators.quote[0];
      timestamps = res0.timestamp;
      opens = q.open;
      highs = q.high;
      lows = q.low;
      closes = q.close;
      volumes = q.volume;
    }
  } catch (err) {
    // console.warn('Query1 failed, trying APAC endpoint:', err.message);
  }

  // Try 2: APAC Libra Charts fallback
  if (!timestamps || timestamps.length < 5) {
    const apacUrl = 'https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService.ApacLibraCharts;period=d;symbols=%5B%22%5ETWII%22%5D';
    const apacRes = await fetchJson(apacUrl, {
      'Referer': 'https://tw.stock.yahoo.com/'
    }, 4500);

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

  // Filter valid entries
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

  // Calculate daily changes and streaks
  const fullRecords = [];
  for (let i = 0; i < validEntries.length; i++) {
    const cur = validEntries[i];
    const prev = i > 0 ? validEntries[i - 1] : cur;
    const change = Number((cur.close - prev.close).toFixed(2));
    const changePct = prev.close > 0 ? Number(((change / prev.close) * 100).toFixed(2)) : 0;

    // Calculate streak
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

  // Recent 10 trading days descending
  const recent10 = fullRecords.slice(-10).reverse();
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
    records: recent10,
    all_recent: fullRecords.slice(-30) // for chart rendering
  };
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  const now = Date.now();
  if (CACHE.data && (now - CACHE.timestamp) < CACHE_TTL_MS) {
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
    res.setHeader('X-Cache', 'HIT');
    res.status(200).json(CACHE.data);
    return;
  }

  try {
    const data = await fetchMarketData();
    CACHE.data = data;
    CACHE.timestamp = now;
    res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
    res.setHeader('X-Cache', 'MISS');
    res.status(200).json(data);
  } catch (err) {
    res.status(500).json({ error: `無法獲取加權指數端點資料: ${err.message}` });
  }
};
