(() => {
  const form = document.querySelector('[data-p21-form]');
  const paper = form?.querySelector('[data-p21-paper]');
  const source = form?.querySelector('[data-p21-document-source]');
  const letterhead = form?.querySelector('[data-p21-letterhead]');
  const textareas = Array.from(form?.querySelectorAll('[data-p21-rich-editor]') || []);
  if (!form || !paper || !source || !letterhead || typeof window.Jodit === 'undefined') return;

  const canEdit = form.dataset.canEdit === 'true';
  const numberInput = form.querySelector('[name="letter_number"]');
  const manualInput = form.querySelector('[name="manual_number"]');
  const dateInput = form.querySelector('[name="letter_date"]');
  const natureInput = form.querySelector('[name="letter_nature"]');
  const attachmentInput = form.querySelector('[name="attachment"]');
  const subjectInput = form.querySelector('[data-p21-subject]');
  const barcodeInput = form.querySelector('[data-p21-barcode-input]');
  const warning = form.querySelector('[data-p21-overflow-warning]');
  let frame = 0;
  let barcodeUrl = '';

  function safe(html) {
    const parsed = new DOMParser().parseFromString(html || '', 'text/html');
    parsed.querySelectorAll('script,style,iframe,object,embed,form,input,button,link,meta,base,video,audio,svg,math').forEach((node) => node.remove());
    parsed.body.querySelectorAll('*').forEach((node) => Array.from(node.attributes).forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim().toLowerCase();
      if (name.startsWith('on') || name === 'srcdoc') node.removeAttribute(attribute.name);
      if ((name === 'href' || name === 'src') && /^(javascript|vbscript):/.test(value)) node.removeAttribute(attribute.name);
      if (name === 'style' && /(url\s*\(|expression\s*\(|@import)/i.test(attribute.value)) node.removeAttribute(attribute.name);
    }));
    return parsed.body;
  }

  function dateID(value) {
    if (!value) return '—';
    const date = new Date(`${value}T00:00:00Z`);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('id-ID', {
      day: '2-digit', month: 'long', year: 'numeric', timeZone: 'UTC',
    }).format(date);
  }

  const editors = textareas.map((textarea) => {
    const section = textarea.dataset.p21RichEditor;
    const tall = ['legal-basis', 'body'].includes(section);
    const editor = window.Jodit.make(textarea, {
      height: tall ? 320 : 220,
      minHeight: tall ? 260 : 180,
      maxHeight: 560,
      readonly: !canEdit,
      theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
      toolbarAdaptive: true,
      toolbarSticky: false,
      statusbar: true,
      showCharsCounter: false,
      showWordsCounter: true,
      showXPathInStatusbar: false,
      askBeforePasteHTML: false,
      askBeforePasteFromWord: false,
      defaultActionOnPaste: 'insert_clear_html',
      buttons: ['undo', 'redo', '|', 'fontsize', '|', 'bold', 'italic', 'underline', '|', 'ol', 'ul', '|', 'outdent', 'indent', '|', 'left', 'center', 'right', 'justify', '|', 'eraser', 'source'],
    });
    editor.editor.style.fontFamily = 'Arial, sans-serif';
    editor.editor.style.fontSize = '10pt';
    editor.editor.style.lineHeight = '1.15';
    return { section, editor };
  });

  function render() {
    frame = 0;
    const content = safe(source.innerHTML);
    paper.replaceChildren(letterhead.content.cloneNode(true), ...Array.from(content.childNodes).map((node) => node.cloneNode(true)));
    const set = (name, value) => paper.querySelectorAll(`[data-p21-output="${name}"]`).forEach((node) => { node.textContent = value || '—'; });
    let displayedNumber = numberInput?.value.trim() || '';
    if (/^\d+$/.test(displayedNumber) && dateInput?.value && form.dataset.numberRegion && form.dataset.numberCode) {
      const [year, month] = dateInput.value.split('-');
      displayedNumber = `B-${displayedNumber}/${form.dataset.numberRegion}/${form.dataset.numberCode}/${month}/${year}`;
    }
    set('number', displayedNumber);
    set('date', dateID(dateInput?.value));
    set('nature', natureInput?.value.trim());
    set('attachment', attachmentInput?.value.trim());

    const subjectTarget = paper.querySelector('[data-p21-section="subject"]');
    if (subjectTarget && subjectInput) subjectTarget.textContent = subjectInput.value.trim();
    ['legal-basis', 'body', 'copies'].forEach((section) => {
      const target = paper.querySelector(`[data-p21-section="${section}"]`);
      const editor = editors.find((record) => record.section === section)?.editor;
      if (target && editor) target.replaceChildren(...Array.from(safe(editor.value).childNodes).map((node) => node.cloneNode(true)));
    });

    paper.querySelectorAll('[data-p21-section="body"] > ol').forEach((list) => {
      const start = Number(list.getAttribute('start') || 1);
      Array.from(list.children).forEach((item, index) => {
        if (item.tagName === 'LI') item.dataset.p21ListNumber = String(start + index);
      });
    });

    let recipients = [];
    try { recipients = JSON.parse(form.querySelector('[name="recipients_json"]')?.value || '[]'); } catch (_error) { recipients = []; }
    const recipient = paper.querySelector('[data-p21-section="recipient"]');
    if (recipient && recipients.length) {
      const recipientBlock = document.createElement('span');
      recipientBlock.append(document.createTextNode('Yth. '));
      recipients.forEach((item, index) => {
        if (index) recipientBlock.append(document.createElement('br'));
        recipientBlock.append(document.createTextNode(item.recipient || ''));
      });
      recipientBlock.append(document.createElement('br'), document.createTextNode('Di -'), document.createElement('br'));
      const place = document.createElement('u');
      place.textContent = recipients[0]?.place || 'Tempat';
      recipientBlock.append(place);
      recipient.replaceChildren(recipientBlock);
    }
    if (barcodeUrl) {
      const mark = paper.querySelector('[data-p21-barcode-mark]');
      const image = document.createElement('img');
      image.src = barcodeUrl;
      image.alt = 'Barcode verifikasi P-21';
      mark?.classList.add('has-barcode');
      mark?.replaceChildren(image);
    }
    requestAnimationFrame(() => {
      const overflowing = paper.scrollHeight > paper.clientHeight + 2;
      paper.classList.toggle('p21-overflowing', overflowing);
      if (warning) warning.hidden = !overflowing;
    });
  }

  function queue() {
    if (frame) cancelAnimationFrame(frame);
    frame = requestAnimationFrame(render);
  }

  function numberMode() {
    if (!numberInput || !manualInput) return;
    numberInput.readOnly = !canEdit;
    numberInput.value = numberInput.value.replace(/\D/g, '');
    const help = form.querySelector('[data-p21-number-help]');
    if (help) help.textContent = 'Isi angka saja. Awalan B dan kode surat dibuat otomatis.';
  }

  if (!canEdit) [numberInput, dateInput, natureInput, attachmentInput, subjectInput, manualInput].forEach((input) => { if (input) input.disabled = true; });
  editors.forEach(({ editor }) => editor.events.on('change', queue));
  [numberInput, dateInput, natureInput, attachmentInput, subjectInput].forEach((input) => {
    input?.addEventListener('input', queue);
    input?.addEventListener('change', queue);
  });
  numberInput?.addEventListener('input', () => {
    numberInput.value = numberInput.value.replace(/\D/g, '');
    queue();
  });
  manualInput?.addEventListener('change', () => { numberMode(); queue(); });
  form.addEventListener('letter-recipients-change', queue);
  barcodeInput?.addEventListener('change', () => {
    if (barcodeUrl) URL.revokeObjectURL(barcodeUrl);
    barcodeUrl = barcodeInput.files?.[0] ? URL.createObjectURL(barcodeInput.files[0]) : '';
    queue();
  });
  form.querySelector('[data-p21-print]')?.addEventListener('click', () => {
    render();
    requestAnimationFrame(() => requestAnimationFrame(() => window.print()));
  });
  window.addEventListener('resize', queue);
  numberMode();
  render();
})();
