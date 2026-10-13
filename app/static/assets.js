function syncAssetType(type) {
  const form = type.closest('[data-asset-form]');
  if (!form) return;
  const host = form.querySelector('[data-field-host]');
  if (!host) return;
  host.disabled = type.value !== 'virtual';
  if (host.disabled) host.value = '';
}

document.addEventListener('change', (event) => {
  const type = event.target.closest('[data-asset-type]');
  if (!type) return;
  syncAssetType(type);
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-asset-type]').forEach(syncAssetType);
});
