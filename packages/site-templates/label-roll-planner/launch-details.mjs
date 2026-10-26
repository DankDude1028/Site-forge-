/** Public operator details for the privacy page. Previews never invent them; production fails closed. */
export function getLaunchDetails(mode, environment = process.env) {
  const host = environment.SITEFORGE_HOST_NAME?.trim() || null;
  const hostPrivacyUrl = environment.SITEFORGE_HOST_PRIVACY_URL?.trim() || null;
  const contactEmail = environment.SITEFORGE_CONTACT_EMAIL?.trim() || null;
  if (mode === 'production' && (!host || !hostPrivacyUrl || !contactEmail)) {
    throw new Error('Production requires SITEFORGE_HOST_NAME, SITEFORGE_HOST_PRIVACY_URL and SITEFORGE_CONTACT_EMAIL');
  }
  if (host && (host.length > 80 || /[<>]/.test(host))) throw new Error('Host name must be plain text under 80 characters');
  if (hostPrivacyUrl) {
    let parsed;
    try { parsed = new URL(hostPrivacyUrl); } catch { throw new Error('Host privacy URL must be an HTTPS URL'); }
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password) throw new Error('Host privacy URL must be an HTTPS URL');
  }
  if (contactEmail && !/^[^\s@<>"]+@[^\s@<>"]+\.[^\s@<>"]+$/.test(contactEmail)) {
    throw new Error('Contact email must be a plain email address');
  }
  return { host, hostPrivacyUrl, contactEmail };
}
