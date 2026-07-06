# Rig Email Slack Bot

Drop screenshots + a short caption into Slack → the bot uploads the images to Cloudinary,
has Claude write the release-notes copy and place each screenshot, builds the Rig-styled HTML
(via `email-builder/build_email.py`), and creates a **draft** Klaviyo campaign. It replies in the
thread with a preview link. **It never sends** — a human reviews and sends from Klaviyo.

```
Slack message (images + caption)
   → download images (files:read)
   → Cloudinary signed upload (from bytes)
   → Claude: caption + images ⇒ structured copy + image→section mapping
   → build_email.py ⇒ HTML
   → Klaviyo: create template + draft campaign + assign
   → reply in thread with campaign + template links
```

## How you use it (once running)
DM the bot (or post in a channel it's in) with your screenshots attached and a caption like:

> **RBAC & Graph Toggles.** New user-management page with Admin/Manager/User tiers, connector
> deletion from the UI, and a vertical/horizontal toggle in Access Explorer.

Attach the screenshots in the **order** you want them to appear. That's it — the bot replies with
a Klaviyo draft link.

## Setup

### 1. Create the Slack app
- https://api.slack.com/apps → **Create New App → From an app manifest** → paste [`manifest.yaml`](manifest.yaml).
- **Install to Workspace**, copy the **Bot User OAuth Token** (`xoxb-…`) → `SLACK_BOT_TOKEN`.
- **Basic Information → App-Level Tokens** → generate one with `connections:write` (`xapp-…`) → `SLACK_APP_TOKEN`.
- Invite the bot to a channel (`/invite @rig-email-builder`) or just DM it.

### 2. Configure env
```bash
cp .env.example .env
# fill in the tokens/keys
```
You'll need: Slack bot + app tokens, an Anthropic API key, Cloudinary cloud/key/**secret**
(rotate the one shared earlier and put a fresh secret here), and a Klaviyo **private** API key
with Templates + Campaigns write scopes.

### 3. Run
```bash
npm install
npm start        # ⚡️ connects via Socket Mode — no public URL needed
```

## Hosting
Socket Mode means no inbound webhook, so it runs anywhere with outbound internet:
- **Easiest:** Render / Railway / Fly.io background worker (`npm start`), or a small VM with `pm2`/systemd.
- Needs **Node ≥18** and **python3** on the host (the bot shells out to `build_email.py`).
- Keep `.env` secret (it holds 4 sets of credentials). Add `.env` to `.gitignore`.

## Notes & knobs
- `ALLOWED_CHANNEL` in `.env` restricts the bot to one channel; leave blank to respond anywhere it's added.
- The design lives entirely in `../email-builder/build_email.py` — change styling there and the bot picks it up.
- Images are matched to sections by Claude using their upload order; caption cues ("first screenshot shows…") help.
- Multiple screenshots + caption should be sent in **one** Slack message (one message = one email).

## Not included (easy add-ons)
- **Rendered preview image** in the Slack reply (needs a headless browser like Puppeteer).
- **Approve-to-send**: react ✅ on the bot's reply to trigger the Klaviyo send (add a `reaction_added` handler).
- **Multi-message batching**: collect images across several messages before building.
