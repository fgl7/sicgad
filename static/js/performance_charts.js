const formatNumber = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 });
const compactNumber = new Intl.NumberFormat('es-CL', {
  notation: 'compact',
  maximumFractionDigits: 1,
});
const shortMonthNamesEs = [
  'ene',
  'feb',
  'mar',
  'abr',
  'may',
  'jun',
  'jul',
  'ago',
  'sep',
  'oct',
  'nov',
  'dic',
];
let xlsxLoaderPromise = null;

function ensureXlsxLoaded() {
  if (window.XLSX) {
    return Promise.resolve(window.XLSX);
  }
  if (xlsxLoaderPromise) {
    return xlsxLoaderPromise;
  }
  xlsxLoaderPromise = new Promise(function (resolve, reject) {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js';
    script.async = true;
    script.onload = function () {
      resolve(window.XLSX);
    };
    script.onerror = function () {
      reject(new Error('No se pudo cargar XLSX'));
    };
    document.head.appendChild(script);
  });
  return xlsxLoaderPromise;
}

document.addEventListener('DOMContentLoaded', function () {
  const indicatorBox = document.getElementById('performance-indicator-box');
  const frequencySelect = document.getElementById('performance-frequency-select');
  const chartTypeSelect = document.getElementById('performance-chart-type-select');
  const executiveModeToggle = document.getElementById('performance-executive-mode-toggle');
  const dateStartInput = document.getElementById('performance-date-start');
  const dateEndInput = document.getElementById('performance-date-end');
  const dateApplyButton = document.getElementById('performance-date-apply');
  const chartStage = document.getElementById('performance-chart-stage');
  const presentationButton = document.getElementById('performance-chart-presentation-btn');
  const chartContainer = document.getElementById('performance-chart');
  const emptyNote = document.getElementById('performance-chart-empty');
  const dailyTableContainer = document.getElementById('performance-table-daily');
  const monthlyTableContainer = document.getElementById('performance-table-monthly');
  const exportCsvDaily = document.getElementById('performance-export-csv-daily');
  const exportExcelDaily = document.getElementById('performance-export-excel-daily');
  const exportCsvMonthly = document.getElementById('performance-export-csv-monthly');
  const exportExcelMonthly = document.getElementById('performance-export-excel-monthly');

  if (
    !indicatorBox ||
    !frequencySelect ||
    !chartTypeSelect ||
    !dateStartInput ||
    !dateEndInput ||
    !dateApplyButton ||
    !chartContainer
  ) {
    return;
  }

  let chart = null;
  if (window.echarts) {
    chart = echarts.init(chartContainer);
  }
  const baseChartHeight = chartContainer.style.height || Math.max(chartContainer.clientHeight, 300) + 'px';
  let presentationHintTimer = null;
  let wasPresentationFullscreen = false;

  let lastPayloads = [];
  let lastDailyTable = null;
  let lastMonthlyTable = null;
  let requestToken = 0;
  let tableRequestToken = 0;
  let deferredTablesTimer = null;
  const PERFORMANCE_EXECUTIVE_MODE_STORAGE_KEY = 'sicgad_performance_executive_mode';

  function getStoredExecutiveMode() {
    try {
      return window.localStorage.getItem(PERFORMANCE_EXECUTIVE_MODE_STORAGE_KEY) === '1';
    } catch (_err) {
      return false;
    }
  }

  function setStoredExecutiveMode(enabled) {
    try {
      window.localStorage.setItem(PERFORMANCE_EXECUTIVE_MODE_STORAGE_KEY, enabled ? '1' : '0');
    } catch (_err) {
      // ignore storage restrictions
    }
  }

  function isExecutiveMode() {
    return Boolean(executiveModeToggle && executiveModeToggle.checked);
  }

  function getFullscreenElement() {
    return document.fullscreenElement || document.webkitFullscreenElement || null;
  }

  function isChartStageFullscreen() {
    const fsElement = getFullscreenElement();
    return Boolean(chartStage && fsElement && (fsElement === chartStage || chartStage.contains(fsElement)));
  }

  function requestFullscreenForElement(element) {
    if (!element) {
      return Promise.resolve(false);
    }
    if (typeof element.requestFullscreen === 'function') {
      return element.requestFullscreen().then(function () {
        return true;
      });
    }
    if (typeof element.webkitRequestFullscreen === 'function') {
      element.webkitRequestFullscreen();
      return Promise.resolve(true);
    }
    return Promise.resolve(false);
  }

  function exitFullscreenIfNeeded() {
    if (typeof document.exitFullscreen === 'function') {
      return document.exitFullscreen();
    }
    if (typeof document.webkitExitFullscreen === 'function') {
      document.webkitExitFullscreen();
      return Promise.resolve();
    }
    return Promise.resolve();
  }

  function resizeChartSoon() {
    if (!chart) {
      return;
    }
    window.requestAnimationFrame(function () {
      if (chart) {
        chart.resize();
      }
    });
  }

  function ensurePresentationHintElement() {
    if (!chartStage) {
      return null;
    }
    let hint = chartStage.querySelector('[data-presentation-hint="performance"]');
    if (hint) {
      return hint;
    }
    hint = document.createElement('div');
    hint.setAttribute('data-presentation-hint', 'performance');
    hint.className =
      'pointer-events-none absolute left-1/2 top-14 z-20 -translate-x-1/2 rounded-full border border-amber-300/20 bg-slate-950/85 px-3 py-1.5 text-[11px] font-medium text-amber-100 shadow-lg shadow-black/30 opacity-0 transition-opacity duration-200';
    hint.textContent = 'Presiona Esc para salir de presentacion';
    chartStage.appendChild(hint);
    return hint;
  }

  function hidePresentationHint() {
    const hint = ensurePresentationHintElement();
    if (!hint) {
      return;
    }
    hint.classList.add('opacity-0');
    hint.classList.remove('opacity-100');
  }

  function flashPresentationHint() {
    const hint = ensurePresentationHintElement();
    if (!hint) {
      return;
    }
    if (presentationHintTimer) {
      window.clearTimeout(presentationHintTimer);
      presentationHintTimer = null;
    }
    hint.classList.remove('opacity-0');
    hint.classList.add('opacity-100');
    presentationHintTimer = window.setTimeout(function () {
      hidePresentationHint();
    }, 2200);
  }

  function syncChartPresentationUi() {
    const inPresentation = isChartStageFullscreen();
    const enteredPresentation = inPresentation && !wasPresentationFullscreen;
    wasPresentationFullscreen = inPresentation;
    if (chartStage) {
      chartStage.classList.toggle('ring-2', inPresentation);
      chartStage.classList.toggle('ring-amber-300/20', inPresentation);
      chartStage.classList.toggle('bg-slate-950/95', inPresentation);
      chartStage.classList.toggle('border-amber-300/20', inPresentation);
    }
    chartContainer.style.height = inPresentation
      ? Math.max(360, window.innerHeight - 120) + 'px'
      : baseChartHeight;
    if (presentationButton) {
      presentationButton.textContent = inPresentation ? 'Salir presentación' : 'Presentación';
      presentationButton.title = inPresentation
        ? 'Salir de presentación (Esc)'
        : 'Abrir en presentación';
    }
    if (enteredPresentation) {
      flashPresentationHint();
    } else if (!inPresentation) {
      hidePresentationHint();
    }
    resizeChartSoon();
  }

  function activateExecutiveMode() {
    if (!executiveModeToggle || executiveModeToggle.checked) {
      return;
    }
    executiveModeToggle.checked = true;
    setStoredExecutiveMode(true);
    renderChart(lastPayloads);
  }

  function togglePresentationMode() {
    activateExecutiveMode();
    if (!chartStage) {
      return;
    }
    if (isChartStageFullscreen()) {
      exitFullscreenIfNeeded().catch(function (err) {
        console.error(err);
      });
      return;
    }
    requestFullscreenForElement(chartStage)
      .then(function (entered) {
        if (!entered) {
          syncChartPresentationUi();
        }
      })
      .catch(function (err) {
        console.error(err);
      });
  }

  function scheduleIdleWork(callback, timeout) {
    if (typeof window.requestIdleCallback === 'function') {
      return window.requestIdleCallback(callback, { timeout: timeout || 1200 });
    }
    return window.setTimeout(callback, Math.min(timeout || 1200, 500));
  }

  function formatDateInput(date) {
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
  }

  function setDefaultRange() {
    const today = new Date();
    if (!dateEndInput.value) {
      dateEndInput.value = formatDateInput(today);
    }
    if (!dateStartInput.value) {
      const start = new Date(today.getTime());
      if ((frequencySelect.value || 'MONTHLY') === 'DAILY') {
        start.setDate(start.getDate() - 29);
      } else {
        start.setMonth(start.getMonth() - 11);
      }
      dateStartInput.value = formatDateInput(start);
    }
  }

  function getDateParams() {
    setDefaultRange();
    const start = dateStartInput.value;
    const end = dateEndInput.value;
    if (start && end && start > end) {
      dateEndInput.value = start;
      return { start, end: start };
    }
    return { start, end };
  }

  function parseDateInput(value) {
    if (!value) {
      return null;
    }
    const parsed = new Date(value + 'T00:00:00');
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function parseDateValue(raw) {
    if (!raw && raw !== 0) {
      return null;
    }
    if (raw instanceof Date) {
      return new Date(raw.getTime());
    }
    const text = String(raw).trim();
    if (!text) {
      return null;
    }
    let match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) {
      match = text.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$/);
    }
    if (match) {
      return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    }
    const parsed = new Date(text);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function inferDateGranularity(values, frequency) {
    if (frequency === 'DAILY') {
      return 'daily';
    }
    if (frequency === 'MONTHLY') {
      return 'monthly';
    }
    const stamps = (values || [])
      .map(function (value) {
        const date = parseDateValue(value);
        return date ? date.getTime() : null;
      })
      .filter(function (value) {
        return value != null;
      })
      .sort(function (a, b) {
        return a - b;
      });

    if (stamps.length < 2) {
      return 'date';
    }

    const deltas = [];
    for (let i = 1; i < stamps.length; i += 1) {
      const diff = stamps[i] - stamps[i - 1];
      if (diff > 0) {
        deltas.push(diff);
      }
    }
    if (!deltas.length) {
      return 'date';
    }
    deltas.sort(function (a, b) {
      return a - b;
    });
    const median = deltas[Math.floor(deltas.length / 2)];
    const dayMs = 24 * 60 * 60 * 1000;
    if (median <= dayMs * 3) {
      return 'daily';
    }
    if (median <= dayMs * 45) {
      return 'monthly';
    }
    if (median <= dayMs * 120) {
      return 'quarterly';
    }
    return 'yearly';
  }

  function formatPeriodShort(raw, granularity) {
    const date = parseDateValue(raw);
    if (!date) {
      return raw != null ? String(raw) : '';
    }
    const dd = String(date.getDate()).padStart(2, '0');
    const mon = shortMonthNamesEs[date.getMonth()];
    const yy = String(date.getFullYear()).slice(-2);
    const yyyy = date.getFullYear();
    if (granularity === 'yearly') {
      return String(yyyy);
    }
    if (granularity === 'monthly' || granularity === 'quarterly') {
      return mon + ' ' + yy;
    }
    if (granularity === 'daily') {
      return dd + ' ' + mon;
    }
    return dd + ' ' + mon + ' ' + yy;
  }

  function formatPeriodLong(raw) {
    const date = parseDateValue(raw);
    if (!date) {
      return raw != null ? String(raw) : '';
    }
    const dd = String(date.getDate()).padStart(2, '0');
    const mon = shortMonthNamesEs[date.getMonth()];
    const yyyy = date.getFullYear();
    return dd + ' ' + mon + ' ' + yyyy;
  }

  function truncateLabel(value, maxLength) {
    const text = value == null ? '' : String(value);
    if (text.length <= maxLength) {
      return text;
    }
    return text.slice(0, Math.max(0, maxLength - 1)) + '…';
  }

  function formatMetricValue(raw) {
    if (raw == null || !Number.isFinite(raw)) {
      return '--';
    }
    const abs = Math.abs(raw);
    if (abs >= 100000) {
      return compactNumber.format(raw);
    }
    return formatNumber.format(raw);
  }

  function getRangeForFrequency(freq) {
    setDefaultRange();
    const endValue = dateEndInput.value;
    const endDate = parseDateInput(endValue) || new Date();
    const startDate = new Date(endDate.getTime());
    if (freq === 'DAILY') {
      startDate.setDate(startDate.getDate() - 29);
    } else {
      startDate.setMonth(startDate.getMonth() - 11);
    }
    return {
      start: formatDateInput(startDate),
      end: formatDateInput(endDate),
    };
  }

  function getSelectedIndicatorInputs() {
    return Array.from(
      indicatorBox.querySelectorAll('input[type="checkbox"]:checked')
    );
  }

  function buildSeriesName(indicator, fallbackIndex) {
    const parts = [];
    if (indicator && indicator.entity_code) {
      parts.push('[' + indicator.entity_code + ']');
    }
    if (indicator && indicator.label) {
      parts.push(indicator.label);
    }
    if (!parts.length) {
      return 'Indicador ' + (fallbackIndex + 1);
    }
    return parts.join(' ');
  }

  function buildSeriesNames(payloads) {
    const names = [];
    const counts = {};
    payloads.forEach(function (set, idx) {
      const base = buildSeriesName(set.indicator || {}, idx);
      const count = counts[base] || 0;
      counts[base] = count + 1;
      const name = count ? base + ' (' + (count + 1) + ')' : base;
      names.push(name);
    });
    return names;
  }

  function formatCellValue(value) {
    if (value == null || value === '') {
      return '-';
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value.toFixed(2);
    }
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (!trimmed) {
        return '-';
      }
      if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
        const numeric = Number(trimmed);
        return Number.isFinite(numeric) ? numeric.toFixed(2) : trimmed;
      }
    }
    return value;
  }

  function renderPerformanceTable(container, tableData) {
    if (!container) {
      return;
    }
    container.innerHTML = '';

    if (!tableData || !tableData.columns || !tableData.columns.length) {
      const empty = document.createElement('div');
      empty.className = 'p-3 text-[11px] text-slate-400';
      empty.textContent = 'No hay datos para mostrar.';
      container.appendChild(empty);
      return;
    }

    if (!tableData.rows || !tableData.rows.length) {
      const empty = document.createElement('div');
      empty.className = 'p-3 text-[11px] text-slate-400';
      empty.textContent = 'No hay datos para mostrar.';
      container.appendChild(empty);
      return;
    }

    const table = document.createElement('table');
    table.className = 'min-w-full text-[11px]';

    const thead = document.createElement('thead');
    thead.className = 'bg-white/[0.02] text-[10px] font-black text-slate-500 uppercase tracking-widest';
    const headRow = document.createElement('tr');
    tableData.columns.forEach(function (col) {
      const th = document.createElement('th');
      th.className = 'px-3 py-1 text-left font-semibold';
      th.textContent = col;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);

    const tbody = document.createElement('tbody');
    tableData.rows.forEach(function (row) {
      const tr = document.createElement('tr');
      tr.className = 'border-t border-slate-800';
      row.forEach(function (cell) {
        const td = document.createElement('td');
        td.className = 'px-3 py-1 align-top whitespace-nowrap';
        td.textContent = formatCellValue(cell);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);
    container.appendChild(table);
  }

  function updateExportState(buttonCsv, buttonExcel, hasRows) {
    if (buttonCsv) {
      buttonCsv.disabled = !hasRows;
    }
    if (buttonExcel) {
      buttonExcel.disabled = !hasRows;
    }
  }

  function escapeCsv(value) {
    if (value == null) {
      return '';
    }
    const text = String(value);
    if (/[",\n]/.test(text)) {
      return '"' + text.replace(/"/g, '""') + '"';
    }
    return text;
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function exportTableCsv(tableData, filename) {
    if (!tableData || !tableData.rows || !tableData.rows.length) {
      return;
    }
    const header = tableData.columns.map((col) => escapeCsv(col)).join(',');
    const lines = tableData.rows.map((row) => row.map(escapeCsv).join(','));
    const csv = [header, ...lines].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    downloadBlob(blob, filename);
  }

  function exportTableExcel(tableData, filename) {
    if (!tableData || !tableData.rows || !tableData.rows.length) {
      return;
    }
    ensureXlsxLoaded()
      .then(function () {
        if (!window.XLSX) {
          throw new Error('XLSX no disponible para exportar.');
        }
        const worksheet = window.XLSX.utils.aoa_to_sheet([
          tableData.columns,
          ...tableData.rows,
        ]);
        const workbook = window.XLSX.utils.book_new();
        window.XLSX.utils.book_append_sheet(workbook, worksheet, 'Resultados');
        window.XLSX.writeFile(workbook, filename);
      })
      .catch(function (err) {
        console.error(err);
      });
  }

  function renderChart(payloads) {
    if (!chart) {
      return;
    }

    const dataSets = Array.isArray(payloads) ? payloads : [];
    const hasRows = dataSets.some((set) => (set.rows || []).length);

    if (!dataSets.length || !hasRows) {
      chart.clear();
      if (emptyNote) {
        emptyNote.classList.remove('hidden');
      }
      return;
    }

    if (emptyNote) {
      emptyNote.classList.add('hidden');
    }

    const periodSet = new Set();
    dataSets.forEach((set) => {
      (set.rows || []).forEach((row) => {
        if (row.period_end) {
          periodSet.add(row.period_end);
        }
      });
    });

    let labels = Array.from(periodSet);
    labels.sort(function (a, b) {
      return new Date(a) - new Date(b);
    });

    if (!labels.length) {
      chart.clear();
      if (emptyNote) {
        emptyNote.classList.remove('hidden');
      }
      return;
    }

    const chartType = chartTypeSelect.value || 'line';
    let seriesType = 'line';
    let smooth = true;
    let stack = undefined;

    if (chartType === 'bar' || chartType === 'stacked_bar') {
      seriesType = 'bar';
      smooth = false;
    }

    if (chartType === 'stacked_bar') {
      stack = 'total';
    }

    const colors = ['#6366f1', '#10b981', '#8b5cf6', '#f43f5e', '#f59e0b', '#06b6d4'];
    const executiveMode = isExecutiveMode();
    const granularity = inferDateGranularity(labels, frequencySelect.value || 'MONTHLY');
    const showArea = seriesType === 'line' && !stack && dataSets.length === 1 && !executiveMode;
    const showSymbols = !executiveMode && labels.length <= 36;
    const barMaxWidth =
      labels.length > 180 ? 6 : labels.length > 120 ? 8 : labels.length > 70 ? 10 : 14;
    const xLabelTargetCount = executiveMode ? 8 : 14;
    const xLabelInterval =
      labels.length > xLabelTargetCount
        ? Math.max(0, Math.ceil(labels.length / xLabelTargetCount) - 1)
        : 0;
    const unitsBySeriesName = {};

    const series = dataSets.map(function (set, idx) {
      const valueMap = new Map();
      (set.rows || []).forEach(function (row) {
        const value = row.value != null ? Number(row.value) : null;
        valueMap.set(row.period_end, value);
      });

      const values = labels.map(function (label) {
        return valueMap.has(label) ? valueMap.get(label) : null;
      });

      const color = colors[idx % colors.length];
      const seriesName = buildSeriesName(set.indicator || {}, idx);
      unitsBySeriesName[seriesName] =
        set && set.indicator && set.indicator.unit ? set.indicator.unit : '';

      const baseSeries = {
        name: seriesName,
        type: seriesType,
        stack: stack,
        showSymbol: seriesType === 'line' ? showSymbols : false,
        symbol: 'circle',
        symbolSize: labels.length > 90 ? 4 : 6,
        connectNulls: false,
        animationDuration: 420,
        animationEasing: 'cubicOut',
        emphasis: {
          focus: 'series',
        },
        itemStyle: {
          color:
            seriesType === 'bar'
              ? new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: color + 'ff' },
                  { offset: 1, color: color + '9f' },
                ])
              : color,
          borderRadius: seriesType === 'bar' ? [7, 7, 0, 0] : 0,
        },
        data: values,
      };

      if (seriesType === 'line') {
        baseSeries.smooth = smooth;
        baseSeries.sampling = 'lttb';
        baseSeries.lineStyle = {
          width: 3,
          color: color,
          shadowColor: 'rgba(0, 0, 0, 0.28)',
          shadowBlur: executiveMode ? 6 : 10,
          shadowOffsetY: executiveMode ? 2 : 4,
          cap: 'round',
          join: 'round',
        };
        if (showArea) {
          baseSeries.areaStyle = {
            opacity: 0.18,
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: color + '70' },
              { offset: 0.6, color: color + '1f' },
              { offset: 1, color: color + '00' },
            ]),
          };
        }
      } else {
        baseSeries.barMaxWidth = barMaxWidth;
        baseSeries.barMinHeight = 1;
        baseSeries.barCategoryGap = stack ? '22%' : '30%';
        baseSeries.emphasis = {
          focus: 'series',
          itemStyle: {
            shadowColor: color + '55',
            shadowBlur: 12,
          },
        };
      }

      return baseSeries;
    });

    const units = dataSets
      .map(function (set) {
        return set && set.indicator ? set.indicator.unit : null;
      })
      .filter(function (unit) {
        return unit;
      });

    const unit =
      units.length &&
        units.every(function (value) {
          return value === units[0];
        })
        ? units[0]
        : null;

    const rotate = executiveMode ? 0 : labels.length > 32 ? 28 : 0;
    const gridTop = series.length > 1 ? (executiveMode ? 42 : 48) : executiveMode ? 20 : 24;
    const tooltipPointerType = seriesType === 'bar' ? 'shadow' : 'line';

    chart.setOption({
      animationDurationUpdate: 220,
      animationEasingUpdate: 'cubicOut',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(99, 102, 241, 0.2)',
        borderWidth: 1,
        borderRadius: executiveMode ? 12 : 14,
        padding: executiveMode ? [8, 10] : [10, 12],
        extraCssText:
          'box-shadow: 0 10px 30px rgba(2,6,23,.35); backdrop-filter: blur(8px);',
        textStyle: { color: '#f8fafc', fontSize: 13, fontFamily: 'Plus Jakarta Sans' },
        formatter: function (params) {
          const items = Array.isArray(params) ? params : [params];
          if (!items.length) {
            return '';
          }
          const axisRaw = items[0].axisValue;
          const title = formatPeriodLong(axisRaw);
          const rowsHtml = items
            .map(function (item, itemIdx) {
              const seriesName = item.seriesName || '';
              const unitLabel = unitsBySeriesName[seriesName] ? ' ' + unitsBySeriesName[seriesName] : '';
              const color =
                typeof item.color === 'string'
                  ? item.color
                  : item.color &&
                    Array.isArray(item.color.colorStops) &&
                    item.color.colorStops[0]
                    ? item.color.colorStops[0].color
                    : colors[itemIdx % colors.length];
              const value = Array.isArray(item.value) ? item.value[item.value.length - 1] : item.value;
              const numericValue =
                value == null || value === '' ? null : Number.isFinite(Number(value)) ? Number(value) : null;
              return (
                '<div style="display:flex;align-items:center;justify-content:space-between;gap:14px;min-width:220px;margin-top:6px;">' +
                '<div style="display:flex;align-items:center;gap:8px;color:#dbeafe;">' +
                '<span style="width:8px;height:8px;border-radius:999px;background:' +
                color +
                ';box-shadow:0 0 0 3px ' +
                color +
                '22;"></span>' +
                '<span style="opacity:.95;">' +
                seriesName +
                '</span>' +
                '</div>' +
                '<div style="font-weight:700;color:#ffffff;">' +
                formatMetricValue(numericValue) +
                unitLabel +
                '</div>' +
                '</div>'
              );
            })
            .join('');

          return (
            '<div style="font-family:Plus Jakarta Sans, Lexend, sans-serif;">' +
            '<div style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:#93c5fd;opacity:.9;margin-bottom:2px;">Periodo</div>' +
            '<div style="font-size:13px;font-weight:700;color:#f8fafc;">' +
            title +
            '</div>' +
            rowsHtml +
            '</div>'
          );
        },
        axisPointer: {
          type: tooltipPointerType,
          lineStyle: { color: 'rgba(99, 102, 241, 0.4)', width: executiveMode ? 1.5 : 2 },
          shadowStyle: {
            color: 'rgba(99, 102, 241, 0.06)',
          },
          label: { show: false },
        },
      },
      legend: {
        show: series.length > 1,
        top: executiveMode ? 4 : 0,
        left: 'center',
        icon: 'roundRect',
        itemWidth: executiveMode ? 12 : 14,
        itemHeight: executiveMode ? 6 : 8,
        itemGap: executiveMode ? 10 : 14,
        textStyle: { color: '#475569', fontSize: executiveMode ? 10 : 11, fontWeight: 600 },
      },
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: 0,
          start: 0,
          end: 100,
          zoomLock: false,
          throttle: 50,
        },
        {
          type: 'slider',
          xAxisIndex: 0,
          height: executiveMode ? 28 : 36,
          bottom: executiveMode ? 2 : 0,
          showDetail: false,
          brushSelect: false,
          borderRadius: 10,
          backgroundColor: 'rgba(15, 23, 42, 0.42)',
          handleStyle: {
            color: '#6366f1',
            borderColor: '#1e293b',
            shadowBlur: 8,
            shadowColor: 'rgba(0,0,0,.25)',
          },
          textStyle: {
            color: '#64748b',
          },
          fillerColor: 'rgba(99, 102, 241, 0.08)',
          dataBackground: {
            lineStyle: {
              color: 'rgba(148, 163, 184, 0.3)',
              width: 1,
            },
            areaStyle: {
              color: 'rgba(99, 102, 241, 0.06)',
            },
          },
          selectedDataBackground: {
            lineStyle: {
              color: 'rgba(165, 180, 252, 0.55)',
              width: 1.2,
            },
            areaStyle: {
              color: 'rgba(99, 102, 241, 0.1)',
            },
          },
          labelFormatter: function (value) {
            return formatPeriodShort(value, granularity);
          },
          borderColor: 'rgba(255, 255, 255, 0.03)',
          showDataShadow: !executiveMode,
        },
      ],
      grid: {
        left: executiveMode ? 44 : 54,
        right: executiveMode ? 12 : 18,
        top: gridTop,
        bottom: executiveMode ? 52 : 78,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: seriesType === 'bar',
        name: executiveMode ? '' : 'Periodo',
        nameTextStyle: {
          color: '#94a3b8',
          fontSize: executiveMode ? 9 : 10,
          fontWeight: 600,
          padding: [12, 0, 0, 0],
        },
        axisLine: {
          lineStyle: { color: 'rgba(148, 163, 184, 0.18)', width: 1 },
        },
        axisTick: { show: false },
        axisLabel: {
          fontSize: executiveMode ? 9 : 10,
          lineHeight: executiveMode ? 10 : 12,
          color: '#94a3b8',
          margin: executiveMode ? 6 : 10,
          rotate: rotate,
          hideOverlap: true,
          interval: xLabelInterval,
          formatter: function (value) {
            const short = formatPeriodShort(value, granularity);
            return truncateLabel(short, executiveMode ? 12 : 18);
          },
        },
      },
      yAxis: {
        type: 'value',
        name: unit ? '(' + unit + ')' : 'Valores',
        nameTextStyle: {
          color: '#94a3b8',
          fontSize: executiveMode ? 9 : 10,
          fontWeight: 600,
          padding: [0, 0, executiveMode ? 2 : 6, 0],
        },
        splitNumber: executiveMode ? 4 : 5,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          margin: executiveMode ? 6 : 10,
          fontSize: executiveMode ? 9 : 10,
          color: '#94a3b8',
          formatter: function (value) {
            return formatMetricValue(value);
          },
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: executiveMode ? 'rgba(148, 163, 184, 0.06)' : 'rgba(148, 163, 184, 0.1)',
            width: 1,
            type: executiveMode ? [3, 6] : [4, 4],
          },
        },
      },
      series: series,
    });
  }

  function buildTableData(payloads) {
    const dataSets = Array.isArray(payloads) ? payloads : [];
    if (!dataSets.length) {
      return { columns: [], rows: [] };
    }

    const periodSet = new Set();
    dataSets.forEach((set) => {
      (set.rows || []).forEach((row) => {
        if (row.period_end) {
          periodSet.add(row.period_end);
        }
      });
    });

    const labels = Array.from(periodSet).sort(function (a, b) {
      return new Date(a) - new Date(b);
    });

    if (!labels.length) {
      return { columns: [], rows: [] };
    }

    const seriesNames = buildSeriesNames(dataSets);
    const valueMaps = dataSets.map(function (set) {
      const map = new Map();
      (set.rows || []).forEach(function (row) {
        map.set(row.period_end, row.value != null ? Number(row.value) : null);
      });
      return map;
    });

    const rows = labels.map(function (label) {
      const row = [label];
      valueMaps.forEach(function (map) {
        row.push(map.has(label) ? map.get(label) : null);
      });
      return row;
    });

    return {
      columns: ['Periodo', ...seriesNames],
      rows: rows,
    };
  }

  function fetchIndicatorPayloads(selectedInputs, frequency, range) {
    const params = new URLSearchParams({ frequency: frequency });
    if (range && range.start) {
      params.append('date_start', range.start);
    }
    if (range && range.end) {
      params.append('date_end', range.end);
    }

    const requests = selectedInputs.map(function (input) {
      const url =
        '/kpis/performance-data/' +
        encodeURIComponent(input.value) +
        '/?' +
        params.toString();
      return fetch(url)
        .then(function (resp) {
          if (!resp.ok) {
            throw new Error('Error al cargar datos de desempeno');
          }
          return resp.json();
        })
        .catch(function (err) {
          console.error(err);
          return null;
        });
    });

    return Promise.all(requests).then(function (payloads) {
      return payloads.filter(function (item) {
        return item;
      });
    });
  }

  function clearPerformanceTables() {
    lastDailyTable = null;
    lastMonthlyTable = null;
    renderPerformanceTable(dailyTableContainer, { columns: [], rows: [] });
    renderPerformanceTable(monthlyTableContainer, { columns: [], rows: [] });
    updateExportState(exportCsvDaily, exportExcelDaily, false);
    updateExportState(exportCsvMonthly, exportExcelMonthly, false);
  }

  function loadPerformanceChart(selectedInputs) {
    const freq = frequencySelect.value || 'MONTHLY';
    const dates = getDateParams();
    const currentToken = ++requestToken;

    fetchIndicatorPayloads(selectedInputs, freq, dates).then(function (payloads) {
      if (currentToken !== requestToken) {
        return;
      }
      lastPayloads = payloads;
      renderChart(lastPayloads);
    });
  }

  function loadPerformanceTables(selectedInputs) {
    const dailyRange = getRangeForFrequency('DAILY');
    const monthlyRange = getRangeForFrequency('MONTHLY');
    const currentToken = ++tableRequestToken;

    Promise.all([
      fetchIndicatorPayloads(selectedInputs, 'DAILY', dailyRange),
      fetchIndicatorPayloads(selectedInputs, 'MONTHLY', monthlyRange),
    ]).then(function (results) {
      if (currentToken !== tableRequestToken) {
        return;
      }
      const dailyPayloads = results[0] || [];
      const monthlyPayloads = results[1] || [];

      lastDailyTable = buildTableData(dailyPayloads);
      lastMonthlyTable = buildTableData(monthlyPayloads);

      renderPerformanceTable(dailyTableContainer, lastDailyTable);
      renderPerformanceTable(monthlyTableContainer, lastMonthlyTable);

      updateExportState(
        exportCsvDaily,
        exportExcelDaily,
        lastDailyTable && lastDailyTable.rows && lastDailyTable.rows.length
      );
      updateExportState(
        exportCsvMonthly,
        exportExcelMonthly,
        lastMonthlyTable && lastMonthlyTable.rows && lastMonthlyTable.rows.length
      );
    });
  }

  function loadPerformanceData(options) {
    const deferTables = Boolean(options && options.deferTables);
    const selectedInputs = getSelectedIndicatorInputs();
    if (!selectedInputs.length) {
      lastPayloads = [];
      if (chart) {
        chart.clear();
      }
      if (emptyNote) {
        emptyNote.classList.add('hidden');
      }
      clearPerformanceTables();
      return;
    }

    if (deferredTablesTimer) {
      if (typeof window.cancelIdleCallback === 'function') {
        window.cancelIdleCallback(deferredTablesTimer);
      } else {
        window.clearTimeout(deferredTablesTimer);
      }
      deferredTablesTimer = null;
    }

    loadPerformanceChart(selectedInputs);
    if (deferTables) {
      deferredTablesTimer = scheduleIdleWork(function () {
        deferredTablesTimer = null;
        loadPerformanceTables(selectedInputs);
      }, 1500);
    } else {
      loadPerformanceTables(selectedInputs);
    }
  }

  const indicatorInputs = Array.from(
    indicatorBox.querySelectorAll('input[type="checkbox"]')
  );

  indicatorInputs.forEach(function (input) {
    input.addEventListener('change', function () {
      const selected = getSelectedIndicatorInputs();
      if (!selected.length) {
        input.checked = true;
        return;
      }
      loadPerformanceData();
    });
  });

  frequencySelect.addEventListener('change', function () {
    dateStartInput.value = '';
    dateEndInput.value = '';
    loadPerformanceData();
  });

  chartTypeSelect.addEventListener('change', function () {
    renderChart(lastPayloads);
  });

  if (executiveModeToggle) {
    executiveModeToggle.checked = getStoredExecutiveMode();
    executiveModeToggle.addEventListener('change', function () {
      setStoredExecutiveMode(executiveModeToggle.checked);
      renderChart(lastPayloads);
    });
  }

  dateApplyButton.addEventListener('click', loadPerformanceData);

  if (exportCsvDaily) {
    exportCsvDaily.addEventListener('click', function () {
      exportTableCsv(lastDailyTable, 'desempeno_diario.csv');
    });
  }
  if (exportExcelDaily) {
    exportExcelDaily.addEventListener('click', function () {
      exportTableExcel(lastDailyTable, 'desempeno_diario.xlsx');
    });
  }
  if (exportCsvMonthly) {
    exportCsvMonthly.addEventListener('click', function () {
      exportTableCsv(lastMonthlyTable, 'desempeno_mensual.csv');
    });
  }
  if (exportExcelMonthly) {
    exportExcelMonthly.addEventListener('click', function () {
      exportTableExcel(lastMonthlyTable, 'desempeno_mensual.xlsx');
    });
  }
  if (presentationButton) {
    presentationButton.addEventListener('click', togglePresentationMode);
  }
  document.addEventListener('fullscreenchange', syncChartPresentationUi);
  document.addEventListener('webkitfullscreenchange', syncChartPresentationUi);
  window.addEventListener('resize', resizeChartSoon);

  setDefaultRange();
  if (getSelectedIndicatorInputs().length) {
    loadPerformanceData({ deferTables: true });
  }
  syncChartPresentationUi();
});
