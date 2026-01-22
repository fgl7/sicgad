document.addEventListener("DOMContentLoaded", function () {
  const modeSelect = document.getElementById("kpi-mode-select");
  const instanceSelect = document.getElementById("kpi-instance-select");
  const xFieldSelect = document.getElementById("kpi-x-field-select");
  const yFieldBox = document.getElementById("kpi-y-field-box");
  const chartTypeSelect = document.getElementById("kpi-chart-type-select");
  const dateStartInput = document.getElementById("kpi-date-start");
  const dateEndInput = document.getElementById("kpi-date-end");
  const dateApplyButton = document.getElementById("kpi-date-apply");
  const chartContainer = document.getElementById("kpi-chart");
  const tableContainer = document.getElementById("kpi-table-container");
  const exportCsvButton = document.getElementById("kpi-export-csv");
  const exportExcelButton = document.getElementById("kpi-export-excel");

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

  const numberFormatter = new Intl.NumberFormat("es-CL", {
    maximumFractionDigits: 2,
  });

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
  const filterBounds = { start: null, end: null };

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
    const defaultStart = new Date(maxDate.getTime());
    defaultStart.setDate(defaultStart.getDate() - 29);
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
      if (xIsTime && xVal) {
        const d = parseDateValue(xVal);
        if (d) {
          const dd = String(d.getDate()).padStart(2, "0");
          const mm = String(d.getMonth() + 1).padStart(2, "0");
          const yyyy = d.getFullYear();
          xVal = `${dd}/${mm}/${yyyy}`;
        }
      }
      xValues.push(xVal);
    });
    const chartType = chartTypeSelect.value || "line";

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

    const seriesColors = ["#10b981", "#0ea5e9", "#f59e0b", "#ec4899", "#8b5cf6", "#f97316"];
    const series = yCols.map(function (yCol, idx) {
      const values = rows.map(function (row) {
        const raw = (row.values || {})[yCol.name];
        return raw != null && raw !== "" ? Number(raw) : null;
      });
      return {
        name: yCol.label || yCol.name,
        type: seriesType,
        smooth: smooth,
        stack: stack,
        showSymbol: seriesType === "line" ? false : true,
        lineStyle: { width: 2 },
        itemStyle: { color: seriesColors[idx % seriesColors.length] },
        data: values,
      };
    });

    const gridTop = yCols.length > 1 ? 56 : 32;

    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(3, 7, 18, 0.9)",
        borderColor: "rgba(255, 255, 255, 0.1)",
        borderWidth: 1,
        textStyle: { color: "#f8fafc", fontSize: 12, fontFamily: 'Inter' },
        axisPointer: {
          type: "line",
          lineStyle: { color: "rgba(16, 185, 129, 0.5)", width: 2 },
        },
      },
      legend: {
        show: yCols.length > 1,
        top: 0,
        textStyle: {
          color: "#e2e8f0",
          fontSize: 11,
        },
      },
      dataZoom: [
        {
          type: "inside",
          xAxisIndex: 0,
          start: 0,
          end: 100,
        },
        {
          type: "slider",
          xAxisIndex: 0,
          height: 40,
          bottom: 0,
          brushSelect: false,
          handleStyle: {
            color: "#34d399",
            borderColor: "#1f2937",
          },
          textStyle: {
            color: "#94a3b8",
          },
          fillerColor: "rgba(16, 185, 129, 0.1)",
          borderColor: "rgba(255, 255, 255, 0.05)",
        },
      ],
      grid: {
        left: 46,
        right: 24,
        top: gridTop,
        bottom: (xIsTime ? 48 : 30) + 40,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: xValues,
        name: xCol.label || xCol.name,
        axisLine: { lineStyle: { color: "#1f2937" } },
        axisTick: { show: false },
        axisLabel: {
          rotate: xIsTime ? 30 : 0,
          fontSize: 9,
          color: "#94a3b8",
          margin: 6,
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
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          margin: 6,
          fontSize: 9,
          color: "#94a3b8",
          formatter: function (value) {
            return numberFormatter.format(value);
          },
        },
        splitLine: {
          show: true,
          lineStyle: { color: "rgba(148, 163, 184, 0.12)" },
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
    rows.forEach(function (row) {
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
    const plant = sanitizeFileName(dataset.plant_code);
    const mode = sanitizeFileName(modeSelect.value || "published");
    let range = "";
    if (filterBounds.start && filterBounds.end) {
      range = `${formatInputDate(filterBounds.start)}_a_${formatInputDate(filterBounds.end)}`;
    }
    const pieces = ["sicgad", plant, name, mode, range].filter(Boolean);
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
    if (!window.XLSX) {
      console.error("XLSX no disponible para exportar.");
      return;
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
  }

  function updateChart() {
    if (!chart || !currentData) {
      return;
    }
    const rows = getFilteredRows(currentData.rows || []);
    const option = buildChartOptions(currentData, rows);
    if (option) {
      chart.setOption(option, true);
    } else {
      chart.clear();
    }
  }

  function loadInstanceData() {
    const datasetId = instanceSelect.value;
    const mode = modeSelect.value || "published";
    if (!datasetId) {
      currentData = null;
      if (chart) {
        chart.clear();
      }
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
        populateFieldSelectors(data.columns || []);
        updateDateInputs(currentColumns, data.rows || []);
        const filteredRows = getFilteredRows(data.rows || []);
        updateChart();
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
    loadInstanceData();
  });

  xFieldSelect.addEventListener("change", function () {
    updateDateInputs(currentColumns, currentData ? currentData.rows || [] : []);
    updateChart();
  });
  chartTypeSelect.addEventListener("change", updateChart);
  dateApplyButton.addEventListener("click", applyDateFilter);
  if (exportCsvButton) {
    exportCsvButton.addEventListener("click", exportCsv);
  }
  if (exportExcelButton) {
    exportExcelButton.addEventListener("click", exportExcel);
  }

});
