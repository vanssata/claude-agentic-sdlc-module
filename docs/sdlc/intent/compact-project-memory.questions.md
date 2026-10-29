# Questions — compact-project-memory
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Трябва ли нов разработчик да възстановява пълната история кой какво кога е решил само от Git clone, без сървър и без чужда локална база?
asked: 2026-10-28T17:33:24Z · stage: intent
A. Да — Git носи сбитото знание и пълен архив на записаната история; локалната база се възстановява от тях. (recommended)
B. Не — Git носи само сбитото знание; пълната история се споделя отделно чрез архив или сървър.
X. Other — answer as `X: <text>`
[Answer]: X: Не е необходима цялата история. По задача трябва да се пази само необходимото, за да се види кой какво как и защо е направил. Желателна е проверка преди push за оптимизирана история. Трябва да се оцени дали локална база ускорява процесите. — by vanssa via prose at 2026-10-28T17:42:40Z

## Q2. Как да се групират в Git сбитите записи на приключените задачи?
asked: 2026-10-28T18:25:05Z · stage: intent
A. Пакети с уникални имена: един файл на разработчик за период или партида, нов файл при нов период; при двама души около 12 файла на година; без merge driver (recommended)
B. Един файл за проект, .ai/ledger.jsonl, append-only, слят с merge=union през .gitattributes; най-малко файлове, но зависи от merge driver, който не всеки hosting прилага, и редът на редовете след сливане не е гарантиран
C. Една директория на задача с два файла, events.jsonl и record.md; най-четимо в PR, но броят файлове расте с всяка задача
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-28T18:28:25Z

## Q3. Новият формат на номера на задачата да важи и във файловия режим?
asked: 2026-10-28T19:02:00Z · stage: intent
A. Да: колизията е бъг на файловия режим и един генератор означава по-малко тестове (recommended)
B. Не: само в режим packages; файловият режим продължава да се сблъсква
X. Other — answer as `X: <text>`
[Answer]: X: накъв слъг на задачата кратък но ясен — by vanssa via prose at 2026-10-28T19:11:30Z

## Q4. Командите recall и memory risk да работят и във файловия режим, така че никой skill да не чете known-risks.md цял?
asked: 2026-10-28T19:02:00Z · stage: intent
A. Да: само четене плюс текст в skill-овете, поведение 0 (recommended)
B. Не: текстът на skill-овете се разклонява по режим и четенето на 146 KB остава
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-28T19:11:30Z

## Q5. SQLite индексът да се строи само след измерен праг?
asked: 2026-10-28T19:02:00Z · stage: intent
A. Да: строи се, ако recall p95 е над 300 ms или search над 1 s при 1000 задачи в базовото измерване (recommended)
B. Не: индексът се доставя винаги
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-28T19:11:30Z

## Q6. Период по подразбиране за пакетите?
asked: 2026-10-28T19:02:00Z · stage: intent
A. Тримесечие: около 8 файла на година за двама души (recommended)
B. Месец: около 24 файла на година
C. Година: 2 файла, но големи
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-28T19:11:30Z
