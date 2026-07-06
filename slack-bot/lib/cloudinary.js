import crypto from 'node:crypto';

// Signed upload straight from an in-memory buffer (no temp file, no local-path issues).
export async function uploadBuffer(buf, { cloud, key, secret, publicId, mime }) {
  const ts = Math.floor(Date.now() / 1000);
  const toSign = `overwrite=true&public_id=${publicId}&timestamp=${ts}`;
  const signature = crypto.createHash('sha1').update(toSign + secret).digest('hex');

  const form = new FormData();
  form.append('file', new Blob([buf], { type: mime || 'application/octet-stream' }), publicId);
  form.append('api_key', key);
  form.append('timestamp', String(ts));
  form.append('public_id', publicId);
  form.append('overwrite', 'true');
  form.append('signature', signature);

  const res = await fetch(`https://api.cloudinary.com/v1_1/${cloud}/image/upload`, {
    method: 'POST',
    body: form,
  });
  const json = await res.json();
  if (!json.secure_url) throw new Error('Cloudinary upload failed: ' + JSON.stringify(json));
  return json.secure_url;
}
