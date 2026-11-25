(function () {
  const form = document.querySelector('[data-p17-form]');
  const pagesHolder = form?.querySelector('[data-p17-pages]');
  const source = form?.querySelector('[data-p17-document-source]');
  const letterhead = form?.querySelector('[data-p17-letterhead]');
  const textareas = Array.from(form?.querySelectorAll('[data-p17-rich-editor]') || []);
  if (!form || !pagesHolder || !source || !letterhead || typeof window.Jodit === 'undefined') return;

  const canEdit = form.dataset.canEdit === 'true';
  const numberInput = form.querySelector('[name="letter_number"]');
  const manualInput = form.querySelector('[name="manual_number"]');
  const numberPreview = form.querySelector('[data-p17-number-preview]');
  const numberRegionCode = form.dataset.p17NumberRegion || '';
  const numberLetterCode = form.dataset.p17NumberCode || '';
  const dateInput = form.querySelector('[name="letter_date"]');
  const natureInput = form.querySelector('[name="letter_nature"]');
  const attachmentInput = form.querySelector('[name="attachment"]');
  const subjectInput = form.querySelector('[data-p17-subject]');
  const recipientsInput = form.querySelector('[data-p17-recipients-json]');
  const recipientRows = form.querySelector('[data-p17-recipient-rows]');
  const addRecipientButton = form.querySelector('[data-p17-add-recipient]');
  const recipientPlaceInput = form.querySelector('[data-p17-recipient-place]');
  const barcodeInput = form.querySelector('[data-p17-barcode-input]');
  const barcodeDropzone = form.querySelector('[data-p17-barcode-dropzone]');
  const barcodePreview = form.querySelector('[data-p17-barcode-preview]');
  const barcodeTitle = form.querySelector('[data-p17-barcode-title]');
  const barcodeStatus = form.querySelector('[data-p17-barcode-status]');
  const overflowWarning = form.querySelector('[data-p17-overflow-warning]');
  let renderFrame = 0;
  let barcodePreviewUrl = '';
  let hasOversizedBlock = false;

  function completeP17Number() {
    const sequence = numberInput?.value.trim() || '';
    const dateParts = (dateInput?.value || '').split('-');
    if (!/^\d+$/.test(sequence) || dateParts.length !== 3 || !numberRegionCode || !numberLetterCode) return '';
    return `B-${sequence}/${numberRegionCode}/${numberLetterCode}/${dateParts[1]}/${dateParts[0]}`;
  }

  function readRecipients() {
    try {
      const value = JSON.parse(recipientsInput?.value || '[]');
      return Array.isArray(value) ? value.filter((item) => item && typeof item === 'object').map((item) => ({
        recipient: String(item.recipient || '').trim(),
        place: String(item.place || '').trim()
      })) : [];
    } catch (error) {
      return [];
    }
  }

  function writeRecipients() {
    if (!recipientsInput || !recipientRows) return;
    const place = recipientPlaceInput?.value.trim() || '';
    const recipients = Array.from(recipientRows.querySelectorAll('[data-p17-recipient-row]')).map((row) => ({
      recipient: row.querySelector('[data-p17-recipient-name]')?.value.trim() || '',
      place
    })).filter((item) => item.recipient);
    recipientsInput.value = JSON.stringify(recipients);
  }

  function recipientRow(item = {}) {
    const row = document.createElement('div');
    row.className = 'p17-recipient-row';
    row.dataset.p17RecipientRow = '';
    const index = document.createElement('span');
    index.className = 'p17-recipient-index';
    const fields = document.createElement('div');
    fields.className = 'p17-recipient-row-fields';
    const recipientLabel = document.createElement('label');
    recipientLabel.textContent = 'Tujuan';
    const recipient = document.createElement('input');
    recipient.type = 'text';
    recipient.maxLength = 300;
    recipient.placeholder = 'Contoh: Kepala Kepolisian Resor Buleleng';
    recipient.value = item.recipient || '';
    recipient.dataset.p17RecipientName = '';
    recipient.disabled = !canEdit;
    recipientLabel.appendChild(recipient);
    fields.appendChild(recipientLabel);
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'p17-recipient-remove';
    remove.dataset.p17RemoveRecipient = '';
    remove.setAttribute('aria-label', 'Hapus tujuan surat');
    remove.title = 'Hapus tujuan';
    remove.textContent = '×';
    remove.disabled = !canEdit;
    row.append(index, fields, remove);
    return row;
  }

  function refreshRecipientRows() {
    if (!recipientRows) return;
    const rows = Array.from(recipientRows.querySelectorAll('[data-p17-recipient-row]'));
    rows.forEach((row, index) => {
      const marker = row.querySelector('.p17-recipient-index');
      if (marker) marker.textContent = String(index + 1);
      const remove = row.querySelector('[data-p17-remove-recipient]');
      if (remove) remove.hidden = rows.length === 1;
    });
  }

  function addRecipient(item = {}) {
    if (!recipientRows) return;
    recipientRows.appendChild(recipientRow(item));
    refreshRecipientRows();
    writeRecipients();
    queueRender();
  }

  function renderRecipientPreview(target) {
    if (!target) return;
    const recipients = readRecipients().filter((item) => item.recipient);
    const wrapper = document.createElement('div');
    wrapper.className = 'p17-recipient-list';
    const salutation = document.createElement('p');
    const yth = document.createElement('strong');
    yth.textContent = 'Yth.';
    salutation.appendChild(yth);
    wrapper.appendChild(salutation);
    const parent = document.createElement(recipients.length > 1 ? 'ol' : 'div');
    parent.className = recipients.length > 1 ? 'p17-recipient-numbered' : 'p17-recipient-single';
    recipients.forEach((item) => {
      const row = document.createElement(recipients.length > 1 ? 'li' : 'div');
      const name = document.createElement('strong');
      name.textContent = item.recipient;
      row.appendChild(name);
      parent.appendChild(row);
    });
    wrapper.appendChild(parent);
    const placeLine = document.createElement('div');
    placeLine.className = 'p17-recipient-place';
    const prefix = document.createElement('span');
    prefix.textContent = 'Di -';
    const place = document.createElement('u');
    place.textContent = recipientPlaceInput?.value.trim() || recipients[0]?.place || '---';
    placeLine.append(prefix, place);
    wrapper.appendChild(placeLine);
    target.replaceChildren(wrapper);
  }

  function safeFragment(html) {
    const parsed = new DOMParser().parseFromString(html || '', 'text/html');
    parsed.querySelectorAll('script,style,iframe,object,embed,form,input,button,link,meta,base,video,audio,svg,math').forEach((node) => node.remove());
    parsed.body.querySelectorAll('*').forEach((node) => {
      Array.from(node.attributes).forEach((attribute) => {
        const name = attribute.name.toLowerCase();
        const value = attribute.value.trim().toLowerCase();
        if (name.startsWith('on') || name === 'srcdoc') node.removeAttribute(attribute.name);
        if ((name === 'href' || name === 'src') && /^(javascript|vbscript):/.test(value)) node.removeAttribute(attribute.name);
        if (name === 'style' && /(url\s*\(|expression\s*\(|@import)/i.test(attribute.value)) node.removeAttribute(attribute.name);
      });
    });
    return parsed.body;
  }

  function indonesianDate(value) {
    if (!value) return '—';
    const date = new Date(`${value}T00:00:00Z`);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('id-ID', {
      day: '2-digit', month: 'long', year: 'numeric', timeZone: 'UTC'
    }).format(date);
  }

  const editors = textareas.map((textarea) => {
    const section = textarea.dataset.p17RichEditor;
    const editor = window.Jodit.make(textarea, {
      height: section === 'body' ? 360 : 230,
      minHeight: section === 'body' ? 290 : 190,
      maxHeight: 620,
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
      buttons: ['undo', 'redo', '|', 'fontsize', '|', 'bold', 'italic', 'underline', '|', 'ol', 'ul', '|', 'outdent', 'indent', '|', 'left', 'center', 'right', 'justify', '|', 'eraser', 'source']
    });
    editor.editor.style.fontFamily = 'Arial, sans-serif';
    editor.editor.style.fontSize = '10pt';
    editor.editor.style.lineHeight = '1.15';
    return { textarea, section, editor };
  });

  function editorFor(section) {
    return editors.find((record) => record.section === section)?.editor;
  }

  function pageSafeBottom(paper) {
    const rect = paper.getBoundingClientRect();
    const paddingBottom = Number.parseFloat(window.getComputedStyle(paper).paddingBottom) || 0;
    return rect.bottom - paddingBottom;
  }

  function deepestFlowBottom(paper) {
    let bottom = 0;
    Array.from(paper.querySelectorAll('.p17-letterhead,.p17-page-flow,.p17-page-flow *')).forEach((node) => {
      if (node.closest('.p17-verification-mark')) return;
      const style = window.getComputedStyle(node);
      if (style.position === 'absolute' || style.display === 'none' || style.visibility === 'hidden') return;
      const rect = node.getBoundingClientRect();
      if (rect.height > 0) bottom = Math.max(bottom, rect.bottom);
    });
    return bottom;
  }

  function paperOverflows(paper) {
    return paper.scrollHeight > paper.clientHeight + 2 || deepestFlowBottom(paper) > pageSafeBottom(paper) + 1;
  }

  function createPaper(firstPage, barcodeMark) {
    const frame = document.createElement('div');
    frame.className = 'p17-paper-frame';
    const paper = document.createElement('article');
    paper.className = 'p17-paper';
    paper.style.transform = 'none';
    if (firstPage) paper.appendChild(letterhead.content.cloneNode(true));
    const flow = document.createElement('section');
    flow.className = 'p17-page-flow';
    paper.appendChild(flow);
    if (barcodeMark) paper.appendChild(barcodeMark.cloneNode(true));
    frame.appendChild(paper);
    pagesHolder.appendChild(frame);
    return { frame, paper, flow };
  }

  function flowBlocks(content) {
    const blocks = [];
    Array.from(content.children).forEach((child) => {
      if (child.matches('.p17-verification-mark')) return;
      if (!child.matches('.p17-letter-body')) {
        blocks.push(child.cloneNode(true));
        return;
      }
      const bodyChildren = Array.from(child.childNodes).filter((node) => {
        return node.nodeType !== Node.TEXT_NODE || node.nodeValue.trim();
      });
      if (!bodyChildren.length) {
        blocks.push(child.cloneNode(true));
        return;
      }
      bodyChildren.forEach((bodyChild) => {
        const wrapper = child.cloneNode(false);
        wrapper.classList.add('p17-flow-block');
        if (bodyChild.nodeType === Node.TEXT_NODE) {
          const paragraph = document.createElement('p');
          paragraph.textContent = bodyChild.nodeValue;
          wrapper.appendChild(paragraph);
        } else {
          wrapper.appendChild(bodyChild.cloneNode(true));
        }
        blocks.push(wrapper);
      });
    });
    return blocks;
  }

  function cloneTextSlice(root, start, end) {
    const state = { offset: 0 };
    function cloneNodeSlice(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        const nodeStart = state.offset;
        const nodeEnd = nodeStart + node.nodeValue.length;
        state.offset = nodeEnd;
        const sliceStart = Math.max(start, nodeStart);
        const sliceEnd = Math.min(end, nodeEnd);
        if (sliceStart >= sliceEnd) return null;
        return document.createTextNode(node.nodeValue.slice(sliceStart - nodeStart, sliceEnd - nodeStart));
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return null;
      if (node.tagName === 'BR') {
        const nodeStart = state.offset;
        state.offset += 1;
        return start <= nodeStart && nodeStart < end ? node.cloneNode(false) : null;
      }
      const clone = node.cloneNode(false);
      Array.from(node.childNodes).forEach((child) => {
        const childClone = cloneNodeSlice(child);
        if (childClone) clone.appendChild(childClone);
      });
      return clone.childNodes.length ? clone : null;
    }
    return cloneNodeSlice(root);
  }

  function wordBoundaries(text) {
    const boundaries = [];
    const matcher = /\s+/g;
    let match;
    while ((match = matcher.exec(text)) !== null) {
      if (match.index > 0 && match.index < text.length) boundaries.push(match.index);
    }
    return boundaries;
  }

  function linearText(root) {
    let value = '';
    root.childNodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) value += node.nodeValue;
      else if (node.nodeType === Node.ELEMENT_NODE && node.tagName === 'BR') value += '\n';
      else if (node.nodeType === Node.ELEMENT_NODE) value += linearText(node);
    });
    return value;
  }

  function splitBlockToFit(block, page) {
    if (!block.matches('.p17-letter-body')) return null;
    const text = linearText(block);
    const boundaries = wordBoundaries(text);
    if (!boundaries.length) return null;
    let low = 0;
    let high = boundaries.length - 1;
    let best = -1;
    while (low <= high) {
      const middle = Math.floor((low + high) / 2);
      const splitAt = boundaries[middle];
      const candidate = cloneTextSlice(block, 0, splitAt);
      if (!candidate) break;
      page.flow.appendChild(candidate);
      const fits = !paperOverflows(page.paper);
      candidate.remove();
      if (fits) {
        best = middle;
        low = middle + 1;
      } else {
        high = middle - 1;
      }
    }
    if (best < 0) return null;
    const splitAt = boundaries[best];
    const head = cloneTextSlice(block, 0, splitAt);
    const tail = cloneTextSlice(block, splitAt, text.length);
    if (!head?.textContent.trim() || !tail?.textContent.trim()) return null;
    return { head, tail };
  }

  function paginate(content) {
    pagesHolder.replaceChildren();
    hasOversizedBlock = false;
    const sourceBarcode = content.querySelector('.p17-verification-mark');
    let page = createPaper(true, sourceBarcode);

    flowBlocks(content).forEach((originalBlock) => {
      let block = originalBlock;
      let safety = 0;
      while (block && safety < 100) {
        safety += 1;
        page.flow.appendChild(block);
        if (!paperOverflows(page.paper)) break;
        block.remove();

        const split = splitBlockToFit(block, page);
        if (split?.head && split?.tail) {
          page.flow.appendChild(split.head);
          block = split.tail;
          page = createPaper(false, sourceBarcode);
          continue;
        }

        if (page.flow.children.length) {
          page = createPaper(false, sourceBarcode);
          continue;
        }

        page.flow.appendChild(block);
        if (paperOverflows(page.paper)) {
          block.classList.add('p17-oversized-block');
          hasOversizedBlock = true;
        }
        break;
      }
    });

    pagesHolder.querySelectorAll('.p17-paper').forEach((paper, index) => {
      paper.dataset.pageNumber = String(index + 1);
    });
    if (overflowWarning) overflowWarning.hidden = !hasOversizedBlock;
    applyPreviewScale();
  }

  function applyPreviewScale() {
    pagesHolder.querySelectorAll('.p17-paper-frame').forEach((frame) => {
      const paper = frame.querySelector('.p17-paper');
      if (!paper) return;
      paper.style.transform = 'none';
      const naturalWidth = paper.offsetWidth;
      const naturalHeight = paper.offsetHeight;
      if (!naturalWidth || !naturalHeight) return;
      const scale = Math.min(1, frame.clientWidth / naturalWidth);
      paper.style.transform = scale < 1 ? `scale(${scale})` : 'none';
      frame.style.height = `${Math.round(naturalHeight * scale)}px`;
    });
  }

  function applyBarcodePreview(content) {
    if (!barcodePreviewUrl) return;
    content.querySelectorAll('.p17-verification-mark').forEach((mark) => {
      mark.classList.add('has-barcode');
      mark.replaceChildren();
      const image = document.createElement('img');
      image.src = barcodePreviewUrl;
      image.alt = 'Preview barcode P-17';
      mark.appendChild(image);
    });
  }

  function renderPreview() {
    renderFrame = 0;
    const content = safeFragment(source.innerHTML);
    const setText = (name, value) => content.querySelectorAll(`[data-p17-output="${name}"]`).forEach((node) => {
      node.textContent = value || '—';
    });
    setText('number', completeP17Number() || '—');
    setText('date', indonesianDate(dateInput?.value));
    setText('nature', natureInput?.value.trim());
    setText('attachment', attachmentInput?.value.trim());
    const subjectTarget = content.querySelector('[data-p17-section="subject"]');
    if (subjectTarget) subjectTarget.textContent = subjectInput?.value.trim() || '—';
    ['body', 'copies'].forEach((section) => {
      const target = content.querySelector(`[data-p17-section="${section}"]`);
      const editor = editorFor(section);
      if (target && editor) target.replaceChildren(...Array.from(safeFragment(editor.value).childNodes).map((node) => node.cloneNode(true)));
    });
    renderRecipientPreview(content.querySelector('[data-p17-section="recipient"]'));
    applyBarcodePreview(content);
    paginate(content.querySelector('.p17-page-content'));
  }

  function queueRender() {
    if (renderFrame) window.cancelAnimationFrame(renderFrame);
    renderFrame = window.requestAnimationFrame(renderPreview);
  }

  function syncNumberMode() {
    if (!numberInput) return;
    numberInput.readOnly = !canEdit;
    numberInput.setAttribute('aria-readonly', String(numberInput.readOnly));
    const help = form.querySelector('[data-p17-number-help]');
    const fullNumber = completeP17Number();
    if (help) help.textContent = 'Isi angka nomor urut saja, contoh: 11.';
    if (numberPreview) numberPreview.textContent = fullNumber || 'Masukkan nomor urut';
  }

  function updateBarcodeWidget(file) {
    if (barcodePreviewUrl) URL.revokeObjectURL(barcodePreviewUrl);
    barcodePreviewUrl = file ? URL.createObjectURL(file) : '';
    if (file && barcodePreview) {
      barcodePreview.replaceChildren();
      const image = document.createElement('img');
      image.src = barcodePreviewUrl;
      image.alt = 'Preview barcode P-17';
      barcodePreview.appendChild(image);
    }
    if (file && barcodeTitle) barcodeTitle.textContent = 'Barcode siap disimpan';
    if (file && barcodeStatus) barcodeStatus.textContent = `${file.name} - ${Math.max(1, Math.round(file.size / 1024))} KB`;
    queueRender();
  }

  function assignBarcodeFiles(files) {
    const file = files?.[0];
    if (!file || !barcodeInput) return;
    if (!file.type.startsWith('image/')) {
      if (barcodeStatus) barcodeStatus.textContent = 'File harus berupa gambar barcode/QR.';
      return;
    }
    const transfer = new DataTransfer();
    transfer.items.add(file);
    barcodeInput.files = transfer.files;
    updateBarcodeWidget(file);
  }

  if (!canEdit) {
    [numberInput, dateInput, natureInput, attachmentInput, manualInput, subjectInput, barcodeInput, recipientPlaceInput].forEach((input) => {
      if (input) input.disabled = true;
    });
  }

  editors.forEach(({ editor }) => editor.events.on('change', queueRender));
  [numberInput, dateInput, natureInput, attachmentInput, subjectInput].forEach((input) => {
    input?.addEventListener('input', queueRender);
    input?.addEventListener('change', queueRender);
  });
  [numberInput, dateInput].forEach((input) => input?.addEventListener('input', syncNumberMode));
  [numberInput, dateInput].forEach((input) => input?.addEventListener('change', syncNumberMode));
  addRecipientButton?.addEventListener('click', () => addRecipient());
  recipientRows?.addEventListener('input', () => { writeRecipients(); queueRender(); });
  recipientPlaceInput?.addEventListener('input', () => { writeRecipients(); queueRender(); });
  recipientRows?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-p17-remove-recipient]');
    if (!button) return;
    button.closest('[data-p17-recipient-row]')?.remove();
    refreshRecipientRows();
    writeRecipients();
    queueRender();
  });
  barcodeInput?.addEventListener('change', () => updateBarcodeWidget(barcodeInput.files?.[0]));
  barcodeDropzone?.addEventListener('click', () => barcodeInput?.click());
  barcodeDropzone?.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    barcodeInput?.click();
  });
  barcodeDropzone?.addEventListener('dragover', (event) => {
    event.preventDefault();
    barcodeDropzone.classList.add('dragging');
  });
  barcodeDropzone?.addEventListener('dragleave', () => barcodeDropzone.classList.remove('dragging'));
  barcodeDropzone?.addEventListener('drop', (event) => {
    event.preventDefault();
    barcodeDropzone.classList.remove('dragging');
    assignBarcodeFiles(event.dataTransfer?.files);
  });
  form.querySelector('[data-p17-print]')?.addEventListener('click', () => {
    renderPreview();
    if (hasOversizedBlock) {
      window.alert('Masih ada satu blok P-17 yang terlalu panjang. Pisahkan paragraf tersebut sebelum mencetak.');
      return;
    }
    window.print();
  });
  window.addEventListener('resize', applyPreviewScale);
  window.addEventListener('load', queueRender, { once: true });
  if (document.fonts?.ready) document.fonts.ready.then(queueRender);
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(applyPreviewScale).observe(pagesHolder);
  form.addEventListener('submit', () => {
    writeRecipients();
    editors.forEach(({ textarea, editor }) => { textarea.value = editor.value; });
  });
  new MutationObserver(() => {
    const theme = document.documentElement.classList.contains('dark') ? 'dark' : 'default';
    editors.forEach(({ editor }) => editor.setOptions({ theme }));
  }).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

  syncNumberMode();
  const initialRecipients = readRecipients();
  if (recipientPlaceInput) {
    recipientPlaceInput.value = initialRecipients.find((item) => item.place)?.place || '';
  }
  (initialRecipients.length ? initialRecipients : [{ recipient: '' }]).forEach((item) => addRecipient(item));
  if (addRecipientButton) addRecipientButton.disabled = !canEdit;
  renderPreview();
})();
