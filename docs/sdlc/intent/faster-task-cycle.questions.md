# Questions — faster-task-cycle
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Стъпка 2 (без пълен suite след MEDIUM/LOW фиксове и след редакции само в документи): къде живее промяната?
asked: 2026-10-29T18:17:17Z · stage: intent
A. само текст — rr-review и testing.md казват, че MEDIUM/LOW не се поправят в задачата, а отиват в known-risks; правилото на close не се пипа
B. само state.py — close приема verify --scope step/--files, когда diff-ът след последното зелено пускане е само в не-кодови файлове (.md, .json под docs/.ai); текстът не се пипа
C. и двете — A за находките, B за документните редакции (recommended)
X. Other — answer as `X: <text>`
[Answer]: C — by vanssa via prose at 2026-10-29T18:40:05Z

## Q2. Паралелният runner за verify_command: с какво?
asked: 2026-10-29T18:40:05Z · stage: intent
A. собствен скрипт tests/run_suite.py само със stdlib — един процес на тестов файл, concurrent.futures, обединен unittest изход, exit 1 при всеки червен; TestTimed се пуска сериен след останалите (recommended)
B. pytest + pytest-xdist (-n auto) — нова зависимост, unittest тестовете се пускат от pytest
C. оставяме unittest discover сериен, само ускоряваме бавните файлове (споделен fixture в test_ai_task_state и др.)
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-29T18:41:59Z

## Q3. Бюджетът на reviewer-а (стъпка 3): как се налага?
asked: 2026-10-29T18:41:59Z · stage: intent
A. текст в rr-review и в agents/ai-reviewer — диф + посочените тестове, без експерименти в scratchpad, до 40 tool calls; без код (recommended)
B. A плюс runtime-gate.py — бюджет reviewer_tool_calls в profile.json, при превишаване PreToolUse на субагента отказва следващия call и той връща вердикт с това, което има
C. само смяна на тиера — ревютата на BALANCED (Sonnet) не са по-бързи, всички ревюта на STRONG с текущите правила
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-29T18:43:07Z

## Q4. Тежестта (стъпка 4): как промени само в документи и само в тестове стават light?
asked: 2026-10-29T18:43:07Z · stage: intent
A. weight.json — нов пример в light за това хранилище: диф само в docs/, .ai/project/, .ai/reports/, README/CONTRIBUTING или само в tests/ (без hooks/, skills/, state.py) е light; constitution C6 остава както е
B. A плюс state.py weight — автоматично поставя behaviour 0 когда --files не съдържа кодов файл; човекът може да вдигне с --declare (recommended)
C. не пипаме тежестта — само записваме в CLAUDE.md че .md промените се оценяват на око
X. Other — answer as `X: <text>`
[Answer]: B — by vanssa via prose at 2026-10-29T18:44:28Z

## Q5. Стъпка 5 (по-малко отделни ходове) и критерий за готово: какво влиза?
asked: 2026-10-29T18:44:28Z · stage: intent
A. стъпка 5 е само текст в rr-build/rr-review/rr-ship (верижни команди step-done && verify, review && close); критерий: verify_command < 120 s на тази машина, измерено в доклада, и броят suite пускания на задача в state.json (recommended)
B. стъпка 5 отпада от задачата (печалбата е ~8 s на call); критерият е само suite < 120 s
C. A плюс нов sensor в rr-status --cost: минути suite и минути ревю на задача, за да се вижда ефектът след това
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-29T18:46:56Z

## Q6. Ред 4: правилото documents-only нулира ли и domain и novelty, или само behaviour?
asked: 2026-10-29T19:11:41Z · stage: intent
context: concern 8: behaviour 0 само не прави документна промяна light — domain и novelty остават unknown = 1 (weight.py:239-240)
A. и трите (behaviour, domain, novelty) — както е в дизайна (c) (recommended)
B. само behaviour; light примерът казва на сесията да декларира domain/novelty 0
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via picker at 2026-10-29T19:16:02Z

## Q7. Шаблоните за user проекти (documents ключ, doc_tests ред): сега или отделна задача след G1/G2?
asked: 2026-10-29T19:11:41Z · stage: intent
context: concern 10: шаблоните в skills/ai-init/templates и weight.md mirror остават непипнати; правилата са изключени за user проекти
A. отделна задача след измерване (R6) и G1/G2 (recommended)
B. сега, като ред 6 в batch-а
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via picker at 2026-10-29T19:16:02Z

## Q8. Таванът ~40 tool calls на reviewer-а важи ли и във full режим?
asked: 2026-10-29T19:11:41Z · stage: intent
context: ai-reviewer.md.tmpl:63-64 — в full режим списъкът 'look for' е неограничен
A. да, един таван за всички режими; недостигнатото се изброява като 'not reached (budget)'
B. full получава по-висок таван (~80) (recommended)
C. full е без таван; таванът е само за guarded/light
X. Other — answer as `X: <text>`
[Answer]: B — by vanssa via picker at 2026-10-29T19:16:02Z

## Q9. Правилото за документи в close (2b, D1-D5): в batch-а сега или отлагане, докато ред 1 е измерен?
asked: 2026-10-29T19:11:41Z · stage: intent
context: concern 3: след ред 1 пълният suite е ~60-100 s, правилото за документи спестява ~1 мин на повторение, но отслабва отказ (behaviour 2)
A. сега, както Q1=C (recommended)
B. отлагане: ред 2 прави само 2a (политика за находки); 2b става отделна задача, ако R6 не стигне
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via picker at 2026-10-29T19:16:02Z
