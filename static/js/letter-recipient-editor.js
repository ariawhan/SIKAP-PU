(() => {
  document.querySelectorAll('[data-letter-extras]').forEach((root) => {
    const form = root.closest('form');
    const editable = form?.dataset.canEdit === 'true';
    const hidden = root.querySelector('[name="recipients_json"]');
    const rows = root.querySelector('[data-letter-recipient-rows]');
    const place = root.querySelector('[data-letter-recipient-place]');
    if (!form || !hidden || !rows || !place) return;

    let items = [];
    try { items = JSON.parse(hidden.value || '[]'); } catch (_error) { items = []; }
    if (!Array.isArray(items) || !items.length) items = [{ recipient: '', place: 'Singaraja' }];
    place.value = items[0]?.place || 'Singaraja';
    place.disabled = !editable;

    const sync = () => {
      const commonPlace = place.value.trim();
      items = Array.from(rows.querySelectorAll('[data-letter-recipient-row]')).map((row) => ({
        recipient: row.querySelector('input')?.value.trim() || '',
        place: commonPlace,
      })).filter((item) => item.recipient);
      hidden.value = JSON.stringify(items);
      form.dispatchEvent(new CustomEvent('letter-recipients-change'));
    };

    const draw = () => {
      rows.replaceChildren();
      items.forEach((item, index) => {
        const row = document.createElement('div');
        row.className = 'letter-recipient-row';
        row.dataset.letterRecipientRow = '';

        const badge = document.createElement('span');
        badge.className = 'letter-recipient-index';
        badge.textContent = String(index + 1);

        const input = document.createElement('input');
        input.type = 'text';
        input.required = true;
        input.maxLength = 300;
        input.value = item.recipient || '';
        input.placeholder = 'Contoh: Kepala Kepolisian Resor Buleleng';
        input.disabled = !editable;
        input.addEventListener('input', sync);

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'letter-recipient-remove';
        remove.textContent = '\u00d7';
        remove.title = 'Hapus tujuan';
        remove.setAttribute('aria-label', `Hapus tujuan ${index + 1}`);
        remove.disabled = !editable || items.length === 1;
        remove.addEventListener('click', () => {
          items.splice(index, 1);
          draw();
          sync();
        });
        row.append(badge, input, remove);
        rows.append(row);
      });
    };

    root.querySelector('[data-letter-add-recipient]')?.addEventListener('click', () => {
      items.push({ recipient: '', place: place.value });
      draw();
    });
    place.addEventListener('input', sync);

    const dropzone = root.querySelector('[data-letter-barcode-dropzone]');
    const fileInput = root.querySelector('[data-letter-barcode-widget] input[type="file"]');
    const preview = root.querySelector('[data-letter-barcode-preview]');
    const title = root.querySelector('[data-letter-barcode-title]');
    const status = root.querySelector('[data-letter-barcode-status]');
    let objectUrl = '';

    const showSelected = (selected) => {
      if (!selected || !preview || !title || !status) return;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(selected);
      const image = document.createElement('img');
      image.src = objectUrl;
      image.alt = 'Preview barcode';
      preview.replaceChildren(image);
      title.textContent = 'Barcode siap digunakan';
      status.textContent = selected.name;
    };
    const chooseFile = () => { if (editable && !fileInput?.disabled) fileInput.click(); };

    dropzone?.addEventListener('click', chooseFile);
    dropzone?.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      chooseFile();
    });
    ['dragenter', 'dragover'].forEach((name) => dropzone?.addEventListener(name, (event) => {
      event.preventDefault();
      if (editable) dropzone.classList.add('dragging');
    }));
    ['dragleave', 'drop'].forEach((name) => dropzone?.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove('dragging');
    }));
    dropzone?.addEventListener('drop', (event) => {
      const selected = event.dataTransfer?.files?.[0];
      if (!editable || !selected || !fileInput) return;
      const transfer = new DataTransfer();
      transfer.items.add(selected);
      fileInput.files = transfer.files;
      fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    });
    fileInput?.addEventListener('change', () => showSelected(fileInput.files?.[0]));

    draw();
    sync();
  });
})();
