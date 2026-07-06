import 'dotenv/config';
import pkg from '@slack/bolt';
const { App } = pkg;

import { uploadBuffer } from './lib/cloudinary.js';
import { generateContent } from './lib/generate.js';
import { assembleContent, buildHtml } from './lib/buildEmail.js';
import { createTemplate, createCampaign, assignTemplate } from './lib/klaviyo.js';

const cfg = {
  buildScript: process.env.BUILD_SCRIPT || '../email-builder/build_email.py',
  allowedChannel: process.env.ALLOWED_CHANNEL || '',
  cloud: {
    cloud: process.env.CLOUDINARY_CLOUD,
    key: process.env.CLOUDINARY_KEY,
    secret: process.env.CLOUDINARY_SECRET,
  },
  brand: {
    headerLogo: process.env.BRAND_HEADER_LOGO,
    mascot: process.env.BRAND_MASCOT,
    spotlightIcon: process.env.BRAND_SPOTLIGHT_ICON,
  },
  klaviyo: {
    key: process.env.KLAVIYO_API_KEY,
    listId: process.env.KLAVIYO_LIST_ID,
    fromEmail: process.env.KLAVIYO_FROM_EMAIL,
    fromLabel: process.env.KLAVIYO_FROM_LABEL || 'Rig',
  },
  anthropic: {
    apiKey: process.env.ANTHROPIC_API_KEY,
    model: process.env.ANTHROPIC_MODEL || 'claude-sonnet-5',
  },
};

const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  appToken: process.env.SLACK_APP_TOKEN,
  socketMode: true,
});

// Build a "/Release Notes for <Month Dayth, Year>" label for today.
function dateLabel() {
  const d = new Date();
  const month = d.toLocaleString('en-US', { month: 'long' });
  const day = d.getDate();
  const suffix = [11, 12, 13].includes(day) ? 'th'
    : day % 10 === 1 ? 'st' : day % 10 === 2 ? 'nd' : day % 10 === 3 ? 'rd' : 'th';
  return `/Release Notes for ${month} ${day}${suffix}, ${d.getFullYear()}`;
}

async function downloadSlackFile(url, botToken) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${botToken}` } });
  if (!res.ok) throw new Error(`Slack file download ${res.status}`);
  return Buffer.from(await res.arrayBuffer());
}

const slug = (s) => (s || 'image').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40);

app.event('message', async ({ event, client, logger }) => {
  try {
    // Ignore bot messages, edits, joins, and anything without image files.
    if (event.subtype || event.bot_id) return;
    if (cfg.allowedChannel && event.channel !== cfg.allowedChannel) return;

    const files = (event.files || []).filter((f) => (f.mimetype || '').startsWith('image/'));
    if (!files.length) return;

    const caption = (event.text || '').trim();
    const thread_ts = event.ts;
    const react = (name) => client.reactions.add({ channel: event.channel, timestamp: event.ts, name }).catch(() => {});

    await react('hourglass_flowing_sand');
    await client.chat.postMessage({ channel: event.channel, thread_ts, text: `Got ${files.length} image(s) — building your Rig email…` });

    // 1. Download + upload each image to Cloudinary (in order).
    const stamp = event.ts.replace('.', '');
    const images = [];
    const imageUrls = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const buf = await downloadSlackFile(f.url_private_download || f.url_private, process.env.SLACK_BOT_TOKEN);
      const publicId = `slack/${stamp}-${i}-${slug(f.title || f.name)}`;
      const url = await uploadBuffer(buf, { ...cfg.cloud, publicId, mime: f.mimetype });
      imageUrls.push(url);
      images.push({ mime: f.mimetype, b64: buf.toString('base64') });
    }

    // 2. Claude writes the copy + maps images to sections.
    const gen = await generateContent({
      caption, images, apiKey: cfg.anthropic.apiKey, model: cfg.anthropic.model, dateLabel: dateLabel(),
    });

    // 3. Assemble + build HTML via the shared generator.
    const content = assembleContent(gen, imageUrls, cfg.brand);
    const html = await buildHtml(content, cfg.buildScript);

    // 4. Klaviyo: template + draft campaign + assign.
    const name = gen.headline.slice(0, 120);
    const templateId = await createTemplate(cfg.klaviyo.key, `${name} (auto)`, html);
    const { campaignId, messageId } = await createCampaign(cfg.klaviyo.key, {
      name,
      listId: cfg.klaviyo.listId,
      content: {
        subject: gen.headline,
        preview_text: gen.preheader,
        from_email: cfg.klaviyo.fromEmail,
        from_label: cfg.klaviyo.fromLabel,
        reply_to_email: cfg.klaviyo.fromEmail,
      },
    });
    await assignTemplate(cfg.klaviyo.key, messageId, templateId);

    // 5. Reply with links (draft only — a human sends it).
    await react('white_check_mark');
    await client.chat.postMessage({
      channel: event.channel,
      thread_ts,
      text:
        `*Draft ready:* ${gen.headline}\n` +
        `• Campaign (review & send): https://www.klaviyo.com/campaign/${campaignId}/wizard\n` +
        `• Template editor: https://www.klaviyo.com/email-editor/${templateId}/edit\n` +
        `• ${imageUrls.length} image(s) hosted on Cloudinary, ${content.sections.length} section(s).\n` +
        `_It's a draft — nothing was sent. Review, then hit send in Klaviyo._`,
    });
  } catch (err) {
    logger.error(err);
    await client.reactions.add({ channel: event.channel, timestamp: event.ts, name: 'x' }).catch(() => {});
    await client.chat.postMessage({
      channel: event.channel,
      thread_ts: event.ts,
      text: `:warning: Something went wrong building the email:\n\`\`\`${String(err.message || err).slice(0, 800)}\`\`\``,
    }).catch(() => {});
  }
});

(async () => {
  await app.start();
  console.log('⚡️ Rig email Slack bot is running (Socket Mode).');
})();
