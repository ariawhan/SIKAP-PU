(() => {
  const startDialog = document.querySelector('#start-p16-dialog');
  const prosecutorDialog = document.querySelector('#prosecutor-dialog');

  function setText(dialog, selector, value) {
    const element = dialog?.querySelector(selector);
    if (element) element.textContent = value || '-';
  }

  function closeActionMenus() {
    document.querySelectorAll('.action-menu[open]').forEach(menu => {
      menu.removeAttribute('open');
    });
  }

  function getPickerItems(picker) {
    return picker.querySelectorAll('input[type="hidden"]');
  }

  function renderPickerEmptyState(picker) {
    const list = picker.querySelector('[data-picker-list]');
    if (!list || getPickerItems(picker).length) return;
    list.innerHTML = `<div class="workflow-empty-selection">${list.dataset.empty || 'Belum ada pilihan.'}</div>`;
  }

  function clearPickerError(picker) {
    picker.querySelector('.workflow-picker-error')?.remove();
  }

  function showPickerError(picker, message) {
    clearPickerError(picker);
    const error = document.createElement('div');
    error.className = 'workflow-picker-error';
    error.textContent = message;
    picker.appendChild(error);
  }

  function addPickerItem(picker) {
    const select = picker.querySelector('[data-picker-select]');
    const list = picker.querySelector('[data-picker-list]');
    const inputName = picker.dataset.inputName;
    const option = select?.selectedOptions?.[0];
    if (!select || !list || !inputName || !option?.value) return;

    clearPickerError(picker);
    list.querySelector('.workflow-empty-selection')?.remove();

    const item = document.createElement('div');
    item.className = 'workflow-selected-item';
    item.dataset.value = option.value;
    item.innerHTML = `
      <input type="hidden" name="${inputName}" value="${option.value}">
      <span class="workflow-avatar">${option.dataset.initials || option.textContent.slice(0, 2).toUpperCase()}</span>
      <span class="workflow-selected-text"><b>${option.textContent}</b><small>${option.dataset.subtitle || ''}</small></span>
      <button type="button" data-picker-remove aria-label="Hapus ${option.textContent}">&times;</button>
    `;
    list.appendChild(item);
    option.disabled = true;
    select.value = '';
  }

  function resetPicker(picker) {
    picker.querySelectorAll('[data-picker-select] option').forEach(option => {
      option.disabled = false;
    });
    const select = picker.querySelector('[data-picker-select]');
    const list = picker.querySelector('[data-picker-list]');
    if (select) select.value = '';
    if (list) list.innerHTML = '';
    clearPickerError(picker);
    renderPickerEmptyState(picker);
  }

  function validatePicker(picker) {
    if (picker.hidden || picker.dataset.required !== 'true') return true;
    if (getPickerItems(picker).length) {
      clearPickerError(picker);
      return true;
    }
    showPickerError(picker, 'Tambahkan minimal satu pilihan.');
    picker.querySelector('[data-picker-select]')?.focus();
    return false;
  }

  document.querySelectorAll('[data-workflow]').forEach(button => {
    button.addEventListener('click', () => {
      const dialog = button.dataset.workflow === 'start' ? startDialog : prosecutorDialog;
      if (!dialog) return;
      dialog.querySelector('[data-workflow-form]').action = button.dataset.dialogUrl;
      setText(dialog, '[data-case-number]', button.dataset.number);
      setText(dialog, '[data-case-date]', button.dataset.date);
      setText(dialog, '[data-case-kasi]', button.dataset.kasi);
      dialog.querySelectorAll('[data-workflow-picker]').forEach(resetPicker);
      const adminToggle = dialog.querySelector('[data-admin-toggle]');
      const adminPanel = dialog.querySelector('[data-admin-panel]');
      if (adminToggle) adminToggle.checked = false;
      if (adminPanel) adminPanel.hidden = true;
      closeActionMenus();
      dialog.showModal();
      requestAnimationFrame(() => dialog.querySelector('select, input')?.focus());
    });
  });

  document.querySelectorAll('[data-dialog-close]').forEach(button => {
    button.addEventListener('click', () => button.closest('dialog')?.close());
  });

  document.querySelectorAll('.workflow-modal').forEach(dialog => {
    dialog.querySelectorAll('[data-workflow-picker]').forEach(picker => {
      renderPickerEmptyState(picker);
      picker.querySelector('[data-picker-add]')?.addEventListener('click', () => addPickerItem(picker));
      picker.querySelector('[data-picker-select]')?.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
          event.preventDefault();
          addPickerItem(picker);
        }
      });
      picker.addEventListener('click', event => {
        const removeButton = event.target.closest('[data-picker-remove]');
        if (!removeButton) return;
        const item = removeButton.closest('.workflow-selected-item');
        const value = item?.dataset.value;
        const option = value ? picker.querySelector(`[data-picker-select] option[value="${CSS.escape(value)}"]`) : null;
        if (option) option.disabled = false;
        item?.remove();
        renderPickerEmptyState(picker);
      });
    });

    dialog.querySelector('[data-admin-toggle]')?.addEventListener('change', event => {
      const panel = dialog.querySelector('[data-admin-panel]');
      if (!panel) return;
      panel.hidden = !event.target.checked;
      if (!event.target.checked) resetPicker(panel);
      if (event.target.checked) panel.querySelector('[data-picker-select]')?.focus();
    });

    dialog.querySelector('[data-workflow-form]')?.addEventListener('submit', event => {
      const invalidPicker = Array.from(dialog.querySelectorAll('[data-workflow-picker]')).find(picker => !validatePicker(picker));
      if (invalidPicker) event.preventDefault();
    });

    dialog.addEventListener('click', event => {
      if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener('close', () => {
      dialog.querySelectorAll('input[type="checkbox"]').forEach(input => {
        input.checked = false;
      });
      dialog.querySelectorAll('[data-workflow-picker]').forEach(resetPicker);
      const adminPanel = dialog.querySelector('[data-admin-panel]');
      if (adminPanel) adminPanel.hidden = true;
    });
  });

})();
