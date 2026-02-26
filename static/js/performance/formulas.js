document.addEventListener('DOMContentLoaded', function () {
  const chartDom = document.getElementById('chart');
  if (!chartDom) return;
  if (typeof echarts === 'undefined') return;

  const parseJsonAttr = (raw) => {
    const source = raw || '[]';
    try {
      return JSON.parse(source);
    } catch (_) {
      // json.dumps can emit NaN/Infinity if upstream values are non-finite.
      const sanitized = source
        .replace(/\bNaN\b/g, 'null')
        .replace(/\b-Infinity\b/g, 'null')
        .replace(/\bInfinity\b/g, 'null');
      try {
        return JSON.parse(sanitized);
      } catch (_) {
        return [];
      }
    }
  };

  const labelsRaw = parseJsonAttr(chartDom.getAttribute('data-labels'));
  const valuesRaw = parseJsonAttr(chartDom.getAttribute('data-values'));
  const labels = Array.isArray(labelsRaw) ? labelsRaw : [];
  const values = (Array.isArray(valuesRaw) ? valuesRaw : []).map((v) => {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  });
  const seriesName = chartDom.getAttribute('data-series-name') || 'Valor';

  const myChart = echarts.init(chartDom);

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0f172a',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#fff', fontSize: 10 },
      formatter: function (params) {
        let res = `<div class="font-bold mb-1">${params[0].name}</div>`;
        params.forEach(item => {
          const displayValue = item.value == null ? 'N/D' : item.value.toLocaleString();
          res += `<div class="flex items-center gap-2">
                        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${item.color}"></span>
                        <span class="text-slate-400">${item.seriesName}:</span>
                        <span class="font-mono text-emerald-400">${displayValue}</span>
                    </div>`;
        });
        return res;
      }
    },
    grid: {
      top: '15%',
      left: '3%',
      right: '4%',
      bottom: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
      axisLabel: { color: '#64748b', fontSize: 10, fontWeight: 700 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.02)', type: 'dashed' } },
      axisLabel: { color: '#64748b', fontSize: 10, fontWeight: 700 }
    },
    series: [
      {
        name: seriesName,
        data: values,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: { color: '#10b981' },
        lineStyle: { width: 3, shadowBlur: 10, shadowColor: 'rgba(16, 185, 129, 0.5)' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(16, 185, 129, 0.2)' },
            { offset: 1, color: 'rgba(16, 185, 129, 0)' }
          ])
        }
      }
    ]
  };

  myChart.setOption(option);

  window.addEventListener('resize', function () {
    myChart.resize();
  });
});
