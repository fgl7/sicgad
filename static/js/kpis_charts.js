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
  const chartControlsPanel = document.getElementById("kpi-chart-controls-panel");
  const yFieldSection = document.querySelector("[data-kpi-y-field-section]");
  const kpiTableSection = document.getElementById("kpi-table-section");
  const kpiTableCard = document.getElementById("kpi-table-card");
  const kpiTableHeader = document.getElementById("kpi-table-header");
  const tableContainer = document.getElementById("kpi-table-container");
  const kpiTableModalOpenButton = document.getElementById("kpi-table-modal-open-btn");
  const kpiTableModal = document.getElementById("kpi-table-modal");
  const kpiTableModalBackdrop = document.getElementById("kpi-table-modal-backdrop");
  const kpiTableModalCloseButton = document.getElementById("kpi-table-modal-close-btn");
  const tableToggleButton = document.getElementById("kpi-table-toggle-btn");
  const exportCsvButton = document.getElementById("kpi-export-csv");
  const exportExcelButton = document.getElementById("kpi-export-excel");
  const relatedPerformanceSection = document.getElementById("related-performance-section");
  const relatedPerformanceHelp = document.getElementById("related-performance-help");
  const relatedPerformanceIndicatorSelect = document.getElementById("related-performance-indicator-select");
  const relatedPerformanceFrequencyBadge = document.getElementById("related-performance-frequency-badge");
  const relatedPerformanceChartTypeSelect = document.getElementById("related-performance-chart-type-select");
  const relatedPerformanceChartContainer = document.getElementById("related-performance-chart");
  const relatedPerformanceEmpty = document.getElementById("related-performance-empty");
  const relatedPerformanceTableModalOpenButton = document.getElementById("related-performance-table-modal-open-btn");
  const relatedPerformanceTableModal = document.getElementById("related-performance-table-modal");
  const relatedPerformanceTableModalBackdrop = document.getElementById("related-performance-table-modal-backdrop");
  const relatedPerformanceTableModalCloseButton = document.getElementById("related-performance-table-modal-close-btn");
  const relatedPerformanceTableContainer = document.getElementById("related-performance-table-container");
  const relatedPerformanceExportCsv = document.getElementById("related-performance-export-csv");
  const relatedPerformanceExportExcel = document.getElementById("related-performance-export-excel");
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
  let relatedPerformanceChart = null;
  const baseChartHeight = chartContainer.style.height || `${Math.max(chartContainer.clientHeight, 320)}px`;
  const relatedPerformanceBaseChartHeight =
    relatedPerformanceChartContainer && relatedPerformanceChartContainer.style.height
      ? relatedPerformanceChartContainer.style.height
      : `${Math.max(relatedPerformanceChartContainer ? relatedPerformanceChartContainer.clientHeight : 0, 300)}px`;
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
  let isKpiTableModalOpen = false;
  let isRelatedPerformanceTableModalOpen = false;
  let isKpiTableHidden = false;
  const filterBounds = { start: null, end: null };
  const url = new URL(window.location.href);
  const TABLE_RENDER_LIMIT = 300;
  let xlsxLoaderPromise = null;
  const KPI_EXECUTIVE_MODE_STORAGE_KEY = "sicgad_kpi_executive_mode";
  const KPI_TABLE_HIDDEN_STORAGE_KEY = "sicgad_kpi_table_hidden";
  let relatedPerformanceIndicators = [];
  let relatedPerformancePayload = null;
  let relatedPerformanceRequestSeq = 0;
  let relatedPerformanceCurrentFrequency = "MONTHLY";

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
      syncKpiControlsPanelHeight();
    });
  }

  function syncKpiControlsPanelHeight() {
    if (!chartControlsPanel || !chartStage) {
      return;
    }
    const isDesktop = window.matchMedia ? window.matchMedia("(min-width: 768px)").matches : window.innerWidth >= 768;
    if (!isDesktop || isChartStageFullscreen()) {
      chartControlsPanel.style.height = "";
      chartControlsPanel.style.maxHeight = "";
      return;
    }
    const stageHeight = Math.round(chartStage.getBoundingClientRect().height || 0);
    if (stageHeight <= 0) {
      return;
    }
    chartControlsPanel.style.height = `${stageHeight}px`;
    chartControlsPanel.style.maxHeight = `${stageHeight}px`;
    syncYFieldBoxHeight();
  }

  function syncYFieldBoxHeight() {
    if (!chartControlsPanel || !yFieldBox || !yFieldSection) {
      return;
    }
    const isDesktop = window.matchMedia ? window.matchMedia("(min-width: 768px)").matches : window.innerWidth >= 768;
    if (!isDesktop) {
      yFieldBox.style.maxHeight = "";
      yFieldBox.style.height = "";
      return;
    }

    const panelHeight = Math.round(chartControlsPanel.getBoundingClientRect().height || 0);
    if (panelHeight <= 0) {
      return;
    }

    const children = Array.from(chartControlsPanel.children || []).filter(function (el) {
      return el && el.nodeType === 1;
    });
    const panelStyles = window.getComputedStyle ? window.getComputedStyle(chartControlsPanel) : null;
    const gap = panelStyles ? parseFloat(panelStyles.rowGap || panelStyles.gap || "0") || 0 : 0;
    function getVerticalMargins(el) {
      if (!window.getComputedStyle || !el) {
        return 0;
      }
      const styles = window.getComputedStyle(el);
      const mt = parseFloat(styles.marginTop || "0") || 0;
      const mb = parseFloat(styles.marginBottom || "0") || 0;
      return mt + mb;
    }

    let otherHeight = 0;
    children.forEach(function (child) {
      if (child === yFieldSection) {
        return;
      }
      otherHeight += Math.ceil(child.getBoundingClientRect().height || 0) + Math.ceil(getVerticalMargins(child));
    });

    const gapsTotal = children.length > 1 ? gap * (children.length - 1) : 0;
    const labelEl = yFieldSection.querySelector("label");
    let labelHeight = 0;
    if (labelEl) {
      const labelRect = labelEl.getBoundingClientRect();
      const labelStyles = window.getComputedStyle ? window.getComputedStyle(labelEl) : null;
      const marginBottom = labelStyles ? parseFloat(labelStyles.marginBottom || "0") || 0 : 0;
      labelHeight = Math.ceil(labelRect.height || 0) + marginBottom;
    }
    const ySectionStyles = window.getComputedStyle ? window.getComputedStyle(yFieldSection) : null;
    const ySectionChrome = ySectionStyles
      ? (parseFloat(ySectionStyles.paddingTop || "0") || 0) +
        (parseFloat(ySectionStyles.paddingBottom || "0") || 0) +
        (parseFloat(ySectionStyles.borderTopWidth || "0") || 0) +
        (parseFloat(ySectionStyles.borderBottomWidth || "0") || 0)
      : 0;
    const ySectionMargins = Math.ceil(getVerticalMargins(yFieldSection));

    const available = Math.floor(
      panelHeight - otherHeight - gapsTotal - labelHeight - ySectionChrome - ySectionMargins
    );
    if (available <= 0) {
      yFieldBox.style.maxHeight = "";
      yFieldBox.style.height = "";
      return;
    }

    // Fit content when there are few indicators; use scroll only when content exceeds panel space.
    const contentHeight = Math.ceil(yFieldBox.scrollHeight || 0);
    const minHeight = 96;
    const minTarget = Math.min(minHeight, available);
    const target = Math.max(minTarget, Math.min(contentHeight, available));
    yFieldBox.style.maxHeight = `${target}px`;
    yFieldBox.style.height = contentHeight > target ? `${target}px` : "auto";
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
    syncKpiControlsPanelHeight();
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
    syncYFieldBoxHeight();
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
    syncYFieldBoxHeight();
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
    if (!dateStartInput || !dateEndInput) {
      return;
    }
    const startValue = dateStartInput.value || null;
    let endValue = dateEndInput.value || null;
    if (startValue && endValue && startValue > endValue) {
      endValue = startValue;
      dateEndInput.value = endValue;
    }
    if (availableDateColumn) {
      setFilterBounds(startValue, endValue);
      updateChart();
      if (currentData) {
        renderTable(currentData, getFilteredRows(currentData.rows || []));
      }
    }
    const relatedVisible =
      relatedPerformanceSection && !relatedPerformanceSection.classList.contains("hidden");
    if (hasRelatedPerformanceUi() && relatedVisible) {
      loadRelatedPerformanceData();
    }
  }

  function getStoredKpiTableHidden() {
    try {
      return window.localStorage.getItem(KPI_TABLE_HIDDEN_STORAGE_KEY) === "1";
    } catch (_err) {
      return false;
    }
  }

  function setStoredKpiTableHidden(hidden) {
    try {
      window.localStorage.setItem(KPI_TABLE_HIDDEN_STORAGE_KEY, hidden ? "1" : "0");
    } catch (_err) {
      // ignore storage restrictions
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
    if (kpiTableModalOpenButton) {
      kpiTableModalOpenButton.disabled = !hasRows;
    }
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

  function applyKpiTableVisibility(hidden) {
    // Backward-compatible no-op for older templates that still use inline table toggling.
    isKpiTableHidden = Boolean(hidden);
    if (!tableContainer) {
      return;
    }
    if (!kpiTableSection && !tableToggleButton && kpiTableModal) {
      tableContainer.classList.remove("hidden");
      tableContainer.style.maxHeight = "";
      tableContainer.style.borderWidth = "";
      tableContainer.style.marginTop = "";
      return;
    }
    tableContainer.classList.toggle("hidden", isKpiTableHidden);
    if (isKpiTableHidden) {
      tableContainer.style.maxHeight = "0";
      tableContainer.style.borderWidth = "0";
      tableContainer.style.marginTop = "0";
    } else {
      tableContainer.style.maxHeight = "";
      tableContainer.style.borderWidth = "";
      tableContainer.style.marginTop = "";
    }
    if (kpiTableHeader) {
      kpiTableHeader.style.marginBottom = isKpiTableHidden ? "0" : "";
      kpiTableHeader.style.gap = isKpiTableHidden ? "0.5rem" : "";
    }
    if (kpiTableCard) {
      kpiTableCard.style.padding = isKpiTableHidden ? "0.75rem 1rem" : "";
    }
    if (kpiTableSection) {
      kpiTableSection.style.padding = isKpiTableHidden ? "0.75rem" : "";
    }
    if (tableToggleButton) {
      tableToggleButton.textContent = isKpiTableHidden ? "Mostrar tabla" : "Ocultar tabla";
    }
    setStoredKpiTableHidden(isKpiTableHidden);
  }

  function openKpiTableModal() {
    if (!kpiTableModal || !kpiTableModalOpenButton || kpiTableModalOpenButton.disabled) {
      return;
    }
    kpiTableModal.classList.remove("hidden");
    kpiTableModal.setAttribute("aria-hidden", "false");
    isKpiTableModalOpen = true;
    document.body.classList.add("overflow-hidden");
    window.setTimeout(function () {
      if (kpiTableModalCloseButton) {
        kpiTableModalCloseButton.focus();
      }
    }, 0);
  }

  function closeKpiTableModal() {
    if (!kpiTableModal) {
      return;
    }
    kpiTableModal.classList.add("hidden");
    kpiTableModal.setAttribute("aria-hidden", "true");
    isKpiTableModalOpen = false;
    if (!isRelatedPerformanceTableModalOpen) {
      document.body.classList.remove("overflow-hidden");
    }
  }

  function openRelatedPerformanceTableModal() {
    if (
      !relatedPerformanceTableModal ||
      !relatedPerformanceTableModalOpenButton ||
      relatedPerformanceTableModalOpenButton.disabled
    ) {
      return;
    }
    relatedPerformanceTableModal.classList.remove("hidden");
    relatedPerformanceTableModal.setAttribute("aria-hidden", "false");
    isRelatedPerformanceTableModalOpen = true;
    document.body.classList.add("overflow-hidden");
    window.setTimeout(function () {
      if (relatedPerformanceTableModalCloseButton) {
        relatedPerformanceTableModalCloseButton.focus();
      }
    }, 0);
  }

  function closeRelatedPerformanceTableModal() {
    if (!relatedPerformanceTableModal) {
      return;
    }
    relatedPerformanceTableModal.classList.add("hidden");
    relatedPerformanceTableModal.setAttribute("aria-hidden", "true");
    isRelatedPerformanceTableModalOpen = false;
    if (!isKpiTableModalOpen) {
      document.body.classList.remove("overflow-hidden");
    }
  }

  function resizeRelatedPerformanceChartSoon() {
    if (!relatedPerformanceChartContainer) {
      return;
    }
    window.requestAnimationFrame(function () {
      const chartRef = ensureRelatedPerformanceChart();
      if (!chartRef) {
        return;
      }
      chartRef.resize();
      window.requestAnimationFrame(function () {
        const lateChartRef = ensureRelatedPerformanceChart();
        if (lateChartRef) {
          lateChartRef.resize();
        }
      });
    });
    window.setTimeout(function () {
      const delayedChartRef = ensureRelatedPerformanceChart();
      if (delayedChartRef) {
        delayedChartRef.resize();
      }
    }, 80);
  }

  function ensureRelatedPerformanceChart(forceReinit) {
    if (!window.echarts || !relatedPerformanceChartContainer) {
      return null;
    }
    const containerWidth = Math.round(
      relatedPerformanceChartContainer.getBoundingClientRect
        ? relatedPerformanceChartContainer.getBoundingClientRect().width || 0
        : relatedPerformanceChartContainer.clientWidth || 0
    );
    const needsInit = !relatedPerformanceChart || forceReinit;
    if (containerWidth <= 0 && needsInit) {
      return relatedPerformanceChart || null;
    }
    const looksCollapsed =
      relatedPerformanceChart &&
      containerWidth > 240 &&
      typeof relatedPerformanceChart.getWidth === "function" &&
      relatedPerformanceChart.getWidth() > 0 &&
      relatedPerformanceChart.getWidth() < Math.floor(containerWidth * 0.6);

    if (needsInit || looksCollapsed) {
      if (relatedPerformanceChart) {
        try {
          relatedPerformanceChart.dispose();
        } catch (_err) {
          // ignore dispose errors and re-init
        }
      }
      relatedPerformanceChart = echarts.init(relatedPerformanceChartContainer);
    }
    return relatedPerformanceChart;
  }

  function handleGlobalKeydown(event) {
    if (!event) {
      return;
    }
    if (event.key === "Escape") {
      if (isRelatedPerformanceTableModalOpen) {
        closeRelatedPerformanceTableModal();
        return;
      }
      if (isKpiTableModalOpen) {
        closeKpiTableModal();
      }
    }
  }

  function hasRelatedPerformanceUi() {
    return Boolean(
      relatedPerformanceSection &&
      relatedPerformanceIndicatorSelect &&
      relatedPerformanceChartTypeSelect &&
      relatedPerformanceTableContainer
    );
  }

  function getRelatedPerformanceSelectedIndicator() {
    const id = Number(relatedPerformanceIndicatorSelect && relatedPerformanceIndicatorSelect.value);
    if (!id) {
      return null;
    }
    return relatedPerformanceIndicators.find((item) => item.id === id) || null;
  }

  function setRelatedPerformanceExportState(rows) {
    const hasRows = Boolean(rows && rows.length);
    if (relatedPerformanceTableModalOpenButton) {
      relatedPerformanceTableModalOpenButton.disabled = !hasRows;
    }
    if (relatedPerformanceExportCsv) {
      relatedPerformanceExportCsv.disabled = !hasRows;
    }
    if (relatedPerformanceExportExcel) {
      relatedPerformanceExportExcel.disabled = !hasRows;
    }
  }

  function renderRelatedPerformanceTable(payload) {
    if (!relatedPerformanceTableContainer) {
      return;
    }
    relatedPerformanceTableContainer.innerHTML = "";

    const rows = payload && Array.isArray(payload.rows) ? payload.rows : [];
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "p-3 text-[11px] text-slate-400";
      empty.textContent = "No hay datos para mostrar.";
      relatedPerformanceTableContainer.appendChild(empty);
      setRelatedPerformanceExportState([]);
      return;
    }

    const table = document.createElement("table");
    table.className = "w-full text-left border-collapse";

    const thead = document.createElement("thead");
    thead.className = "bg-white/[0.02] text-[10px] font-black text-slate-500 uppercase tracking-widest";
    const headRow = document.createElement("tr");
    ["Periodo", "Valor", "Estado"].forEach(function (label) {
      const th = document.createElement("th");
      th.className = "px-6 py-4";
      th.textContent = label;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);

    const tbody = document.createElement("tbody");
    tbody.className = "text-sm";
    rows.forEach(function (row) {
      const tr = document.createElement("tr");
      tr.className = "border-t border-white/5 hover:bg-white/[0.02] transition-colors";

      const tdPeriod = document.createElement("td");
      tdPeriod.className = "px-6 py-4 text-slate-300 whitespace-nowrap";
      tdPeriod.textContent = row.period_end || "-";
      tr.appendChild(tdPeriod);

      const tdValue = document.createElement("td");
      tdValue.className = "px-6 py-4 text-slate-300 whitespace-nowrap";
      tdValue.textContent =
        row.value == null || !Number.isFinite(Number(row.value))
          ? "-"
          : Number(row.value).toFixed(2);
      tr.appendChild(tdValue);

      const tdStatus = document.createElement("td");
      tdStatus.className = "px-6 py-4 text-slate-300 whitespace-nowrap";
      tdStatus.textContent = row.status || "-";
      tr.appendChild(tdStatus);

      tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);
    relatedPerformanceTableContainer.appendChild(table);
    setRelatedPerformanceExportState(rows);
  }

  function hideRelatedPerformanceSection() {
    if (!hasRelatedPerformanceUi()) {
      return;
    }
    relatedPerformanceIndicators = [];
    relatedPerformancePayload = null;
    relatedPerformanceRequestSeq += 1;
    setRelatedPerformanceFrequencyDisplay("MONTHLY");
    if (relatedPerformanceSection) {
      relatedPerformanceSection.classList.add("hidden");
    }
    closeRelatedPerformanceTableModal();
    if (relatedPerformanceIndicatorSelect) {
      relatedPerformanceIndicatorSelect.innerHTML = "";
    }
    if (relatedPerformanceChart) {
      relatedPerformanceChart.clear();
    }
    if (relatedPerformanceEmpty) {
      relatedPerformanceEmpty.classList.add("hidden");
    }
    renderRelatedPerformanceTable({ rows: [] });
  }

  function buildRelatedPerformanceIndicatorLabel(indicator) {
    if (!indicator) {
      return "Formula";
    }
    const prefix = indicator.entity_code ? `[${indicator.entity_code}] ` : "";
    return `${prefix}${indicator.label || indicator.key || "Formula"}`;
  }

  function normalizeRelatedPerformanceFrequency(value) {
    const raw = String(value || "").toUpperCase();
    return raw === "DAILY" ? "DAILY" : "MONTHLY";
  }

  function formatRelatedPerformanceFrequencyLabel(value) {
    const freq = normalizeRelatedPerformanceFrequency(value);
    return freq === "DAILY" ? "Diaria" : "Mensual";
  }

  function setRelatedPerformanceFrequencyDisplay(value) {
    relatedPerformanceCurrentFrequency = normalizeRelatedPerformanceFrequency(value);
    if (!relatedPerformanceFrequencyBadge) {
      return;
    }
    relatedPerformanceFrequencyBadge.textContent = formatRelatedPerformanceFrequencyLabel(
      relatedPerformanceCurrentFrequency
    );
  }

  function populateRelatedPerformanceIndicators(indicators) {
    if (!relatedPerformanceIndicatorSelect) {
      return;
    }
    relatedPerformanceIndicatorSelect.innerHTML = "";
    (indicators || []).forEach(function (indicator, index) {
      const opt = document.createElement("option");
      opt.value = String(indicator.id);
      opt.textContent = buildRelatedPerformanceIndicatorLabel(indicator);
      relatedPerformanceIndicatorSelect.appendChild(opt);
      if (index === 0) {
        relatedPerformanceIndicatorSelect.value = String(indicator.id);
      }
    });
  }

  function buildRelatedPerformanceChartOption(payload) {
    if (!payload || !Array.isArray(payload.rows) || !payload.rows.length) {
      return null;
    }

    const validRows = payload.rows.filter(function (row) {
      return row && row.period_end;
    });
    if (!validRows.length) {
      return null;
    }

    const labels = validRows.map(function (row) { return row.period_end; });
    const values = validRows.map(function (row) {
      return row.value == null || !Number.isFinite(Number(row.value)) ? null : Number(row.value);
    });
    const chartType = (relatedPerformanceChartTypeSelect && relatedPerformanceChartTypeSelect.value) || "line";
    const seriesType = chartType === "bar" ? "bar" : "line";
    const granularity = inferDateGranularity(labels);
    const color = "#22d3ee";
    const indicator = payload.indicator || {};

    return {
      animationDurationUpdate: 220,
      animationEasingUpdate: "cubicOut",
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 23, 42, 0.95)",
        borderColor: "rgba(34, 211, 238, 0.2)",
        borderWidth: 1,
        borderRadius: 12,
        padding: [10, 12],
        textStyle: { color: "#f8fafc", fontSize: 12, fontFamily: "Lexend" },
        formatter: function (params) {
          const item = Array.isArray(params) ? params[0] : params;
          if (!item) return "";
          const numericValue = item.value == null || !Number.isFinite(Number(item.value)) ? null : Number(item.value);
          const unit = indicator.unit ? ` ${indicator.unit}` : "";
          return (
            `<div style="font-family:Lexend, sans-serif;">` +
            `<div style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:#67e8f9;opacity:.9;margin-bottom:2px;">Periodo</div>` +
            `<div style="font-size:13px;font-weight:700;color:#f8fafc;">${formatDateLong(item.axisValue)}</div>` +
            `<div style="display:flex;justify-content:space-between;gap:12px;margin-top:6px;">` +
            `<span style="color:#cbd5e1;">Valor</span>` +
            `<span style="font-weight:700;color:#fff;">${formatMetricValue(numericValue)}${unit}</span>` +
            `</div>` +
            `</div>`
          );
        },
      },
      grid: { left: 56, right: 18, top: 40, bottom: 64, containLabel: true },
      xAxis: {
        type: "category",
        data: labels,
        boundaryGap: seriesType === "bar",
        axisLine: { lineStyle: { color: "rgba(148,163,184,0.18)" } },
        axisTick: { show: false },
        axisLabel: {
          color: "#94a3b8",
          fontSize: 10,
          margin: 10,
          hideOverlap: true,
          formatter: function (value) {
            return formatDateShort(value, granularity);
          },
        },
      },
      yAxis: {
        type: "value",
        name: indicator.unit ? `(${indicator.unit})` : "Valores",
        nameGap: 18,
        nameTextStyle: { color: "#94a3b8", fontSize: 10, fontWeight: 600, padding: [0, 0, 8, 0] },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: "#94a3b8",
          fontSize: 10,
          formatter: function (value) {
            return formatMetricValue(value);
          },
        },
        splitLine: {
          show: true,
          lineStyle: { color: "rgba(148,163,184,0.1)", type: [4, 4] },
        },
      },
      dataZoom: [
        { type: "inside", xAxisIndex: 0, start: 0, end: 100 },
        {
          type: "slider",
          xAxisIndex: 0,
          height: 36,
          bottom: 0,
          showDetail: false,
          brushSelect: false,
          borderRadius: 10,
          backgroundColor: "rgba(15,23,42,0.42)",
          handleStyle: { color: "#22d3ee", borderColor: "#1e293b" },
          fillerColor: "rgba(34,211,238,0.08)",
          borderColor: "rgba(255,255,255,0.03)",
          labelFormatter: function (value) { return formatDateShort(value, granularity); },
        },
      ],
      series: [
        {
          name: indicator.label || indicator.key || "Formula",
          type: seriesType,
          data: values,
          smooth: seriesType === "line",
          showSymbol: seriesType === "line" && labels.length <= 48,
          symbolSize: 5,
          connectNulls: false,
          lineStyle: { width: 3, color: color },
          itemStyle: {
            color:
              seriesType === "bar"
                ? new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: "#22d3eedd" },
                    { offset: 1, color: "#0891b2aa" },
                  ])
                : color,
            borderRadius: seriesType === "bar" ? [7, 7, 0, 0] : 0,
          },
          areaStyle:
            seriesType === "line"
              ? {
                  opacity: 0.14,
                  color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: "#22d3ee66" },
                    { offset: 1, color: "#22d3ee00" },
                  ]),
                }
              : undefined,
        },
      ],
    };
  }

  function renderRelatedPerformancePayload(payload) {
    relatedPerformancePayload = payload || null;
    if (payload && payload.frequency) {
      setRelatedPerformanceFrequencyDisplay(payload.frequency);
    }
    const rows = payload && Array.isArray(payload.rows) ? payload.rows : [];
    const hasRows = rows.some(function (row) {
      return row && row.value != null && Number.isFinite(Number(row.value));
    });

    const relatedChart = ensureRelatedPerformanceChart();
    if (relatedChart && relatedPerformanceChartContainer) {
      relatedPerformanceChartContainer.style.height = relatedPerformanceBaseChartHeight;
      const option = buildRelatedPerformanceChartOption(payload);
      if (option && hasRows) {
        relatedChart.setOption(option, true);
      } else {
        relatedChart.clear();
      }
      relatedChart.resize();
      resizeRelatedPerformanceChartSoon();
    }

    if (relatedPerformanceEmpty) {
      relatedPerformanceEmpty.classList.toggle("hidden", hasRows);
    }
    renderRelatedPerformanceTable(payload);

    const indicator = payload && payload.indicator ? payload.indicator : getRelatedPerformanceSelectedIndicator();
    if (relatedPerformanceHelp) {
      relatedPerformanceHelp.textContent = indicator
        ? `Formula seleccionada: ${buildRelatedPerformanceIndicatorLabel(indicator)}`
        : "Se muestra cuando el dataset seleccionado participa en una formula aprobada.";
    }
  }

  function currentRelatedPerformanceRangeParams() {
    const params = new URLSearchParams();
    if (dateStartInput && dateStartInput.value) {
      params.set("date_start", dateStartInput.value);
    }
    if (dateEndInput && dateEndInput.value) {
      params.set("date_end", dateEndInput.value);
    }
    return params;
  }

  function loadRelatedPerformanceData() {
    if (!hasRelatedPerformanceUi() || !relatedPerformanceIndicators.length) {
      return;
    }
    const indicator = getRelatedPerformanceSelectedIndicator();
    if (!indicator) {
      hideRelatedPerformanceSection();
      return;
    }

    const seq = ++relatedPerformanceRequestSeq;
    const params = currentRelatedPerformanceRangeParams();
    params.set("frequency", normalizeRelatedPerformanceFrequency(relatedPerformanceCurrentFrequency));

    fetch(`/kpis/performance-data/${encodeURIComponent(indicator.id)}/?${params.toString()}`)
      .then(function (resp) {
        if (!resp.ok) {
          throw new Error("Error al cargar formula relacionada");
        }
        return resp.json();
      })
      .then(function (payload) {
        if (seq !== relatedPerformanceRequestSeq) {
          return;
        }
        if (relatedPerformanceSection) {
          relatedPerformanceSection.classList.remove("hidden");
        }
        resizeRelatedPerformanceChartSoon();
        renderRelatedPerformancePayload(payload);
      })
      .catch(function (err) {
        console.error(err);
        if (seq !== relatedPerformanceRequestSeq) {
          return;
        }
        renderRelatedPerformancePayload({ indicator: indicator, rows: [] });
      });
  }

  function syncRelatedPerformanceFromDatasetPayload(datasetPayload) {
    if (!hasRelatedPerformanceUi()) {
      return;
    }
    const indicators = Array.isArray(datasetPayload && datasetPayload.related_performance_indicators)
      ? datasetPayload.related_performance_indicators
      : [];

    if (!indicators.length) {
      hideRelatedPerformanceSection();
      return;
    }

    relatedPerformanceIndicators = indicators.slice();
    populateRelatedPerformanceIndicators(relatedPerformanceIndicators);

    const first = relatedPerformanceIndicators[0];
    if (first) {
      setRelatedPerformanceFrequencyDisplay(first.frequency);
    }
    if (relatedPerformanceSection) {
      relatedPerformanceSection.classList.remove("hidden");
    }
    loadRelatedPerformanceData();
  }

  function buildRelatedPerformanceExportRows() {
    const payload = relatedPerformancePayload;
    if (!payload || !Array.isArray(payload.rows)) {
      return { columns: [], rows: [] };
    }
    const rows = payload.rows.map(function (row) {
      return [row.period_end || "", row.value != null ? row.value : "", row.status || ""];
    });
    return {
      columns: ["Periodo", "Valor", "Estado"],
      rows: rows,
    };
  }

  function buildRelatedPerformanceExportBaseName() {
    const indicator = getRelatedPerformanceSelectedIndicator() || (relatedPerformancePayload && relatedPerformancePayload.indicator);
    const freq = normalizeRelatedPerformanceFrequency(relatedPerformanceCurrentFrequency);
    const indicatorName = sanitizeFileName((indicator && (indicator.label || indicator.key)) || "formula");
    const entityCode = sanitizeFileName((indicator && indicator.entity_code) || (currentData && currentData.dataset && currentData.dataset.entity_code) || "");
    const range = [dateStartInput && dateStartInput.value, dateEndInput && dateEndInput.value].filter(Boolean).join("_a_");
    return ["sicgad", entityCode, "formula", indicatorName, freq.toLowerCase(), sanitizeFileName(range)]
      .filter(Boolean)
      .join("_");
  }

  function exportRelatedPerformanceCsvFile() {
    const data = buildRelatedPerformanceExportRows();
    if (!data.rows.length) {
      return;
    }
    const header = data.columns.map((col) => escapeCsv(col)).join(",");
    const lines = data.rows.map(function (row) {
      return row.map(escapeCsv).join(",");
    });
    const blob = new Blob([[header, ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    downloadBlob(blob, `${buildRelatedPerformanceExportBaseName()}.csv`);
  }

  function exportRelatedPerformanceExcelFile() {
    const data = buildRelatedPerformanceExportRows();
    if (!data.rows.length) {
      return;
    }
    ensureXlsxLoaded()
      .then(function () {
        if (!window.XLSX) {
          throw new Error("XLSX no disponible para exportar.");
        }
        const worksheet = window.XLSX.utils.aoa_to_sheet([data.columns, ...data.rows]);
        const workbook = window.XLSX.utils.book_new();
        window.XLSX.utils.book_append_sheet(workbook, worksheet, "Formula");
        window.XLSX.writeFile(workbook, `${buildRelatedPerformanceExportBaseName()}.xlsx`);
      })
      .catch(function (err) {
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
      closeKpiTableModal();
      updateAuthorityCards(null, []);
      if (tableContainer) {
        tableContainer.innerHTML = "";
      }
      updateExportState([]);
      hideRelatedPerformanceSection();
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
        syncKpiControlsPanelHeight();
        syncRelatedPerformanceFromDatasetPayload(data);
      })
      .catch((err) => {
        console.error(err);
        hideRelatedPerformanceSection();
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
  if (kpiTableModalOpenButton) {
    kpiTableModalOpenButton.addEventListener("click", openKpiTableModal);
  }
  if (kpiTableModalCloseButton) {
    kpiTableModalCloseButton.addEventListener("click", closeKpiTableModal);
  }
  if (kpiTableModalBackdrop) {
    kpiTableModalBackdrop.addEventListener("click", closeKpiTableModal);
  }
  if (relatedPerformanceTableModalOpenButton) {
    relatedPerformanceTableModalOpenButton.addEventListener("click", openRelatedPerformanceTableModal);
  }
  if (relatedPerformanceTableModalCloseButton) {
    relatedPerformanceTableModalCloseButton.addEventListener("click", closeRelatedPerformanceTableModal);
  }
  if (relatedPerformanceTableModalBackdrop) {
    relatedPerformanceTableModalBackdrop.addEventListener("click", closeRelatedPerformanceTableModal);
  }
  if (tableToggleButton) {
    tableToggleButton.addEventListener("click", function () {
      applyKpiTableVisibility(!isKpiTableHidden);
    });
  }
  if (relatedPerformanceIndicatorSelect) {
    relatedPerformanceIndicatorSelect.addEventListener("change", function () {
      const selected = getRelatedPerformanceSelectedIndicator();
      if (selected) {
        setRelatedPerformanceFrequencyDisplay(selected.frequency);
      }
      loadRelatedPerformanceData();
    });
  }
  if (relatedPerformanceChartTypeSelect) {
    relatedPerformanceChartTypeSelect.addEventListener("change", function () {
      renderRelatedPerformancePayload(relatedPerformancePayload);
    });
  }
  if (relatedPerformanceExportCsv) {
    relatedPerformanceExportCsv.addEventListener("click", exportRelatedPerformanceCsvFile);
  }
  if (relatedPerformanceExportExcel) {
    relatedPerformanceExportExcel.addEventListener("click", exportRelatedPerformanceExcelFile);
  }
  if (presentationButton) {
    presentationButton.addEventListener("click", togglePresentationMode);
  }
  document.addEventListener("fullscreenchange", syncChartPresentationUi);
  document.addEventListener("webkitfullscreenchange", syncChartPresentationUi);
  document.addEventListener("keydown", handleGlobalKeydown);
  window.addEventListener("resize", function () {
    resizeChartSoon();
    if (relatedPerformanceChart) {
      window.requestAnimationFrame(function () {
        relatedPerformanceChart.resize();
      });
    }
    syncKpiControlsPanelHeight();
    syncYFieldBoxHeight();
  });

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
  if (tableToggleButton) {
    applyKpiTableVisibility(getStoredKpiTableHidden());
  } else {
    updateExportState([]);
  }
  setRelatedPerformanceFrequencyDisplay("MONTHLY");
  hideRelatedPerformanceSection();
  loadInstanceData();
  syncChartPresentationUi();
  syncKpiControlsPanelHeight();
  syncYFieldBoxHeight();

});
