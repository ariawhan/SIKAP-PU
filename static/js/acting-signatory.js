(function () {
  function setup(root) {
    const form = root.closest('form') || document;
    const typeInput = root.querySelector('[data-acting-type]');
    const choices = Array.from(root.querySelectorAll('[data-acting-choice]'));
    const fields = root.querySelector('[data-acting-fields]');
    const inputs = {
      name: root.querySelector('[data-acting-input="name"]'),
      position: root.querySelector('[data-acting-input="position"]'),
      nip: root.querySelector('[data-acting-input="nip"]')
    };
    if (!typeInput || !fields) return;

    function outputValue(kind) {
      const type = typeInput.value;
      if (kind === 'title') {
        const prefix = type === 'plt' ? 'Plt. ' : type === 'plh' ? 'Plh. ' : '';
        return prefix + (root.dataset.defaultTitle || 'Kepala Kejaksaan Negeri');
      }
      if (kind === 'name') return type ? inputs.name.value.trim() : root.dataset.defaultName;
      if (kind === 'identity') {
        const position = type ? inputs.position.value.trim() : root.dataset.defaultPosition;
        const nip = type ? inputs.nip.value.trim() : root.dataset.defaultNip;
        return [position, nip ? `NIP.${nip}` : ''].filter(Boolean).join(' ');
      }
      return '';
    }

    function updatePreview() {
      form.querySelectorAll('[data-acting-output]').forEach(function (node) {
        const value = outputValue(node.dataset.actingOutput);
        if (node.textContent !== value) node.textContent = value;
      });
      form.querySelectorAll('[data-sop-sipede-field="penandatangan"],[data-p17-sipede-field="penandatangan"]').forEach(function (select) {
        const name = typeInput.value ? inputs.name.value.trim() : root.dataset.defaultName;
        if (!name) return;
        let option = Array.from(select.options).find(function (item) { return item.value === name; });
        if (!option) {
          option = new Option(name, name);
          select.add(option, 0);
        }
        select.value = name;
      });
    }

    function sync() {
      choices.forEach(function (choice) { choice.checked = choice.value === typeInput.value; });
      fields.hidden = !typeInput.value;
      updatePreview();
    }

    choices.forEach(function (choice) {
      choice.addEventListener('change', function () {
        typeInput.value = choice.checked ? choice.value : '';
        typeInput.dispatchEvent(new Event('change', { bubbles: true }));
        sync();
      });
    });
    Object.values(inputs).forEach(function (input) {
      if (input) input.addEventListener('input', updatePreview);
    });
    new MutationObserver(updatePreview).observe(form, { childList: true, subtree: true });
    sync();
  }

  document.querySelectorAll('[data-acting-signatory]').forEach(setup);
})();
