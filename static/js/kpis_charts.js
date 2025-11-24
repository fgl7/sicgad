document.addEventListener("DOMContentLoaded", function () {
  const modeSelect = document.getElementById("kpi-mode-select");
  const instanceSelect = document.getElementById("kpi-instance-select");
  const xFieldSelect = document.getElementById("kpi-x-field-select");
  const yFieldSelect = document.getElementById("kpi-y-field-select");
  const chartContainer = document.getElementById("kpi-chart");
  const tableContainer = document.getElementById("kpi-table-container");

  if (!modeSelect || !instanceSelect || !xFieldSelect || !yFieldSelect || !chartContainer) {
    return;
  }

  let chart = null;
  if (window.echarts) {
    chart = echarts.init(chartContainer);
  }

  let currentData = null;

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
      return { x: null, y: null };
    }

    let xField = null;
    let yField = null;

    // X: preferir axis_role X, luego DATE, luego la primera
    xField =
      columns.find((c) => c.axis_role === "X") ||
      columns.find((c) => c.data_type === "DATE") ||
      columns[0];

    // Y: preferir numérico y marcado como KPI principal
    const numericCols = columns.filter(
      (c) => c.data_type === "INTEGER" || c.data_type === "FLOAT"
    );
    yField =
      numericCols.find((c) => c.is_primary_kpi) ||
      numericCols[0] ||
      columns[0];

    return { x: xField ? xField.name : null, y: yField ? yField.name : null };
  }

  function populateFieldSelectors(columns) {
    xFieldSelect.innerHTML = "";
    yFieldSelect.innerHTML = "";

    if (!columns || !columns.length) {
      return;
    }

    columns.forEach(function (col) {
      const label = col.label || col.name;

      const optX = document.createElement("option");
      optX.value = col.name;
      optX.textContent = label;
      xFieldSelect.appendChild(optX);

      const optY = document.createElement("option");
      optY.value = col.name;
      optY.textContent = label;
      yFieldSelect.appendChild(optY);
    });

    const defaults = chooseDefaultFields(columns);
    if (defaults.x) {
      xFieldSelect.value = defaults.x;
    }
    if (defaults.y) {
      yFieldSelect.value = defaults.y;
    }
  }

  function buildChartOptions(data) {
    if (!data || !data.columns || !data.rows) {
      return null;
    }

    const xName = xFieldSelect.value;
    const yName = yFieldSelect.value;
    if (!xName || !yName) {
      return null;
    }

    const xCol = data.columns.find((c) => c.name === xName);
    const yCol = data.columns.find((c) => c.name === yName);
    if (!xCol || !yCol) {
      return null;
    }

    const xValues = [];
    const yValues = [];

    data.rows.forEach(function (row) {
      const values = row.values || {};
      xValues.push(values[xName] ?? null);
      yValues.push(values[yName] != null ? Number(values[yName]) : null);
    });

    const xIsTime = xCol.data_type === "DATE";

    return {
      tooltip: { trigger: "axis" },
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
      xAxis: {
        type: xIsTime ? "category" : "category",
        data: xValues,
        name: xCol.label || xCol.name,
        axisLabel: { rotate: xIsTime ? 45 : 0 },
      },
      yAxis: {
        type: "value",
        name: (yCol.label || yCol.name) + (yCol.unit ? ` (${yCol.unit})` : ""),
      },
      series: [
        {
          name: yCol.label || yCol.name,
          type: "line",
          smooth: true,
          showSymbol: false,
          data: yValues,
        },
      ],
    };
  }

  function renderTable(data) {
    if (!tableContainer) {
      return;
    }
    tableContainer.innerHTML = "";

    if (!data || !data.columns || !data.rows || !data.rows.length) {
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
    data.rows.forEach(function (row) {
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
    const option = buildChartOptions(currentData);
    if (option) {
      chart.setOption(option, true);
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
        updateChart();
        renderTable(data);
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

  xFieldSelect.addEventListener("change", updateChart);
  yFieldSelect.addEventListener("change", updateChart);

  filterInstancesByMode();
});

