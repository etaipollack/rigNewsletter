import { execFile } from 'node:child_process';
import { writeFile, readFile, mkdtemp } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

// Assemble the generator's output + uploaded image URLs into the build_email.py content schema.
export function assembleContent(gen, imageUrls, brand) {
  return {
    meta: {
      title: `Rig Security — ${gen.headline}`,
      preheader: gen.preheader,
      brand_label: gen.date_label,
      headline: gen.headline,
    },
    brand: {
      header_logo: brand.headerLogo,
      spotlight_icon: brand.spotlightIcon,
      spotlight_label: gen.spotlight_label || "What's New This Release",
    },
    intro: { icon: brand.mascot, text: gen.intro_text },
    sections: (gen.sections || []).map((s) => ({
      number: s.number,
      heading: s.heading,
      body: s.body,
      bullets: s.bullets || [],
      images: (s.image_indices || [])
        .filter((i) => imageUrls[i])
        .map((i) => ({ src: imageUrls[i], alt: s.heading })),
      card_groups: s.card_groups || [],
    })),
    footer: {
      logo: brand.mascot,
      thanks: 'Thanks for reading!',
      body: gen.footer_body,
      legal:
        "You received this email as a Rig Security customer. If you'd prefer not to receive these updates, you can {% unsubscribe %}.",
    },
  };
}

// Shell out to the shared build_email.py so the design lives in exactly one place.
export async function buildHtml(content, buildScript) {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'rig-email-'));
  const jsonPath = path.join(dir, 'content.json');
  const outPath = path.join(dir, 'out.html');
  await writeFile(jsonPath, JSON.stringify(content), 'utf8');
  await new Promise((resolve, reject) =>
    execFile('python3', [buildScript, jsonPath, outPath], (err, _out, stderr) =>
      err ? reject(new Error(stderr || err.message)) : resolve()
    )
  );
  return readFile(outPath, 'utf8');
}
