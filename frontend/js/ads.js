/* PikaNews ad integration.
   Reuses the GoGo Company AdSense configuration (verified publisher ID
   2895136878543415 and the existing responsive display unit
   7200569170). This file is the PikaNews-specific counterpart of
   gogo-website/assets/js/ads.js and follows the same rules:

   1. The AdSense loader script is injected at most once per page. Pages
      that carry it become Auto-ads-ready (Anchor / Vignette / In-page /
      Multiplex) once the owner enables those formats in the AdSense
      dashboard - Auto ads need no extra page code.
   2. Ad placements stay hidden until a slot id is configured AND the
      page has real content (no ads on empty, error or thin pages).
   3. CONSENT (updated 2026-11-06): browser language and timezone are
      NOT reliable consent or geolocation signals, so they are no longer
      used to guess the visitor's region. Ads stay OFF for ALL visitors
      while cmpReady is false (fail closed). The owner flips cmpReady to
      true only after a Google-certified CMP is enabled and verified in
      the AdSense account (recommended: the built-in consent messaging
      under AdSense -> Privacy & messaging, or Funding Choices). Once
      that is live, Google's certified CMP handles EEA / UK / Switzerland
      consent using its own reliable signals, and ad serving follows
      that consent state.

   IMPORTANT: a configured publisher id does NOT mean PikaNews itself has
   been approved for ad serving. Site review / account status must be
   confirmed in the AdSense dashboard by the owner.
   */
(function () {
  "use strict";

  var CONFIG = {
    publisherId: "ca-pub-2895136878543415", /* GoGo Company verified publisher ID */
    cmpReady: false,    /* true only after a Google-certified CMP is verified */
    /* Placement-key -> AdSense unit id map. Set a placement's id to ""
       to disable that single placement without touching page HTML.
       Single existing responsive display unit reused for every placement.
       Dedicated PikaNews units can be added by the owner in the AdSense
       dashboard; put their ids here when they exist. Do not invent ids. */
    slots: {
      "home-mid": "7200569170",
      "home-side": "7200569170",
      "category-mid": "7200569170",
      "article-bottom": "7200569170"
    }
  };

  function adsAllowed() {
    if (!CONFIG.publisherId) return false;
    /* Fail closed: no ad request is made anywhere until the owner has
       verified that a Google-certified CMP is live. Browser language and
       timezone must never be used as a substitute for consent or reliable
       geolocation. After cmpReady is true, EEA/UK/CH consent is enforced
       by Google's certified CMP, not by this script. */
    if (!CONFIG.cmpReady) return false;
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
