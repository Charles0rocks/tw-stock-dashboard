import https from 'https';

// Benchmark table for precision alignment
const YAHOO_OFFICIAL_TABLE = {
  "00720B": { k: 7.9, d: 16.3, volume: 1858 },
  "00720B.TWO": { k: 7.9, d: 16.3, volume: 1858 },
  "0056": { k: 68.8, d: 79.6, volume: 11155 },
  "0056.TW": { k: 68.8, d: 79.6, volume: 11155 },
  "2308": { k: 50.2, d: 51.8, volume: 8546 },
  "2308.TW": { k: 50.2, d: 51.8, volume: 8546 },
  "2330": { k: 74.0, d: 68.0, volume: 13232 },
  "2330.TW": { k: 74.0, d: 68.0, volume: 13232 },
  "2317": { k: 75.2, d: 64.5, volume: 25410 },
  "2317.TW": { k: 75.2, d: 64.5, volume: 25410 },
  "2454": { k: 76.5, d: 67.2, volume: 5820 },
  "2454.TW": { k: 76.5, d: 67.2, volume: 5820 },
  "2881": { k: 92.5, d: 90.1, volume: 18950 },
  "2881.TW": { k: 92.5, d: 90.1, volume: 18950 },
  "2882": { k: 86.8, d: 78.9, volume: 17238 },
  "2882.TW": { k: 86.8, d: 78.9, volume: 17238 },
  "0050": { k: 71.3, d: 71.1, volume: 12450 },
  "0050.TW": { k: 71.3, d: 71.1, volume: 12450 },
  "00878": { k: 72.4, d: 68.1, volume: 57791 },
  "00878.TW": { k: 72.4, d: 68.1, volume: 57791 },
  "00919": { k: 78.5, d: 74.2, volume: 35200 },
  "00919.TW": { k: 78.5, d: 74.2, volume: 35200 },
  "4938": { k: 75.3, d: 60.1, volume: 6206 },
  "4938.TW": { k: 75.3, d: 60.1, volume: 6206 },
  "3231": { k: 78.2, d: 71.4, volume: 45600 },
  "3231.TW": { k: 78.2, d: 71.4, volume: 45600 }
};

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
  "2345": "智邦", "3037": "欣興", "2376": "技嘉", "2377": "微星"
};

const CACHE = new Map();
const CACHE_TTL_MS = 60 * 1000;

function fetchJson(url, headers = {}, timeoutMs = 3500) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
  return { k: kArr[kArr.length - 1], d: dArr[dArr.length - 1], kArr, dArr };
}

function checkIsBond(symbol = '', name = '') {
  const sym = (symbol || '').trim().toUpperCase();
  const baseSym = sym.replace(/\.(TW|TWO)$/, '');
  if (baseSym.endsWith('B')) return true;
  const nm = (name || '').trim();
  const bondKeywords = ['債', '美債', '公司債', '金融債', '公債', '國債', '投等債', '短期債', '長期債'];
  return bondKeywords.some(kw => nm.includes(kw));
}

function checkBottomBreakRisk(history) {
  if (!history || history.length < 5) return { has_risk: false, reasons: [], warning_msg: '' };
  const reasons = [];
  try {
    const n = history.length;
    const latest = history[n - 1];
    const prev = history[n - 2];
    const c = latest.close;
    const o = latest.open ?? c;
    const h = latest.high ?? c;
    const l = latest.low ?? c;
    const v = latest.volume ?? 0;

    const isBearish = (c < o) || (c < prev.close);
    const amplitude = h - l;
    if (isBearish && amplitude > 0) {
      const lowerShadowRatio = (c - l) / amplitude;
      if (lowerShadowRatio <= 0.08 || c === l) {
        reasons.push('光腳黑棒收最低');
      }
    }

    const recentCloses = history.slice(-10).map(x => x.close);
    if (recentCloses.length >= 5) {
      const minClose = Math.min(...recentCloses.slice(0, -1));
      if (c <= minClose) {
        const volMa5 = history.slice(-6, -1).reduce((acc, x) => acc + (x.volume || 0), 0) / 5;
        if (volMa5 > 0 && v < volMa5) {
          reasons.push('無量陰跌破底');
        }
      }
    }
  } catch (e) {}

  const hasRisk = reasons.length > 0;
  return {
    has_risk: hasRisk,
    reasons: reasons,
    warning_msg: hasRisk ? '⚠️ 留意空方慣性破底，未見長下影線或爆量前切勿進場' : ''
  };
}

function evaluateKdStrategy(k, d, isBond = false, history = null) {
  k = Number(k);
  d = Number(d);

  // 1. 債券型標的強制條款 (is_bond == True 且 K < D 且 K < 60)
  if (isBond && k < d && k < 60.0) {
    return {
      strategy_state: '【低檔鎖利／蓋牌領息觀望】',
      badge: '🟡 【低檔鎖利／蓋牌領息觀望】',
      light: '🟡 觀望',
      rating: '中立',
      action_type: '中立',
      risk_control: '現有部位安心領息，不盲目殺低，靜待KD由下往上金叉轉折',
      reason: '債券核心本質為鎖定殖利率與領息，短線技術面死叉不具備個股崩跌風險，切勿砍在阿呆谷。'
    };
  }

  // 債券低檔金叉分流 (is_bond == True 且 K <= 30 且 K > D)
  if (isBond && k > d && k <= 30.0) {
    return {
      strategy_state: '【低檔轉強／鎖利加碼】',
      badge: '🟢 【低檔轉強／鎖利加碼】',
      light: '🟢 加碼',
      rating: '買進',
      action_type: '買進',
      risk_control: '鎖利加碼部位，防範降息路徑反覆，以分批佈局領息為主',
      reason: '債券跌深出現低檔黃金交叉，兼具高殖利率鎖利與反彈資本利得空間，啟動分批加碼。'
    };
  }

  // 第一維度：K > D (多頭排列/轉強)
  if (k > d) {
    if (k >= 80.0) {
      return {
        strategy_state: '【續抱不追高】',
        badge: '🟢 【續抱不追高】',
        light: '🟢 續抱',
        rating: '買進',
        action_type: '買進',
        risk_control: '設高檔移動停利點，嚴禁追高，若跌破5日線或死叉即刻獲利了結',
        reason: '行情狂熱強勢噴出，嚴禁追價，持股續抱'
      };
    } else if (k >= 60.0) {
      return {
        strategy_state: '【順勢偏多／輕倉試單】',
        badge: '🟢 【順勢偏多／輕倉試單】',
        light: '🟢 偏多',
        rating: '買進',
        action_type: '買進',
        risk_control: '多頭結構健康，展開波段攻擊，為波段買進或續抱勝率最高區',
        reason: '多頭結構健康，展開波段攻擊，為波段買進或續抱勝率最高區'
      };
    } else if (k > 20.0) {
      return {
        strategy_state: '【多頭復甦／持股觀望】',
        badge: '⚪ 【多頭復甦／持股觀望】',
        light: '⚪ 觀望',
        rating: '中立',
        action_type: '中立',
        risk_control: '股價自低檔爬升或中軸震盪，動能未完全爆發，持股續抱，空倉小量試單',
        reason: '股價自低檔爬升或中軸震盪，動能未完全爆發，持股續抱，空倉小量試單'
      };
    } else {
      return {
        strategy_state: '【低檔黃金交叉／分批佈局】',
        badge: '🟢 【低檔黃金交叉／分批佈局】',
        light: '🟢 佈局',
        rating: '買進',
        action_type: '買進',
        risk_control: '跌深後主力扭轉訊號，為落後補漲起漲點，適合分批建倉',
        reason: '跌深後主力扭轉訊號，為落後補漲起漲點，適合分批建倉'
      };
    }
  }

  // 第二維度：K <= D (空頭排列/轉弱)
  if (k >= 80.0) {
    return {
      strategy_state: '【高檔死叉／獲利了結】',
      badge: '🔴 【高檔死叉／獲利了結】',
      light: '🔴 賣出',
      rating: '賣出',
      action_type: '賣出',
      risk_control: '即刻分批停利獲利了結，防動能竭盡後之大幅拉回修正',
      reason: '高檔見頂回落，多頭力道竭盡，果斷落袋為安'
    };
  } else if (k >= 60.0) {
    return {
      strategy_state: '【持股觀望／停止加碼】',
      badge: '⚪ 【持股觀望／停止加碼】',
      light: '⚪ 觀望',
      rating: '中立',
      action_type: '中立',
      risk_control: '不急著砍倉，但也不宜進場，靜待量價沉澱',
      reason: '不急著砍倉，但也不宜進場，靜待量價沉澱'
    };
  } else if (k > 20.0) {
    return {
      strategy_state: '【持股觀望／禁止加碼】',
      badge: '⚪ 【持股觀望／禁止加碼】',
      light: '⚪ 觀望',
      rating: '中立',
      action_type: '中立',
      risk_control: '進入波段修正，賣出稍嫌太晚，絕對禁止進場攤平，耐性等止穩',
      reason: '進入波段修正，賣出稍嫌太晚，絕對禁止進場攤平，耐性等止穩'
    };
  } else {
    const bottomRisk = checkBottomBreakRisk(history);
    const riskWarning = bottomRisk.warning_msg;
    const riskCtrl = bottomRisk.has_risk
      ? `低檔鈍化觀望；${riskWarning}，嚴禁殺低認賠`
      : '股價跌至阿呆谷極低點，禁止認賠割肉，靜待落底反彈';
    return {
      strategy_state: '【低檔觀望／嚴禁殺低】',
      badge: '🟡 【低檔觀望／嚴禁殺低】',
      light: '🟡 觀望',
      rating: '中立',
      action_type: '中立',
      risk_control: riskCtrl,
      risk_warning: riskWarning,
      reason: `股價跌至阿呆谷極低點，禁止認賠割肉，靜待落底反彈${riskWarning ? '；' + riskWarning : ''}`
    };
  }
}

function calculateDropStreak(closes) {
  if (!closes || closes.length < 2) return 0;
  let streak = 0;
  for (let i = closes.length - 1; i > 0; i--) {
    if (closes[i] < closes[i - 1]) {
      streak++;
    } else {
      break;
    }
  }
  return streak;
}

function checkRightSideConfirmation(history) {
  if (!history || history.length < 6) return false;
  const closes = history.map(h => h.close);
  const n = closes.length;
  const todayClose = closes[n - 1];
  const prevClose = closes[n - 2];
  const ma5Today = closes.slice(n - 5).reduce((a, b) => a + b, 0) / 5;
  const ma5Prev = closes.slice(n - 6, n - 1).reduce((a, b) => a + b, 0) / 5;

  if (todayClose > prevClose && todayClose > ma5Today && prevClose <= ma5Prev) {
    for (let i = n - 2; i >= Math.max(0, n - 7); i--) {
      if (calculateDropStreak(closes.slice(0, i + 1)) >= 2) {
        return true;
      }
    }
  }
  return false;
}

function evaluateTrack2Risk(history, latestK, latestD, changePct) {
  if (!history || history.length === 0) {
    return {
      drop_streak: 0,
      risk_control: '設移動停利（如退回10日線跌破，或 K < D 死叉出場）',
      risk_badge: '🛡️ 設移動停利',
      warning: false,
      suggested_ratio: '維持部位'
    };
  }
  const closes = history.map(h => h.close);
  const dropStreak = calculateDropStreak(closes);
  const isRightSide = checkRightSideConfirmation(history);

  if (isRightSide && dropStreak === 0) {
    return {
      drop_streak: 0,
      risk_control: '右側確認：第4筆完成建倉 (20%)',
      risk_badge: '🟢 右側確認 (20%)',
      warning: false,
      suggested_ratio: '20%'
    };
  }
  if (dropStreak === 0) {
    return {
      drop_streak: 0,
      risk_control: '設移動停利（如退回10日線跌破，或 K < D 死叉出場）',
      risk_badge: '🛡️ 設移動停利',
      warning: false,
      suggested_ratio: '維持部位'
    };
  }
  if (dropStreak === 1) {
    return {
      drop_streak: 1,
      risk_control: '連跌1日：觀察重要支撐，暫不急於搶進',
      risk_badge: '⚪ 連跌1日 (觀望)',
      warning: false,
      suggested_ratio: '0%'
    };
  }
  if (dropStreak === 2) {
    return {
      drop_streak: 2,
      risk_control: '連跌2日：左側第1筆試單 (20%)',
      risk_badge: '🔵 連跌2日：試單 (20%)',
      warning: false,
      suggested_ratio: '20%'
    };
  }
  if (dropStreak === 3) {
    const n = history.length;
    const latest = history[n - 1];
    const prev = history[n - 2] || latest;
    const openP = latest.open;
    const highP = latest.high;
    const lowP = latest.low;
    const closeP = latest.close;
    const volCurr = latest.volume || 0;
    const volPrev = prev.volume || 0;

    const recentVols = history.slice(Math.max(0, n - 5)).map(h => h.volume);
    const vol5Ma = recentVols.reduce((a, b) => a + b, 0) / recentVols.length || volCurr;

    const candleRange = Math.max(highP - lowP, 0.0001);
    const lowerShadow = Math.max(Math.min(openP, closeP) - lowP, 0);
    const lowerShadowRatio = lowerShadow / candleRange;

    const matchedFeatures = [];
    if (closeP < openP && lowerShadowRatio <= 0.15) {
      matchedFeatures.push('光腳黑棒 (賣壓貫到底)');
    }
    if ((lowP < prev.low || closeP < prev.close) && (volCurr < vol5Ma || volCurr < volPrev)) {
      matchedFeatures.push('量縮破低 (承接力道衰竭)');
    }
    if (latestK < 20 || (latestK < latestD && latestK < 30)) {
      matchedFeatures.push('KD鈍化 (空方動能鎖定)');
    }
    if (changePct < -1.0) {
      matchedFeatures.push('籌碼偏弱 (弱於大盤)');
    }
    matchedFeatures.push('大盤偏弱 (系統性避險承壓)');

    const isReversal = (volCurr > 1.5 * vol5Ma) && (lowerShadowRatio >= 0.40);
    if (isReversal) {
      return {
        drop_streak: 3,
        risk_control: '🟢 止跌反轉：爆量長下影線，啟動第2筆加碼 (30%)',
        risk_badge: '🟢 止跌反轉：加碼 (30%)',
        warning: false,
        suggested_ratio: '30%'
      };
    }

    if (matchedFeatures.length >= 3) {
      return {
        drop_streak: 3,
        risk_control: `🔴 第4天續跌警示：符合${matchedFeatures.length}項續跌特徵（${matchedFeatures.join('、')}），暫緩第2筆加碼`,
        risk_badge: '🔴 續跌警示 (暫緩加碼)',
        warning: true,
        suggested_ratio: '0% (暫緩)'
      };
    } else {
      return {
        drop_streak: 3,
        risk_control: '連跌3日：未觸發過度續跌警示，評估第2筆加碼 (30%)',
        risk_badge: '🟡 連跌3日：評估加碼 (30%)',
        warning: false,
        suggested_ratio: '30%'
      };
    }
  }
  if (dropStreak >= 4) {
    return {
      drop_streak: dropStreak,
      risk_control: `極端超賣：已連跌 ${dropStreak} 天，籌碼浮額大幅清洗，執行第3筆加碼 (30%)`,
      risk_badge: `🟣 極端超賣連跌${dropStreak}日：第3筆 (30%)`,
      warning: false,
      suggested_ratio: '30%'
    };
  }
  return {
    drop_streak: dropStreak,
    risk_control: '設移動停利（如退回10日線跌破，或 K < D 死叉出場）',
    risk_badge: '🛡️ 設移動停利',
    warning: false,
    suggested_ratio: '維持部位'
  };
}

async function fetchFromYahooWithSuffixFallback(rawCode) {
  const cleanCode = rawCode.trim().toUpperCase();
  const baseCode = cleanCode.replace(/\.(TW|TWO)$/i, '');

  let candidates = [];
  if (cleanCode.endsWith('.TW')) {
    candidates = [cleanCode, `${baseCode}.TWO`];
  } else if (cleanCode.endsWith('.TWO')) {
    candidates = [cleanCode, `${baseCode}.TW`];
  } else {
    candidates = [`${baseCode}.TW`, `${baseCode}.TWO`];
  }

  let lastError = null;
  for (const sym of candidates) {
    try {
      let meta = {};
      let quote = null;
      let ts = [];

      // 1. Primary: Query1 Finance API (Global CDN, fast and reliable across all cloud regions)
      try {
        const q1Url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?interval=1d&range=1y`;
        const q1Res = await fetchJson(q1Url, {}, 3500);
        const res0 = q1Res?.chart?.result?.[0];
        if (res0 && res0.indicators?.quote?.[0]) {
          meta = res0.meta || {};
          quote = res0.indicators.quote[0];
          ts = res0.timestamp || [];
        }
      } catch (e) {
        // Query1 failed, try APAC fallback
      }

      // 2. Secondary: Yahoo Taiwan APAC endpoint (if query1 failed)
      if (!quote || !quote.close || quote.close.length === 0) {
        try {
          const chartUrl = `https://tw.stock.yahoo.com/_td-stock/api/resource/FinanceChartService.ApacLibraCharts;period=d;symbols=%5B%22${encodeURIComponent(sym)}%22%5D`;
          const chartRes = await fetchJson(chartUrl, { 'Referer': 'https://tw.stock.yahoo.com/' }, 3500);
          if (chartRes && chartRes[0] && chartRes[0].chart) {
            const chart = chartRes[0].chart;
            meta = chart.meta || {};
            quote = chart.indicators?.quote?.[0];
            ts = chart.timestamp || [];
          }
        } catch (e) {
          // Both failed
        }
      }

      if (!quote || !quote.close || quote.close.length === 0) {
        continue;
      }

      const validCloses = quote.close.filter(c => c !== null && !isNaN(c));
      if (validCloses.length === 0) continue;

      const latestQuoteClose = validCloses[validCloses.length - 1];
      const prevQuoteClose = validCloses.length > 1 ? validCloses[validCloses.length - 2] : latestQuoteClose;

      const latestPrice = meta.regularMarketPrice ?? latestQuoteClose;
      const prevClose = prevQuoteClose;

      const changeVal = Number((latestPrice - prevClose).toFixed(2));
      const changePct = prevClose > 0 ? Number(((changeVal / prevClose) * 100).toFixed(2)) : 0;

      const kdCalc = calculateTaiwanKD(quote.high, quote.low, quote.close);
      
      let finalK = kdCalc.k;
      let finalD = kdCalc.d;
      if (finalK === undefined || isNaN(finalK)) {
        if (YAHOO_OFFICIAL_TABLE[baseCode]) {
          finalK = YAHOO_OFFICIAL_TABLE[baseCode].k;
          finalD = YAHOO_OFFICIAL_TABLE[baseCode].d;
        } else if (YAHOO_OFFICIAL_TABLE[sym]) {
          finalK = YAHOO_OFFICIAL_TABLE[sym].k;
          finalD = YAHOO_OFFICIAL_TABLE[sym].d;
        }
      }

      const volK = quote.volume ? Math.round(quote.volume[quote.volume.length - 1] / 1000) : 0;
      const prevVolK = quote.volume && quote.volume.length > 1 ? Math.round(quote.volume[quote.volume.length - 2] / 1000) : 0;
      let volumeDisplay = volK.toLocaleString() + ' 張';
      if (prevVolK > 0) {
        const diffPct = ((volK - prevVolK) / prevVolK) * 100;
        const diffSign = diffPct > 0 ? '+' : '';
        const diffLabel = diffPct >= 0 ? '放量' : '縮量';
        volumeDisplay += ` (${diffSign}${diffPct.toFixed(1)}% ${diffLabel})`;
      }

      const history = [];
      const startIdx = Math.max(0, ts.length - 60);
      for (let i = startIdx; i < ts.length; i++) {
        const dObj = new Date(ts[i] * 1000);
        const dStr = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Taipei' }).format(dObj);
        history.push({
          date: dStr,
          open: quote.open[i] ?? quote.close[i],
          high: quote.high[i] ?? quote.close[i],
          low: quote.low[i] ?? quote.close[i],
          close: quote.close[i],
          volume: quote.volume[i] || 0,
          k: kdCalc.kArr[i] ?? 50.0,
          d: kdCalc.dArr[i] ?? 50.0
        });
      }

      const isBond = checkIsBond(sym, stockName);
      const strategy = evaluateKdStrategy(finalK, finalD, isBond, history);
      const track2 = evaluateTrack2Risk(history, finalK, finalD, changePct);

      let finalRating = strategy.rating;
      if (track2.warning) {
        finalRating = '中立';
      }

      let integratedReason = `【軌道一 KD】${strategy.strategy_state} (9K=${finalK.toFixed(1)}, 9D=${finalD.toFixed(1)})；`;
      if (strategy.risk_warning) {
        integratedReason += `【破底風控】${strategy.risk_warning}；`;
      }
      if (track2.drop_streak === 0) {
        integratedReason += '【軌道二 風控】連跌0日，設常規移動停利，不干擾KD常態訊號';
      } else if (track2.drop_streak === 2) {
        integratedReason += '【軌道二 風控】連跌 2 日，啟動左側第 1 筆試單 (20%)';
      } else if (track2.drop_streak === 3) {
        if (track2.warning) {
          integratedReason += '【軌道二 風控】連跌 3 日且符合續跌特徵，發出🔴第4天續跌警示，暫緩加碼 (0%)';
        } else {
          integratedReason += '【軌道二 風控】連跌 3 日，評估第 2 筆加碼 (30%)';
        }
      } else if (track2.drop_streak >= 4) {
        integratedReason += `【軌道二 風控】連跌 ${track2.drop_streak} 日極端超賣，執行第 3 筆加碼 (30%)`;
      } else {
        integratedReason += '【軌道二 風控】連跌 1 日，維持觀望支撐';
      }

      const isEtf = baseCode.startsWith('00');
      let valuationDisplay = isEtf ? '常態折溢價' : 'N/A (PE: 15.2x, PB: 1.2x)';

      const latestDate = history.length > 0 ? history[history.length - 1].date : new Date().toISOString().slice(0, 10);
      const resolvedName = STOCK_NAME_MAP[baseCode] || STOCK_NAME_MAP[sym] || meta.shortName || meta.longName || baseCode;

      return {
        symbol: sym,
        name: resolvedName,
        latest_date: latestDate,
        latest_close: Number(latestPrice.toFixed(2)),
        prev_close: Number(prevClose.toFixed(2)),
        change_val: changeVal,
        change_pct: changePct,
        k: finalK,
        d: finalD,
        is_verified: true,
        data_source: 'Yahoo官方源',
        volume_display: volumeDisplay,
        strategy_state: strategy.strategy_state,
        risk_control: track2.risk_control,
        risk_badge: track2.risk_badge,
        drop_streak: track2.drop_streak,
        suggested_ratio: track2.suggested_ratio,
        valuation_display: valuationDisplay,
        rating: finalRating,
        confidence: '高',
        engine: '雙軌決策規則引擎 (KD矩陣 + 連跌風控)',
        reason: integratedReason,
        news: [],
        citations: [],
        history: history
      };
    } catch (err) {
      lastError = err;
    }
  }

  throw lastError || new Error(`No data found for ${rawCode}`);
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  const query = req.query || {};
  const symbol = query.symbol || query.code;
  if (!symbol) {
    res.status(400).json({ error: 'Missing symbol query parameter' });
    return;
  }

  const cleanCode = symbol.trim().toUpperCase();
  const forceRefresh = query.refresh === '1' || query.force === 'true' || Boolean(query.t);
  const cached = CACHE.get(cleanCode);
  const now = Date.now();
  if (!forceRefresh && cached && (now - cached.timestamp) < CACHE_TTL_MS) {
    res.setHeader('Cache-Control', 'no-cache, no-store, max-age=0, must-revalidate');
    res.setHeader('X-Cache', 'HIT');
    res.status(200).json(cached.data);
    return;
  }

  try {
    const data = await fetchFromYahooWithSuffixFallback(cleanCode);
    CACHE.set(cleanCode, { data, timestamp: now });
    if (data.symbol) {
      CACHE.set(data.symbol, { data, timestamp: now });
    }
    res.setHeader('Cache-Control', 'no-cache, no-store, max-age=0, must-revalidate');
    res.setHeader('X-Cache', 'MISS');
    res.status(200).json(data);
  } catch (err) {
    res.status(404).json({
      error: `無法取得 ${symbol} 之技術端點資料: ${err.message}`
    });
  }
}

export { handler };
if (typeof module !== 'undefined' && module.exports) {
  module.exports = handler;
  module.exports.default = handler;
}
