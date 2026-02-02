const formatNumber = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 });

document.addEventListener('DOMContentLoaded', function () {
  const indicatorBox = document.getElementById('performance-indicator-box');
  const frequencySelect = document.getElementById('performance-frequency-select');
  const chartTypeSelect = document.getElementById('performance-chart-type-select');
  const dateStartInput = document.getElementById('performance-date-start');
  const dateEndInput = document.getElementById('performance-date-end');
  const dateApplyButton = document.getElementById('performance-date-apply');
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

  let lastPayloads = [];
  let lastDailyTable = null;
  let lastMonthlyTable = null;
  let requestToken = 0;
  let tableRequestToken = 0;

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
    if (indicator && indicator.plant_code) {
      parts.push('[' + indicator.plant_code + ']');
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
    if (!window.XLSX) {
      console.error('XLSX no disponible para exportar.');
      return;
    }
    const worksheet = window.XLSX.utils.aoa_to_sheet([
      tableData.columns,
      ...tableData.rows,
    ]);
    const workbook = window.XLSX.utils.book_new();
    window.XLSX.utils.book_append_sheet(workbook, worksheet, 'Resultados');
    window.XLSX.writeFile(workbook, filename);
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

    const series = dataSets.map(function (set, idx) {
      const valueMap = new Map();
      (set.rows || []).forEach(function (row) {
        const value = row.value != null ? Number(row.value) : null;
        valueMap.set(row.period_end, value);
      });

      const values = labels.map(function (label) {
        return valueMap.has(label) ? valueMap.get(label) : null;
      });

      return {
        name: buildSeriesName(set.indicator || {}, idx),
        type: seriesType,
        smooth: smooth,
        stack: stack,
        showSymbol: false,
        lineStyle: {
          width: 3,
          shadowColor: 'rgba(0, 0, 0, 0.3)',
          shadowBlur: 10,
          shadowOffsetY: 5
        },
        itemStyle: {
          color: colors[idx % colors.length],
          borderRadius: seriesType === 'bar' ? [6, 6, 0, 0] : 0
        },
        areaStyle: seriesType === 'line' && !stack ? {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: colors[idx % colors.length] + '33' },
            { offset: 1, color: colors[idx % colors.length] + '00' }
          ])
        } : undefined,
        data: values,
      };
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

    const rotate = labels.length > 12 ? 30 : 0;
    const gridTop = series.length > 1 ? 48 : 24;

    chart.setOption({
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(99, 102, 241, 0.2)',
        borderWidth: 1,
        borderRadius: 12,
        padding: [10, 14],
        textStyle: { color: '#f8fafc', fontSize: 13, fontFamily: 'Plus Jakarta Sans' },
        axisPointer: {
          type: 'line',
          lineStyle: { color: 'rgba(99, 102, 241, 0.4)', width: 2 },
        },
      },
      legend: {
        show: series.length > 1,
        top: 0,
        textStyle: { color: '#475569', fontSize: 11, fontWeight: 600 },
      },
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: 0,
          start: 0,
          end: 100,
        },
        {
          type: 'slider',
          xAxisIndex: 0,
          height: 36,
          bottom: 0,
          brushSelect: false,
          handleStyle: {
            color: '#6366f1',
            borderColor: '#1e293b',
          },
          textStyle: {
            color: '#64748b',
          },
          fillerColor: 'rgba(99, 102, 241, 0.08)',
          borderColor: 'rgba(255, 255, 255, 0.03)',
        },
      ],
      grid: { left: 46, right: 24, top: gridTop, bottom: 76, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { lineStyle: { color: '#1f2937' } },
        axisTick: { show: false },
        axisLabel: { fontSize: 9, color: '#94a3b8', margin: 6, rotate: rotate },
      },
      yAxis: {
        type: 'value',
        name: unit ? '(' + unit + ')' : 'Valores',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          margin: 6,
          fontSize: 9,
          color: '#94a3b8',
          formatter: function (value) {
            return formatNumber.format(value);
          },
        },
        splitLine: { show: true, lineStyle: { color: 'rgba(148, 163, 184, 0.12)' } },
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

  function loadPerformanceData() {
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

    loadPerformanceChart(selectedInputs);
    loadPerformanceTables(selectedInputs);
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

  setDefaultRange();
  if (getSelectedIndicatorInputs().length) {
    loadPerformanceData();
  }
});
