# Rig Email Publishing Routine (API-triggered Claude Code)

Your API trigger invokes Claude Code headless; Claude turns the request text into structured
content; a deterministic script does upload → build → Klaviyo → callback. It replies with the
campaign link and POSTs it back to your endpoint. **Always a draft — never auto-sends.**

```
API request ──► your trigger writes request.json + saves images to disk
            └─► claude -p "/publish-email /path/to/request.json"
                     │  Claude: request.json ──► content.json (formatted copy, images mapped)
                     ▼
                python3 email-builder/publish_campaign.py content.json --callback <url>
                     │  1. upload local images to Cloudinary (signed)
                     │  2. build HTML via build_email.py
                     │  3. Klaviyo: template + DRAFT campaign + assign
                     │  4. POST {campaign_url, ...} to callback_url
                     ▼
                stdout: {"status":"ok","campaign_url":"https://www.klaviyo.com/campaign/<id>/wizard", ...}
```

## The two pieces
- **`.claude/commands/publish-email.md`** — the routine (the Claude prompt). Reads `request.json`,
  writes `content.json`, runs the publisher, returns its JSON.
- **`email-builder/publish_campaign.py`** — the deterministic publisher (no LLM). Handles Cloudinary,
  build, Klaviyo, and the callback. Test it standalone with `--dry-run`.

## request.json contract (your trigger produces this)
```json
{
  "text": "raw release notes...",
  "images": ["/abs/path/img1.png", "/abs/path/img2.png"],
  "callback_url": "https://your-endpoint/notify",
  "date_label": "/Release Notes for July 6th, 2026",   // optional
  "subject": "optional subject override"                // optional
}
```
The callback receives:
```json
{ "status":"ok", "subject":"...", "campaign_id":"...",
  "campaign_url":"https://www.klaviyo.com/campaign/<id>/wizard",
  "template_id":"...", "template_url":"...", "sections": 2 }
```

## How your trigger should invoke it
```bash
# env must be exported for the publisher (see below)
claude -p "/publish-email /path/to/request.json" \
  --output-format text \
  --allowedTools "Read,Write,Bash"
# Claude's final stdout line is the result JSON (also delivered to callback_url).
```
Run it with the working directory set to this project root so relative paths resolve.

## Required environment (export before invoking, or put in the trigger's env)
```
CLOUDINARY_CLOUD=your_cloud_name
CLOUDINARY_KEY=your_cloudinary_key
CLOUDINARY_SECRET=__ROTATE_AND_USE_A_FRESH_SECRET__
KLAVIYO_API_KEY=pk_...            # private key, Templates + Campaigns write
KLAVIYO_LIST_ID=YOUR_LIST_ID            # the "Email List" audience
KLAVIYO_FROM_EMAIL=you@example.com
KLAVIYO_FROM_LABEL=Rig
# optional: BUILD_SCRIPT=/abs/path/email-builder/build_email.py
```

## Test the publisher without Claude or Klaviyo
```bash
# uploads images + builds HTML only; skips Klaviyo + callback
CLOUDINARY_CLOUD=... CLOUDINARY_KEY=... CLOUDINARY_SECRET=... \
python3 email-builder/publish_campaign.py content.json --dry-run
```

## Notes
- Local images in `content.json` (any string that's an existing file path) are auto-uploaded and
  rewritten to Cloudinary URLs; existing `https://` URLs are left untouched.
- The design lives in `build_email.py`; the routine and publisher never hardcode styling.
- Rotate the Cloudinary secret shared earlier and keep all keys out of the repo.
```
