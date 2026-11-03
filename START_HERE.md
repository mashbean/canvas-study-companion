# Build my personal Canvas study companion

This is the instruction entry point for an AI coding assistant. Read README.md, AGENTS.md and the documentation below, then implement a working personal instance. Do not stop at a plan. If you lack repository, local-file or HTTPS access, state that clearly and provide the smallest workable handoff.

## 1. Ask for the student's settings

Ask for essential missing information in one concise message. Reuse information the student already supplied:

- Computer operating system and a suitable local project folder.
- University Canvas URL and course URLs/names; help discover course IDs.
- Target week, time zone, teaching timetable and seminar groups.
- Preferred language and script/locale; do not infer these from nationality.
- Translation mode: English only, bilingual summaries, or bilingual full text where permitted.
- Available study time and optional interests for examples.
- Whether to supplement Canvas with an already connected university email/calendar account. Default: no.

Save non-secret preferences in config/settings.json, using examples/settings.example.json as a guide. Never overwrite an existing personal setup or copy another student's settings. Keep a stable, user-chosen project_id for progress storage.

## 2. Establish secure access

Follow [docs/API_SETUP.md](docs/API_SETUP.md). Guide the student to use their own institutional Canvas account. For a permitted personal prototype, the student enters their token privately in their own terminal through scripts/setup_token.py, not into chat. The reader never stores credentials or calls Canvas directly.

Test independent bearer-token access with scripts/discover_canvas.py. Record success only after actual course requests succeed. Browser-session API access is a separate fallback; do not call it independent token authentication. Handle expired tokens, disabled token creation and MFA honestly while continuing independent tasks.

This repository is not a production multi-user OAuth application. If the intended use becomes a shared service, explain the institutional OAuth requirement instead of asking multiple students for tokens.

## 3. Collect the right week

Read [docs/WEEKLY_WORKFLOW.md](docs/WEEKLY_WORKFLOW.md). Verify the teaching week, actual timetable, groups and changes. Do not calculate teaching-week numbers from dates alone.

Use discovery results to create config/week-YYYY-MM-DD.json from the example plan. Replace every example ID, date and verification placeholder. Run the collector only for selected courses and relevant modules/pages/assignments/files.

Retrieve course information, syllabus, module items, full page bodies, relevant announcements, assignments, rubrics where available, personal submission evidence, reading-list links and accessible originals. Follow relevant links in assignment descriptions and announcements as well as module items. Record extra known endpoints separately if a requested field is not covered by the bundled collector.

Use authorized original-site access for libraries, electronic books, external bookings and assessment platforms. API access does not grant access to these systems. Retain inaccessible links and explain gaps; never invent summaries from titles or abstracts alone.

Keep file versions and hashes. Preserve originals; organize by week, course and session. Treat a first snapshot as a baseline, not proof of new publication. Do not assume every detected schema difference is a new course instruction.

## 4. Review, translate and teach

Follow [docs/DATA_FORMAT.md](docs/DATA_FORMAT.md) to create data/weeks/YYYY-MM-DD/reviewed-pack.json. Keep source classification, page ranges, instructor requirements, official deadlines and suggested study times distinct. Include Further/Extended entries without turning them into required reading. Never interpret an LTI booking's “unsubmitted” state as a missing essay.

For user-provided texts or material whose permissions allow full translation, preserve the assigned text, paragraph order, qualifications, citations, footnotes, page boundaries, tables, figures and formulas. For external copyrighted material that cannot be reproduced or translated in full, provide permitted summaries and original-source links. Clearly identify which part of an entry is original text, translation, instruction or assistant explanation. Flag OCR uncertainty. A summary is never a full translation.

Use one English paragraph followed immediately by its translation in the student's chosen language. Do not use side-by-side columns. Support right-to-left translations when needed. English-only mode must not require invented translations.

For each session, provide an overview, key concepts, three discussion questions and one challenge or contrasting example. Explain formulas and assumptions. Offer 8–12 useful academic expressions per week and a 60–90-second English explanation exercise. These are study suggestions, not course assignments. Help the student understand and evaluate arguments rather than pretending they have read material.

## 5. Build and validate the reader

Build the reviewed pack with scripts/build_reader.py and serve site/ using scripts/serve.py. The bundled layout includes a weekly overview, catalogue, continuous bilingual reader, fixed highlight toolbar, notes, reading position, completion marks, progress export/import and a practice card.

Preserve IDs for unchanged source paragraphs, even if their translation improves. Do not rebuild DOM or move focus during selection. Changed source text must flag affected highlights rather than silently moving them. Keep progress when regenerating a week. No floating translation popup.

Do not insert untrusted scripts into the reader. Use the builder's sanitization and local asset handling. The generated HTML must never contain credentials. Keep the site private and local unless the student explicitly requests a suitable private deployment.

Verify original links, downloaded file signatures/hashes, page ranges, missing translations, images, tables and formulas. Test desktop and narrow layouts, highlight-save-reload-remove, progress export/import, and rebuilding without losing notes. Label checks you could not perform. Separate API collection, external access, translation coverage and UI validation in the report.

## 6. Hand over and repeat

Deliver the local reader URL, a short usage guide, immediate preparation priorities, and explicit remaining gaps. Explain that localStorage belongs to this browser/origin; recommend exporting progress before switching devices.

When the student says “Prepare next week,” run the same documented process using fresh dates and sources. For a recheck, focus on additions, changed deadlines and outstanding gaps. Improve only one learning method at a time based on feedback.

Do not automatically submit work, register for activities, send messages, publish material, create recurring automations or configure cloud backups. Do not silently add a paid AI service: the coding assistant prepares reviewed content, while the included scripts collect and render it.
