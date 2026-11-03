# Reviewed reader data

Start from `examples/demo-pack.json`. It is a complete original example, not an academic source. Keep real packs in `data/weeks/YYYY-MM-DD/`; originals and translated content must not be committed to this public template.

## Pack fields

- `schema`: currently 1.
- `project_id`: a stable personal identifier, not an email address. Browser progress is keyed by this and the week.
- `week`: ISO date of the target Monday. `week_label` can describe the teaching week.
- `title`, `timezone`.
- `language`: `name`, language `code`, `direction` (`ltr` or `rtl`), and `mode` (`english-only`, `bilingual-summaries`, `bilingual-full`). This configures presentation; it does not generate a translation.
- `guide`: title, introduction/optional translation, verification note, sessions, actions, gaps and phrases. All these strings are plain text. Sessions/actions are verified information or explicitly labelled suggestions.
- `documents`: the reading catalogue and reader entries.
- `assets`: explicit relative paths to permitted local originals/images under `assets/` or `sources/`. Assets are copied into the generated reader. Scripts, HTML, SVG, secrets and traversal paths are rejected.

## Documents and paragraphs

Each document has a stable `id`, `title`, `author`, `course`, `session`, `status`, `source_category`, `requirement_basis`, `pages`, `source_url`, optional `download`, `checked_at`, `official_deadline`, `suggested_read_by`, `access_status`, `translation_coverage`, `questions`, and `units`.

`status` is Required, Preparation, Recommended or Background. Preserve a source's original Further/Extended label in `source_category`; record uncertain classification explicitly. `content_kind` is `full-text`, `summary`, `study-guide` or `reference-only`. A full-text entry must actually contain the complete specified reading range. A bilingual-summaries pack should label summaries as summaries.

Each unit has an ID, a page/section `label` and `flow`, an ordered array of paragraph pairs:

```json
{
  "id": "reading-a-p12-paragraph-2",
  "en": "<p>Source paragraph or explicitly labelled summary.</p>",
  "translation": "<p>Faithful translation into the selected language.</p>"
}
```

Use stable source-based IDs, not translation hashes. Reuse IDs when the English source is unchanged. If translation is missing in bilingual mode, provide `translation_gap` with the reason. English-only mode permits an empty translation. Never add filler merely to pass validation.

The builder allows a limited set of formatted HTML tags, tables, local images and native MathML. It strips scripts, event handlers and unsafe URLs. Do not rely on arbitrary inline CSS, iframes, embedded scripts, remote images or LaTeX being automatically rendered. Convert formulas to native MathML or permitted local images, retaining source notation and labels. Include source page images/PDF links where helpful.

Translations use the configured language tag and direction. English remains left-to-right. Add translations to the reviewed pack using your coding assistant; no paid translation API is built in.

## Build and use

```sh
python3 scripts/build_reader.py data/weeks/YYYY-MM-DD/reviewed-pack.json --output site/weeks/YYYY-MM-DD
python3 scripts/serve.py --directory site --port 8765
```

Open `http://127.0.0.1:8765/weeks/YYYY-MM-DD/`. A build writes `index.html`, `app.js`, `style.css`, `pack.js`, a reading manifest, and approved local assets. It does not call Canvas or translate material.

Keep the same project_id, week, hostname and port to preserve localStorage. Highlights store the selected range and source paragraph text. A changed paragraph is flagged for review. Translation improvements alone do not invalidate English highlights. Export/import progress through the toolbar; imports must match the project and week. Browser storage is not a cross-device backup.
