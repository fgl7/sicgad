document.addEventListener("DOMContentLoaded", function () {
  const labelsEl = document.getElementById("project-curve-labels");
  const programEl = document.getElementById("project-curve-program");
  const executedEl = document.getElementById("project-curve-executed");
  const chartEl = document.getElementById("project-curve-chart");
  if (!labelsEl || !programEl || !executedEl || !chartEl || !window.echarts) {
    return;
  }

  const labels = JSON.parse(labelsEl.textContent || "[]");
  const program = JSON.parse(programEl.textContent || "[]");
  const executed = JSON.parse(executedEl.textContent || "[]");

  const chart = echarts.init(chartEl);
  const numberFormatter = new Intl.NumberFormat("es-CL", {
    maximumFractionDigits: 1,
  });

  const option = {
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(15, 23, 42, 0.95)",
      borderColor: "#1f2937",
      textStyle: { color: "#e2e8f0", fontSize: 11 },
      axisPointer: {
        type: "line",
        lineStyle: { color: "#38bdf8", width: 1 },
      },
      valueFormatter: function (value) {
        if (value == null) {
          return "-";
        }
        return `${numberFormatter.format(value)}%`;
      },
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
      axisLabel: { color: "#94a3b8", fontSize: 10 },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#94a3b8",
        fontSize: 10,
        formatter: function (value) {
          return `${numberFormatter.format(value)}%`;
        },
      },
      splitLine: {
        show: true,
        lineStyle: { color: "rgba(148, 163, 184, 0.12)" },
      },
    },
    series: [
      {
        name: "Programado",
        type: "line",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: "#34d399" },
        itemStyle: { color: "#34d399" },
        data: program,
      },
      {
        name: "Ejecutado",
        type: "line",
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: "#38bdf8" },
        itemStyle: { color: "#38bdf8" },
        data: executed,
      },
    ],
  };

  chart.setOption(option, true);
  window.addEventListener("resize", function () {
    chart.resize();
  });
});
