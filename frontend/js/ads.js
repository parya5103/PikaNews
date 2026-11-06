/* PikaNews ad integration.
   Reuses the GoGo Company AdSense configuration (verified publisher ID
   2895136878543415 and the existing responsive display unit
   7200569170). This file is the PikaNews-specific counterpart of
   gogo-website/assets/js/ads.js and follows the same rules:

   1. The AdSense loader script is injected at most once per page.
   2. Ad placements stay hidden until a slot id is configured AND the
      page has real content (no ads on empty, error or thin pages).
   3. EEA / UK / Switzerland visitors get NO ads until a Google-certified
      CMP handles consent (cmpReady stays false until that is verified).
      The region check is a conservative heuristic and FAILS CLOSED:
      when in doubt, no ad is requested.

   IMPORTANT: a configured publisher id does NOT mean PikaNews itself has
   been approved for ad serving. Site review / account status must be
   confirmed in the AdSense dashboard by the owner.
   */
(function () {
  "use strict";

  var CONFIG = {
    publisherId: "ca-pub-2895136878543415", /* GoGo Company verified publisher ID */
    cmpReady: false,    /* true only after a Google-certified CMP is verified */
    /* Single existing responsive display unit reused for every placement.
       Dedicated PikaNews units can be added by the owner in the AdSense
       dashboard; put their ids here when they exist. Do not invent ids. */
    slots: {
      "home-mid": "7200569170",
      "home-side": "7200569170",
      "category-mid": "7200569170",
      "article-bottom": "7200569170"
    }
  };

  /* ISO 3166-1 alpha-2 codes for EEA, UK and Switzerland. */
  var CONSENT_REGIONS = ["GB", "IM", "JE", "GG", "AT", "BE", "BG", "HR", "CY", "CZ", "DK",
    "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IE", "IT", "LV", "LI", "LT", "LU", "MT",
    "NL", "NO", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "CH"];

  function regionFromLanguage() {
    var m = (navigator.language || "").match(/[-_]([A-Za-z]{2})$/);
    return m ? m[1].toUpperCase() : "";
  }

  /* Conservative heuristic only - used to fail closed, never to grant
     ourselves consent. If the signal is unclear we treat the visitor as
     being in a consent-required region and serve no ad. */
  function inConsentRequiredRegion() {
    var r = regionFromLanguage();
    if (r) return CONSENT_REGIONS.indexOf(r) !== -1;
    try {
      return /Europe\/|Atlantic\/(Madeira|Canary)/.test(
        Intl.DateTimeFormat().resolvedOptions().timeZone || ""
      );
    } catch (e) {
      return true;
    }
  }

  function adsAllowed() {
    if (!CONFIG.publisherId) return false;
    if (!CONFIG.cmpReady && inConsentRequiredRegion()) return false;
    return true;
  }

  function pageHasRealContent() {
    /* No ads on pages showing an empty/error state, and no ads on pages
       without any rendered news content. */
    if (document.querySelector(".empty-state")) return false;
    if (!document.querySelector(".news-card, .article-body p, .static-page-card")) return false;
    return true;
  }

  function activateSlots() {
    var slots = document.querySelectorAll(".ad-slot[hidden]");
    for (var i = 0; i < slots.length; i++) {
      var box = slots[i];
      var slotId = CONFIG.slots[box.getAttribute("data-ad-slot")];
      var ins = box.querySelector("ins.adsbygoogle");
      if (!slotId || !ins) continue;
      if (!pageHasRealContent()) continue;
      ins.setAttribute("data-ad-client", CONFIG.publisherId);
      ins.setAttribute("data-ad-slot", slotId);
      box.removeAttribute("hidden");
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    }
  }

  function load() {
    if (!adsAllowed()) return;
    /* Never inject the AdSense loader twice. */
    if (document.getElementById("pikanews-adsense-lib")) return;
    if (document.querySelector('script[src*="adsbygoogle.js?client="]')) {
      activateSlots();
      return;
    }

    var s = document.createElement("script");
    s.id = "pikanews-adsense-lib";
    s.async = true;
    s.crossOrigin = "anonymous";
    s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + CONFIG.publisherId;
    document.head.appendChild(s);
    activateSlots();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }

  /* Exposed so pages that render content asynchronously (article.html)
     can activate their placement only after real content exists. */
  window.PikaNewsAds = { activate: function () { if (adsAllowed()) activateSlots(); } };
})();

