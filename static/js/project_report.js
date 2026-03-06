document.addEventListener("DOMContentLoaded", function () {
  const labelsEl = document.getElementById("project-curve-labels");
  const programEl = document.getElementById("project-curve-program");
  const executedEl = document.getElementById("project-curve-executed");
  const kindEl = document.getElementById("project-curve-kind");
  const chartEl = document.getElementById("project-curve-chart");
  if (!labelsEl || !programEl || !executedEl || !kindEl || !chartEl || !window.echarts) {
    return;
  }

  const labels = JSON.parse(labelsEl.textContent || "[]");
  const program = normalizeSeries(JSON.parse(programEl.textContent || "[]"));
  const executed = normalizeSeries(JSON.parse(executedEl.textContent || "[]"));
  const chartKind = JSON.parse(kindEl.textContent || '"line"');
  if (!Array.isArray(labels) || !labels.length) {
    return;
  }

  const numberFormatter = new Intl.NumberFormat("es-CL", {
    maximumFractionDigits: 1,
  });
  const isBar = chartKind === "bar";

  function normalizeSeries(values) {
    if (!Array.isArray(values)) {
      return [];
    }

    return values.map(function (value) {
      if (value == null || value === "") {
        return null;
      }
      if (typeof value === "number") {
        return Number.isFinite(value) ? value : null;
      }

      const normalized = Number(String(value).replace(",", "."));
      return Number.isFinite(normalized) ? normalized : null;
    });
  }

  const valueFormatter = function (value) {
    if (value == null) {
      return "-";
    }
    return `${numberFormatter.format(value)}%`;
  };

  function buildOption() {
    const width = chartEl.clientWidth || window.innerWidth || 1024;
    const isCompact = width < 640;
    const isTablet = width >= 640 && width < 1024;
    const shouldShowPointLabels = !isCompact && labels.length <= 8;
    const xAxisRotation = isBar
      ? labels.length > (isCompact ? 4 : 6)
        ? (isCompact ? 44 : 24)
        : 0
      : labels.length > (isCompact ? 5 : 8)
      ? (isCompact ? 36 : 18)
      : 0;

    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 23, 42, 0.95)",
        borderColor: "#1f2937",
        textStyle: { color: "#e2e8f0", fontSize: isCompact ? 10 : 11 },
        axisPointer: {
          type: isBar ? "shadow" : "line",
          lineStyle: { color: "#38bdf8", width: 1 },
        },
        valueFormatter: valueFormatter,
      },
      legend: {
        top: 0,
        icon: "roundRect",
        itemWidth: isCompact ? 10 : 14,
        itemHeight: isCompact ? 8 : 10,
        textStyle: {
          color: "#cbd5e1",
          fontSize: isCompact ? 10 : 11,
          fontWeight: 700,
        },
      },
      grid: {
        left: isCompact ? 20 : isTablet ? 32 : 46,
        right: isCompact ? 12 : 24,
        top: isCompact ? 44 : 36,
        bottom: xAxisRotation ? (isCompact ? 58 : 48) : isCompact ? 28 : 40,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.2)" } },
        axisTick: { show: false },
        axisLabel: {
          color: "#94a3b8",
          fontSize: isCompact ? 9 : 11,
          fontWeight: 700,
          interval: 0,
          rotate: xAxisRotation,
          margin: isCompact ? 10 : 12,
        },
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: "#94a3b8",
          fontSize: isCompact ? 9 : 10,
          formatter: valueFormatter,
        },
        splitLine: {
          show: true,
          lineStyle: { color: "rgba(148, 163, 184, 0.12)" },
        },
      },
      series: [
        {
          name: isBar ? "Planificado" : "PROG.",
          type: isBar ? "bar" : "line",
          smooth: !isBar,
          showSymbol: !isBar && !isCompact,
          symbol: "circle",
          symbolSize: isCompact ? 5 : 7,
          barMaxWidth: isBar ? (isCompact ? 22 : 36) : null,
          lineStyle: { width: isCompact ? 2.2 : 3, color: "#38bdf8" },
          itemStyle: {
            color: "#38bdf8",
            borderRadius: isBar ? [8, 8, 0, 0] : 0,
          },
          label: {
            show: shouldShowPointLabels,
            position: "top",
            color: "#7dd3fc",
            fontSize: 10,
            fontWeight: 700,
            formatter: ({ value }) => valueFormatter(value),
          },
          data: program,
        },
        {
          name: "EJECUT.",
          type: isBar ? "bar" : "line",
          smooth: !isBar,
          showSymbol: !isBar && !isCompact,
          symbol: "circle",
          symbolSize: isCompact ? 5 : 7,
          barMaxWidth: isBar ? (isCompact ? 22 : 36) : null,
          lineStyle: { width: isCompact ? 2.2 : 3, color: "#34d399" },
          itemStyle: {
            color: "#34d399",
            borderRadius: isBar ? [8, 8, 0, 0] : 0,
          },
          label: {
            show: shouldShowPointLabels,
            position: "top",
            color: "#6ee7b7",
            fontSize: 10,
            fontWeight: 700,
            formatter: ({ value }) => valueFormatter(value),
          },
          data: executed,
        },
      ],
    };
  }

  let chart = null;
  let resizeObserver = null;

  function ensureChartReady(attempt) {
    const maxAttempts = 12;
    const width = chartEl.clientWidth;
    const height = chartEl.clientHeight;

    if ((width < 24 || height < 24) && attempt < maxAttempts) {
      window.requestAnimationFrame(function () {
        ensureChartReady(attempt + 1);
      });
      return;
    }

    if (!chart) {
      chart = echarts.init(chartEl);
    }
    chart.setOption(buildOption(), true);
    chart.resize();
  }

  ensureChartReady(0);

  window.addEventListener("resize", function () {
    if (chart) {
      chart.setOption(buildOption(), true);
      chart.resize();
    }
  });

  if ("ResizeObserver" in window) {
    resizeObserver = new ResizeObserver(function () {
      if (chart) {
        chart.setOption(buildOption(), true);
        chart.resize();
      } else {
        ensureChartReady(0);
      }
    });
    resizeObserver.observe(chartEl);
  }
});
