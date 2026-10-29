/* RiskRails site: small, dependency-free. Everything is readable without it. */
(function () {
  "use strict";
  var doc = document.documentElement;
  doc.classList.add("js");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* nav toggle */
  var btn = document.querySelector(".navbtn"), nav = document.querySelector(".nav");
  if (btn && nav) {
    btn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  /* scroll progress as a lit track under the top bar */
  var bar = document.querySelector(".track-progress i"), ticking = false;
  function progress() {
    ticking = false;
    var h = doc.scrollHeight - window.innerHeight;
    if (bar) bar.style.setProperty("--p", h > 0 ? Math.min(1, window.scrollY / h).toFixed(4) : 0);
  }
  window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(progress); } }, { passive: true });
  progress();

  /* copy buttons */
  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var text = b.getAttribute("data-copy");
      var done = function () { var t = b.textContent; b.textContent = "Copied"; setTimeout(function () { b.textContent = t; }, 1400); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { selectSibling(b); });
      } else { selectSibling(b); }
    });
  });
  function selectSibling(b) {
    var code = b.parentNode.querySelector("code");
    if (!code) return;
    var r = document.createRange(); r.selectNodeContents(code);
    var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  }

  /* reveal: only what is below the fold at load is hidden, so the first frame is complete */
  if (!reduce && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.remove("pre"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    document.querySelectorAll(".rv, .bars").forEach(function (el) {
      if (el.getBoundingClientRect().top > window.innerHeight) { el.classList.add("pre"); io.observe(el); }
    });
  }

  /* hero: three requests take their routes in turn */
  var svg = document.getElementById("route");
  if (svg) routeDemo(svg);

  function routeDemo(svg) {
    var REQ = [
      { route: "light", req: "fix the typo in the checkout button label", w: "W = 2" },
      { route: "guarded", req: "cache the shipping-zone lookup", w: "W = 5" },
      { route: "full", req: "add a 3% surcharge to card payments", w: "W = 9" }
    ];
    var COLOR = { light: "g", guarded: "y", full: "r" };
    var reqText = document.querySelector("[data-req]"), wText = svg.querySelector(".jt");
    var modeText = document.querySelector("[data-mode]");
    var train = svg.querySelector(".train");
    var paths = {}, lit = {};
    ["light", "guarded", "full"].forEach(function (k) {
      paths[k] = svg.querySelector("#p-" + k);
      lit[k] = svg.querySelector("#l-" + k);
    });
    var sigs = svg.querySelectorAll(".sig");
    var marks = svg.querySelectorAll("[data-route]");

    function showMode(k) {
      if (!modeText) return;
      modeText.textContent = k;
      modeText.className = "chip " + COLOR[k];
    }
    function setRoute(k) {
      sigs.forEach(function (s) { s.setAttribute("class", "sig" + (s.getAttribute("data-r") === k ? " " + COLOR[k] : "")); });
      Object.keys(paths).forEach(function (p) { paths[p].classList.toggle("lit", p === k); });
    }
    function mark(k, x) {
      marks.forEach(function (m) {
        var on = m.getAttribute("data-route") === k && x >= +m.getAttribute("data-at");
        m.classList.toggle("on", on);
      });
    }

    if (reduce) {
      reqText.textContent = REQ[2].req; wText.textContent = REQ[2].w; showMode("full");
      setRoute("full"); mark("full", 9999);
      var pt = paths.full.getPointAtLength(paths.full.getTotalLength());
      train.setAttribute("cx", pt.x); train.setAttribute("cy", pt.y);
      return;
    }

    var i = 0, start = 0, phase = "run", visible = true, raf = 0, len = 0, cur = null, DUR = 4200, HOLD = 1500;
    function begin() {
      cur = REQ[i % REQ.length];
      reqText.textContent = cur.req; wText.textContent = cur.w; showMode(cur.route);
      setRoute(cur.route); mark(cur.route, -1);
      Object.keys(lit).forEach(function (k) { lit[k].style.opacity = 0; });
      len = paths[cur.route].getTotalLength();
      var l = lit[cur.route];
      l.style.strokeDasharray = len; l.style.strokeDashoffset = len; l.style.opacity = 1;
      start = 0; phase = "run";
    }
    function frame(ts) {
      raf = 0;
      if (!visible) return;
      if (!start) start = ts;
      var t = ts - start;
      if (phase === "run") {
        var f = Math.min(1, t / DUR), e = f < .5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2;
        var p = paths[cur.route].getPointAtLength(e * len);
        train.setAttribute("cx", p.x); train.setAttribute("cy", p.y);
        lit[cur.route].style.strokeDashoffset = len * (1 - e);
        mark(cur.route, p.x);
        if (f >= 1) { phase = "hold"; start = ts; }
      } else if (t > HOLD) { i++; begin(); }
      raf = requestAnimationFrame(frame);
    }
    function run() { if (!raf && visible && !document.hidden) raf = requestAnimationFrame(frame); }
    begin();
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) { visible = es[0].isIntersecting; if (visible) { start = 0; run(); } }).observe(svg);
    }
    document.addEventListener("visibilitychange", function () { if (!document.hidden) { start = 0; run(); } });
    run();
  }
})();
