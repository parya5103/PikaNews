/* PikaNews newsroom behaviours: utility-bar date, breaking-news ticker and
   the homepage editorial hero class. Standalone file; every function no-ops
   when its container is missing, so it is safe to include on any page. */
(function () {
  "use strict";

  function initUtilityDate() {
    var el = document.getElementById("utility-date");
    if (!el) return;
    try {
      el.textContent = new Date().toLocaleDateString("en-GB", {
        weekday: "long", year: "numeric", month: "long", day: "numeric"
      });
    } catch (e) {
      el.textContent = new Date().toDateString();
    }
  }

  /* The homepage lead story is simply the newest featured card, styled
   large by CSS. Never fabricate a "lead" - the first real card wins. */
  function initEditorialHero() {
    var featured = document.getElementById("featured-news");
    if (featured) featured.classList.add("featured-news-editorial");
  }

  /* Breaking ticker: latest published headlines only (latest.json),
     newest first, with the original source name on each item. */
  function initTicker() {
    var track = document.getElementById("ticker-track");
    if (!track) return;

    fetch("data/latest.json")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (articles) {
        if (!Array.isArray(articles) || articles.length === 0) {
          track.innerHTML = '<span class="ticker-empty">Headlines refresh automatically every 30 minutes.</span>';
          return;
        }
        var items = articles.slice(0, 8).map(function (a) {
          var safeTitle = Utils.escapeHtml(a.title || "Untitled");
          var safeSource = Utils.escapeHtml(a.source || "");
          var safeId = Utils.escapeHtml(String(a.id || ""));
          return '<a class="ticker-item" href="article.html?id=' + safeId + '">' +
            (safeSource ? '<span class="ticker-source">' + safeSource + '</span>' : "") +
            safeTitle + "</a>";
        }).join("");
        track.innerHTML = items;
      })
      .catch(function () {
        track.innerHTML = '<span class="ticker-empty">Live headlines resume with the next scheduled update.</span>';
      });
  }

  function init() {
    initUtilityDate();
    initEditorialHero();
    initTicker();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
