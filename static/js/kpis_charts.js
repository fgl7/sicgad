document.addEventListener("DOMContentLoaded", function () {
  const modeSelect = document.getElementById("kpi-mode-select");
  const instanceSelect = document.getElementById("kpi-instance-select");
  const xFieldSelect = document.getElementById("kpi-x-field-select");
  const yFieldBox = document.getElementById("kpi-y-field-box");
  const chartTypeSelect = document.getElementById("kpi-chart-type-select");
  const executiveModeToggle = document.getElementById("kpi-executive-mode-toggle");
  const dateStartInput = document.getElementById("kpi-date-start");
  const dateEndInput = document.getElementById("kpi-date-end");
  const dateApplyButton = document.getElementById("kpi-date-apply");
  const chartContainer = document.getElementById("kpi-chart");
  const chartStage = document.getElementById("kpi-chart-stage");
  const presentationButton = document.getElementById("kpi-chart-presentation-btn");
  const authorityCards = document.getElementById("authority-kpi-cards");
  const tableContainer = document.getElementById("kpi-table-container");
  const exportCsvButton = document.getElementById("kpi-export-csv");
  const exportExcelButton = document.getElementById("kpi-export-excel");
  const isAuthorityView = Boolean(authorityCards);

  if (
    !modeSelect ||
    !instanceSelect ||
    !xFieldSelect ||
    !yFieldBox ||
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
  const baseChartHeight = chartContainer.style.height || `${Math.max(chartContainer.clientHeight, 320)}px`;
  let presentationHintTimer = null;
  let wasPresentationFullscreen = false;

  const numberFormatter = new Intl.NumberFormat("es-CL", {
    maximumFractionDigits: 2,
  });
  const compactFormatter = new Intl.NumberFormat("es-CL", {
    notation: "compact",
    maximumFractionDigits: 1,
  });
  const shortMonthNamesEs = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
  ];
  const authorityPalette = ["#f5b14f", "#33b6ff", "#23d3a6", "#8b7dff"];

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
      const year = Number(match[1]);
      const month = Number(match[2]) - 1;
      const day = Number(match[3]);
      return new Date(year, month, day);
    }

    const parsed = new Date(text);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  let currentData = null;
  let currentColumns = [];
  let availableDateColumn = null;
  let tableExpanded = false;
  const filterBounds = { start: null, end: null };
  const url = new URL(window.location.href);
  const TABLE_RENDER_LIMIT = 300;
  let xlsxLoaderPromise = null;
  const KPI_EXECUTIVE_MODE_STORAGE_KEY = "sicgad_kpi_executive_mode";

  function getStoredExecutiveMode() {
    try {
      return window.localStorage.getItem(KPI_EXECUTIVE_MODE_STORAGE_KEY) === "1";
    } catch (_err) {
      return false;
    }
  }

  function setStoredExecutiveMode(enabled) {
    try {
      window.localStorage.setItem(KPI_EXECUTIVE_MODE_STORAGE_KEY, enabled ? "1" : "0");
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
    if (typeof element.requestFullscreen === "function") {
      return element.requestFullscreen().then(() => true);
    }
    if (typeof element.webkitRequestFullscreen === "function") {
      element.webkitRequestFullscreen();
      return Promise.resolve(true);
    }
    return Promise.resolve(false);
  }

  function exitFullscreenIfNeeded() {
    if (typeof document.exitFullscreen === "function") {
      return document.exitFullscreen();
    }
    if (typeof document.webkitExitFullscreen === "function") {
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
    let hint = chartStage.querySelector('[data-presentation-hint="kpi"]');
    if (hint) {
      return hint;
    }
    hint = document.createElement("div");
    hint.setAttribute("data-presentation-hint", "kpi");
    hint.className =
      "pointer-events-none absolute left-1/2 top-14 z-20 -translate-x-1/2 rounded-full border border-cyan-300/20 bg-slate-950/85 px-3 py-1.5 text-[11px] font-medium text-cyan-100 shadow-lg shadow-black/30 opacity-0 transition-opacity duration-200";
    hint.textContent = "Presiona Esc para salir de presentacion";
    chartStage.appendChild(hint);
    return hint;
  }

  function hidePresentationHint() {
    const hint = ensurePresentationHintElement();
    if (!hint) {
      return;
    }
    hint.classList.add("opacity-0");
    hint.classList.remove("opacity-100");
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
    hint.classList.remove("opacity-0");
    hint.classList.add("opacity-100");
    presentationHintTimer = window.setTimeout(function () {
      hidePresentationHint();
    }, 2200);
  }

  function syncChartPresentationUi() {
    const inPresentation = isChartStageFullscreen();
    const enteredPresentation = inPresentation && !wasPresentationFullscreen;
    wasPresentationFullscreen = inPresentation;
    if (chartStage) {
      chartStage.classList.toggle("ring-2", inPresentation);
      chartStage.classList.toggle("ring-cyan-300/20", inPresentation);
      chartStage.classList.toggle("bg-slate-950/95", inPresentation);
      chartStage.classList.toggle("border-cyan-300/20", inPresentation);
    }
    if (chartContainer) {
      chartContainer.style.height = inPresentation
        ? `${Math.max(420, window.innerHeight - 120)}px`
        : baseChartHeight;
    }
    if (presentationButton) {
      presentationButton.textContent = inPresentation ? "Salir presentación" : "Presentación";
      presentationButton.title = inPresentation
        ? "Salir de presentación (Esc)"
        : "Abrir en presentación";
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
    updateChart();
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

  function ensureXlsxLoaded() {
    if (window.XLSX) {
      return Promise.resolve(window.XLSX);
    }
    if (xlsxLoaderPromise) {
      return xlsxLoaderPromise;
    }
    xlsxLoaderPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js";
      script.async = true;
      script.onload = function () {
        resolve(window.XLSX);
      };
      script.onerror = function () {
        reject(new Error("No se pudo cargar XLSX"));
      };
      document.head.appendChild(script);
    });
    return xlsxLoaderPromise;
  }

  function setDatasetInUrl(datasetId) {
    if (!datasetId) {
      url.searchParams.delete("dataset");
    } else {
      url.searchParams.set("dataset", String(datasetId));
    }
    window.history.replaceState({}, "", `${url.pathname}?${url.searchParams.toString()}`);
  }

  function applyDatasetFromUrl() {
    const datasetFromUrl = url.searchParams.get("dataset");
    if (!datasetFromUrl) {
      return false;
    }
    const optionExists = Array.from(instanceSelect.options || []).some(
      (opt) => opt.value === datasetFromUrl
    );
    if (!optionExists) {
      return false;
    }
    instanceSelect.value = datasetFromUrl;
    return true;
  }

  function getSelectedYFields() {
    if (!yFieldBox) {
      return [];
    }
    return Array.from(yFieldBox.querySelectorAll('input[type="checkbox"]:checked')).map(
      (input) => input.value
    );
  }

  function chooseDefaultFields(columns) {
    if (!columns || !columns.length) {
      return { x: null, y: [] };
    }

    const xField =
      columns.find((c) => c.axis_role === "X") ||
      columns.find((c) => c.data_type === "DATE") ||
      columns[0];

    const numericCols = columns.filter(
      (c) => c.data_type === "INTEGER" || c.data_type === "FLOAT"
    );
    const prioritized = numericCols.filter((c) => c.is_primary_kpi);
    const merged = [...prioritized, ...numericCols.filter((c) => !c.is_primary_kpi)];

    const yFields = [];
    merged.forEach((col) => {
      if (!yFields.includes(col.name)) {
        yFields.push(col.name);
      }
    });

    if (!yFields.length) {
      yFields.push(columns[0].name);
    }

    return {
      x: xField ? xField.name : null,
      y: yFields.slice(0, 3),
    };
  }

  function populateFieldSelectors(columns) {
    currentColumns = columns || [];
    xFieldSelect.innerHTML = "";
    if (yFieldBox) {
      yFieldBox.innerHTML = "";
    }

    if (!columns || !columns.length) {
      return;
    }

    const xCandidates = columns.filter(
      (col) => col.axis_role === "X" || col.data_type === "DATE"
    );
    const xSource = xCandidates.length ? xCandidates : columns;

    xSource.forEach(function (col) {
      const label = col.label || col.name;

      const optX = document.createElement("option");
      optX.value = col.name;
      optX.textContent = label;
      xFieldSelect.appendChild(optX);
    });

    const defaults = chooseDefaultFields(columns);
    if (defaults.x) {
      xFieldSelect.value = defaults.x;
    }
    renderYFieldOptions(columns, defaults.y || []);
  }

  function renderYFieldOptions(columns, defaultY) {
    if (!yFieldBox) {
      return;
    }
    yFieldBox.innerHTML = "";

    if (!columns || !columns.length) {
      const empty = document.createElement("div");
      empty.className = "text-[11px] text-slate-500";
      empty.textContent = "No hay columnas disponibles.";
      yFieldBox.appendChild(empty);
      return;
    }

    const numericCols = columns.filter(
      (c) => c.data_type === "INTEGER" || c.data_type === "FLOAT"
    );
    const sourceColumns = numericCols.length ? numericCols : columns;

    sourceColumns.forEach(function (col, index) {
      const checkboxId = `kpi-y-field-${col.name}`;
      const wrapper = document.createElement("label");
      wrapper.className = "flex items-center gap-2 text-[11px] text-slate-200";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = col.name;
      checkbox.id = checkboxId;
      checkbox.className =
        "size-3.5 rounded border-slate-600 bg-slate-900 text-emerald-400 focus:ring-emerald-500";

      if ((defaultY && defaultY.includes(col.name)) || (!defaultY.length && index === 0)) {
        checkbox.checked = true;
      }

      checkbox.addEventListener("change", function () {
        const selected = getSelectedYFields();
        if (!selected.length) {
          checkbox.checked = true;
          return;
        }
        updateChart();
      });

      const span = document.createElement("span");
      span.textContent = col.label || col.name;

      wrapper.appendChild(checkbox);
      wrapper.appendChild(span);
      yFieldBox.appendChild(wrapper);
    });
  }

  function setFilterBounds(startValue, endValue) {
    filterBounds.start = startValue ? parseDateValue(startValue) : null;
    if (filterBounds.start) {
      filterBounds.start.setHours(0, 0, 0, 0);
    }
    filterBounds.end = endValue ? parseDateValue(endValue) : null;
    if (filterBounds.end) {
      filterBounds.end.setHours(23, 59, 59, 999);
    }
  }

  function formatInputDate(date) {
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
  }

  function formatMetricValue(raw) {
    if (raw == null || !Number.isFinite(raw)) {
      return "--";
    }
    const abs = Math.abs(raw);
    if (abs >= 100000) {
      return compactFormatter.format(raw);
    }
    return numberFormatter.format(raw);
  }

  function inferDateGranularity(values) {
    const stamps = (values || [])
      .map((value) => parseDateValue(value))
      .filter(Boolean)
      .map((date) => date.getTime())
      .sort((a, b) => a - b);

    if (stamps.length < 2) {
      return "date";
    }

    const deltas = [];
    for (let i = 1; i < stamps.length; i += 1) {
      const diff = stamps[i] - stamps[i - 1];
      if (diff > 0) {
        deltas.push(diff);
      }
    }
    if (!deltas.length) {
      return "date";
    }

    deltas.sort((a, b) => a - b);
    const median = deltas[Math.floor(deltas.length / 2)];
    const dayMs = 24 * 60 * 60 * 1000;

    if (median <= dayMs * 3) {
      return "daily";
    }
    if (median <= dayMs * 45) {
      return "monthly";
    }
    if (median <= dayMs * 120) {
      return "quarterly";
    }
    return "yearly";
  }

  function formatDateShort(raw, granularity) {
    const date = parseDateValue(raw);
    if (!date) {
      return raw != null ? String(raw) : "";
    }
    const dd = String(date.getDate()).padStart(2, "0");
    const mon = shortMonthNamesEs[date.getMonth()];
    const yy = String(date.getFullYear()).slice(-2);
    const yyyy = date.getFullYear();

    if (granularity === "yearly") {
      return String(yyyy);
    }
    if (granularity === "monthly" || granularity === "quarterly") {
      return `${mon} ${yy}`;
    }
    if (granularity === "daily") {
      return `${dd} ${mon}`;
    }
    return `${dd} ${mon} ${yy}`;
  }

  function formatDateLong(raw) {
    const date = parseDateValue(raw);
    if (!date) {
      return raw != null ? String(raw) : "";
    }
    const dd = String(date.getDate()).padStart(2, "0");
    const mon = shortMonthNamesEs[date.getMonth()];
    const yyyy = date.getFullYear();
    return `${dd} ${mon} ${yyyy}`;
  }

  function truncateAxisLabel(value, maxLength) {
    const text = value == null ? "" : String(value);
    if (text.length <= maxLength) {
      return text;
    }
    return `${text.slice(0, Math.max(0, maxLength - 1))}…`;
  }

  function createSparkline(values, color) {
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", "0 0 100 40");
    svg.setAttribute("preserveAspectRatio", "none");
    svg.classList.add("authority-kpi-sparkline");

    const clean = values.filter((v) => Number.isFinite(v));
    if (clean.length < 2) {
      return svg;
    }

    const min = Math.min(...clean);
    const max = Math.max(...clean);
    const span = max - min || 1;

    const d = clean
      .map((value, idx) => {
        const x = (idx / (clean.length - 1)) * 100;
        const y = 36 - ((value - min) / span) * 30;
        return `${idx === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(" ");

    const path = document.createElementNS(svgNS, "path");
    path.setAttribute("d", d);
    path.setAttribute("stroke", color);
    svg.appendChild(path);

    return svg;
  }

  function updateAuthorityCards(data, rows) {
    if (!authorityCards) {
      return;
    }

    authorityCards.innerHTML = "";

    if (!data || !data.columns || !rows || !rows.length) {
      for (let i = 0; i < 3; i += 1) {
        const card = document.createElement("article");
        card.className = "authority-kpi-card authority-kpi-card-empty";
        card.innerHTML =
          '<div class="authority-kpi-label">Métrica</div><div class="authority-kpi-value">--</div><div class="authority-kpi-trend">Selecciona un dataset</div>';
        authorityCards.appendChild(card);
      }
      return;
    }

    const selectedNames = getSelectedYFields();
    const selectedCols = selectedNames
      .map((name) => data.columns.find((c) => c.name === name))
      .filter(Boolean);
    const numericCols = data.columns.filter(
      (c) => c.data_type === "INTEGER" || c.data_type === "FLOAT"
    );
    const sourceCols = (selectedCols.length ? selectedCols : numericCols).slice(0, 3);

    if (!sourceCols.length) {
      updateAuthorityCards(null, []);
      return;
    }

    sourceCols.forEach((col, idx) => {
      const values = rows
        .map((row) => {
          const raw = (row.values || {})[col.name];
          if (raw == null || raw === "") {
            return null;
          }
          const parsed = Number(raw);
          return Number.isFinite(parsed) ? parsed : null;
        })
        .filter((v) => v != null);

      const latest = values.length ? values[values.length - 1] : null;
      const prev = values.length > 1 ? values[values.length - 2] : null;
      const delta = latest != null && prev != null ? latest - prev : null;
      const pct =
        delta != null && prev !== 0 ? (delta / Math.abs(prev)) * 100 : null;

      const trendClass = pct == null ? "" : pct >= 0 ? "up" : "down";
      const trendPrefix = pct == null ? "" : pct >= 0 ? "+" : "";
      const trendText =
        pct == null
          ? "Sin variación reciente"
          : `${trendPrefix}${pct.toFixed(2)}% vs anterior`;

      const card = document.createElement("article");
      card.className = "authority-kpi-card";

      const label = document.createElement("div");
      label.className = "authority-kpi-label";
      label.textContent = col.label || col.name;

      const value = document.createElement("div");
      value.className = "authority-kpi-value";
      value.textContent = `${formatMetricValue(latest)}${col.unit ? ` ${col.unit}` : ""}`;

      const trend = document.createElement("div");
      trend.className = `authority-kpi-trend ${trendClass}`.trim();
      trend.textContent = trendText;

      card.appendChild(label);
      card.appendChild(value);
      card.appendChild(trend);
      card.appendChild(createSparkline(values, authorityPalette[idx % authorityPalette.length]));

      authorityCards.appendChild(card);
    });
  }

  function firstDayOfRecentThreeMonths(maxDate) {
    const d = new Date(maxDate.getTime());
    d.setDate(1);
    d.setMonth(d.getMonth() - 2);
    d.setHours(0, 0, 0, 0);
    return d;
  }

  function updateDateInputs(columns, rows) {
    if (!dateStartInput || !dateEndInput || !dateApplyButton) {
      return;
    }

    const selectedX = xFieldSelect.value;
    const xColumn = columns.find((c) => c.name === selectedX);
    availableDateColumn =
      xColumn && xColumn.data_type === "DATE" ? xColumn.name : null;

    if (!availableDateColumn) {
      dateStartInput.value = "";
      dateEndInput.value = "";
      dateStartInput.disabled = true;
      dateEndInput.disabled = true;
      dateApplyButton.disabled = true;
      setFilterBounds(null, null);
      return;
    }

    dateStartInput.disabled = false;
    dateEndInput.disabled = false;
    dateApplyButton.disabled = false;

    let minDate = null;
    let maxDate = null;
    rows.forEach(function (row) {
      const raw = (row.values || {})[availableDateColumn];
      if (!raw) {
        return;
      }
      const d = parseDateValue(raw);
      if (!d) {
        return;
      }
      if (!minDate || d.getTime() < minDate.getTime()) {
        minDate = new Date(d.getTime());
      }
      if (!maxDate || d.getTime() > maxDate.getTime()) {
        maxDate = new Date(d.getTime());
      }
    });

    if (!minDate || !maxDate) {
      const today = new Date();
      minDate = new Date(today.getTime());
      maxDate = new Date(today.getTime());
    }

    const minStr = formatInputDate(minDate);
    const maxStr = formatInputDate(maxDate);
    const defaultEnd = new Date(maxDate.getTime());
    const defaultStart = firstDayOfRecentThreeMonths(maxDate);
    if (defaultStart < minDate) {
      defaultStart.setTime(minDate.getTime());
    }

    dateStartInput.min = minStr;
    dateStartInput.max = maxStr;
    dateEndInput.min = minStr;
    dateEndInput.max = maxStr;

    dateStartInput.value = formatInputDate(defaultStart);
    dateEndInput.value = formatInputDate(defaultEnd);

    setFilterBounds(dateStartInput.value, dateEndInput.value);
  }

  function getFilteredRows(rows) {
    const sourceRows = rows || [];
    if (!availableDateColumn || !sourceRows.length) {
      return sourceRows;
    }

    const start = filterBounds.start;
    const end = filterBounds.end;
    if (!start && !end) {
      return sourceRows;
    }

    return sourceRows.filter(function (row) {
      const raw = (row.values || {})[availableDateColumn];
      if (!raw) {
        return false;
      }
      const d = parseDateValue(raw);
      if (!d) {
        return false;
      }
      if (start && d < start) {
        return false;
      }
      if (end && d > end) {
        return false;
      }
      return true;
    });
  }

  function applyDateFilter() {
    if (!dateStartInput || !dateEndInput || !availableDateColumn) {
      return;
    }
    const startValue = dateStartInput.value || null;
    let endValue = dateEndInput.value || null;
    if (startValue && endValue && startValue > endValue) {
      endValue = startValue;
      dateEndInput.value = endValue;
    }
    setFilterBounds(startValue, endValue);
    updateChart();
    if (currentData) {
      renderTable(currentData, getFilteredRows(currentData.rows || []));
    }
  }

  function buildChartOptions(data, rowsOverride) {
    if (!data || !data.columns) {
      return null;
    }

    const rows = rowsOverride || data.rows || [];

    const xName = xFieldSelect.value;
    const yNames = getSelectedYFields();
    if (!xName || !yNames.length) {
      return null;
    }

    const xCol = data.columns.find((c) => c.name === xName);
    const yCols = yNames
      .map((name) => data.columns.find((c) => c.name === name))
      .filter(Boolean);
    if (!xCol || !yCols.length) {
      return null;
    }

    const xIsTime = xCol.data_type === "DATE";
    const xValues = [];

    if (!rows.length) {
      return null;
    }

    rows.forEach(function (row) {
      const values = row.values || {};
      let xVal = values[xName] ?? null;
      xValues.push(xVal);
    });
    const chartType = chartTypeSelect.value || "line";
    const xGranularity = xIsTime ? inferDateGranularity(xValues) : "text";
    const executiveMode = isExecutiveMode();

    let seriesType = "line";
    let smooth = true;
    let stack = undefined;

    if (chartType === "bar" || chartType === "stacked_bar") {
      seriesType = "bar";
      smooth = false;
    }
    if (chartType === "stacked_bar") {
      stack = "total";
    }

    const seriesColors = isAuthorityView
      ? ["#f5b14f", "#33b6ff", "#23d3a6", "#8b7dff", "#f97393", "#39d1ff"]
      : ["#6366f1", "#10b981", "#8b5cf6", "#f43f5e", "#f59e0b", "#06b6d4"];
    const showArea = seriesType === "line" && !stack && yCols.length === 1 && !executiveMode;
    const showSymbols = !executiveMode && rows.length <= 36;
    const barMaxWidth =
      rows.length > 180 ? 6 : rows.length > 120 ? 8 : rows.length > 70 ? 10 : 14;
    const xLabelTargetCount = executiveMode ? 8 : 14;
    const xLabelInterval =
      rows.length > xLabelTargetCount
        ? Math.max(0, Math.ceil(rows.length / xLabelTargetCount) - 1)
        : 0;
    const unitsBySeriesName = {};
    const series = yCols.map(function (yCol, idx) {
      const values = rows.map(function (row) {
        const raw = (row.values || {})[yCol.name];
        return raw != null && raw !== "" ? Number(raw) : null;
      });
      const color = seriesColors[idx % seriesColors.length];
      const seriesName = yCol.label || yCol.name;
      unitsBySeriesName[seriesName] = yCol.unit || "";

      const baseSeries = {
        name: seriesName,
        type: seriesType,
        stack: stack,
        showSymbol: seriesType === "line" ? showSymbols : false,
        symbol: "circle",
        symbolSize: rows.length > 90 ? 4 : 6,
        connectNulls: false,
        animationDuration: 420,
        animationEasing: "cubicOut",
        emphasis: {
          focus: "series",
        },
        itemStyle: {
          color:
            seriesType === "bar"
              ? new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: `${color}ff` },
                  { offset: 1, color: `${color}9f` },
                ])
              : color,
          borderRadius: seriesType === "bar" ? [7, 7, 0, 0] : 0,
        },
        data: values,
      };

      if (seriesType === "line") {
        baseSeries.smooth = smooth;
        baseSeries.sampling = "lttb";
        baseSeries.lineStyle = {
          width: isAuthorityView ? 2.8 : 3,
          color: color,
          shadowColor: isAuthorityView ? "rgba(0, 0, 0, 0.38)" : "rgba(0, 0, 0, 0.28)",
          shadowBlur: executiveMode ? 6 : 10,
          shadowOffsetY: executiveMode ? 2 : 4,
          cap: "round",
          join: "round",
        };
        if (showArea) {
          baseSeries.areaStyle = {
            opacity: isAuthorityView ? 0.2 : 0.18,
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: `${color}70` },
              { offset: 0.6, color: `${color}1f` },
              { offset: 1, color: `${color}00` },
            ]),
          };
        }
      } else {
        baseSeries.barMaxWidth = barMaxWidth;
        baseSeries.barMinHeight = 1;
        baseSeries.barCategoryGap = stack ? "22%" : "30%";
        baseSeries.emphasis = {
          focus: "series",
          itemStyle: {
            shadowColor: `${color}55`,
            shadowBlur: 12,
          },
        };
      }

      return baseSeries;
    });

    const gridTop = yCols.length > 1 ? (executiveMode ? 50 : 56) : executiveMode ? 28 : 32;
    const tooltipPointerType = seriesType === "bar" ? "shadow" : "line";
    const xAxisRotate = executiveMode
      ? 0
      : xIsTime
        ? (rows.length > 32 ? 28 : 0)
        : rows.length > 20
          ? 18
          : 0;

    return {
      animationDurationUpdate: 220,
      animationEasingUpdate: "cubicOut",
      tooltip: {
        trigger: "axis",
        backgroundColor: isAuthorityView ? "rgba(6, 16, 32, 0.97)" : "rgba(15, 23, 42, 0.95)",
        borderColor: isAuthorityView ? "rgba(51, 182, 255, 0.35)" : "rgba(99, 102, 241, 0.2)",
        borderWidth: 1,
        borderRadius: executiveMode ? 12 : 14,
        padding: executiveMode ? [8, 10] : [10, 12],
        extraCssText:
          "box-shadow: 0 10px 30px rgba(2,6,23,.35); backdrop-filter: blur(8px);",
        textStyle: { color: "#f8fafc", fontSize: 12, fontFamily: "Lexend" },
        formatter: function (params) {
          const items = Array.isArray(params) ? params : [params];
          if (!items.length) {
            return "";
          }

          const axisRaw = items[0].axisValue;
          const title = xIsTime ? formatDateLong(axisRaw) : truncateAxisLabel(axisRaw, 44);
          const rowsHtml = items
            .map(function (item) {
              const seriesName = item.seriesName || "";
              const unit = unitsBySeriesName[seriesName] ? ` ${unitsBySeriesName[seriesName]}` : "";
              const color =
                typeof item.color === "string"
                  ? item.color
                  : item.color && Array.isArray(item.color.colorStops) && item.color.colorStops[0]
                    ? item.color.colorStops[0].color
                    : seriesColors[items.indexOf(item) % seriesColors.length];
              const value = Array.isArray(item.value) ? item.value[item.value.length - 1] : item.value;
              const numericValue =
                value == null || value === "" ? null : Number.isFinite(Number(value)) ? Number(value) : null;
              return (
                `<div style="display:flex;align-items:center;justify-content:space-between;gap:14px;min-width:220px;margin-top:6px;">` +
                `<div style="display:flex;align-items:center;gap:8px;color:#dbeafe;">` +
                `<span style="width:8px;height:8px;border-radius:999px;background:${color};box-shadow:0 0 0 3px ${color}22;"></span>` +
                `<span style="opacity:.95;">${seriesName}</span>` +
                `</div>` +
                `<div style="font-weight:700;color:#ffffff;">${formatMetricValue(numericValue)}${unit}</div>` +
                `</div>`
              );
            })
            .join("");

          return (
            `<div style="font-family:Lexend, sans-serif;">` +
            `<div style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:#93c5fd;opacity:.9;margin-bottom:2px;">${xCol.label || xCol.name}</div>` +
            `<div style="font-size:13px;font-weight:700;color:#f8fafc;">${title}</div>` +
            rowsHtml +
            `</div>`
          );
        },
        axisPointer: {
          type: tooltipPointerType,
          lineStyle: {
            color: isAuthorityView ? "rgba(51, 182, 255, 0.45)" : "rgba(99, 102, 241, 0.4)",
            width: executiveMode ? 1.5 : 2,
          },
          shadowStyle: {
            color: isAuthorityView ? "rgba(51, 182, 255, 0.08)" : "rgba(99, 102, 241, 0.06)",
          },
          label: {
            show: false,
          },
        },
      },
      legend: {
        show: yCols.length > 1,
        top: executiveMode ? 4 : 0,
        left: "center",
        icon: "roundRect",
        itemWidth: executiveMode ? 12 : 14,
        itemHeight: executiveMode ? 6 : 8,
        itemGap: executiveMode ? 10 : 14,
        textStyle: {
          color: isAuthorityView ? "#aec5e8" : "#475569",
          fontSize: executiveMode ? 10 : 11,
          fontWeight: 600
        },
      },
      dataZoom: [
        {
          type: "inside",
          xAxisIndex: 0,
          start: 0,
          end: 100,
          zoomLock: false,
          throttle: 50,
        },
        {
          type: "slider",
          xAxisIndex: 0,
          height: executiveMode ? 30 : 40,
          bottom: executiveMode ? 2 : 0,
          showDetail: false,
          brushSelect: false,
          borderRadius: 10,
          backgroundColor: isAuthorityView
            ? "rgba(11, 24, 44, 0.7)"
            : "rgba(15, 23, 42, 0.42)",
          handleStyle: {
            color: isAuthorityView ? "#1bc9ff" : "#6366f1",
            borderColor: isAuthorityView ? "#0f2745" : "#1e293b",
            shadowBlur: 8,
            shadowColor: "rgba(0,0,0,.25)",
          },
          textStyle: {
            color: isAuthorityView ? "#7ea1cc" : "#64748b",
          },
          fillerColor: isAuthorityView
            ? "rgba(27, 201, 255, 0.14)"
            : "rgba(99, 102, 241, 0.08)",
          dataBackground: {
            lineStyle: {
              color: isAuthorityView ? "rgba(125, 162, 214, 0.35)" : "rgba(148, 163, 184, 0.3)",
              width: 1,
            },
            areaStyle: {
              color: isAuthorityView ? "rgba(59, 130, 246, 0.08)" : "rgba(99, 102, 241, 0.06)",
            },
          },
          selectedDataBackground: {
            lineStyle: {
              color: isAuthorityView ? "rgba(125, 162, 214, 0.65)" : "rgba(165, 180, 252, 0.55)",
              width: 1.2,
            },
            areaStyle: {
              color: isAuthorityView ? "rgba(51, 182, 255, 0.1)" : "rgba(99, 102, 241, 0.1)",
            },
          },
          labelFormatter: xIsTime
            ? function (value) {
                return formatDateShort(value, xGranularity);
              }
            : function (value) {
                return truncateAxisLabel(value, 12);
              },
          borderColor: isAuthorityView
            ? "rgba(27, 201, 255, 0.2)"
            : "rgba(255, 255, 255, 0.03)",
          showDataShadow: !executiveMode,
        },
      ],
      grid: {
        left: executiveMode ? 44 : 54,
        right: executiveMode ? 12 : 18,
        top: gridTop,
        bottom: (xIsTime ? (executiveMode ? 26 : 54) : executiveMode ? 22 : 32) +
          (executiveMode ? 30 : 40),
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: xValues,
        boundaryGap: seriesType === "bar",
        name: executiveMode ? "" : xCol.label || xCol.name,
        nameTextStyle: {
          color: isAuthorityView ? "#8ba6cb" : "#94a3b8",
          fontSize: executiveMode ? 9 : 10,
          fontWeight: 600,
          padding: [12, 0, 0, 0],
        },
        axisLine: {
          lineStyle: {
            color: isAuthorityView ? "rgba(72, 108, 153, 0.55)" : "rgba(148, 163, 184, 0.18)",
            width: 1,
          },
        },
        axisTick: { show: false },
        axisLabel: {
          rotate: xAxisRotate,
          fontSize: executiveMode ? 9 : 10,
          lineHeight: executiveMode ? 10 : 12,
          color: isAuthorityView ? "#8ba6cb" : "#94a3b8",
          margin: executiveMode ? 6 : 10,
          hideOverlap: true,
          interval: xLabelInterval,
          formatter: xIsTime
            ? function (value) {
                return formatDateShort(value, xGranularity);
              }
            : function (value) {
                return truncateAxisLabel(value, executiveMode ? 12 : 18);
              },
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        name:
          yCols.length === 1
            ? (yCols[0].label || yCols[0].name) +
            (yCols[0].unit ? ` (${yCols[0].unit})` : "")
            : "Valores",
        minInterval: 0,
        nameTextStyle: {
          color: isAuthorityView ? "#8ba6cb" : "#94a3b8",
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
          color: isAuthorityView ? "#8ba6cb" : "#94a3b8",
          formatter: function (value) {
            return formatMetricValue(value);
          },
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: isAuthorityView
              ? executiveMode
                ? "rgba(101, 141, 189, 0.1)"
                : "rgba(101, 141, 189, 0.16)"
              : executiveMode
                ? "rgba(148, 163, 184, 0.06)"
                : "rgba(148, 163, 184, 0.1)",
            width: 1,
            type: executiveMode ? [3, 6] : [4, 4],
          },
        },
      },
      series: series,
    };
  }

  function updateExportState(rows) {
    const hasRows = rows && rows.length;
    if (exportCsvButton) {
      exportCsvButton.disabled = !hasRows;
    }
    if (exportExcelButton) {
      exportExcelButton.disabled = !hasRows;
    }
  }

  function renderTable(data, rowsOverride) {
    if (!tableContainer) {
      return;
    }
    tableContainer.innerHTML = "";

    if (!data || !data.columns) {
      updateExportState([]);
      return;
    }

    const rows = rowsOverride != null ? rowsOverride : data.rows || [];

    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "p-3 text-[11px] text-slate-400";
      empty.textContent = "No hay datos para mostrar.";
      tableContainer.appendChild(empty);
      updateExportState([]);
      return;
    }

    function formatCellValue(value) {
      if (value == null || value === "") {
        return "-";
      }
      if (typeof value === "number" && Number.isFinite(value)) {
        return value.toFixed(2);
      }
      if (typeof value === "string") {
        const trimmed = value.trim();
        if (!trimmed) {
          return "-";
        }
        if (/^-?\\d+(\\.\\d+)?$/.test(trimmed)) {
          const numeric = Number(trimmed);
          return Number.isFinite(numeric) ? numeric.toFixed(2) : trimmed;
        }
      }
      return value;
    }

    const visibleRows =
      !tableExpanded && rows.length > TABLE_RENDER_LIMIT
        ? rows.slice(0, TABLE_RENDER_LIMIT)
        : rows;

    if (rows.length > TABLE_RENDER_LIMIT && !tableExpanded) {
      const summary = document.createElement("div");
      summary.className =
        "flex flex-wrap items-center justify-between gap-3 p-3 text-[11px] text-slate-400 border-b border-white/5 bg-white/[0.02]";
      summary.innerHTML =
        `<span>Mostrando ${visibleRows.length} de ${rows.length} filas para mejorar la velocidad inicial.</span>`;
      const expandBtn = document.createElement("button");
      expandBtn.type = "button";
      expandBtn.className =
        "px-3 py-1 rounded-lg border border-cyan-400/20 bg-cyan-400/5 text-cyan-300 hover:bg-cyan-400/10 transition-colors";
      expandBtn.textContent = "Mostrar todas";
      expandBtn.addEventListener("click", function () {
        tableExpanded = true;
        renderTable(data, rows);
      });
      summary.appendChild(expandBtn);
      tableContainer.appendChild(summary);
    }

    const table = document.createElement("table");
    table.className = "w-full text-left border-collapse";

    const thead = document.createElement("thead");
    thead.className = "bg-white/[0.02] text-[10px] font-black text-slate-500 uppercase tracking-widest";
    const headRow = document.createElement("tr");
    data.columns.forEach(function (col) {
      const th = document.createElement("th");
      th.className = "px-6 py-4";
      th.textContent = col.name;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);

    const tbody = document.createElement("tbody");
    tbody.className = "text-sm";
    visibleRows.forEach(function (row) {
      const tr = document.createElement("tr");
      tr.className = "border-t border-white/5 hover:bg-white/[0.02] transition-colors";
      data.columns.forEach(function (col) {
        const td = document.createElement("td");
        td.className = "px-6 py-4 text-slate-300 whitespace-nowrap";
        const v = (row.values || {})[col.name];
        td.textContent = formatCellValue(v);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);
    tableContainer.appendChild(table);
    updateExportState(rows);
  }

  function sanitizeFileName(text) {
    if (!text) {
      return "datos";
    }
    return text
      .toString()
      .toLowerCase()
      .replace(/[^a-z0-9]+/gi, "_")
      .replace(/^_+|_+$/g, "");
  }

  function buildFileBaseName() {
    if (!currentData || !currentData.dataset) {
      return "sicgad_datos";
    }
    const dataset = currentData.dataset || {};
    const name = sanitizeFileName(dataset.name);
    const entity = sanitizeFileName(dataset.entity_code);
    const mode = sanitizeFileName(modeSelect.value || "published");
    let range = "";
    if (filterBounds.start && filterBounds.end) {
      range = `${formatInputDate(filterBounds.start)}_a_${formatInputDate(filterBounds.end)}`;
    }
    const pieces = ["sicgad", entity, name, mode, range].filter(Boolean);
    return pieces.join("_");
  }

  function escapeCsv(value) {
    if (value == null) {
      return "";
    }
    const text = String(value);
    if (/[",\n]/.test(text)) {
      return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
  }

  function buildExportRows() {
    if (!currentData || !currentData.columns) {
      return { columns: [], rows: [] };
    }
    const rows = getFilteredRows(currentData.rows || []);
    return { columns: currentData.columns || [], rows };
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function exportCsv() {
    const data = buildExportRows();
    if (!data.rows.length) {
      return;
    }
    const header = data.columns.map((col) => escapeCsv(col.name)).join(",");
    const lines = data.rows.map((row) => {
      return data.columns
        .map((col) => escapeCsv((row.values || {})[col.name]))
        .join(",");
    });
    const csv = [header, ...lines].join("\n");
    const filename = `${buildFileBaseName()}.csv`;
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    downloadBlob(blob, filename);
  }

  function exportExcel() {
    const data = buildExportRows();
    if (!data.rows.length) {
      return;
    }

    ensureXlsxLoaded()
      .then(() => {
        if (!window.XLSX) {
          throw new Error("XLSX no disponible para exportar.");
        }

        const header = data.columns.map((col) => col.name);
        const rows = data.rows.map((row) => {
          return data.columns.map((col) => {
            const value = (row.values || {})[col.name];
            return value != null ? value : "";
          });
        });

        const worksheet = window.XLSX.utils.aoa_to_sheet([header, ...rows]);
        const workbook = window.XLSX.utils.book_new();
        window.XLSX.utils.book_append_sheet(workbook, worksheet, "Datos");

        const filename = `${buildFileBaseName()}.xlsx`;
        window.XLSX.writeFile(workbook, filename);
      })
      .catch((err) => {
        console.error(err);
      });
  }

  function updateChart(rowsOverride) {
    if (!chart || !currentData) {
      return;
    }
    const rows =
      Array.isArray(rowsOverride) ? rowsOverride : getFilteredRows(currentData.rows || []);
    const option = buildChartOptions(currentData, rows);
    if (option) {
      chart.setOption(option, true);
    } else {
      chart.clear();
    }
    updateAuthorityCards(currentData, rows);
  }

  function loadInstanceData() {
    const datasetId = instanceSelect.value;
    const mode = modeSelect.value || "published";
    if (!datasetId) {
      currentData = null;
      if (chart) {
        chart.clear();
      }
      updateAuthorityCards(null, []);
      if (tableContainer) {
        tableContainer.innerHTML = "";
      }
      updateExportState([]);
      return;
    }

    fetch(`/kpis/data/${datasetId}/?source=${encodeURIComponent(
      mode === "draft" ? "draft" : "published"
    )}`)
      .then((resp) => {
        if (!resp.ok) {
          throw new Error("Error al cargar datos");
        }
        return resp.json();
      })
      .then((data) => {
        currentData = data;
        tableExpanded = false;
        populateFieldSelectors(data.columns || []);
        updateDateInputs(currentColumns, data.rows || []);
        const filteredRows = getFilteredRows(data.rows || []);
        updateChart(filteredRows);
        renderTable(data, filteredRows);
      })
      .catch((err) => {
        console.error(err);
      });
  }

  modeSelect.addEventListener("change", function () {
    loadInstanceData();
  });

  instanceSelect.addEventListener("change", function () {
    setDatasetInUrl(instanceSelect.value);
    loadInstanceData();
  });

  xFieldSelect.addEventListener("change", function () {
    updateDateInputs(currentColumns, currentData ? currentData.rows || [] : []);
    updateChart();
  });
  chartTypeSelect.addEventListener("change", updateChart);
  if (executiveModeToggle) {
    executiveModeToggle.checked = getStoredExecutiveMode();
    executiveModeToggle.addEventListener("change", function () {
      setStoredExecutiveMode(executiveModeToggle.checked);
      updateChart();
    });
  }
  dateApplyButton.addEventListener("click", applyDateFilter);
  if (exportCsvButton) {
    exportCsvButton.addEventListener("click", exportCsv);
  }
  if (exportExcelButton) {
    exportExcelButton.addEventListener("click", exportExcel);
  }
  if (presentationButton) {
    presentationButton.addEventListener("click", togglePresentationMode);
  }
  document.addEventListener("fullscreenchange", syncChartPresentationUi);
  document.addEventListener("webkitfullscreenchange", syncChartPresentationUi);
  window.addEventListener("resize", resizeChartSoon);

  const appliedFromUrl = applyDatasetFromUrl();
  if (!appliedFromUrl && !instanceSelect.value) {
    const firstDatasetOption = Array.from(instanceSelect.options || []).find(
      (opt) => Boolean(opt.value)
    );
    if (firstDatasetOption) {
      instanceSelect.value = firstDatasetOption.value;
    }
  }
  setDatasetInUrl(instanceSelect.value);
  loadInstanceData();
  syncChartPresentationUi();

});
