# API access for a personal local project

Use Python 3.10 or newer. Run setup commands from your local copy of this repository. On Windows, `py -3` can replace `python3`.

Install the platform dependency with `python3 -m pip install -r requirements.txt` in a local virtual environment. This supplies the time-zone database on Windows; macOS and Linux use the system database.

## Credentials

If your institution permits manual tokens for personal development, open your institution's Canvas site and navigate to **Account → Settings → Approved Integrations → New Access Token**. Enter a descriptive purpose and follow the institution's expiration requirements. If the button is disabled, use an institution-approved integration or ask support; do not work around account restrictions.

[Canvas token management](https://community.instructure.com/en/kb/articles/662901-how-do-i-manage-api-access-tokens-in-my-user-account) · [Canvas authentication and OAuth requirements](https://developerdocs.instructure.com/services/canvas/oauth2/file.oauth)

In your own terminal, run:

```sh
python3 scripts/setup_token.py
```

Paste the token only at the hidden input prompt. This stores it outside the repository at `~/.config/canvas-study-companion/canvas.env`. On macOS/Linux the directory has mode 700 and the file 600. On Windows, confirm the file's ACL limits access to your account; an OS credential store is also suitable. The helper refuses non-interactive input and never prints the token.

The collector accepts `CANVAS_ACCESS_TOKEN` from its environment or reads the secret file. Prefer an OS credential-store integration or the helper; never type a literal token into a shell command. `--secret-file` accepts a path, never the secret value. A personal token may have broader account privileges, even though this collector performs only GET requests.

Do not paste credentials into chat, put them in config/, commit them, or embed them in a webpage. Do not collect classmates' tokens. A multi-user application requires approved OAuth; this template does not implement that service.

## Verify course access

Replace the example origin with your actual Canvas URL:

```sh
python3 scripts/discover_canvas.py --base-url https://canvas.example.edu
```

This saves a private `data/discovery.json`. To inspect only selected course IDs:

```sh
python3 scripts/discover_canvas.py --base-url https://canvas.example.edu --course 101 --course 102
```

The discovery lists course metadata and modules. It does not choose your teaching week or claim reading coverage. Your assistant should verify the timetable and select the appropriate IDs before collection.

Copy `examples/week-plan.example.json` to `config/week-YYYY-MM-DD.json`, fill real values, then run:

```sh
python3 scripts/collect_canvas.py --plan config/week-YYYY-MM-DD.json --output-root data
```

The collector follows [HTTP Link pagination](https://developerdocs.instructure.com/services/canvas/basics/file.pagination), retrieves omitted module items, follows relevant same-course links, and saves sanitized evidence and downloaded files. Authorization is restricted to the configured HTTPS API origin and is not forwarded to file-download hosts.

`complete` means the selected Canvas collection had no recorded errors, not that external readings or translations are complete. `partial` retains successful records plus gaps; `blocked` means no records were obtained. The first run is a baseline, not a list of newly published content.

## Troubleshooting

- **401 / 403:** check expiry, revocation, account permissions and institutional policy; do not print the token for debugging.
- **404 on a page index:** known page endpoints may still work. Record the index gap rather than saying the course has no pages.
- **Empty syllabus_body:** look for a PDF syllabus in modules.
- **Hidden or locked file:** the bundled collector skips it. Use the authorized course route and record the limitation.
- **429 / temporary server errors:** bounded retries are built in. A longer delay is reported rather than silently omitting records.
- **Library, LTI or Inspera:** use separate authorized access. A Canvas token cannot replace those services.
- **Network sandbox restrictions:** use the coding assistant's normal network-permission mechanism. Do not confuse a network block with an invalid token.

For an already authorized browser fallback, record the method as `browser_session_api`; do not extract browser cookies or pretend it was an independent token test. `--import-browser` accepts sanitized evidence and intentionally marks coverage partial.
