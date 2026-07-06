import Anthropic from '@anthropic-ai/sdk';

// Claude sees the images + caption and returns the email structure.
// It references images by INDEX (not URL) so it never has to reproduce long URLs.
const SYSTEM = `You are an email copy generator for Rig Security's "Release Notes" newsletter.
Given a caption/notes and a set of product screenshots (referenced by index), produce a JSON
object describing the email. Respond with ONLY valid JSON, no prose, no code fences.

Schema:
{
  "headline": string,               // short, punchy title for the release
  "preheader": string,              // 1 sentence inbox-preview summary
  "date_label": string,             // e.g. "/Release Notes for July 6th, 2026"
  "spotlight_label": string,        // e.g. "What's New This Release"
  "intro_text": string,             // 1-2 sentence intro; use **bold** for key terms
  "sections": [
    {
      "number": string,             // "1", "2", ...
      "heading": string,
      "body": string,               // may use **bold**
      "bullets": [string],          // optional; each may use "**Label:** text"
      "image_indices": [number]     // which screenshots belong in this section
    }
  ],
  "footer_body": string             // closing CTA line
}

Rules:
- Use every provided image index exactly once, placed in the most relevant section.
- Write concise, professional B2B security product copy. Emphasize key terms with **bold**.
- If the caption already contains structured sections/bullets, follow that structure faithfully.
- Use the date label provided in the user message.`;

export async function generateContent({ caption, images, apiKey, model, dateLabel }) {
  const client = new Anthropic({ apiKey });

  const imageBlocks = images.flatMap((img, i) => [
    { type: 'text', text: `Image index ${i}:` },
    { type: 'image', source: { type: 'base64', media_type: img.mime, data: img.b64 } },
  ]);

  const msg = await client.messages.create({
    model: model || 'claude-sonnet-5',
    max_tokens: 2500,
    system: SYSTEM,
    messages: [
      {
        role: 'user',
        content: [
          {
            type: 'text',
            text:
              `Date label to use: ${dateLabel}\n\n` +
              `Caption / release notes:\n${caption || '(none provided — infer from the images)'}\n\n` +
              `There are ${images.length} images, indices 0..${images.length - 1}. Return ONLY the JSON.`,
          },
          ...imageBlocks,
        ],
      },
    ],
  });

  const text = msg.content
    .filter((b) => b.type === 'text')
    .map((b) => b.text)
    .join('')
    .trim()
    .replace(/^```(?:json)?/i, '')
    .replace(/```$/, '')
    .trim();

  return JSON.parse(text);
}
