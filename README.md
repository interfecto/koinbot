# koinbot

Telegram community bot for [Koinos](https://koinos.io): join captcha,
moderation helpers, info commands, and an ecosystem project directory
with per-project updates.

## Updating the bot via pull request

All user-facing text lives in [`content/`](content/) — **you can change
what the bot says without touching code**:

- [`content/commands.yml`](content/commands.yml) — the static
  `/commands` (add a new key = add a new command) and the texts behind
  the menu buttons.
- [`content/projects.yml`](content/projects.yml) — the ecosystem
  project directory shown by `/projects`.

### Adding a project update

Append an entry to your project's `updates` list in
`content/projects.yml`:

```yaml
  - id: my-project
    name: My Project
    url: https://example.com
    category: dApps & Platforms
    updates:
      - date: 2026-08-10
        text: "V2 launched — now with XYZ support"
```

Updates appear in `/updates` (newest first, across all projects) and in
`/project <name>`. Text may use Telegram HTML (`<b>`, `<i>`,
`<a href="...">`).

### How deployment works

1. Open a PR. CI validates the content files.
2. A maintainer reviews and merges.
3. **Merges that only touch `content/` go live automatically within
   ~2 minutes.** Anything touching code requires a manual deploy by the
   server operator — code is never auto-deployed.

## Commands

| Command | Source |
|---|---|
| `/info`, `/start`, `/menu` | code (menu from `texts.main_menu`) |
| `/projects`, `/project <name>`, `/updates` | rendered from `projects.yml` |
| `/report` | code |
| `/mana`, `/rules`, `/claim`, `/price`, `/supply`, `/vhpsupply`, `/roadmap`, `/website`, `/programs`, ... | `commands.yml` |

## Running

```bash
cp .env.example .env   # set TELEGRAM_BOT_TOKEN (and optional ADMIN_CHAT_ID)
docker compose up -d --build
```

The container is hardened: non-root, read-only filesystem, all
capabilities dropped, memory-limited. The bot uses long polling — no
inbound ports are required.

Validate content locally:

```bash
pip install -r requirements.txt
python content.py
```

## Server-side auto-updater

`deploy/koinbot-update.sh` (installed to `/usr/local/bin`, driven by the
`deploy/koinbot-update.{service,timer}` systemd units) fetches
`origin/main` every 2 minutes and:

- deploys content-only changes (validates them in the bot image first;
  rolls back and keeps the old content if validation fails),
- never applies code changes — it logs to `/var/log/koinbot-update.log`
  and notifies `ADMIN_CHAT_ID` once per pending commit.
