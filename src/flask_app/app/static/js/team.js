document.addEventListener('DOMContentLoaded', function () {
  const isDark    = document.documentElement.getAttribute('data-theme') !== 'light';
  const gridColor = isDark ? '#1e2e1e' : '#e0e0e0';
  const tickColor = isDark ? '#9e9e9e' : '#555555';
  const cfg       = window.TEAM_CONFIG;

  // Theme the charts to match the design system (default Chart.js Arial +
  // gray tooltip clashed with the Barlow/Inter + dark-green identity).
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.color = tickColor;
  Chart.defaults.plugins.tooltip.backgroundColor = isDark ? '#111a11' : '#ffffff';
  Chart.defaults.plugins.tooltip.titleColor = isDark ? '#f5f5f5' : '#0a0f0a';
  Chart.defaults.plugins.tooltip.bodyColor = isDark ? '#9e9e9e' : '#4a5a4a';
  Chart.defaults.plugins.tooltip.borderColor = isDark ? '#1e2e1e' : '#c8d8c8';
  Chart.defaults.plugins.tooltip.borderWidth = 1;

  const baseScales = {
    x: { ticks: { autoSkip: true, maxTicksLimit: 20, color: tickColor }, grid: { color: gridColor } },
    y: { ticks: { color: tickColor }, grid: { color: gridColor } }
  };

  if (cfg.eloData.length > 0) {
    new Chart(document.getElementById('eloChart').getContext('2d'), {
      type: 'line',
      data: {
        labels:   cfg.eloData.map(d => d.label),
        datasets: [{ label: cfg.labelElo, data: cfg.eloData.map(d => d.rating),
          borderColor: '#00e676', backgroundColor: 'rgba(0,230,118,0.1)',
          fill: true, tension: 0.1, pointRadius: 1, borderWidth: 2 }]
      },
      options: {
        scales: baseScales,
        plugins: { zoom: { pan: { enabled: true, mode: 'x' }, zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' } } }
      }
    });
  }

  if (cfg.positionData.length > 0) {
    new Chart(document.getElementById('positionChart').getContext('2d'), {
      type: 'line',
      data: {
        labels:   cfg.positionData.map(d => d.season),
        datasets: [{ label: cfg.labelPosition, data: cfg.positionData.map(d => d.position),
          spanGaps: true, fill: true,
          borderColor: '#ffc400', backgroundColor: 'rgba(255,196,0,0.1)', tension: 0.1 }]
      },
      options: {
        scales: {
          x: baseScales.x,
          y: { reverse: true, beginAtZero: false, ticks: { stepSize: 1, color: tickColor }, grid: { color: gridColor } }
        }
      }
    });
  }

  // ── wykresy sezonowe ──
  function createChart(canvasId, label, data, color, yExtra = {}) {
    if (!data || data.length === 0) return;
    new Chart(document.getElementById(canvasId).getContext('2d'), {
      type: 'line',
      data: {
        labels:   data.map(d => d.matchday),
        datasets: [{ label, data: data.map(d => d.value),
          borderColor: color, backgroundColor: color.replace('1)', '0.15)'),
          fill: true, tension: 0.1 }]
      },
      options: {
        scales: {
          x: { title: { display: true, text: cfg.labelMatchday, color: tickColor }, ticks: { color: tickColor }, grid: { color: gridColor } },
          y: { ticks: { color: tickColor }, grid: { color: gridColor }, ...yExtra }
        },
        plugins: { zoom: { pan: { enabled: true, mode: 'x' }, zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' } } }
      }
    });
  }

  createChart('seasonEloChart',           cfg.labelElo,           cfg.chartData.elo,           'rgba(0, 230, 118, 1)');
  createChart('seasonPointsChart',        cfg.labelPoints,        cfg.chartData.points,        'rgba(41, 182, 246, 1)');
  createChart('seasonGoalsForChart',      cfg.labelGoalsFor,      cfg.chartData.goalsFor,      'rgba(0, 230, 118, 1)');
  createChart('seasonGoalsConcededChart', cfg.labelGoalsConceded, cfg.chartData.goalsConceded, 'rgba(255, 23, 68, 1)');
  createChart('seasonPositionChart',      cfg.labelPosition,      cfg.chartData.position,      'rgba(255, 196, 0, 1)',
    { reverse: true, beginAtZero: false, ticks: { stepSize: 1, precision: 0, color: tickColor } });

  if (cfg.chartData.w_d_l && cfg.chartData.w_d_l.length > 0) {
    new Chart(document.getElementById('w_d_lChart').getContext('2d'), {
      type: 'line',
      data: {
        labels:   cfg.chartData.w_d_l.map(d => d.matchday),
        datasets: [
          { label: cfg.labelWins,   data: cfg.chartData.w_d_l.map(d => d.wins),   borderColor: 'rgba(0,230,118,1)',  backgroundColor: 'rgba(0,230,118,0.1)',  fill: false, tension: 0.1 },
          { label: cfg.labelDraws,  data: cfg.chartData.w_d_l.map(d => d.draws),  borderColor: 'rgba(255,214,0,1)',  backgroundColor: 'rgba(255,214,0,0.1)',  fill: false, tension: 0.1 },
          { label: cfg.labelLosses, data: cfg.chartData.w_d_l.map(d => d.losses), borderColor: 'rgba(255,23,68,1)',  backgroundColor: 'rgba(255,23,68,0.1)',  fill: false, tension: 0.1 }
        ]
      },
      options: {
        scales: {
          x: { title: { display: true, text: cfg.labelMatchday, color: tickColor }, ticks: { color: tickColor }, grid: { color: gridColor } },
          y: { title: { display: true, text: cfg.labelCount,    color: tickColor }, beginAtZero: true, ticks: { color: tickColor }, grid: { color: gridColor } }
        },
        plugins: { zoom: { pan: { enabled: true, mode: 'x' }, zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' } } }
      }
    });
  }
});
