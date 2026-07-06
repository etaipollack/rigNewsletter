#!/usr/bin/env python3
"""
Rig email builder.

Reads a content JSON file and emits a finished, email-client-safe HTML file
styled exactly like the Rig "Release Notes" email. You supply text + image URLs;
this handles all the table markup, spacing, colors, and formatting.

Usage:
    python3 build_email.py content.json out.html

Inline text formatting supported anywhere text is accepted:
    **bold**              -> <strong>bold</strong>
    [label](https://url)  -> styled link
Everything else is HTML-escaped, so you can type & < > freely.

Content model (see content.example.json for a full example):
{
  "meta":   { "title", "preheader", "brand_label", "headline" },
  "brand":  { "header_logo", "spotlight_icon", "spotlight_label" },
  "intro":  { "icon", "text" },
  "sections": [
     { "number", "heading", "body", "bullets"[], "images"[{src,alt}],
       "card_groups"[ { "logo", "logo_w", "logo_h", "name",
                        "cards"[ {icon, title, body} ] } ] }
  ],
  "footer": { "logo", "thanks", "body", "legal" }
}
Every field is optional except where noted; omit what you don't need
(no bullets? drop "bullets". Plain section? just heading + body + images).
"""

import sys, json, re, html

# ---- Design tokens (single source of truth for the look) --------------------
FONT      = "'Segoe UI', Arial, Helvetica, sans-serif"
PAGE_BG   = "#f4f9fa"
HEAD_BG   = "#dff3ec"
ACCENT    = "#047866"   # green headings / links
INK       = "#24242d"   # body text
BRAND_INK = "#46485e"   # header label
PILL_BG   = "#d1faea"   # spotlight + card icon cell
LINE      = "#a7f3da"   # dividers + card borders
MUTED     = "#6b7280"   # footer legal
CONTENT_W = 595
IMG_W     = 535

# ---- Inline formatter -------------------------------------------------------
def fmt(text):
    """Escape HTML, then apply **bold** and [label](url)."""
    if text is None:
        return ""
    s = html.escape(str(text), quote=False)
    s = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',
               rf'<a href="\2" style="color:{ACCENT};text-decoration:underline;">\1</a>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    return s

def esc_attr(text):
    return html.escape(str(text or ""), quote=True)

# ---- Block builders ---------------------------------------------------------
def row(inner):
    return f'<tr><td style="padding:0 30px;">{inner}</td></tr>\n'

def divider():
    return (f'<tr><td style="padding:6px 30px;"><div style="height:1px;line-height:1px;'
            f'font-size:0;background:{LINE};">&nbsp;</div></td></tr>\n')

def spacer(px):
    return (f'<tr><td style="height:{px}px;line-height:{px}px;font-size:0;">&nbsp;</td></tr>\n')

def heading(number, text):
    num = f'<span style="color:{ACCENT};">{esc_attr(number)}.</span> ' if number else ""
    return (f'<tr><td style="padding:14px 30px 6px 30px;font-family:{FONT};font-size:13px;'
            f'font-weight:700;color:{INK};">{num}{fmt(text)}</td></tr>\n')

def paragraph_with_bullets(body, bullets):
    inner = fmt(body)
    if bullets:
        lis = ""
        for i, b in enumerate(bullets):
            mb = "margin-bottom:4px;" if i < len(bullets) - 1 else ""
            lis += f'<li style="{mb}">{fmt(b)}</li>\n'
        inner += (f'\n<ul style="margin:10px 0 4px 0;padding-left:18px;">\n{lis}</ul>')
    return (f'<tr><td style="padding:0 30px;font-family:{FONT};font-size:12px;'
            f'line-height:1.5;color:{INK};">{inner}</td></tr>\n')

def image_block(img):
    src = esc_attr(img.get("src"))
    alt = esc_attr(img.get("alt", ""))
    return (f'<tr><td style="padding:4px 30px 8px 30px;">'
            f'<img src="{src}" alt="{alt}" width="{IMG_W}" '
            f'style="display:block;width:100%;max-width:{IMG_W}px;height:auto;border:0;'
            f'border-radius:6px;" /></td></tr>\n')

def group_label(group):
    logo = group.get("logo")
    logo_html = ""
    if logo:
        w = group.get("logo_w", 24); h = group.get("logo_h", 24)
        logo_html = (f'<td valign="middle" style="padding-right:6px;">'
                     f'<img src="{esc_attr(logo)}" width="{w}" height="{h}" alt="" '
                     f'style="display:block;border:0;" /></td>')
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            'style="margin:0 0 8px 0;"><tr>'
            f'{logo_html}'
            f'<td valign="middle" style="font-family:{FONT};font-size:12px;font-weight:700;'
            f'color:{INK};">{fmt(group.get("name",""))}</td></tr></table>')

def finding_card(card):
    icon = card.get("icon")
    icon_cell = ""
    if icon:
        icon_cell = (f'<td width="44" valign="middle" align="center" '
                     f'style="width:44px;background:{PILL_BG};border-right:1px solid {LINE};'
                     f'border-radius:6px 0 0 6px;">'
                     f'<img src="{esc_attr(icon)}" width="24" height="24" alt="" '
                     f'style="display:block;width:24px;height:24px;border:0;" /></td>')
    title = f'<strong>{fmt(card.get("title"))}</strong> ' if card.get("title") else ""
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="border:1px solid {LINE};border-radius:6px;border-collapse:separate;'
            'margin:0 0 8px 0;"><tr>'
            f'{icon_cell}'
            f'<td valign="middle" style="padding:10px;font-family:{FONT};font-size:12px;'
            f'line-height:1.45;color:{INK};">{title}{fmt(card.get("body"))}</td>'
            '</tr></table>')

def card_group_row(group):
    inner = group_label(group) + "\n" + "\n".join(finding_card(c) for c in group.get("cards", []))
    return f'<tr><td style="padding:12px 30px 0 30px;">\n{inner}\n</td></tr>\n'

def section(sec, is_last):
    out = heading(sec.get("number"), sec.get("heading", ""))
    if sec.get("body") or sec.get("bullets"):
        out += paragraph_with_bullets(sec.get("body", ""), sec.get("bullets"))
    for img in sec.get("images", []):
        out += image_block(img)
    for grp in sec.get("card_groups", []):
        out += card_group_row(grp)
    if not is_last:
        out += divider()
    return out

# ---- Page assembly ----------------------------------------------------------
def build(content):
    meta   = content.get("meta", {})
    brand  = content.get("brand", {})
    intro  = content.get("intro", {})
    footer = content.get("footer", {})
    secs   = content.get("sections", [])

    title      = esc_attr(meta.get("title", "Email"))
    preheader  = fmt(meta.get("preheader", ""))
    brand_lbl  = fmt(meta.get("brand_label", ""))
    headline   = fmt(meta.get("headline", ""))

    # Header
    header = ""
    if brand.get("header_logo") or brand_lbl:
        logo = ""
        if brand.get("header_logo"):
            logo = (f'<td valign="middle" style="padding-right:8px;">'
                    f'<img src="{esc_attr(brand["header_logo"])}" width="60" height="26" alt="Rig" '
                    f'style="display:block;width:60px;height:26px;border:0;" /></td>')
        header += (f'<tr><td style="padding:22px 30px 0 30px;background:{HEAD_BG};font-family:{FONT};">'
                   '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
                   f'{logo}'
                   f'<td valign="middle" style="font-family:{FONT};font-size:13px;font-weight:600;'
                   f'letter-spacing:-0.4px;color:{BRAND_INK};">{brand_lbl}</td>'
                   '</tr></table></td></tr>\n')
    if headline:
        header += (f'<tr><td style="padding:12px 30px 22px 30px;background:{HEAD_BG};font-family:{FONT};'
                   f'font-size:22px;font-weight:700;letter-spacing:-0.5px;color:{INK};line-height:1.16;">'
                   f'{headline}</td></tr>\n')

    # Intro card
    intro_html = ""
    if intro.get("text"):
        icon = ""
        if intro.get("icon"):
            icon = (f'<td width="75" valign="middle" style="padding:15px 0 15px 15px;width:75px;">'
                    f'<img src="{esc_attr(intro["icon"])}" width="60" height="60" alt="" '
                    f'style="display:block;width:60px;height:60px;border:0;border-radius:8px;" /></td>')
        intro_html = ('<tr><td style="padding:22px 30px 0 30px;">'
                      '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
                      'style="background:#ffffff;border-radius:6px;"><tr>'
                      f'{icon}'
                      f'<td valign="middle" style="padding:15px;font-family:{FONT};font-size:12px;'
                      f'line-height:1.45;color:{INK};">{fmt(intro["text"])}</td>'
                      '</tr></table></td></tr>\n')

    # Spotlight pill
    pill = ""
    if brand.get("spotlight_label"):
        pill_icon = ""
        if brand.get("spotlight_icon"):
            pill_icon = (f'<td width="30" valign="middle" style="padding:8px 0 8px 8px;width:30px;">'
                         f'<img src="{esc_attr(brand["spotlight_icon"])}" width="16" height="16" alt="" '
                         f'style="display:block;width:16px;height:16px;border:0;" /></td>')
        pill = ('<tr><td style="padding:24px 30px 0 30px;">'
                '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
                f'style="background:{PILL_BG};border-radius:6px;"><tr>'
                f'{pill_icon}'
                f'<td valign="middle" style="padding:8px 8px 8px 7px;font-family:{FONT};font-size:14px;'
                f'font-weight:700;letter-spacing:-0.4px;color:{ACCENT};">'
                f'{fmt(brand["spotlight_label"])}</td></tr></table></td></tr>\n')
        pill += spacer(10)

    # Sections
    body = ""
    for i, sec in enumerate(secs):
        body += section(sec, is_last=(i == len(secs) - 1))
    body += divider()

    # Footer
    foot = ""
    if footer:
        flogo = ""
        if footer.get("logo"):
            flogo = (f'<img src="{esc_attr(footer["logo"])}" width="48" height="48" alt="Rig" '
                     f'style="display:block;width:48px;height:48px;border:0;border-radius:8px;'
                     f'margin:0 auto 10px auto;" />')
        thanks = (f'<div style="font-size:14px;font-weight:700;letter-spacing:-0.4px;color:{ACCENT};'
                  f'margin-bottom:6px;">{fmt(footer["thanks"])}</div>') if footer.get("thanks") else ""
        fbody  = (f'<div style="font-size:11px;font-weight:300;line-height:1.5;color:{ACCENT};'
                  f'max-width:392px;margin:0 auto;">{fmt(footer["body"])}</div>') if footer.get("body") else ""
        # legal / unsubscribe left as raw so Klaviyo tags like {% unsubscribe %} survive
        legal = ""
        if footer.get("legal"):
            legal = (f'<div style="font-size:11px;font-weight:300;line-height:1.5;color:{MUTED};'
                     f'max-width:392px;margin:14px auto 0 auto;">{footer["legal"]}</div>')
        foot = (f'<tr><td align="center" style="padding:50px 30px 60px 30px;font-family:{FONT};">'
                f'{flogo}{thanks}{fbody}{legal}</td></tr>\n')

    preheader_div = (f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;">'
                     f'{preheader}</div>') if preheader else ""

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta http-equiv="X-UA-Compatible" content="IE=edge" />
<title>{title}</title>
<!--[if mso]><style>table,td,div,p,a{{font-family:Arial,Helvetica,sans-serif !important;}}</style><![endif]-->
</head>
<body style="margin:0;padding:0;background:{PAGE_BG};">
{preheader_div}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{PAGE_BG};">
  <tr>
    <td align="center" style="padding:0;">
      <table role="presentation" width="{CONTENT_W}" cellpadding="0" cellspacing="0" border="0" style="width:{CONTENT_W}px;max-width:{CONTENT_W}px;background:{PAGE_BG};">
{header}{intro_html}{pill}{body}{foot}      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 build_email.py <content.json> <out.html>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        content = json.load(f)
    out = build(content)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(out)
    imgs = out.count("<img ")
    print(f"Wrote {sys.argv[2]}  ({len(out):,} bytes, {imgs} images, {len(content.get('sections', []))} sections)")

if __name__ == "__main__":
    main()
