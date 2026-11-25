(function () {
  const form = document.querySelector('[data-sop-form]');
  const paper = form?.querySelector('[data-sop-paper]');
  const source = form?.querySelector('[data-sop-document-source]');
  const head = form?.querySelector('[data-sop-letterhead]');
  const areas = Array.from(form?.querySelectorAll('[data-sop-rich-editor]') || []);
  if (!form || !paper || !source || !head || typeof Jodit === 'undefined') return;

  const editable = form.dataset.canEdit === 'true';
  const number = form.querySelector('[name="letter_number"]');
  const manual = form.querySelector('[name="manual_number"]');
  const date = form.querySelector('[name="letter_date"]');
  const nature = form.querySelector('[name="letter_nature"]');
  const attachment = form.querySelector('[name="attachment"]');
  const subject = form.querySelector('[data-sop-subject]');
  const barcodeInput = form.querySelector('[data-sop-barcode-input]');
  const barcodeField = form.querySelector('.sop-barcode-field');
  const recipientsInput = form.querySelector('[data-sop-recipients-json]');
  const recipientRows = form.querySelector('[data-sop-recipient-rows]');
  const recipientPlace = form.querySelector('[data-sop-recipient-place]');
  const warning = form.querySelector('[data-sop-overflow-warning]');
  const numberRegion = form.dataset.sopNumberRegion || '';
  const numberCode = form.dataset.sopNumberCode || '';
  let frame = 0;
  let barcodeObjectUrl = '';

  let recipients = [];
  try { recipients = JSON.parse(recipientsInput?.value || '[]'); } catch (_error) { recipients = []; }
  if (!Array.isArray(recipients) || !recipients.length) recipients = [{ recipient: '', place: 'Singaraja' }];
  if (recipientPlace) recipientPlace.value = recipients[0]?.place || 'Singaraja';

  function syncRecipients() {
    const place = (recipientPlace?.value || '').trim();
    recipients = Array.from(recipientRows?.querySelectorAll('[data-sop-recipient-row]') || []).map((row) => ({
      recipient: (row.querySelector('input')?.value || '').trim(), place,
    })).filter((item) => item.recipient);
    if (recipientsInput) recipientsInput.value = JSON.stringify(recipients);
    queueRender();
  }

  function drawRecipients() {
    if (!recipientRows) return;
    recipientRows.replaceChildren();
    recipients.forEach((item, index) => {
      const row = document.createElement('div');
      row.dataset.sopRecipientRow = '';
      row.className = 'sop-recipient-row letter-recipient-row';
      const badge = document.createElement('span');
      badge.className = 'letter-recipient-index';
      badge.textContent = String(index + 1);
      const input = document.createElement('input');
      input.type = 'text'; input.maxLength = 250; input.required = true;
      input.placeholder = 'Contoh: Kepala Kepolisian Resor Buleleng'; input.value = item.recipient || '';
      input.disabled = !editable; input.addEventListener('input', syncRecipients);
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'letter-recipient-remove';
      remove.textContent = '×'; remove.title = 'Hapus tujuan';
      remove.setAttribute('aria-label', `Hapus tujuan ${index + 1}`);
      remove.disabled = !editable || recipients.length === 1;
      remove.addEventListener('click', () => { recipients.splice(index, 1); drawRecipients(); syncRecipients(); });
      row.append(badge, input, remove); recipientRows.append(row);
    });
  }

  function setupBarcodeUploader() {
    if (!barcodeField || !barcodeInput) return;
    const originalLabel = barcodeField.querySelector('label');
    const currentLink = barcodeField.querySelector('a[href]');
    const currentName = barcodeField.querySelector('small')?.textContent.replace(/^Barcode saat ini:\s*/i, '').trim();

    const fieldLabel = document.createElement('span');
    fieldLabel.className = 'p16-field-label';
    fieldLabel.textContent = 'Upload Barcode/QR';

    const uploader = document.createElement('div');
    uploader.className = 'p16-barcode-uploader';
    uploader.tabIndex = editable ? 0 : -1;
    uploader.setAttribute('role', 'button');
    uploader.setAttribute('aria-label', 'Pilih gambar barcode atau QR');

    const preview = document.createElement('div');
    preview.className = 'p16-barcode-preview';
    const initialImageUrl = currentLink?.href || '';
    if (initialImageUrl) {
      const image = document.createElement('img');
      image.src = initialImageUrl;
      image.alt = 'Barcode saat ini';
      preview.append(image);
    } else {
      const placeholder = document.createElement('span');
      placeholder.textContent = 'QR';
      preview.append(placeholder);
    }

    const copy = document.createElement('div');
    copy.className = 'p16-barcode-copy';
    const title = document.createElement('b');
    title.textContent = initialImageUrl ? 'Barcode sudah terpasang' : 'Upload barcode verifikasi';
    const status = document.createElement('small');
    status.textContent = initialImageUrl && currentName ? currentName : 'Klik atau tarik gambar ke sini.';
    copy.append(title, status);
    uploader.append(preview, copy);

    const native = document.createElement('div');
    native.className = 'p16-barcode-native';
    if (originalLabel) native.append(originalLabel);
    else native.append(barcodeInput);
    barcodeField.classList.add('p16-barcode-field');
    barcodeField.replaceChildren(fieldLabel, uploader, native);

    const chooseFile = () => { if (editable && !barcodeInput.disabled) barcodeInput.click(); };
    uploader.addEventListener('click', chooseFile);
    uploader.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      chooseFile();
    });
    ['dragenter', 'dragover'].forEach((eventName) => uploader.addEventListener(eventName, (event) => {
      event.preventDefault();
      if (editable) uploader.classList.add('dragging');
    }));
    ['dragleave', 'drop'].forEach((eventName) => uploader.addEventListener(eventName, (event) => {
      event.preventDefault();
      uploader.classList.remove('dragging');
    }));
    uploader.addEventListener('drop', (event) => {
      if (!editable || !event.dataTransfer?.files?.length) return;
      const transfer = new DataTransfer();
      transfer.items.add(event.dataTransfer.files[0]);
      barcodeInput.files = transfer.files;
      barcodeInput.dispatchEvent(new Event('change', { bubbles: true }));
    });
    barcodeInput.addEventListener('change', () => {
      const file = barcodeInput.files?.[0];
      if (!file) return;
      if (barcodeObjectUrl) URL.revokeObjectURL(barcodeObjectUrl);
      barcodeObjectUrl = URL.createObjectURL(file);
      const image = document.createElement('img');
      image.src = barcodeObjectUrl;
      image.alt = 'Barcode yang dipilih';
      preview.replaceChildren(image);
      title.textContent = 'Barcode siap digunakan';
      status.textContent = file.name;
      queueRender();
    });
  }

  function completeNumber() {
    const sequence = (number?.value || '').trim().replace(/\D/g, '');
    const parts = (date?.value || '').split('-');
    if (!sequence || parts.length !== 3 || !numberRegion || !numberCode) return '';
    return `B-${sequence}/${numberRegion}/${numberCode}/${parts[1]}/${parts[0]}`;
  }

  function safe(html) {
    const document = new DOMParser().parseFromString(html || '', 'text/html');
    document.querySelectorAll('script,style,iframe,object,embed,form,input,button,link,meta,base,video,audio,svg,math')
      .forEach((node) => node.remove());
    document.body.querySelectorAll('*').forEach((node) => Array.from(node.attributes).forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim().toLowerCase();
      if (name.startsWith('on') || name === 'srcdoc' ||
        ((name === 'href' || name === 'src') && /^(javascript|vbscript):/.test(value))) {
        node.removeAttribute(attribute.name);
      }
    }));
    return document.body;
  }

  function indonesianDate(value) {
    if (!value) return '—';
    const parsed = new Date(`${value}T00:00:00Z`);
    return new Intl.DateTimeFormat('id-ID', {
      day: '2-digit', month: 'long', year: 'numeric', timeZone: 'UTC',
    }).format(parsed);
  }

  const editors = areas.map((area) => {
    const section = area.dataset.sopRichEditor;
    const editor = Jodit.make(area, {
      height: section === 'body' ? 330 : 220,
      minHeight: 180,
      maxHeight: 550,
      readonly: !editable,
      toolbarAdaptive: true,
      toolbarSticky: false,
      statusbar: true,
      showCharsCounter: false,
      showWordsCounter: true,
      showXPathInStatusbar: false,
      askBeforePasteHTML: false,
      askBeforePasteFromWord: false,
      defaultActionOnPaste: 'insert_clear_html',
      buttons: [
        'undo', 'redo', '|', 'fontsize', '|', 'bold', 'italic', 'underline',
        '|', 'ol', 'ul', '|', 'outdent', 'indent', '|', 'left', 'center', 'right',
        'justify', '|', 'eraser', 'source',
      ],
    });
    editor.editor.classList.add(`sop-editor-${section}`);
    editor.editor.style.fontFamily = 'Arial, sans-serif';
    editor.editor.style.fontSize = '10pt';
    editor.editor.style.lineHeight = '1.15';
    return { section, editor };
  });

  function render() {
    frame = 0;
    const content = safe(source.innerHTML);
    paper.replaceChildren(head.content.cloneNode(true), ...Array.from(content.childNodes).map((node) => node.cloneNode(true)));
    const setOutput = (key, value) => paper.querySelectorAll(`[data-sop-output="${key}"]`)
      .forEach((node) => { node.textContent = value || '—'; });
    setOutput('number', completeNumber());
    setOutput('date', indonesianDate(date?.value));
    setOutput('nature', nature?.value.trim());
    setOutput('attachment', attachment?.value.trim());
    const subjectTarget = paper.querySelector('[data-sop-section="subject"]');
    if (subjectTarget && subject) subjectTarget.textContent = subject.value.trim();
    ['body', 'copies'].forEach((section) => {
      const target = paper.querySelector(`[data-sop-section="${section}"]`);
      const editor = editors.find((item) => item.section === section)?.editor;
      if (target && editor) {
        target.replaceChildren(...Array.from(safe(editor.value).childNodes).map((node) => node.cloneNode(true)));
      }
    });
    const recipientTarget = paper.querySelector('[data-sop-section="recipient"]');
    if (recipientTarget) {
      const place = (recipientPlace?.value || '').trim() || 'Tempat';
      const names = recipients.map((item) => item.recipient).filter(Boolean);
      const strong = document.createElement('strong');
      strong.append(document.createTextNode('Yth. '));
      names.forEach((name, index) => {
        if (index) strong.append(document.createElement('br'));
        strong.append(document.createTextNode(name));
      });
      strong.append(document.createElement('br'), document.createTextNode('Di -'), document.createElement('br'));
      const placeNode = document.createElement('u'); placeNode.textContent = place; strong.append(placeNode);
      recipientTarget.replaceChildren(strong);
    }
    if (barcodeObjectUrl) {
      const mark = paper.querySelector('[data-sop-barcode-mark]');
      const image = document.createElement('img');
      image.src = barcodeObjectUrl;
      image.alt = 'Barcode verifikasi';
      mark?.classList.add('has-barcode');
      mark?.replaceChildren(image);
    }
    requestAnimationFrame(() => {
      const overflowing = paper.scrollHeight > paper.clientHeight + 2;
      paper.classList.toggle('sop-overflowing', overflowing);
      if (warning) warning.hidden = !overflowing;
    });
  }

  function queueRender() {
    if (frame) cancelAnimationFrame(frame);
    frame = requestAnimationFrame(render);
  }

  function syncNumberMode() {
    if (!number) return;
    number.readOnly = !editable;
    number.value = number.value.replace(/\D/g, '');
  }

  if (!editable) [number, manual, date, nature, attachment, subject].forEach((input) => {
    if (input) input.disabled = true;
  });
  editors.forEach(({ editor }) => editor.events.on('change', queueRender));
  number?.addEventListener('input', () => {
    number.value = number.value.replace(/\D/g, '');
    queueRender();
  });
  [date, nature, attachment, subject].forEach((input) => {
    input?.addEventListener('input', queueRender);
    input?.addEventListener('change', queueRender);
  });
  manual?.addEventListener('change', () => {
    syncNumberMode();
    queueRender();
  });
  form.querySelector('[data-sop-add-recipient]')?.addEventListener('click', () => {
    recipients.push({ recipient: '', place: recipientPlace?.value || '' }); drawRecipients(); syncRecipients();
  });
  recipientPlace?.addEventListener('input', syncRecipients);
  form.querySelector('[data-sop-print]')?.addEventListener('click', () => {
    render();
    if (paper.scrollHeight > paper.clientHeight + 2) {
      paper.scrollIntoView({ behavior: 'smooth' });
      return;
    }
    window.print();
  });
  window.addEventListener('resize', queueRender);
  syncNumberMode();
  setupBarcodeUploader();
  drawRecipients();
  syncRecipients();
  render();
})();
