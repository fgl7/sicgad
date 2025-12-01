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

  function filterInstancesByMode() {
    const mode = modeSelect.value || "published";
    Array.from(instanceSelect.options).forEach(function (opt) {
      const optMode = opt.getAttribute("data-mode");
      if (!optMode) {
        return;
      }
      opt.hidden = optMode !== mode;
    });

    // Si la opción seleccionada no pertenece al modo actual, limpiar selección
    const selected = instanceSelect.options[instanceSelect.selectedIndex];
    if (selected && selected.getAttribute("data-mode") !== mode) {
      instanceSelect.value = "";
    }
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
    filterBounds.start = startValue ? new Date(startValue) : null;
    if (filterBounds.start) {
      filterBounds.start.setHours(0, 0, 0, 0);
    }
    filterBounds.end = endValue ? new Date(endValue) : null;
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
      const d = new Date(raw);
      if (Number.isNaN(d.getTime())) {
        return;
      }
      if (!minDate || d < minDate) {
        minDate = new Date(d);
      }
      if (!maxDate || d > maxDate) {
        maxDate = new Date(d);
      }
    });

    if (!minDate || !maxDate) {
      const today = new Date();
      minDate = new Date(today);
      maxDate = new Date(today);
    }

    const minStr = formatInputDate(minDate);
    const maxStr = formatInputDate(maxDate);

    dateStartInput.min = minStr;
    dateStartInput.max = maxStr;
    dateEndInput.min = minStr;
    dateEndInput.max = maxStr;

    dateStartInput.value = minStr;
    dateEndInput.value = maxStr;

    setFilterBounds(minStr, maxStr);
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
      const d = new Date(raw);
      if (Number.isNaN(d.getTime())) {
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
        const d = new Date(xVal);
        if (!Number.isNaN(d.getTime())) {
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

    const series = yCols.map(function (yCol) {
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
        data: values,
      };
    });

    const gridTop = yCols.length > 1 ? 52 : 28;

    return {
      tooltip: { trigger: "axis" },
      legend: {
        show: yCols.length > 1,
        top: 0,
        textStyle: {
          color: "#cbd5f5",
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
          fillerColor: "rgba(16, 185, 129, 0.2)",
          borderColor: "#1f2937",
        },
      ],
      grid: {
        left: 40,
        right: 16,
        top: gridTop,
        bottom: (xIsTime ? 45 : 28) + 40,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: xValues,
        name: xCol.label || xCol.name,
        axisLabel: {
          rotate: xIsTime ? 30 : 0,
          fontSize: 9,
          margin: 6,
        },
      },
      yAxis: {
        type: "value",
        name:
          yCols.length === 1
            ? (yCols[0].label || yCols[0].name) +
              (yCols[0].unit ? ` (${yCols[0].unit})` : "")
            : "Valores",
        axisLabel: {
          margin: 6,
          fontSize: 9,
          formatter: function (value) {
            return numberFormatter.format(value);
          },
        },
      },
      series: series,
    };
  }

  function renderTable(data, rowsOverride) {
    if (!tableContainer) {
      return;
    }
    tableContainer.innerHTML = "";

    if (!data || !data.columns) {
      return;
    }

    const rows = rowsOverride != null ? rowsOverride : data.rows || [];

    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "p-3 text-[11px] text-slate-400";
      empty.textContent = "No hay datos para mostrar.";
      tableContainer.appendChild(empty);
      return;
    }

    const table = document.createElement("table");
    table.className = "min-w-full text-[11px]";

    const thead = document.createElement("thead");
    thead.className = "bg-slate-950 text-slate-300";
    const headRow = document.createElement("tr");
    data.columns.forEach(function (col) {
      const th = document.createElement("th");
      th.className = "px-3 py-1 text-left font-semibold";
      th.textContent = col.label || col.name;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);

    const tbody = document.createElement("tbody");
    rows.forEach(function (row) {
      const tr = document.createElement("tr");
      tr.className = "border-t border-slate-800";
      data.columns.forEach(function (col) {
        const td = document.createElement("td");
        td.className = "px-3 py-1 align-top whitespace-nowrap";
        const v = (row.values || {})[col.name];
        td.textContent = v != null && v !== "" ? v : "-";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);
    tableContainer.appendChild(table);
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
    const instanceId = instanceSelect.value;
    const mode = modeSelect.value || "published";
    if (!instanceId) {
      currentData = null;
      if (chart) {
        chart.clear();
      }
      if (tableContainer) {
        tableContainer.innerHTML = "";
      }
      return;
    }

    fetch(`/kpis/data/${instanceId}/?source=${encodeURIComponent(
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
    filterInstancesByMode();
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

  filterInstancesByMode();
});
