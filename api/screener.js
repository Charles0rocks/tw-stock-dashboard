import https from 'https';

const POPULAR_UNIVERSE = [
  // Taiwan 50 & Top Heavyweights
  "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "2881.TW", "2882.TW", "2412.TW",
  "2891.TW", "3711.TW", "2886.TW", "2357.TW", "2884.TW", "1216.TW", "2892.TW", "3231.TW",
  "2885.TW", "2303.TW", "2880.TW", "2603.TW", "1301.TW", "2002.TW", "2887.TW", "2890.TW",
  "5880.TW", "2379.TW", "2883.TW", "1303.TW", "3008.TW", "3034.TW", "2609.TW", "2345.TW",
  "4938.TW", "6669.TW", "5871.TW", "2801.TW", "2207.TW", "2395.TW", "2615.TW", "3037.TW",
  "1101.TW", "2356.TW", "2408.TW", "4904.TW", "2912.TW", "6505.TW", "9910.TW", "2409.TW",
  "3481.TW", "2812.TW", "2324.TW", "3605.TW",

  // Popular High Volume Stocks & Tech Leaders
  "2376.TW", "2377.TW", "2618.TW", "2610.TW", "1519.TW", "1503.TW", "1504.TW", "1513.TW",
  "1605.TW", "1802.TW", "2368.TW", "2449.TW", "3017.TW", "3324.TWO", "3443.TW", "3529.TWO",
  "3661.TW", "5483.TWO", "6274.TWO", "6488.TWO", "8069.TWO", "8299.TWO", "8996.TWO", "3293.TWO",
  "6121.TWO", "5347.TWO", "3105.TWO", "6147.TWO", "8050.TWO", "5425.TWO", "3260.TWO",

  // Benchmark ETFs (Broad, High Dividend, Tech, Bond)
  "0050.TW", "0056.TW", "00878.TW", "00919.TW", "00929.TW", "00940.TW", "00713.TW", "00918.TW",
  "00939.TW", "006208.TW", "00757.TW", "00830.TW", "00679B.TW", "00720B.TWO", "00687B.TW",
  "00937B.TWO", "00724B.TWO", "00933B.TW", "00740B.TWO", "00751B.TWO", "00772B.TWO", "00773B.TWO",
  "00882.TW", "00891.TW", "00892.TW", "00935.TW", "00922.TW", "00923.TW"
];

const EXTENDED_UNIVERSE = [
  ...POPULAR_UNIVERSE,
  "2006.TW", "2014.TW", "2027.TW", "2105.TW", "2201.TW", "2204.TW", "2313.TW", "2323.TW",
  "2337.TW", "2344.TW", "2352.TW", "2353.TW", "2360.TW", "2362.TW", "2363.TW", "2371.TW",
  "2383.TW", "2385.TW", "2404.TW", "2451.TW", "2458.TW", "2498.TW", "2515.TW", "2520.TW",
  "2542.TW", "2606.TW", "2617.TW", "2637.TW", "2834.TW", "2888.TW", "2889.TW", "2897.TW",
  "3035.TW", "3036.TW", "3044.TW", "3045.TW", "3406.TW", "3532.TW", "3533.TW", "3596.TW",
  "3702.TW", "3706.TW", "4915.TW", "4958.TW", "4968.TW", "5269.TW", "5876.TW", "6116.TW",
  "6176.TW", "6213.TW", "6239.TW", "6285.TW", "6414.TW", "6415.TW", "6531.TW", "8046.TW",
  "9904.TW", "9945.TW", "9958.TW"
];

const STOCK_NAME_MAP = {
  "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2308": "台達電",
  "2881": "富邦金", "2882": "國泰金", "0050": "元大台灣50", "0056": "元大高股息",
  "00878": "國泰永續高股息", "00919": "群益台灣精選高收益", "00720B": "元大投資級公司債",
  "4938": "和碩", "3231": "緯創", "2404": "漢唐", "2382": "廣達",
  "2357": "華碩", "2301": "光寶科", "2002": "中鋼", "6669": "緯穎",
  "2409": "友達", "2356": "英業達", "3034": "聯詠", "2603": "長榮",
  "2609": "陽明", "2615": "萬海", "2303": "聯電", "2891": "中信金",
  "2884": "玉山金", "2886": "兆豐金", "2892": "第一金", "2880": "華南金",
  "2395": "研華", "00981A": "主動統一台股增長", "00929": "復華台灣科技優息",
  "00940": "元大台灣價值高息", "00918": "大華優利高填息30", "00713": "元大台灣高息低波",
  "00939": "統一台灣高息動能", "2379": "瑞昱", "3711": "日月光投控",
  "2345": "智邦", "3037": "欣興", "2376": "技嘉", "2377": "微星",
  "2324": "仁寶", "3605": "宏致", "00679B": "元大美債20年", "00687B": "國泰20年美債",
  "00937B": "群益ESG投等債20+", "00724B": "群益10年IG金融債"
};

let SCREENER_CACHE = null;
let CACHE_TIME = 0;
const CACHE_TTL = 120 * 1000; // 120 seconds cache

function fetchJson(url, headers = {}, timeoutMs = 4500) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://tw.stock.yahoo.com/',
        'Accept': 'application/json',
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
        } catch (e) {
          reject(e);
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
  let k = 50.0;
  let d = 50.0;
  for (let idx = period - 1; idx < closes.length; idx++) {
    let hMax = -Infinity;
    let lMin = Infinity;
    for (let j = idx - period + 1; j <= idx; j++) {
      if (highs[j] > hMax) hMax = highs[j];
      if (lows[j] < lMin) lMin = lows[j];
    }
    const diff = hMax - lMin;
    let rsv = diff === 0 ? 50.0 : ((closes[idx] - lMin) / diff) * 100.0;
    rsv = Math.max(0, Math.min(100, rsv));
    k = (2.0 / 3.0) * k + (1.0 / 3.0) * rsv;
    d = (2.0 / 3.0) * d + (1.0 / 3.0) * k;
  }
  return { k: Number(k.toFixed(1)), d: Number(d.toFixed(1)) };
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const { expanded } = req.query || {};
  const isExpanded = expanded === 'true' || expanded === '1';
  const now = Date.now();

  // Return cached result if valid and not explicitly forced
  if (SCREENER_CACHE && (now - CACHE_TIME < CACHE_TTL) && !isExpanded) {
    res.setHeader('Cache-Control', 's-maxage=120, stale-while-revalidate=120');
    return res.status(200).json(SCREENER_CACHE);
  }

  const t0 = Date.now();
  const universe = isExpanded ? EXTENDED_UNIVERSE : POPULAR_UNIVERSE;

  // Split into chunks of 50
  const chunkSize = 50;
  const chunks = [];
  for (let i = 0; i < universe.length; i += chunkSize) {
    chunks.push(universe.slice(i, i + chunkSize));
  }

  const oversoldList = [];
  const overboughtList = [];
  let totalScanned = 0;

  try {
    const fetchPromises = chunks.map(chunk => {
      const symEnc = encodeURIComponent(JSON.stringify(chunk));
      const url = `https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService.ApacLibraCharts;period=d;symbols=${symEnc}`;
      return fetchJson(url, {}, 4000).catch(() => []);
    });

    const results = await Promise.all(fetchPromises);

    for (const batch of results) {
      if (!Array.isArray(batch)) continue;
      for (const item of batch) {
        if (!item || !item.chart) continue;
        const chart = item.chart;
        const meta = chart.meta || {};
        const q = chart.indicators?.quote?.[0];
        if (!q || !q.close) continue;

        const closes = q.close.filter(c => c != null && !isNaN(c));
        const highs = q.high.filter(c => c != null && !isNaN(c));
        const lows = q.low.filter(c => c != null && !isNaN(c));
        if (closes.length < 9) continue;

        totalScanned++;

        const { k, d } = calculateTaiwanKD(highs, lows, closes, 9);
        const sym = meta.symbol || item.symbol || '';
        const baseCode = sym.replace(/\.(TW|TWO)$/, '');
        const name = STOCK_NAME_MAP[sym] || STOCK_NAME_MAP[baseCode] || meta.name || meta.shortName || baseCode;

        const latestPrice = meta.regularMarketPrice ?? closes[closes.length - 1];
        const prevClose = meta.previousClose ?? (closes.length > 1 ? closes[closes.length - 2] : latestPrice);
        const changeVal = Number((latestPrice - prevClose).toFixed(2));
        const changePct = prevClose > 0 ? Number(((changeVal / prevClose) * 100).toFixed(2)) : 0;

        const vols = q.volume || [];
        const volLots = vols.length > 0 ? Math.floor(vols[vols.length - 1] / 1000) : 0;
        const volumeDisplay = `${volLots.toLocaleString()} 張`;

        const stockObj = {
          symbol: sym,
          name: name,
          latest_close: Number(latestPrice.toFixed(2)),
          change_pct: changePct,
          k: k,
          d: d,
          volume_lots: volLots,
          volume_display: volumeDisplay
        };

        // 條件 1: 買方轉折區 (超賣金叉 / 築底)：K > D 且 K < 20
        if (k > d && k < 20.0) {
          stockObj.tag = "🟢【超賣區金叉 / 築底反轉】";
          stockObj.condition = "K > D 且 K < 20";
          stockObj.meaning = "指標處於 20 以下極端超賣區，且已由下往上穿越 D 值（低檔金叉或轉強），具備跌深反彈與左側安全邊際。";
          oversoldList.push(stockObj);
        }
        // 條件 2: 賣方警戒區 (超買死叉 / 鈍化)：K < D 且 K > 80
        else if (k < d && k > 80.0) {
          stockObj.tag = "🔴【高檔死叉 / 超買警戒】";
          stockObj.condition = "K < D 且 K > 80";
          stockObj.meaning = "指標處於 80 以上極端超買區，且已跌破 D 值（高檔死叉），短線動能竭盡，拉回風險高。";
          overboughtList.push(stockObj);
        }
      }
    }

    oversoldList.sort((a, b) => a.k - b.k);
    overboughtList.sort((a, b) => b.k - a.k);

    const elapsed = Number(((Date.now() - t0) / 1000).toFixed(2));

    const payload = {
      timestamp: Date.now(),
      total_scanned: totalScanned,
      oversold: oversoldList,
      overbought: overboughtList,
      oversold_symbols: oversoldList.map(s => s.symbol),
      overbought_symbols: overboughtList.map(s => s.symbol),
      elapsed_seconds: elapsed
    };

    if (!isExpanded) {
      SCREENER_CACHE = payload;
      CACHE_TIME = Date.now();
    }

    res.setHeader('Cache-Control', 's-maxage=120, stale-while-revalidate=120');
    return res.status(200).json(payload);

  } catch (err) {
    return res.status(500).json({
      error: 'Failed to screen KD extremes',
      message: err.message,
      oversold: [],
      overbought: []
    });
  }
}
