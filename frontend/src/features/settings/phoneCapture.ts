export function phoneCaptureExample(apiUrl: string): string {
  return [
    `POST ${apiUrl}/captures`,
    'Authorization: Bearer <your token>',
    'Content-Type: application/json',
    '',
    '{"title": "<video title>", "channel": "<channel>", "at": "12:34", "source": "phone"}',
  ].join('\n');
}
