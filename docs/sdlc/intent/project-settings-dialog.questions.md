# Questions — project-settings-dialog
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Какво е 'TUI диалогът' за настройките на проекта?
asked: 2026-10-30T14:19:34Z · stage: intent
A. Нативният диалог на runtime-а (AskUserQuestion / request_user_input), както при R36: hook-ът записва избора от tool_response, агентът не може да пише .ai/policies/*.json (recommended)
B. Собствено терминално TUI (python curses), което човекът стартира сам в своя терминал; агентът само подсказва командата
C. И двете: нативният диалог в сесията, плюс терминално TUI като резервен вариант при изключен диалог или Codex без request_user_input
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-30T14:20:41Z

## Q2. Кои настройки влизат в диалога за проекта в тази първа версия?
asked: 2026-10-30T14:20:41Z · stage: intent
A. Регистър от съществуващите политики, които човекът избира (dialog.enabled, verify_command, e2e_command, модулите on/off), всяка декларирана от модул; нова настройка = нов запис в регистъра (recommended)
B. Само dialog.enabled и флаговете за модулите; останалите политики остават както са днес
C. Всичко от .ai/policies/*.json (включително weight.json и path-guard.json), поле по поле
X. Other — answer as `X: <text>`
[Answer]: X: A — регистър от настройки, всяка декларирана от модула, който я ползва: dialog.enabled, verify_command, e2e_command и модулите вкл./изкл.; нова настройка = нов запис в регистъра; регистърът да може да се разширява впоследствие — by vanssa via prose at 2026-10-30T14:22:56Z

## Q3. Как сесията разбира, че има нова или ненастроена настройка, която трябва да се покаже в началото?
asked: 2026-10-30T14:21:49Z · stage: intent
A. Всяка настройка в регистъра има id и версия; .ai/policies/settings.json пази кои id-та човекът е потвърдил. SessionStart hook сравнява и само при разлика казва на агента да покаже диалога; иначе мълчи и не струва токени (recommended)
B. Сравнява се schema номерът на проекта с плъгина (както при --update); при нов schema се показват всички настройки
C. Hash на целия регистър; при промяна се показват всички настройки наново
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-30T14:24:27Z

## Q4. Кога се пускат собствените тестове на модула (които живеят в неговата папка)?
asked: 2026-10-30T14:24:27Z · stage: intent
A. verify пуска тестовете само на модулите, чиито файлове са в diff-а на задачата; e2e никога не ги пуска; CI пуска всички модулни тестове при всеки push (recommended)
B. Само когато модулът е променен — и локално, и в CI (CI също филтрира по diff)
C. Винаги като част от бързия verify_command (евтини са), но никога в e2e
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-30T14:25:46Z

## Q5. Къде живеят новите модули и как ги викат големите файлове (state.py, update.py, setup.py, hooks)?
asked: 2026-10-30T14:25:46Z · stage: intent
A. Общ пакет modules/<name>/ в repo-то (инсталира се в <home>/riskrails/modules/), всеки със __init__.py (публичен фасад), manifest (id, версия, настройки, може ли да се изключи) и tests/; state.py, setup.py и hooks внасят само фасада (recommended)
B. Под всяко skill поотделно (skills/ai-task/modules/<name>/); hooks внасят от пътя на skill-а
C. Един Python пакет riskrails/ с подпакети, инсталиран с pip/npm като зависимост
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-30T14:26:59Z

## Q6. Колко твърдо 'задължава' липсата на настройки за проекта?
asked: 2026-10-30T14:26:59Z · stage: intent
A. setup.py check връща SETTINGS_MISSING (като VERIFY_COMMAND_MISSING), а state.py start отказва нова задача, докато човекът не избере настройките в диалога; четенето и /rr-status работят (recommended)
B. Само напомняне от SessionStart; нищо не се блокира
C. Като R36: PreToolUse отказва всеки инструмент освен диалога, докато настройките не са избрани
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-30T14:27:35Z

## Q7. Флагът за изключване на модул (без имплементация сега): как се държи?
asked: 2026-10-30T14:27:35Z · stage: intent
A. settings.json има modules.<id>.enabled, manifest-ът има can_disable; регистърът го чете, но false само дава предупреждение 'изключването още не е имплементирано' и модулът работи; в диалога не се показва, докато не се имплементира (recommended)
B. Същото, но се показва и в диалога, маркирано '(още не действа)'
C. Само полета в manifest-а и в схемата на settings.json; нищо не ги чете
X. Other — answer as `X: <text>`
[Answer]: B — by vanssa via prose at 2026-10-30T14:28:37Z

## Q8. Какво става със съществуващия .ai/policies/dialog.json (R36)?
asked: 2026-10-30T14:28:37Z · stage: intent
A. Остава където е; модулът dialog го декларира в регистъра като своя настройка, settings.json пази само потвържденията и modules.*; без миграция на данни (recommended)
B. Слива се в нов .ai/policies/settings.json с миграция; dialog.json се маха след потвърждение от човека
C. Всички настройки (и verify_command от testing.md) се местят в settings.json
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-30T14:30:13Z

## Q9. OQ1: модул, който може да се изключва, във v1?
asked: 2026-10-30T15:01:54Z · stage: intent
A. can_disable:true на dialog и settings, превключвателите им се виждат '(още не действа)'
B. Да чакаме първия незадължителен модул
X. Other — answer as `X: <text>`
[Answer]: X: A — добави модула за диалозите и самите настройки (dialog и settings с can_disable:true) — by vanssa via prose at 2026-10-30T15:01:54Z

## Q10. OQ2: drifted (стойност, променена след потвърждението) блокира ли start?
asked: 2026-10-30T15:01:54Z · stage: intent
A. Блокира — задача не тръгва без потвърдени настройки
B. Само информативно
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-30T15:01:54Z

## Q11. Обхват на диалога за въпроси
asked: 2026-10-30T15:01:54Z · stage: intent
A. Всички записани въпроси (настройки като поредица, task, spec и plan брейнсторм) минават през диалога; над лимитите се разделят на логически групи и се пускат последователно
B. Само настройките
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-30T15:01:54Z

## Q12. Изключваемост на новите модули
asked: 2026-10-30T15:10:45Z · stage: intent
A. Нито един нов модул не е изключваем; за флага за изключване има отделен модул, който е само тестов
B. dialog и settings изключваеми (Q9)
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-30T15:10:45Z

## Q13. Как да се разделят спецификациите
asked: 2026-10-30T15:10:45Z · stage: intent
A. Две спецификации: (1) модулно разделяне — само settings като нов модул плюс извличане на части от state.py и още един голям файл; (2) диалозите — пуска се веднага след (1)
B. Една спецификация
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-30T15:10:45Z

## Q14. Свободен текст в диалога (вариант, предложен от агента)
asked: 2026-10-30T15:10:45Z · stage: intent
A. Въпросът декларира free_text; hook-ът записва дословно текста от 'Other' (tool_response), с ограничения за размера и знаците; settle го прилага; за команда се показва втори диалог 'Use exactly: <text>' за потвърждение; агентът никога не подава текста (recommended)
B. Свободният текст остава само през чата или файла ([Answer]:)
X. Other — answer as `X: <text>`
[Answer]:
