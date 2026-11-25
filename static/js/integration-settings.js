(() => {
  const modal = document.querySelector('[data-integration-settings-modal]');
  const openButton = document.querySelector('[data-integration-settings-open]');
  if (!modal) return;

  const open = () => {
    modal.hidden = false;
    document.body.classList.add('modal-open');
    modal.querySelector('input:not([type="hidden"])')?.focus();
  };
  const close = () => {
    modal.hidden = true;
    document.body.classList.remove('modal-open');
    openButton?.focus();
  };

  openButton?.addEventListener('click', open);
  modal.querySelectorAll('[data-integration-settings-close]').forEach((button) => {
    button.addEventListener('click', close);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.hidden) close();
  });
  if (modal.dataset.openOnLoad === 'true') open();
})();
