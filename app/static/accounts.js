document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-confirm-action]');
  if (!button) return;
  const target = button.dataset.confirmTarget || '该账号';
  if (!window.confirm(`请确认${button.dataset.confirmAction}：${target}。此操作可能影响登录权限。`)) event.preventDefault();
});
