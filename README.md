# Newsletter Email Builder

Tools for producing a consistent, email-client-safe HTML newsletter from simple content —
plus an API-triggered routine that turns a text + images request into a Klaviyo **draft** campaign.

> All screenshots and copy in this repo are **placeholders/samples**. Point the config at your
> own Cloudinary + Klaviyo + brand assets to use it for real.

## What's here

| Path | What it is |
|------|------------|
| `email-builder/build_email.py` | Content JSON → styled, table-based HTML email. The single source of the design. |
| `email-builder/content.example.json` | A sample content file showing every block (header, intro, spotlight, sections, finding cards, footer). |
| `index.html` | The example output, rendered from `content.example.json`. |
| `email-builder/publish_campaign.py` | Deterministic publisher: upload local images → Cloudinary, build HTML, create a Klaviyo draft campaign, POST the result to a callback. |
| `.claude/commands/publish-email.md` | A Claude Code routine that turns a `request.json` (text + images + callback) into a draft campaign. |
| `email-builder/ROUTINE.md` | How to run the routine (API-triggered / headless). |
| `slack-bot/` | Optional Slack bot: drop screenshots + a caption in Slack, get a draft campaign back. |

## Quick start

```bash
# 1. Build the sample email
python3 email-builder/build_email.py email-builder/content.example.json out.html
open out.html

# 2. (optional) Publish — needs Cloudinary + Klaviyo env vars (see email-builder/ROUTINE.md)
python3 email-builder/publish_campaign.py email-builder/content.example.json --dry-run
```

See `email-builder/README.md` for the content schema and `email-builder/ROUTINE.md` for the
API-triggered routine. Never commit real secrets — copy `*.env.example` to `.env` (git-ignored).
