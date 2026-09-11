import json
import os

with open('stock_data_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

json_data_str = json.dumps(cache, ensure_ascii=False)

html_content = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>台股Dashboard</title>
  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Plotly.js CDN -->
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{
      background-color: #0b0f19;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }}
    .scrollbar-thin::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    .scrollbar-thin::-webkit-scrollbar-thumb {{
      background: #334155;
      border-radius: 3px;
    }}
    .scrollbar-thin::-webkit-scrollbar-track {{
      background: #0f172a;
    }}
    .stock-card {{
      transition: all 0.15s ease-in-out;
    }}
    .stock-card.active {{
      background-color: #1e293b;
      border-color: #38bdf8;
      box-shadow: 0 0 15px rgba(56, 189, 248, 0.25);
    }}
    /* Taiwan Stock standard: Red for UP, Green for DOWN */
    .tw-up {{
      color: #ef4444;
    }}
    .tw-down {{
      color: #22c55e;
    }}
    .badge-buy {{ background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4); }}
    .badge-hold {{ background: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.4); }}
    .badge-sell {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }}
    .badge-neutral {{ background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.4); }}
    .badge-warning {{ background: rgba(249, 115, 22, 0.15); color: #fb923c; border: 1px solid rgba(249, 115, 22, 0.4); }}
  </style>
</head>
<body class="h-screen flex flex-col overflow-hidden">

  <!-- 1. Top Navbar -->
  <header class="bg-slate-900/90 border-b border-slate-800 px-6 py-3 flex items-center justify-between shrink-0">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white font-black text-lg shadow-lg shadow-cyan-500/20">
        📈
      </div>
      <div>
        <h1 class="text-lg font-bold tracking-tight text-white flex items-center gap-2">
          台股Dashboard <span class="text-xs font-semibold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">Stock Review</span>
        </h1>
        <p class="text-xs text-slate-400">標準台式 KD (9,3,3) 遞迴演算法 · 雙軌數據交叉校驗 · 6大操作策略矩陣</p>
      </div>
    </div>

    <div class="flex items-center gap-3">
      <button onclick="openModal()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 border border-slate-700 transition-all flex items-center gap-1.5">
        <span>📋</span> KD 策略矩陣
      </button>
      <a href="KD策略.csv" download class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 border border-slate-700 transition-all flex items-center gap-1.5">
        <span>💾</span> 下載 KD策略.csv
      </a>
      <a href="http://localhost:8501" target="_blank" class="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-bold text-white shadow-md shadow-blue-600/30 transition-all flex items-center gap-1.5">
        <span>🚀</span> Streamlit 即時伺服器
      </a>
    </div>
  </header>

  <!-- 2. Main Content Area -->
  <div class="flex-1 flex overflow-hidden">
    
    <!-- Left Sidebar: Stock List -->
    <aside class="w-80 border-r border-slate-800 bg-slate-900/60 flex flex-col shrink-0">
      <!-- Filter / Search -->
      <div class="p-3 border-b border-slate-800">
        <div class="relative">
          <input type="text" id="searchInput" placeholder="搜尋股票代碼或名稱..." oninput="filterStocks()"
                 class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors">
        </div>
        <div class="flex gap-1.5 mt-2">
          <button onclick="setTab('all')" id="tab-all" class="filter-tab px-2.5 py-1 rounded text-xs font-medium bg-cyan-600 text-white">全部</button>
          <button onclick="setTab('etf')" id="tab-etf" class="filter-tab px-2.5 py-1 rounded text-xs font-medium bg-slate-800 text-slate-400 hover:text-white">ETF</button>
          <button onclick="setTab('tech')" id="tab-tech" class="filter-tab px-2.5 py-1 rounded text-xs font-medium bg-slate-800 text-slate-400 hover:text-white">權值股</button>
        </div>
      </div>

      <!-- Stock List Scroll -->
      <div id="stockList" class="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-1.5">
        <!-- Dynamic populated by JS -->
      </div>
    </aside>

    <!-- Right Workspace: Stock Detail & Charts -->
    <main class="flex-1 flex flex-col overflow-y-auto scrollbar-thin p-5 space-y-4 bg-slate-950">
      
      <!-- Top Info Banner -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div>
          <div class="flex items-center gap-3">
            <h2 id="activeName" class="text-2xl font-black text-white">--</h2>
            <span id="activeSymbol" class="text-sm font-semibold px-2.5 py-0.5 rounded bg-slate-800 text-cyan-400 border border-slate-700">--</span>
            <span id="activeDataSource" class="text-xs text-slate-400">--</span>
          </div>
          <div class="flex items-baseline gap-3 mt-2">
            <span id="activePrice" class="text-3xl font-extrabold text-white">$--</span>
            <span id="activeChange" class="text-base font-bold">--</span>
            <span id="activeVolume" class="text-xs text-slate-400 ml-2">成交量: --</span>
          </div>
        </div>

        <!-- Strategy Badge Callout -->
        <div class="flex flex-col items-end gap-1.5">
          <div class="text-xs text-slate-400 font-medium">KD 策略決策狀態</div>
          <div id="activeStrategyBadge" class="text-base font-black px-4 py-1.5 rounded-xl badge-buy">--</div>
          <div id="activeRuleDesc" class="text-xs text-slate-400 max-w-xs text-right truncate">--</div>
        </div>
      </div>

      <!-- Indicator Cards Row -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        
        <!-- Card 1: KD Indicators -->
        <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div class="text-xs text-slate-400 font-semibold mb-2 flex items-center justify-between">
            <span>9日 KD 技術指標 (台式平滑)</span>
            <span class="text-[11px] text-cyan-400">遞迴周期: 3年還原</span>
          </div>
          <div class="flex items-center justify-around my-2">
            <div class="text-center">
              <div class="text-xs text-amber-400 font-semibold">9K (快線)</div>
              <div id="valK" class="text-3xl font-black text-amber-400 mt-1">--</div>
            </div>
            <div class="h-10 w-px bg-slate-800"></div>
            <div class="text-center">
              <div class="text-xs text-cyan-400 font-semibold">9D (慢線)</div>
              <div id="valD" class="text-3xl font-black text-cyan-400 mt-1">--</div>
            </div>
          </div>
          <div id="activeKdSignals" class="text-xs text-slate-300 text-center mt-3 pt-2 border-t border-slate-800 font-medium">
            --
          </div>
        </div>

        <!-- Card 2: Strategy Action & Risk Control -->
        <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div class="text-xs text-slate-400 font-semibold mb-2 flex items-center justify-between">
            <span>操作指引與風控建議</span>
            <span id="activeRuleName" class="text-[11px] text-slate-400">--</span>
          </div>
          <div class="space-y-2 mt-2 text-xs">
            <div>
              <span class="text-slate-400">策略邏輯：</span>
              <span id="valStrategyDesc" class="text-slate-200 font-medium">--</span>
            </div>
            <div>
              <span class="text-slate-400">風控停損：</span>
              <span id="valRiskControl" class="text-amber-300 font-medium">--</span>
            </div>
          </div>
        </div>

        <!-- Card 3: ETF Valuation / Stock Metric -->
        <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div class="text-xs text-slate-400 font-semibold mb-2 flex items-center justify-between">
            <span id="valuationTitle">估值 / ETF 折溢價指標</span>
            <span id="valuationStatus" class="text-[11px] text-emerald-400 font-semibold">正常</span>
          </div>
          <div class="my-2">
            <div class="flex justify-between text-xs text-slate-300 py-1">
              <span class="text-slate-400" id="valLabel1">估算淨值:</span>
              <span id="valNum1" class="font-bold text-white">--</span>
            </div>
            <div class="flex justify-between text-xs text-slate-300 py-1">
              <span class="text-slate-400" id="valLabel2">折溢價比率:</span>
              <span id="valNum2" class="font-bold">--</span>
            </div>
          </div>
          <div id="valAdvice" class="text-xs text-slate-400 pt-2 border-t border-slate-800 truncate">
            --
          </div>
        </div>

      </div>

      <!-- Plotly Chart Box -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex-1 min-h-[460px] flex flex-col">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2 text-xs font-semibold text-slate-300">
            <span>📊 技術走勢與指標圖</span>
            <span class="text-slate-500">|</span>
            <span class="text-slate-400">K線（紅漲綠跌）+ 9日KD走勢（含 80 超買 / 20 超賣線）</span>
          </div>
          <div class="text-xs text-slate-500">支援滾輪縮放與區間拖曳</div>
        </div>
        <div id="chartContainer" class="w-full flex-1 min-h-[420px]"></div>
      </div>

    </main>
  </div>

  <!-- Modal: KD Strategy Rules -->
  <div id="strategyModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <span class="text-xl">📋</span>
          <h3 class="text-base font-bold text-white">核心 6 大 KD 策略操作矩陣對照表</h3>
        </div>
        <button onclick="closeModal()" class="text-slate-400 hover:text-white text-lg font-bold">&times;</button>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-950 text-slate-400 border-b border-slate-800">
              <th class="p-2.5">編號</th>
              <th class="p-2.5">條件名稱</th>
              <th class="p-2.5">建議操作</th>
              <th class="p-2.5">策略標籤</th>
              <th class="p-2.5">操作邏輯與風控</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-200">
            <tr class="hover:bg-slate-800/30">
              <td class="p-2.5 font-bold text-cyan-400">1</td>
              <td class="p-2.5">K &gt; D 且 K &lt; 20</td>
              <td class="p-2.5 text-emerald-400 font-bold">買進</td>
              <td class="p-2.5"><span class="badge-buy px-2 py-0.5 rounded">【買進】分批建倉</span></td>
              <td class="p-2.5 text-slate-300">超賣轉折分批建倉；設近9日低點停損，防無底跌勢續摔。</td>
            </tr>
            <tr class="hover:bg-slate-800/30">
              <td class="p-2.5 font-bold text-cyan-400">2</td>
              <td class="p-2.5">K &gt; D 且 20 &le; K &le; 80</td>
              <td class="p-2.5 text-emerald-400 font-bold">續抱/加碼</td>
              <td class="p-2.5"><span class="badge-buy px-2 py-0.5 rounded">【續抱 / 加碼買進】</span></td>
              <td class="p-2.5 text-slate-300">常態多頭格局；設移動停利（跌破10日線或死叉出場）。</td>
            </tr>
            <tr class="hover:bg-slate-800/30">
              <td class="p-2.5 font-bold text-cyan-400">3</td>
              <td class="p-2.5">K &gt; D 且 K &gt; 80</td>
              <td class="p-2.5 text-amber-400 font-bold">續抱不追高</td>
              <td class="p-2.5"><span class="badge-hold px-2 py-0.5 rounded">【續抱不追高】</span></td>
              <td class="p-2.5 text-slate-300">高檔強勢格局；嚴禁盲目追高，死叉即刻部分獲利了結。</td>
            </tr>
            <tr class="hover:bg-slate-800/30">
              <td class="p-2.5 font-bold text-cyan-400">4</td>
              <td class="p-2.5">K &lt; D 且 K &gt; 80</td>
              <td class="p-2.5 text-rose-400 font-bold">賣出</td>
              <td class="p-2.5"><span class="badge-sell px-2 py-0.5 rounded">【賣出】獲利了結</span></td>
              <td class="p-2.5 text-slate-300">超買轉折高檔死叉；即刻分批停利落袋，防大幅修正。</td>
            </tr>
            <tr class="hover:bg-slate-800/30">
              <td class="p-2.5 font-bold text-cyan-400">5</td>
              <td class="p-2.5">K &lt; D 且 20 &le; K &le; 80</td>
              <td class="p-2.5 text-orange-400 font-bold">觀望/減碼</td>
              <td class="p-2.5"><span class="badge-warning px-2 py-0.5 rounded">【觀望 / 減碼賣出】</span></td>
              <td class="p-2.5 text-slate-300">常態空頭整理格局；破均線/支撐線即刻停損，觀望為主。</td>
            </tr>
            <tr class="hover:bg-slate-800/30">
              <td class="p-2.5 font-bold text-cyan-400">6</td>
              <td class="p-2.5">K &lt; D 且 K &lt; 20</td>
              <td class="p-2.5 text-cyan-400 font-bold">超賣區/尋求築底</td>
              <td class="p-2.5"><span class="badge-neutral px-2 py-0.5 rounded">【超賣區 / 尋求築底】</span></td>
              <td class="p-2.5 text-slate-300">低檔超賣區尋求築底；恐慌拋售未收斂，嚴禁盲目猜底。</td>
            </tr>
            <tr class="hover:bg-slate-800/30">
              <td class="p-2.5 font-bold text-cyan-400">7</td>
              <td class="p-2.5">KD 50 軸附近橫盤黏合</td>
              <td class="p-2.5 text-slate-300 font-bold">中性盤整/觀望</td>
              <td class="p-2.5"><span class="badge-neutral px-2 py-0.5 rounded">【中性盤整 / 觀望】</span></td>
              <td class="p-2.5 text-slate-300">50軸附近橫盤盲目黏合；多空僵持，建議中性觀望防誤判。</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex justify-end pt-2">
        <button onclick="closeModal()" class="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700">
          關閉
        </button>
      </div>
    </div>
  </div>

  <!-- Data & Application Scripts -->
  <script>
    const STOCKS_DATA = {json_data_str};
    let currentSymbol = '0050.TW';
    let currentFilter = 'all';

    function init() {{
      renderStockList();
      selectStock(currentSymbol);
    }}

    function renderStockList() {{
      const listEl = document.getElementById('stockList');
      listEl.innerHTML = '';
      const query = (document.getElementById('searchInput').value || '').trim().toLowerCase();

      Object.keys(STOCKS_DATA).forEach(sym => {{
        const item = STOCKS_DATA[sym];
        const isEtf = sym.startsWith('00');
        
        // Tab filter
        if (currentFilter === 'etf' && !isEtf) return;
        if (currentFilter === 'tech' && isEtf) return;
        
        // Search filter
        if (query && !sym.toLowerCase().includes(query) && !item.name.toLowerCase().includes(query)) {{
          return;
        }}

        const isUp = item.change_val >= 0;
        const colorClass = isUp ? 'tw-up' : 'tw-down';
        const sign = isUp ? '+' : '';
        const badgeClass = getBadgeClass(item.signal_info?.rule_info?.recommendation || '');

        const card = document.createElement('div');
        card.className = `stock-card p-3 rounded-xl border border-slate-800 bg-slate-950/70 hover:bg-slate-800/60 cursor-pointer ${{sym === currentSymbol ? 'active' : ''}}`;
        card.onclick = () => selectStock(sym);

        card.innerHTML = `
          <div class="flex items-center justify-between">
            <div class="font-bold text-xs text-white">${{item.name}}</div>
            <div class="text-[11px] font-semibold ${{colorClass}}">${{sign}}${{item.change_pct}}%</div>
          </div>
          <div class="flex items-center justify-between mt-1 text-[11px] text-slate-400">
            <span>${{sym}}</span>
            <span class="font-medium text-slate-200">$${{item.latest_close.toFixed(2)}}</span>
          </div>
          <div class="flex items-center justify-between mt-2 pt-1.5 border-t border-slate-800/60 text-[10px]">
            <span class="text-slate-400">9K: <b class="text-amber-400">${{item.k}}</b> / 9D: <b class="text-cyan-400">${{item.d}}</b></span>
            <span class="${{badgeClass}} px-1.5 py-0.5 rounded font-semibold">${{item.signal_info?.rule_info?.label || '分析中'}}</span>
          </div>
        `;
        listEl.appendChild(card);
      }});
    }}

    function selectStock(sym) {{
      if (!STOCKS_DATA[sym]) return;
      currentSymbol = sym;
      renderStockList(); // refresh active highlight

      const item = STOCKS_DATA[sym];
      const isUp = item.change_val >= 0;
      const colorClass = isUp ? 'tw-up' : 'tw-down';
      const sign = isUp ? '+' : '';

      // Set Banner
      document.getElementById('activeName').textContent = item.name;
      document.getElementById('activeSymbol').textContent = item.symbol;
      document.getElementById('activeDataSource').textContent = `資料源: ${{item.data_source || '雙軌對齊'}}`;
      document.getElementById('activePrice').textContent = `$${{item.latest_close.toFixed(2)}}`;
      
      const changeEl = document.getElementById('activeChange');
      changeEl.textContent = `${{sign}}${{item.change_val}} (${{sign}}${{item.change_pct}}%)`;
      changeEl.className = `text-base font-bold ${{colorClass}}`;

      const history = item.history || [];
      const latestHist = history.length > 0 ? history[history.length - 1] : {{}};
      document.getElementById('activeVolume').textContent = `成交量: ${{item.volume_display || (latestHist.volume ? Math.floor(latestHist.volume / 1000).toLocaleString() + ' 張' : '--')}}`;

      // Set Strategy Badge
      const rule = item.signal_info?.rule_info || {{}};
      const badgeEl = document.getElementById('activeStrategyBadge');
      badgeEl.textContent = rule.label || '【觀望】';
      badgeEl.className = `text-base font-black px-4 py-1.5 rounded-xl ${{getBadgeClass(rule.recommendation || '')}}`;
      document.getElementById('activeRuleDesc').textContent = rule.strategy_desc || '';

      // Set KD Card
      document.getElementById('valK').textContent = item.k.toFixed(1);
      document.getElementById('valD').textContent = item.d.toFixed(1);
      document.getElementById('activeKdSignals').textContent = item.signal_info?.status_text || '指標常態整理';

      // Set Strategy & Risk Control Card
      document.getElementById('activeRuleName').textContent = rule.rule_name || '';
      document.getElementById('valStrategyDesc').textContent = rule.strategy_desc || '無特定異常';
      document.getElementById('valRiskControl').textContent = rule.risk_control || '嚴守紀律，設好移動停利/停損';

      // Set Valuation Card
      const val = item.valuation || {{}};
      if (val.is_etf) {{
        document.getElementById('valuationTitle').textContent = 'ETF 淨值與折溢價分析';
        document.getElementById('valLabel1').textContent = '估算淨值 (NAV):';
        document.getElementById('valNum1').textContent = val.nav_price ? `$${{val.nav_price.toFixed(2)}}` : '未取得';
        document.getElementById('valLabel2').textContent = '折溢價率:';
        
        const ratio = val.ratio || 0;
        const ratioColor = ratio > 0 ? 'text-amber-400' : 'text-emerald-400';
        document.getElementById('valNum2').innerHTML = `<span class="${{ratioColor}}">${{ratio > 0 ? '+' : ''}}${{ratio.toFixed(2)}}%</span>`;
        document.getElementById('valAdvice').textContent = rule.etf_advice || val.description || '';
      }} else {{
        document.getElementById('valuationTitle').textContent = '個股基本估值面';
        document.getElementById('valLabel1').textContent = '本益比 (PE):';
        document.getElementById('valNum1').textContent = val.pe_ratio ? `${{val.pe_ratio.toFixed(1)}} 倍` : 'N/A';
        document.getElementById('valLabel2').textContent = '估值位階:';
        document.getElementById('valNum2').textContent = val.pe_status || '常態區間';
        document.getElementById('valAdvice').textContent = '個股著重業績基本面與題材動能';
      }}

      // Render Plotly Chart
      renderPlotlyChart(item);
    }}

    function renderPlotlyChart(item) {{
      const history = item.history || [];
      if (history.length === 0) return;

      const dates = history.map(h => h.date);
      const opens = history.map(h => h.open);
      const highs = history.map(h => h.high);
      const lows = history.map(h => h.low);
      const closes = history.map(h => h.close);
      const ks = history.map(h => h.k);
      const ds = history.map(h => h.d);

      // Candlestick Trace
      const candleTrace = {{
        x: dates,
        open: opens,
        high: highs,
        low: lows,
        close: closes,
        type: 'candlestick',
        name: 'K線',
        increasing: {{ line: {{ color: '#ef4444' }}, fillcolor: '#ef4444' }}, // Red for UP
        decreasing: {{ line: {{ color: '#22c55e' }}, fillcolor: '#22c55e' }}, // Green for DOWN
        xaxis: 'x',
        yaxis: 'y'
      }};

      // KD 9K Trace
      const kTrace = {{
        x: dates,
        y: ks,
        type: 'scatter',
        mode: 'lines',
        name: '9K (快線)',
        line: {{ color: '#f59e0b', width: 2 }},
        xaxis: 'x',
        yaxis: 'y2'
      }};

      // KD 9D Trace
      const dTrace = {{
        x: dates,
        y: ds,
        type: 'scatter',
        mode: 'lines',
        name: '9D (慢線)',
        line: {{ color: '#06b6d4', width: 2 }},
        xaxis: 'x',
        yaxis: 'y2'
      }};

      const layout = {{
        grid: {{ rows: 2, columns: 1, pattern: 'independent', roworder: 'top to bottom' }},
        plot_bgcolor: '#0b0f19',
        paper_bgcolor: '#0f172a',
        font: {{ color: '#94a3b8', size: 11 }},
        margin: {{ l: 50, r: 40, t: 30, b: 30 }},
        showlegend: true,
        legend: {{ orientation: 'h', x: 0.1, y: 1.1, font: {{ size: 11, color: '#e2e8f0' }} }},
        xaxis: {{
          autorange: true,
          rangeslider: {{ visible: false }},
          type: 'date',
          gridcolor: '#1e293b',
          linecolor: '#334155'
        }},
        yaxis: {{
          title: '價格 (TWD)',
          domain: [0.38, 1.0],
          gridcolor: '#1e293b',
          linecolor: '#334155',
          tickformat: '.2f'
        }},
        yaxis2: {{
          title: 'KD 指標',
          domain: [0.0, 0.30],
          gridcolor: '#1e293b',
          linecolor: '#334155',
          range: [0, 100],
          tickvals: [20, 50, 80],
          ticktext: ['20 (超賣)', '50', '80 (超買)']
        }},
        shapes: [
          // 80 Overbought line
          {{
            type: 'line',
            xref: 'paper',
            x0: 0,
            x1: 1,
            yref: 'y2',
            y0: 80,
            y1: 80,
            line: {{ color: 'rgba(239, 68, 68, 0.5)', width: 1, dash: 'dot' }}
          }},
          // 20 Oversold line
          {{
            type: 'line',
            xref: 'paper',
            x0: 0,
            x1: 1,
            yref: 'y2',
            y0: 20,
            y1: 20,
            line: {{ color: 'rgba(34, 197, 94, 0.5)', width: 1, dash: 'dot' }}
          }}
        ]
      }};

      const config = {{ responsive: true, displayModeBar: true, displaylogo: false }};
      Plotly.newPlot('chartContainer', [candleTrace, kTrace, dTrace], layout, config);
    }}

    function getBadgeClass(rec) {{
      if (rec.includes('買進')) return 'badge-buy';
      if (rec.includes('續抱')) return 'badge-hold';
      if (rec.includes('賣出')) return 'badge-sell';
      if (rec.includes('減碼')) return 'badge-warning';
      return 'badge-neutral';
    }}

    function setTab(tab) {{
      currentFilter = tab;
      document.querySelectorAll('.filter-tab').forEach(b => {{
        b.className = 'filter-tab px-2.5 py-1 rounded text-xs font-medium bg-slate-800 text-slate-400 hover:text-white';
      }});
      document.getElementById('tab-' + tab).className = 'filter-tab px-2.5 py-1 rounded text-xs font-medium bg-cyan-600 text-white';
      renderStockList();
    }}

    function filterStocks() {{
      renderStockList();
    }}

    function openModal() {{
      document.getElementById('strategyModal').classList.remove('hidden');
    }}

    function closeModal() {{
      document.getElementById('strategyModal').classList.add('hidden');
    }}

    window.onload = init;
  </script>
</body>
</html>
'''

with open('stock_review.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Generated stock_review.html and index.html successfully!")
