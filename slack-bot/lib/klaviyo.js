const REVISION = '2024-10-15';

function headers(key) {
  return {
    Authorization: `Klaviyo-API-Key ${key}`,
    revision: REVISION,
    accept: 'application/json',
    'content-type': 'application/json',
  };
}

export async function createTemplate(key, name, html) {
  const res = await fetch('https://a.klaviyo.com/api/templates/', {
    method: 'POST',
    headers: headers(key),
    body: JSON.stringify({
      data: { type: 'template', attributes: { name, editor_type: 'CODE', html } },
    }),
  });
  const json = await res.json();
  if (!res.ok) throw new Error('Klaviyo createTemplate: ' + JSON.stringify(json));
  return json.data.id;
}

export async function createCampaign(key, { name, listId, content }) {
  const body = {
    data: {
      type: 'campaign',
      attributes: {
        name,
        audiences: { included: [listId] },
        'campaign-messages': {
          data: [
            {
              type: 'campaign-message',
              attributes: { definition: { channel: 'email', label: name, content } },
            },
          ],
        },
      },
    },
  };
  const res = await fetch('https://a.klaviyo.com/api/campaigns/', {
    method: 'POST',
    headers: headers(key),
    body: JSON.stringify(body),
  });
  const json = await res.json();
  if (!res.ok) throw new Error('Klaviyo createCampaign: ' + JSON.stringify(json));
  return {
    campaignId: json.data.id,
    messageId: json.data.relationships['campaign-messages'].data[0].id,
  };
}

export async function assignTemplate(key, messageId, templateId) {
  const res = await fetch('https://a.klaviyo.com/api/campaign-message-assign-template/', {
    method: 'POST',
    headers: headers(key),
    body: JSON.stringify({
      data: {
        type: 'campaign-message',
        id: messageId,
        relationships: { template: { data: { type: 'template', id: templateId } } },
      },
    }),
  });
  const json = await res.json();
  if (!res.ok) throw new Error('Klaviyo assignTemplate: ' + JSON.stringify(json));
  return json.data.id;
}
