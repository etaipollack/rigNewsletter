#!/usr/bin/env python3
"""
Deterministic publish step for the Rig email routine.

Input:  a content.json in the build_email.py schema. Image `src`/`icon`/`logo` values
        may be LOCAL FILE PATHS (the routine drops the request's images on disk) or URLs.
What it does, with no LLM in the loop:
  1. Uploads every local image to Cloudinary (signed) and rewrites the paths to URLs.
  2. Builds the HTML via build_email.py.
  3. Creates a Klaviyo email template + DRAFT campaign + assigns the template.
  4. POSTs a JSON payload (with the campaign link) to the callback URL.
  5. Prints a machine-readable JSON result to stdout.

Network calls go through `curl` (system trust store) for portability.

Usage:
  python3 publish_campaign.py content.json --callback https://your/endpoint [--subject "..."] [--no-callback]

Env (required): CLOUDINARY_CLOUD, CLOUDINARY_KEY, CLOUDINARY_SECRET,
                KLAVIYO_API_KEY, KLAVIYO_LIST_ID, KLAVIYO_FROM_EMAIL
Env (optional): KLAVIYO_FROM_LABEL (default "Rig"), BUILD_SCRIPT
"""
import os, sys, json, re, time, hashlib, subprocess, tempfile, argparse, pathlib

HERE = pathlib.Path(__file__).resolve().parent
REVISION = "2024-10-15"

def log(*a): print("[publish]", *a, file=sys.stderr, flush=True)

def env(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and not v:
        sys.exit(f"Missing required env var: {name}")
    return v

def curl(args):
    """Run curl, return (ok, parsed_json_or_text, raw)."""
    p = subprocess.run(["curl", "-s", "-w", "\n%{http_code}", *args],
                       capture_output=True, text=True)
    raw = p.stdout
    body, _, code = raw.rpartition("\n")
    ok = code.startswith("2")
    try:
        return ok, json.loads(body), body
    except Exception:
        return ok, body, body

# ---- Cloudinary ------------------------------------------------------------
def cloud_upload(path, cfg, cache):
    if path in cache:
        return cache[path]
    stem = re.sub(r'[^a-z0-9]+', '-', pathlib.Path(path).stem.lower()).strip('-') or "img"
    pid = f"auto/{stem}-{hashlib.md5(path.encode()).hexdigest()[:6]}"
    ts = int(time.time())
    sig = hashlib.sha1(f"overwrite=true&public_id={pid}&timestamp={ts}{cfg['secret']}".encode()).hexdigest()
    ok, j, raw = curl([
        "-X", "POST", f"https://api.cloudinary.com/v1_1/{cfg['cloud']}/image/upload",
        "-F", f"file=@{path}", "-F", f"api_key={cfg['key']}", "-F", f"timestamp={ts}",
        "-F", f"public_id={pid}", "-F", "overwrite=true", "-F", f"signature={sig}",
    ])
    if not (isinstance(j, dict) and j.get("secure_url")):
        sys.exit(f"Cloudinary upload failed for {path}: {raw[:300]}")
    url = j["secure_url"]
    cache[path] = url
    log(f"uploaded {path} -> {url}")
    return url

def resolve_local_images(obj, cfg, cache):
    """Recursively replace any string that is an existing local file with its Cloudinary URL."""
    if isinstance(obj, dict):
        return {k: resolve_local_images(v, cfg, cache) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_local_images(v, cfg, cache) for v in obj]
    if isinstance(obj, str) and not obj.startswith(("http://", "https://")) and os.path.isfile(obj):
        return cloud_upload(obj, cfg, cache)
    return obj

# ---- Build -----------------------------------------------------------------
def build_html(content):
    build_script = env("BUILD_SCRIPT", str(HERE / "build_email.py"))
    d = tempfile.mkdtemp(prefix="rig-email-")
    cj, out = os.path.join(d, "content.json"), os.path.join(d, "out.html")
    with open(cj, "w", encoding="utf-8") as f:
        json.dump(content, f)
    r = subprocess.run(["python3", build_script, cj, out], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"build_email.py failed: {r.stderr or r.stdout}")
    return open(out, encoding="utf-8").read()

# ---- Klaviyo ---------------------------------------------------------------
def kl_headers(key):
    return ["-H", f"Authorization: Klaviyo-API-Key {key}", "-H", f"revision: {REVISION}",
            "-H", "accept: application/json", "-H", "content-type: application/json"]

def kl_post(url, key, body):
    d = tempfile.mkdtemp(prefix="kl-")
    bf = os.path.join(d, "body.json")
    with open(bf, "w", encoding="utf-8") as f:
        json.dump(body, f)
    ok, j, raw = curl(["-X", "POST", url, *kl_headers(key), "--data-binary", f"@{bf}"])
    if not ok or not isinstance(j, dict) or "data" not in j:
        sys.exit(f"Klaviyo POST {url} failed: {raw[:400]}")
    return j

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("content_json")
    ap.add_argument("--callback", default=os.environ.get("CALLBACK_URL", ""))
    ap.add_argument("--subject", default=None)
    ap.add_argument("--no-callback", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="Upload images + build HTML, but skip Klaviyo + callback")
    args = ap.parse_args()

    cloud_cfg = {"cloud": env("CLOUDINARY_CLOUD", required=True),
                 "key": env("CLOUDINARY_KEY", required=True),
                 "secret": env("CLOUDINARY_SECRET", required=True)}
    content = json.load(open(args.content_json, encoding="utf-8"))

    # 1. Resolve local images -> Cloudinary URLs
    content = resolve_local_images(content, cloud_cfg, {})

    # 2. Build HTML
    html = build_html(content)

    meta = content.get("meta", {})
    subject = args.subject or meta.get("headline") or "Rig Release Notes"
    preview = meta.get("preheader", "")
    name = (meta.get("headline") or subject)[:120]

    if args.dry_run:
        print(json.dumps({"status": "dry-run", "subject": subject,
                          "html_bytes": len(html), "images": html.count("res.cloudinary.com"),
                          "sections": len(content.get("sections", []))}))
        return

    kl_key = env("KLAVIYO_API_KEY", required=True)
    list_id = env("KLAVIYO_LIST_ID", required=True)
    from_email = env("KLAVIYO_FROM_EMAIL", required=True)
    from_label = env("KLAVIYO_FROM_LABEL", "Rig")

    # 3. Klaviyo template + draft campaign + assign
    tpl = kl_post("https://a.klaviyo.com/api/templates/", kl_key,
                  {"data": {"type": "template", "attributes": {"name": f"{name} (auto)", "editor_type": "CODE", "html": html}}})
    template_id = tpl["data"]["id"]

    camp = kl_post("https://a.klaviyo.com/api/campaigns/", kl_key,
                   {"data": {"type": "campaign", "attributes": {
                       "name": name,
                       "audiences": {"included": [list_id]},
                       "campaign-messages": {"data": [{"type": "campaign-message", "attributes": {"definition": {
                           "channel": "email", "label": name,
                           "content": {"subject": subject, "preview_text": preview,
                                       "from_email": from_email, "from_label": from_label,
                                       "reply_to_email": from_email}}}}]}}}})
    campaign_id = camp["data"]["id"]
    message_id = camp["data"]["relationships"]["campaign-messages"]["data"][0]["id"]

    kl_post("https://a.klaviyo.com/api/campaign-message-assign-template/", kl_key,
            {"data": {"type": "campaign-message", "id": message_id,
                      "relationships": {"template": {"data": {"type": "template", "id": template_id}}}}})

    result = {
        "status": "ok",
        "subject": subject,
        "campaign_id": campaign_id,
        "campaign_url": f"https://www.klaviyo.com/campaign/{campaign_id}/wizard",
        "template_id": template_id,
        "template_url": f"https://www.klaviyo.com/email-editor/{template_id}/edit",
        "sections": len(content.get("sections", [])),
    }
    log(f"draft campaign created: {result['campaign_url']}")

    # 4. Callback
    if args.callback and not args.no_callback:
        d = tempfile.mkdtemp(prefix="cb-")
        bf = os.path.join(d, "cb.json")
        with open(bf, "w", encoding="utf-8") as f:
            json.dump(result, f)
        ok, _, raw = curl(["-X", "POST", args.callback,
                           "-H", "content-type: application/json", "--data-binary", f"@{bf}"])
        result["callback_status"] = "ok" if ok else "failed"
        log(f"callback {args.callback} -> {result['callback_status']}")

    # 5. Machine-readable result on stdout
    print(json.dumps(result))

if __name__ == "__main__":
    main()
