/* Guest-first PikaNews topic preferences.
   Preferences are stored only in this browser; no account or server is required. */
(function () {
  "use strict";

  var STORAGE_KEY = "pikanews.preferences.v1";
  var TOPICS = [
    { id: "world", label: "World" },
    { id: "science", label: "Science" },
    { id: "politics", label: "Politics" },
    { id: "health", label: "Health" },
    { id: "climate", label: "Climate" },
    { id: "technology", label: "Technology" },
    { id: "business", label: "Business" },
    { id: "sports", label: "Sports" },
    { id: "gaming", label: "Gaming" },
    { id: "entertainment", label: "Entertainment" },
    { id: "bollywood", label: "Bollywood" },
    { id: "hollywood", label: "Hollywood" }
  ];
  var DEFAULT_TOPICS = ["world", "science", "technology", "business", "sports", "gaming", "entertainment"];
  var selectedTopics = DEFAULT_TOPICS.slice();

  function readTopics() {
    try {
      var saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (Array.isArray(saved)) {
        return saved.filter(function (item) {
          return TOPICS.some(function (topic) { return topic.id === item; });
        });
      }
    } catch (error) {
      // Private browsing or disabled storage: use an in-memory guest profile.
    }
    return DEFAULT_TOPICS.slice();
  }

  function saveTopics(topics) {
    selectedTopics = topics.slice();
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedTopics));
    } catch (error) {
      // Keep the current selection for this page session if storage is unavailable.
    }
  }

  function openPreferences() {
    var modal = document.getElementById("preferences-modal");
    if (modal) modal.classList.add("open");
  }

  function closePreferences() {
    var modal = document.getElementById("preferences-modal");
    if (modal) modal.classList.remove("open");
  }

  function renderTopicOptions() {
    var container = document.getElementById("preferences-options");
    if (!container) return;
    container.innerHTML = TOPICS.map(function (topic) {
      var checked = selectedTopics.indexOf(topic.id) !== -1 ? " checked" : "";
      return '<label class="preference-option"><input type="checkbox" name="topic" value="' +
        Utils.escapeHtml(topic.id) + '"' + checked + '> <span>' +
        Utils.escapeHtml(topic.label) + '</span></label>';
    }).join("");
  }

  function renderForYou() {
    var target = document.getElementById("for-you-news");
    if (!target || typeof DataManager === "undefined") return;

    DataManager.loadAllArticles().then(function (articles) {
      var filtered = (Array.isArray(articles) ? articles : [])
        .filter(function (article) {
          return selectedTopics.indexOf(String(article.category || "").toLowerCase()) !== -1;
        })
        .sort(function (a, b) {
          var aTime = Date.parse(a.published_at || "") || 0;
          var bTime = Date.parse(b.published_at || "") || 0;
          return bTime - aTime;
        })
        .slice(0, 8);

      if (!filtered.length) {
        target.innerHTML = '<div class="empty-state"><h3>Your feed is ready</h3><p>Select a few topics to see matching headlines here. Your choices stay on this device.</p></div>';
        return;
      }

      target.innerHTML = filtered.map(function (article) {
        var color = Utils.getCategoryColor(article.category);
        var image = article.image_url
          ? '<img src="' + Utils.escapeHtml(article.image_url) + '" alt="' + Utils.escapeHtml(article.title || "") + '" loading="lazy" onerror="this.onerror=null;this.src=\'images/pikanews-logo.svg\'">'
          : '<div class="news-card-placeholder"><span aria-hidden="true">📰</span></div>';
        return '<article class="news-card" style="--category-color:' + color + '">' +
          '<div class="news-card-image">' + image +
          '<span class="news-card-category" style="background-color:var(--category-color)">' + Utils.escapeHtml(article.category || "world") + '</span></div>' +
          '<div class="news-card-content"><h3 class="news-card-title">' +
          '<a href="article.html?id=' + Utils.escapeHtml(String(article.id || "")) + '">' + Utils.escapeHtml(article.title || "Untitled") + '</a></h3>' +
          '<p class="news-card-summary">' + Utils.escapeHtml(Utils.truncate(article.summary || "", 110)) + '</p>' +
          '<div class="news-card-meta"><span class="news-card-source">' + Utils.escapeHtml(article.source || "Publisher") + '</span>' +
          '<span class="news-card-time">' + Utils.formatDate(article.published_at) + '</span></div></div></article>';
      }).join("");
    }).catch(function () {
      target.innerHTML = '<div class="empty-state"><p>Your personalized feed could not load right now. The Latest feed is still available.</p></div>';
    });
  }

  function init() {
    var target = document.getElementById("for-you-news");
    if (!target) return;

    selectedTopics = readTopics();
    renderTopicOptions();
    renderForYou();

    var openButton = document.getElementById("preferences-toggle");
    var closeButton = document.getElementById("preferences-close");
    var overlay = document.getElementById("preferences-overlay");
    var form = document.getElementById("preferences-form");

    if (openButton) openButton.addEventListener("click", openPreferences);
    if (closeButton) closeButton.addEventListener("click", closePreferences);
    if (overlay) overlay.addEventListener("click", closePreferences);

    if (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var checked = Array.prototype.slice.call(
          form.querySelectorAll('input[name="topic"]:checked')
        ).map(function (input) { return input.value; });
        saveTopics(checked);
        closePreferences();
        renderForYou();
        if (typeof showToast === "function") {
          showToast("Your feed preferences were saved on this device.", "success");
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
