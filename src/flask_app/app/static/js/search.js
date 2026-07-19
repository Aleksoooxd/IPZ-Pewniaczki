/* Live search bar in the top navbar.
 *
 * The magnifier button toggles the input open; typing (debounced) queries
 * /api/search and renders grouped teams / leagues / matches results in a
 * dropdown. Clicking a result navigates; Escape or an outside click closes it.
 */
(function () {
  "use strict";

  var container = document.getElementById("searchContainer");
  var toggle = document.getElementById("searchToggle");
  var input = document.getElementById("searchInput");
  var panel = document.getElementById("searchResults");
  if (!container || !toggle || !input || !panel) return;

  var debounceTimer = null;

  function setOpen(open) {
    container.classList.toggle("open", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      input.focus();
    } else {
      hideResults();
    }
  }

  function hideResults() {
    panel.hidden = true;
    panel.innerHTML = "";
  }

  function escapeHtml(str) {
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function teamLogoHtml(url) {
    if (!url) return "<span class='sr-icon'>⚽</span>";
    return "<img class='sr-logo' src='" + escapeHtml(url) + "' alt='' " +
           "onerror=\"this.classList.add('sr-logo-broken')\" />";
  }

  function leagueLogoHtml(url) {
    if (!url) return "<span class='sr-icon'>🏆</span>";
    return "<img class='sr-logo' src='" + escapeHtml(url) + "' alt='' " +
           "onerror=\"this.replaceWith(Object.assign(document.createElement('span'), {className:'sr-icon', textContent:'🏆'}))\" />";
  }

  function groupWrap(title, rowsHtml) {
    if (!rowsHtml) return "";
    return "<div class='search-group'>" +
             "<div class='search-group-title'>" + escapeHtml(title) + "</div>" +
             rowsHtml +
           "</div>";
  }

  function render(data) {
    var teams = (data && data.teams) || [];
    var leagues = (data && data.leagues) || [];
    var matches = (data && data.matches) || [];

    if (!teams.length && !leagues.length && !matches.length) {
      panel.innerHTML = "<div class='search-empty'>Brak wyników</div>";
      panel.hidden = false;
      return;
    }

    var html = "";

    // Ligi — logo ligi zamiast ikony pucharu
    if (leagues.length) {
      var leagueRows = leagues.map(function (it) {
        return "<a class='search-item' href='" + escapeHtml(it.url || "#") + "'>" +
                 leagueLogoHtml(it.logo) +
                 "<span class='sr-text'><span class='sr-name'>" + escapeHtml(it.name) + "</span></span>" +
               "</a>";
      }).join("");
      html += groupWrap("Ligi", leagueRows);
    }

    // Zespoły — logo zespołu zamiast ikony piłki
    if (teams.length) {
      var teamRows = teams.map(function (it) {
        return "<a class='search-item' href='" + escapeHtml(it.url || "#") + "'>" +
                 teamLogoHtml(it.logo) +
                 "<span class='sr-text'><span class='sr-name'>" + escapeHtml(it.name) + "</span></span>" +
               "</a>";
      }).join("");
      html += groupWrap("Zespoły", teamRows);
    }

    // Mecze — loga obu zespołów
    if (matches.length) {
      var matchRows = matches.map(function (it) {
        var sub = "<span class='sr-sub'>" +
                  escapeHtml(it.league) +
                  (it.date ? " · " + escapeHtml(it.date) : "") +
                  "</span>";
        return "<a class='search-item' href='" + escapeHtml(it.url || "#") + "'>" +
                 "<span class='sr-logos'>" + teamLogoHtml(it.home_logo) + teamLogoHtml(it.away_logo) + "</span>" +
                 "<span class='sr-text'><span class='sr-name'>" +
                   escapeHtml(it.home) + " <span class='sr-vs'>vs</span> " + escapeHtml(it.away) +
                 "</span>" + sub + "</span>" +
               "</a>";
      }).join("");
      html += groupWrap("Mecze", matchRows);
    }

    panel.innerHTML = html;
    panel.hidden = false;
  }

  function fetchResults(query) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/api/search?q=" + encodeURIComponent(query), true);
    xhr.onload = function () {
      if (xhr.status === 200) {
        try {
          render(JSON.parse(xhr.responseText));
        } catch (e) {
          hideResults();
        }
      } else {
        hideResults();
      }
    };
    xhr.onerror = hideResults;
    xhr.send();
  }

  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    setOpen(!container.classList.contains("open"));
  });

  input.addEventListener("input", function () {
    var q = input.value.trim();
    if (debounceTimer) clearTimeout(debounceTimer);
    if (q.length < 2) {
      hideResults();
      return;
    }
    debounceTimer = setTimeout(function () {
      fetchResults(q);
    }, 200);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      setOpen(false);
    }
  });

  // Close on outside click.
  document.addEventListener("click", function (e) {
    if (!container.contains(e.target)) {
      if (container.classList.contains("open")) setOpen(false);
    }
  });

  // Prevent the form click from immediately closing via the document handler.
  container.addEventListener("click", function (e) {
    e.stopPropagation();
  });
})();
