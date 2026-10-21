/* ==========================================================================
   Opal — site behaviour
   Language switch (English / Hinglish), scroll reveal, the working wheel
   demo, the studio switcher, mobile nav, copy-to-clipboard.
   ========================================================================== */

(function () {
  "use strict";

  var LANG_KEY = "opal.lang";

  /* ---------------------------------------------------------------- language */
  function applyLanguage(lang) {
    document.documentElement.setAttribute("data-lang", lang);
    document.documentElement.setAttribute("lang", lang === "hinglish" ? "hi-Latn" : "en");

    var nodes = document.querySelectorAll("[data-en]");
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var text = lang === "hinglish" ? el.getAttribute("data-hing") : el.getAttribute("data-en");
      if (text) el.textContent = text;
    }

    var buttons = document.querySelectorAll("[data-set-lang]");
    for (var j = 0; j < buttons.length; j++) {
      buttons[j].classList.toggle("is-active", buttons[j].getAttribute("data-set-lang") === lang);
    }
    try { localStorage.setItem(LANG_KEY, lang); } catch (e) { /* private mode */ }
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", lang === "hinglish" ? "#hinglish" : "#top");
    }
  }

  function initLanguage() {
    var buttons = document.querySelectorAll("[data-set-lang]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function (event) {
        applyLanguage(event.currentTarget.getAttribute("data-set-lang"));
      });
    }
    var saved = null;
    try { saved = localStorage.getItem(LANG_KEY); } catch (e) { /* ignore */ }
    if (window.location.hash === "#hinglish") {
      saved = "hinglish";
    }
    applyLanguage(saved === "hinglish" ? "hinglish" : "en");
  }

  /* ------------------------------------------------------------------ reveal */
  function initReveal() {
    var items = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) {
      for (var i = 0; i < items.length; i++) items[i].classList.add("is-visible");
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0.06 });
    for (var j = 0; j < items.length; j++) observer.observe(items[j]);

    // Whatever is already on screen does not need to wait for a scroll.
    for (var k = 0; k < items.length; k++) {
      if (items[k].getBoundingClientRect().top < window.innerHeight) {
        items[k].classList.add("is-visible");
        observer.unobserve(items[k]);
      }
    }

    // And if the observer never speaks up, the page still shows everything.
    window.setTimeout(function () {
      for (var m = 0; m < items.length; m++) items[m].classList.add("is-visible");
    }, 1200);
  }

  /* ------------------------------------------------------- the wheel demo */
  var WHEEL_MODES = {
    convert: {
      title: "Convert",
      hub: "portrait.jpg",
      wedges: ["PDF → Word", "HEIC → PNG", "MP4 → GIF", "JPG → WebP", "DOCX → PDF", "PNG → JPG", "WAV → MP3", "PDF → EPUB"]
    },
    tools: {
      title: "Tools",
      hub: "portrait.jpg",
      wedges: ["Remove BG", "Upscale 2×", "Blur face", "Remove object", "Beautify", "Auto enhance", "Palette", "EXIF strip"]
    },
    actions: {
      title: "Actions",
      hub: "portrait.jpg",
      wedges: ["Sign with DSC", "Stamp photo", "Join photos", "Extract pages", "Add watermark", "Protect PDF", "Print A4", "OCR scan"]
    }
  };

  function initWheel() {
    var group = document.querySelector("#wheel-wedges");
    if (!group) return;

    var chips = document.querySelectorAll("[data-wheel-mode]");
    var hubTitle = document.getElementById("wheel-hub-title");
    var hubMode = document.getElementById("wheel-hub-mode");
    var NS = "http://www.w3.org/2000/svg";

    function draw(mode) {
      var data = WHEEL_MODES[mode] || WHEEL_MODES.convert;
      group.innerHTML = "";
      var count = data.wedges.length;
      var gap = 2.4;
      var span = 360 / count;
      for (var i = 0; i < count; i++) {
        var start = -90 + i * span + gap / 2;
        var end = start + span - gap;
        var path = document.createElementNS(NS, "path");
        path.setAttribute("d", wedgePath(200, 200, 86, 190, start, end));
        path.setAttribute("fill", i === 0 ? "url(#wedge-on)" : "rgba(255,255,255,0.045)");
        path.setAttribute("stroke", i === 0 ? "rgba(255,255,255,0.35)" : "rgba(255,255,255,0.10)");
        path.setAttribute("stroke-width", "1");
        path.setAttribute("class", "wheel-wedge");
        group.appendChild(path);

        var mid = ((start + end) / 2) * Math.PI / 180;
        var lr = 138;
        var lx = 200 + lr * Math.cos(mid);
        var ly = 200 + lr * Math.sin(mid);
        var label = document.createElementNS(NS, "text");
        label.setAttribute("x", lx);
        label.setAttribute("y", ly + 4);
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("class", "wheel-label");
        label.setAttribute("fill", i === 0 ? "#ffffff" : "#cdd4e4");
        label.textContent = data.wedges[i];
        group.appendChild(label);
      }
      if (hubTitle) hubTitle.textContent = data.hub;
      if (hubMode) hubMode.textContent = data.title;
    }

    function wedgePath(cx, cy, rIn, rOut, start, end) {
      var p = document.createElementNS(NS, "path");
      var s = start * Math.PI / 180;
      var e = end * Math.PI / 180;
      var x1 = cx + rOut * Math.cos(s), y1 = cy + rOut * Math.sin(s);
      var x2 = cx + rOut * Math.cos(e), y2 = cy + rOut * Math.sin(e);
      var x3 = cx + rIn * Math.cos(e), y3 = cy + rIn * Math.sin(e);
      var x4 = cx + rIn * Math.cos(s), y4 = cy + rIn * Math.sin(s);
      return "M" + x1 + " " + y1 +
             " A" + rOut + " " + rOut + " 0 0 1 " + x2 + " " + y2 +
             " L" + x3 + " " + y3 +
             " A" + rIn + " " + rIn + " 0 0 0 " + x4 + " " + y4 + " Z";
    }

    for (var i = 0; i < chips.length; i++) {
      (function (chip) {
        var mode = chip.getAttribute("data-wheel-mode");
        chip.addEventListener("click", function () {
          for (var j = 0; j < chips.length; j++) chips[j].classList.remove("is-on");
          chip.classList.add("is-on");
          draw(mode);
        });
        chip.addEventListener("mouseenter", function () {
          for (var j = 0; j < chips.length; j++) chips[j].classList.remove("is-on");
          chip.classList.add("is-on");
          draw(mode);
        });
      })(chips[i]);
    }

    draw("convert");
  }

  /* -------------------------------------------------------- studio switcher */
  function initStudios() {
    var tabs = document.querySelectorAll("[data-studio]");
    var panels = document.querySelectorAll("[data-studio-panel]");
    if (!tabs.length) return;

    for (var i = 0; i < tabs.length; i++) {
      (function (tab) {
        tab.addEventListener("click", function () {
          var key = tab.getAttribute("data-studio");
          for (var j = 0; j < tabs.length; j++) {
            var on = tabs[j] === tab;
            tabs[j].classList.toggle("is-active", on);
            tabs[j].setAttribute("aria-selected", on ? "true" : "false");
          }
          for (var k = 0; k < panels.length; k++) {
            panels[k].classList.toggle("is-active", panels[k].getAttribute("data-studio-panel") === key);
          }
        });
      })(tabs[i]);
    }
  }

  /* -------------------------------------------------------------- mobile nav */
  function initNav() {
    var toggle = document.querySelector(".nav-toggle");
    var nav = document.querySelector(".nav");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    nav.addEventListener("click", function (event) {
      if (event.target.tagName === "A") {
        nav.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  /* ------------------------------------------------------------------- copy */
  function initCopy() {
    var buttons = document.querySelectorAll("[data-copy-target]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function (event) {
        var target = document.getElementById(event.currentTarget.getAttribute("data-copy-target"));
        if (!target) return;
        var text = target.innerText;
        var done = function () {
          var original = event.currentTarget.textContent;
          event.currentTarget.textContent = "Copied";
          setTimeout(function () { event.currentTarget.textContent = original; }, 1600);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () { });
        } else {
          var area = document.createElement("textarea");
          area.value = text;
          document.body.appendChild(area);
          area.select();
          try { document.execCommand("copy"); done(); } catch (e) { /* ignore */ }
          document.body.removeChild(area);
        }
      });
    }
  }

  /* ------------------------------------------------------------------- misc */
  function initMisc() {
    var year = document.getElementById("year");
    if (year) year.textContent = new Date().getFullYear();

    var links = document.querySelectorAll('a[href^="#"]');
    for (var i = 0; i < links.length; i++) {
      links[i].addEventListener("click", function (event) {
        var id = this.getAttribute("href");
        if (!id || id === "#") return;
        var target = document.querySelector(id);
        if (!target) return;
        event.preventDefault();
        var top = target.getBoundingClientRect().top + window.pageYOffset - 84;
        window.scrollTo({ top: top, behavior: "smooth" });
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initLanguage();
    initReveal();
    initWheel();
    initStudios();
    initNav();
    initCopy();
    initMisc();
  });
})();
