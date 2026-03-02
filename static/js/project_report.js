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
  const program = JSON.parse(programEl.textContent || "[]");
  const executed = JSON.parse(executedEl.textContent || "[]");
  const chartKind = JSON.parse(kindEl.textContent || '"line"');
  if (!Array.isArray(labels) || !labels.length) {
    return;
  }

  const chart = echarts.init(chartEl);
  const numberFormatter = new Intl.NumberFormat("es-CL", {
    maximumFractionDigits: 1,
  });
  const isBar = chartKind === "bar";
  const valueFormatter = function (value) {
    if (value == null) {
      return "-";
    }
    return `${numberFormatter.format(value)}%`;
  };

  const option = {
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(15, 23, 42, 0.95)",
      borderColor: "#1f2937",
      textStyle: { color: "#e2e8f0", fontSize: 11 },
      axisPointer: {
        type: isBar ? "shadow" : "line",
        lineStyle: { color: "#38bdf8", width: 1 },
      },
      valueFormatter: valueFormatter,
    },
    legend: {
      top: 0,
      textStyle: { color: "#e2e8f0", fontSize: 11 },
    },
    grid: {
      left: 46,
      right: 24,
      top: 36,
      bottom: 40,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: labels,
      axisLine: { lineStyle: { color: "#1f2937" } },
      axisTick: { show: false },
      axisLabel: {
        color: "#94a3b8",
        fontSize: 10,
        interval: 0,
        rotate: isBar && labels.length > 6 ? 20 : 0,
      },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#94a3b8",
        fontSize: 10,
        formatter: valueFormatter,
      },
      splitLine: {
        show: true,
        lineStyle: { color: "rgba(148, 163, 184, 0.12)" },
      },
    },
    series: [
      {
        name: isBar ? "Planificado" : "Programado",
        type: isBar ? "bar" : "line",
        smooth: !isBar,
        showSymbol: false,
        barMaxWidth: isBar ? 36 : null,
        lineStyle: { width: 2, color: "#34d399" },
        itemStyle: {
          color: "#34d399",
          borderRadius: isBar ? [8, 8, 0, 0] : 0,
        },
        data: program,
      },
      {
        name: "Ejecutado",
        type: isBar ? "bar" : "line",
        smooth: !isBar,
        showSymbol: false,
        barMaxWidth: isBar ? 36 : null,
        lineStyle: { width: 2, color: "#38bdf8" },
        itemStyle: {
          color: "#38bdf8",
          borderRadius: isBar ? [8, 8, 0, 0] : 0,
        },
        data: executed,
      },
    ],
  };

  chart.setOption(option, true);
  window.addEventListener("resize", function () {
    chart.resize();
  });
});
