import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getLaunchDetails } from '../launch-details.mjs';

const complete = { SITEFORGE_HOST_NAME: 'Netlify', SITEFORGE_HOST_PRIVACY_URL: 'https://www.netlify.com/privacy/',
  SITEFORGE_CONTACT_EMAIL: 'hello@lawnnumbers.com' };

test('previews show placeholders instead of invented host or contact details', () => {
  assert.deepEqual(getLaunchDetails('preview', {}), { host: null, hostPrivacyUrl: null, contactEmail: null });
  assert.deepEqual(getLaunchDetails('preview', complete),
    { host: 'Netlify', hostPrivacyUrl: 'https://www.netlify.com/privacy/', contactEmail: 'hello@lawnnumbers.com' });
});

test('production fails closed until every public detail is supplied and well formed', () => {
  assert.throws(() => getLaunchDetails('production', {}), /requires SITEFORGE_HOST_NAME/);
  for (const key of Object.keys(complete)) {
    assert.throws(() => getLaunchDetails('production', { ...complete, [key]: ' ' }), /requires/);
  }
  for (const [key, value] of [['SITEFORGE_HOST_PRIVACY_URL', 'http://www.netlify.com/privacy/'],
    ['SITEFORGE_HOST_PRIVACY_URL', 'not a url'], ['SITEFORGE_CONTACT_EMAIL', 'hello at rollwise'],
    ['SITEFORGE_CONTACT_EMAIL', '<a>@b.c'], ['SITEFORGE_HOST_NAME', '<script>']]) {
    assert.throws(() => getLaunchDetails('production', { ...complete, [key]: value }), key);
  }
  assert.equal(getLaunchDetails('production', complete).contactEmail, 'hello@lawnnumbers.com');
});
