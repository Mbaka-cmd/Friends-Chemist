(function () {
  var rm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var ARROW = function (d) { return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + d + '"/></svg>'; };

  document.querySelectorAll("[data-carousel]").forEach(function (root) {
    var slides = [].slice.call(root.querySelectorAll(".slide"));
    if (slides.length < 2) return;
    var i = 0, dots = [];
    var ctl = document.createElement("div"); ctl.className = "ctl";
    var prev = document.createElement("button"); prev.type = "button"; prev.setAttribute("aria-label", "Previous slide"); prev.innerHTML = ARROW("M15 5l-7 7 7 7");
    var next = document.createElement("button"); next.type = "button"; next.setAttribute("aria-label", "Next slide"); next.innerHTML = ARROW("M9 5l7 7-7 7");
    var wrap = document.createElement("div"); wrap.className = "dots";
    slides.forEach(function (_, n) {
      var b = document.createElement("button"); b.type = "button"; b.setAttribute("aria-label", "Go to slide " + (n + 1));
      b.addEventListener("click", function () { go(n); }); wrap.appendChild(b); dots.push(b);
    });
    ctl.appendChild(prev); ctl.appendChild(wrap); ctl.appendChild(next); root.appendChild(ctl);
    function go(n) {
      i = (n + slides.length) % slides.length;
      slides.forEach(function (s, k) { s.classList.toggle("is-active", k === i); });
      dots.forEach(function (d, k) { d.setAttribute("aria-current", k === i ? "true" : "false"); });
    }
    prev.addEventListener("click", function () { go(i - 1); });
    next.addEventListener("click", function () { go(i + 1); });
    root.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") { go(i - 1); } else if (e.key === "ArrowRight") { go(i + 1); }
    });
    var sx = null;
    root.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; }, { passive: true });
    root.addEventListener("touchend", function (e) {
      if (sx === null) return;
      var dx = e.changedTouches[0].clientX - sx; sx = null;
      if (Math.abs(dx) > 40) { go(i + (dx < 0 ? 1 : -1)); }
    }, { passive: true });
    go(0);
  });

  document.querySelectorAll("[data-cats]").forEach(function (w) {
    var t = w.querySelector(".track"), p = w.querySelector(".prev"), n = w.querySelector(".next");
    function upd() { p.disabled = t.scrollLeft < 4; n.disabled = t.scrollLeft + t.clientWidth >= t.scrollWidth - 4; }
    p.addEventListener("click", function () { t.scrollBy({ left: -t.clientWidth * 0.8, behavior: rm ? "auto" : "smooth" }); });
    n.addEventListener("click", function () { t.scrollBy({ left: t.clientWidth * 0.8, behavior: rm ? "auto" : "smooth" }); });
    t.addEventListener("scroll", upd, { passive: true }); window.addEventListener("resize", upd); upd();
  });

  var m = document.querySelector(".menu"), nav = document.getElementById("nav");
  if (m && nav) {
    m.addEventListener("click", function () {
      var open = nav.classList.toggle("open"); m.setAttribute("aria-expanded", open ? "true" : "false");
    });
    nav.addEventListener("click", function (e) { if (e.target.tagName === "A") { nav.classList.remove("open"); m.setAttribute("aria-expanded", "false"); } });
  }
})();