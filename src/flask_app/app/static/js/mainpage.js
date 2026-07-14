function slugify(name) {
  return name.toLowerCase().replace(/_/g, "-").replace(/ /g, "-");
}

function redirectToMatches() {
  const selectedDate = document.getElementById('date-picker').value;
  if (selectedDate) {
    window.location.href = `/main?date=${selectedDate}`;
  } else {
    alert(window.MAINPAGE_CONFIG.msgPickDate);
  }
}

async function fetchMatches() {
  const selectedDate      = document.getElementById('date-picker').value;
  const matchesContainer  = document.getElementById('matches-container');
  const leagueFilter      = document.getElementById('league-filter');
  const sortOrder         = document.getElementById('sort-order');
  const cfg               = window.MAINPAGE_CONFIG;

  matchesContainer.innerHTML = '';
  if (!selectedDate) {
    matchesContainer.innerHTML = `<p class="info-message">${cfg.msgPickDate}</p>`;
    return;
  }

  try {
    const response = await fetch(`/api/matches?date=${selectedDate}`);
    const data     = await response.json();

    if (data.error) { matchesContainer.innerHTML = `<p class="error-message">${data.error}</p>`; return; }
    if (data.length === 0) { matchesContainer.innerHTML = `<p class="info-message">${cfg.msgNoMatches}</p>`; return; }

    if (leagueFilter.options.length <= 1) {
      const uniqueLeagues = new Set();
      data.forEach(match => uniqueLeagues.add(match.league));
      uniqueLeagues.forEach(leagueCode => {
        const option       = document.createElement('option');
        option.value       = leagueCode;
        option.textContent = cfg.leagueDisplayNames[leagueCode] || leagueCode.toUpperCase();
        leagueFilter.appendChild(option);
      });
    }

    let filteredMatches        = data;
    const selectedLeagueCode   = leagueFilter.value;
    if (selectedLeagueCode) filteredMatches = data.filter(match => match.league === selectedLeagueCode);

    const selectedSortOrder = sortOrder.value;
    if (selectedSortOrder === 'league-asc') {
      filteredMatches.sort((a, b) =>
        (cfg.leagueDisplayNames[a.league] || a.league)
          .localeCompare(cfg.leagueDisplayNames[b.league] || b.league));
    } else if (selectedSortOrder === 'time-asc') {
      filteredMatches.sort((a, b) => (a.time || '00:00').localeCompare(b.time || '00:00'));
    }

    const matchesByLeague = {};
    filteredMatches.forEach(match => {
      if (!matchesByLeague[match.league]) matchesByLeague[match.league] = [];
      matchesByLeague[match.league].push(match);
    });

    for (const leagueCodeFromAPI in matchesByLeague) {
      const leagueSection = document.createElement('div');
      leagueSection.classList.add('league-section');

      const leagueTitle       = document.createElement('h2');
      leagueTitle.classList.add('league-title');
      leagueTitle.textContent = cfg.leagueDisplayNames[leagueCodeFromAPI] || leagueCodeFromAPI.toUpperCase();

      const flagFileName = cfg.leagueFlagMap[leagueCodeFromAPI];
      if (flagFileName) {
        const flagImg   = document.createElement('img');
        flagImg.src     = cfg.flagsBaseUrl + flagFileName;
        flagImg.alt     = cfg.leagueDisplayNames[leagueCodeFromAPI] || leagueCodeFromAPI;
        flagImg.classList.add('league-flag');
        leagueTitle.prepend(flagImg);
      }

      leagueSection.appendChild(leagueTitle);

      const leagueMatchesContainer = document.createElement('div');
      leagueMatchesContainer.classList.add('league-matches-grid');

      matchesByLeague[leagueCodeFromAPI].forEach(match => {
        const matchCard    = document.createElement('a');
        matchCard.href     = "/match/" + match.match_type + "/" + match.match_id;
        matchCard.classList.add('match-card');

        const isFinished   = match.home_goals !== null && match.away_goals !== null;
        const scoreDisplay = isFinished ? match.home_goals + ' - ' + match.away_goals : (match.time || '--:--');
        const statusClass  = isFinished ? 'status-finished' : 'status-upcoming';
        const statusText   = isFinished ? cfg.msgFinished : cfg.msgUpcoming;

        const homeSlug = slugify(match.home_team);
        const awaySlug = slugify(match.away_team);

        matchCard.innerHTML = `
          <div class="mc-bg mc-bg-home" style="--logo: url('../img/logos/128x128/${homeSlug}.png')"></div>
          <div class="mc-bg mc-bg-away" style="--logo: url('../img/logos/128x128/${awaySlug}.png')"></div>
          <div class="mc-content">
            <div class="mc-team mc-home"><span class="mc-name">${match.home_team}</span></div>
            <div class="mc-center">
              <span class="mc-score">${scoreDisplay}</span>
              <span class="mc-status ${statusClass}">${statusText}</span>
            </div>
            <div class="mc-team mc-away"><span class="mc-name">${match.away_team}</span></div>
          </div>`;
        leagueMatchesContainer.appendChild(matchCard);
      });

      leagueSection.appendChild(leagueMatchesContainer);
      matchesContainer.appendChild(leagueSection);
    }
  } catch (err) {
    console.error("Błąd pobierania meczów:", err);
    matchesContainer.innerHTML = `<p class="error-message">${window.MAINPAGE_CONFIG.msgError}</p>`;
  }
}

window.onload = function () {
  const urlParams = new URLSearchParams(window.location.search);
  const dateParam = urlParams.get('date');
  const datePicker = document.getElementById('date-picker');
  datePicker.value = dateParam || new Date().toISOString().split('T')[0];
  if (dateParam) fetchMatches();
};
