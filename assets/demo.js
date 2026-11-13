/* Demo player: two illustrative sessions, built from the outputs documented in docs/getting-started.md.
   Each line: [html, {stage, kv, wait}]. Lines are trusted, authored here. */
(function () {
  "use strict";
  var ID_L = "T-2026-10-30-0912-checkout-typo", ID_F = "T-2026-10-30-1034-card-surcharge";
  var S = {
    light: {
      stages: ["plan", "build", "verify", "close", "commit · you"],
      stops: [4],
      kv: { task: "—", mode: "—", W: "—", files: "—", verify: "0 of 2" },
      lines: [
        ['<span class="p">❯</span> <span class="h">/rr-build fix the typo in the checkout button label</span>', { stage: 0, wait: 900 }],
        ['<span class="d">no task in flight → /rr-plan</span>'],
        ['bugfix · files: <span class="c">templates/checkout/button.html.twig</span>'],
        ['<span class="d">recall: 1 item about these files (a task one-liner)</span>', { wait: 700 }],
        ['scope          <span class="p">0</span>  1 reference'],
        ['behaviour      <span class="p">0</span>  a label (declared)'],
        ['reversibility  <span class="p">0</span>  git revert returns everything'],
        ['domain         <span class="p">1</span>  templates/** is customer-visible'],
        ['novelty        <span class="p">0</span>  nothing new (declared)'],
        ['coverage       <span class="p">1</span>  no test names the file'],
        ['<span class="p">W 2</span> → <span class="g">light</span>   <span class="d">hints none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2</span>', { kv: { mode: "light", W: "2" }, wait: 900 }],
        ['<span class="d">plan (inline): the file · the test · rollback: git revert</span>'],
        [ID_L + ' started: light · 1 files in scope · .ai/reports/' + ID_L + '/task.md', { kv: { task: ID_L, files: "1 in scope" }, wait: 1000 }],
        ['<span class="p">❯</span> edit templates/checkout/button.html.twig  <span class="g">✓</span>', { stage: 1 }],
        ['<span class="p">❯</span> edit templates/checkout/summary.html.twig', { wait: 500 }],
        ['<span class="r">✗ SCOPE_CHANGE_REQUIRED</span> — templates/checkout/summary.html.twig is outside the approved scope of step task (task ' + ID_L + ').', { wait: 900 }],
        ['<span class="d">agent: the typo is only in button.html.twig; the summary edit was a guess. Leaving it.</span>', { wait: 1100 }],
        ['<span class="p">❯</span> state.py verify --scope all', { stage: 2, wait: 1200 }],
        ['suite run 1: exit 0 in 41s'],
        ['log: .ai/state/logs/' + ID_L + '/suite-1.log'],
        ['suite runs used: 1 of 2', { kv: { verify: "1 of 2 · green" }, wait: 900 }],
        ['<span class="p">❯</span> <span class="h">/rr-ship</span>', { stage: 3 }],
        [ID_L + ' closed (light): .ai/reports/' + ID_L + '/task.md'],
        ['record: .ai/memory/2026-Q4.dev.k3m9.jsonl (+7 entries, ' + ID_L + ' sealed, coverage 9/9 lines)'],
        ['<span class="d">the record stays on this machine: .ai/memory/ and .ai/reports/ are git-ignored (share with memory enable --share git)</span>', { wait: 900 }],
        ['<span class="ask">dialog · branch fix/checkout-typo · 1 file changed, 1 insertion(+), 1 deletion(-)\n  Run these, in this order?\n  ▸ git commit -m \'fix: typo in the checkout button label\'\n    Not now — commit nothing</span>', { stage: 4, wait: 1400 }],
        ['<span class="d">you picked the commit · it runs once, verbatim</span>'],
        ['<span class="g">done.</span> three state.py calls, no agent, no gate.']
      ]
    },
    full: {
      stages: ["plan", "plan · you", "build", "verify", "review STRONG", "approve · you", "close"],
      stops: [1, 5],
      kv: { task: "—", mode: "—", W: "—", files: "—", verify: "0 of 2" },
      lines: [
        ['<span class="p">❯</span> <span class="h">/rr-build add a 3% surcharge to card payments</span>', { stage: 0, wait: 900 }],
        ['<span class="d">no task in flight → /rr-plan</span>'],
        ['feature · files: <span class="c">src/Payment/Surcharge.php</span> (new), <span class="c">src/Payment/CardCharge.php</span>, <span class="c">tests/Payment/CardChargeTest.php</span>'],
        ['<span class="d">recall: open risk "CardCharge rounds per order, not per line" (src/Payment/CardCharge.php)</span>', { wait: 900 }],
        ['scope          <span class="p">1</span>  3 references'],
        ['behaviour      <span class="p">1</span>  changes the charged amount (declared)'],
        ['reversibility  <span class="p">0</span>  git revert returns everything'],
        ['domain         <span class="p">2</span>  src/Payment/** is in domain.modules'],
        ['novelty        <span class="p">1</span>  adaptation (declared)'],
        ['coverage       <span class="p">1</span>  1 of 2 code files have a test'],
        ['<span class="p">W 6</span> → <span class="r">full</span>   <span class="d">hints none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2</span>', { kv: { mode: "full", W: "6 · domain 2" }, wait: 1000 }],
        ['<span class="ask">question Q1 · Is the surcharge taken on the net amount or on the gross?\n  ▸ net, before VAT\n    gross, after VAT</span>', { wait: 1400 }],
        ['<span class="d">you: net, before VAT · recorded verbatim in task.md</span>'],
        ['plan written: 3 steps · what stays the same · risks · rollback · <span class="d">design closed, no architect</span>', { wait: 900 }],
        ['<span class="ask">dialog · Accept the plan for ' + ID_F + '?\n  ▸ accept\n    change it</span>', { stage: 1, wait: 1400 }],
        [ID_F + ' started: full · 3 files in scope · .ai/reports/' + ID_F + '/task.md', { kv: { task: ID_F, files: "3 in scope" }, wait: 900 }],
        ['<span class="p">❯</span> step 1 · characterize CardCharge before the change', { stage: 2 }],
        ['verify --scope step · <span class="g">green</span> on the old behaviour · step-done 1'],
        ['<span class="p">❯</span> step 2 · Surcharge.php and its call in CardCharge.php'],
        ['verify --scope step · <span class="g">green</span> · step-done 2', { wait: 900 }],
        ['<span class="p">❯</span> state.py verify --scope all', { stage: 3, wait: 1200 }],
        ['suite run 1: exit 1 in 58s · 1 failure: CardChargeTest::testRefundKeepsSurcharge', { kv: { verify: "1 of 2 · red" } }],
        ['<span class="d">every failure classified, the regressions fixed as one batch</span>', { wait: 900 }],
        ['<span class="p">❯</span> state.py verify --scope all --after-fix "1 regression: the refund drops the surcharge"', { wait: 1200 }],
        ['suite run 2: exit 0 in 57s'],
        ['e2e run 3: exit 0 in 12s'],
        ['suite runs used: 2 of 2', { kv: { verify: "2 of 2 · green" }, wait: 900 }],
        ['<span class="p">❯</span> <span class="h">/rr-review</span>  <span class="d">ai-reviewer on STRONG · focus: security</span>', { stage: 4, wait: 1400 }],
        ['<span class="y">MEDIUM</span> M1 a partial capture rounds the surcharge per capture, not per order · CardCharge.php'],
        ['review: passed_with_findings (STRONG, pass 1 of 2)'],
        ['<span class="d">no BLOCKER or HIGH · M1 recorded as a risk for its own task, not fixed here</span>', { wait: 900 }],
        ['<span class="p">❯</span> <span class="h">/rr-ship</span>', { stage: 5 }],
        ['facts: (a) suite green on this tree (run 2) · (b) 3 changed files, all in the task\'s files'],
        ['DIALOG_PENDING D3 · the approval waits for you', { wait: 900 }],
        ['<span class="ask">dialog · ' + ID_F + ' · full · 3 files\n  Approve this tree?\n  ▸ state.py approve --by "dev"\n    Not now</span>', { wait: 1500 }],
        ['<span class="d">you picked it · it runs once, verbatim · a tree that changes after this invalidates it</span>'],
        [ID_F + ' closed (full): .ai/reports/' + ID_F + '/task.md', { stage: 6 }],
        ['record: .ai/memory/2026-Q4.dev.k3m9.jsonl (+31 entries, ' + ID_F + ' sealed, coverage 42/42 lines)'],
        ['<span class="g">done.</span> the commit comes to you in the dialog. nothing merged, nothing deployed.']
      ]
    }
  };

  var screen = document.getElementById("screen"), list = document.getElementById("stages"), kvBox = document.getElementById("kv");
  if (!screen) return;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var cur = "light", i = 0, timer = 0, playing = false, kv = {};
  var bPlay = document.getElementById("b-play"), bStep = document.getElementById("b-step"),
      bAll = document.getElementById("b-all"), bRe = document.getElementById("b-restart");

  function renderStages(active) {
    var sc = S[cur];
    list.innerHTML = "";
    sc.stages.forEach(function (name, k) {
      var li = document.createElement("li");
      li.textContent = name;
      if (sc.stops.indexOf(k) >= 0) li.classList.add("stop");
      if (k < active) li.classList.add("done");
      if (k === active) li.classList.add("now");
      list.appendChild(li);
    });
  }
  function renderKv() {
    kvBox.innerHTML = "";
    Object.keys(kv).forEach(function (k) {
      var dt = document.createElement("span"); dt.textContent = k;
      var dd = document.createElement("b"); dd.textContent = kv[k];
      kvBox.appendChild(dt); kvBox.appendChild(dd);
    });
  }
  var stage = -1;
  function reset() {
    stop(); i = 0; stage = -1; screen.innerHTML = "";
    kv = JSON.parse(JSON.stringify(S[cur].kv));
    renderStages(-1); renderKv();
  }
  function emit(n, animate) {
    var ln = S[cur].lines[n], o = ln[1] || {};
    var span = document.createElement("span");
    span.className = "ln"; if (!animate) span.style.animation = "none";
    span.innerHTML = ln[0] + (ln[0].indexOf('class="ask"') >= 0 ? "" : "\n");
    screen.appendChild(span);
    if (o.stage !== undefined) stage = o.stage;
    if (o.kv) Object.keys(o.kv).forEach(function (k) { kv[k] = o.kv[k]; });
    return o;
  }
  function refresh() {
    var done = i >= S[cur].lines.length;
    renderStages(done ? S[cur].stages.length : stage); renderKv();
    screen.scrollTop = screen.scrollHeight;
    bPlay.textContent = playing ? "Pause" : (done ? "Replay" : "Play");
  }
  function next() {
    if (i >= S[cur].lines.length) { playing = false; refresh(); return; }
    var o = emit(i++, true);
    refresh();
    if (playing) timer = setTimeout(next, o.wait || 420);
  }
  function play() { if (i >= S[cur].lines.length) reset(); playing = true; next(); }
  function stop() { playing = false; clearTimeout(timer); }
  function all() { stop(); while (i < S[cur].lines.length) emit(i++, false); refresh(); }

  bPlay.addEventListener("click", function () { if (playing) { stop(); refresh(); } else play(); });
  bStep.addEventListener("click", function () { stop(); next(); });
  bAll.addEventListener("click", all);
  bRe.addEventListener("click", function () { reset(); play(); });
  document.querySelectorAll(".tab").forEach(function (t) {
    t.addEventListener("click", function () {
      document.querySelectorAll(".tab").forEach(function (x) { x.setAttribute("aria-selected", x === t ? "true" : "false"); });
      cur = t.getAttribute("data-s"); reset();
      if (reduce) all(); else play();
    });
  });

  reset();
  if (reduce) { all(); return; }
  /* start when the player is on screen; pause when it leaves */
  var started = false;
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) {
      if (es[0].isIntersecting && !started) { started = true; play(); }
      else if (!es[0].isIntersecting && playing) { stop(); refresh(); }
    }, { threshold: .3 }).observe(screen);
  } else { all(); }
})();
