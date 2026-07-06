# Rig Email Builder

Turn plain text + image URLs into a finished, Rig-styled HTML email — the same
design as the "Release Notes" campaign. You edit one JSON file; the script emits
email-client-safe HTML (table layout, inlined styles, MSO fallbacks).

## Usage

```bash
python3 build_email.py content.json out.html
```

Start from the example (it reproduces the June 29th release-notes email exactly):

```bash
cp content.example.json content.json
# edit content.json with your text + image URLs
python3 build_email.py content.json out.html
open out.html   # preview in a browser
```

## Writing content

Everything lives in `content.json`. Text fields accept lightweight formatting:

| You type | You get |
|----------|---------|
| `**bold**` | **bold** |
| `[Acme](https://example.com)` | a styled green link |
| `&` `<` `>` | escaped automatically — just type them |

### Structure

- **meta** — `title`, `preheader` (inbox preview text), `brand_label`, `headline`
- **brand** — `header_logo`, `spotlight_icon`, `spotlight_label`
- **intro** — the white intro card: `icon` + `text`
- **sections[]** — each numbered block:
  - `number`, `heading`, `body`
  - `bullets[]` — optional bulleted list
  - `images[]` — `{ "src", "alt" }`, one full-width screenshot per entry
  - `card_groups[]` — optional finding cards (the Salesforce/GitLab style):
    `{ "logo", "logo_w", "logo_h", "name", "cards": [ { "icon", "title", "body" } ] }`
- **footer** — `logo`, `thanks`, `body`, `legal`

Omit anything you don't need — a section can be just a heading + body, or heading + images.
The `legal` field is passed through raw, so Klaviyo tags like `{% unsubscribe %}` survive.

## Images

Host images somewhere with public URLs (email clients can't read local files) and put those
URLs in the JSON. To upload a local folder to Cloudinary from disk, see the signed-upload
approach used for this project. Once uploaded, a Cloudinary URL like
`https://res.cloudinary.com/<cloud>/image/upload/<name>.png` works directly.

## Pushing to Klaviyo

The generated `out.html` drops straight into the Klaviyo `create_email_template` tool
(editor_type `CODE`), then `create_campaign` + `assign_template_to_campaign_message`.
Keep the `{% unsubscribe %}` tag in the footer — Klaviyo requires it.
