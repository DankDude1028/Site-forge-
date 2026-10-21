export const rows = value => Array.isArray(value) ? value : (Array.isArray(value?.items) ? value.items : []);
export const dollars = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(Number(value) || 0);
export const readable = value => String(value ?? '—').replaceAll('_', ' ');
