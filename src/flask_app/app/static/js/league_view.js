document.addEventListener('DOMContentLoaded', () => {
  const currentLeagueCode = window.LEAGUE_CONFIG.leagueCode;
  document.querySelectorAll('.sidebar-links a').forEach(link => {
    if (link.dataset.leagueCode === currentLeagueCode) link.classList.add('active-league');
  });
});

function exportStandingsCSV() {
  const table = document.querySelector('.standings-table table');
  if (!table) return;

  const rows     = table.querySelectorAll('tr');
  const csvLines = [];
  rows.forEach(row => {
    const cells = row.querySelectorAll('th, td');
    const line  = Array.from(cells).map(cell => '"' + cell.innerText.trim().replace(/"/g, '""') + '"');
    csvLines.push(line.join(','));
  });

  const csv      = csvLines.join('\n');
  const filename = `Pewniaczki_tabela_${window.LEAGUE_CONFIG.leagueName}_${window.LEAGUE_CONFIG.season}`
    .replace(/\s+/g, '_').replace(/\//g, '-') + '.csv';

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function changeSeason() {
  const seasonSelect = document.getElementById('season-select');
  const currentUrl   = new URL(window.location.href);
  currentUrl.searchParams.set('season', seasonSelect.value);
  currentUrl.searchParams.delete('matchday');
  window.location.href = currentUrl.toString();
}

function changeMatchday() {
  const matchdaySelect = document.getElementById('matchday-select');
  const currentUrl     = new URL(window.location.href);
  if (matchdaySelect.value) {
    currentUrl.searchParams.set('matchday', matchdaySelect.value);
  } else {
    currentUrl.searchParams.delete('matchday');
  }
  window.location.href = currentUrl.toString();
}