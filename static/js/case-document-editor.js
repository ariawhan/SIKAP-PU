(function () {
  const form = document.querySelector('[data-case-document-form]');
  const holder = form?.querySelector('[data-document-pages]');
  const source = form?.querySelector('[data-document-source]');
  const letterhead = form?.querySelector('[data-document-letterhead]');
  const textareas = Array.from(form?.querySelectorAll('[data-document-rich-editor]') || []).filter((field) => !field.closest('[hidden]'));
  if (!form || !holder || !source || !letterhead || typeof window.Jodit === 'undefined') return;
  const editable = form.dataset.canEdit === 'true';
  const documentType = form.dataset.documentType;
  const numberInput = form.querySelector('[name="letter_number"]');
  const manualInput = form.querySelector('[name="manual_number"]');
  const dateInput = form.querySelector('[name="letter_date"]');
  const natureInput = form.querySelector('[name="letter_nature"]');
  const attachmentInput = form.querySelector('[name="attachment"]');
  const subjectInput = form.querySelector('[data-document-subject]');
  const barcodeInput = form.querySelector('[data-document-barcode-input]');
  const barcodePreview = form.querySelector('[data-document-barcode-preview]');
  const warning = form.querySelector('[data-document-overflow]');
  let frame = 0;
  let barcodeObjectUrl = '';

  function applyRecipients(content) {
    const target = content.querySelector('[data-document-section="recipient"]');
    if (!target) return;
    let items=[]; try{items=JSON.parse(form.querySelector('[name="recipients_json"]')?.value||'[]')}catch(_error){items=[]}
    if(!items.length)return; const recipientBlock=document.createElement(['p20','sop07'].includes(documentType)?'span':'strong');recipientBlock.append(document.createTextNode('Yth. '));items.forEach((item,index)=>{if(index)recipientBlock.append(document.createElement('br'));recipientBlock.append(document.createTextNode(item.recipient||''))});recipientBlock.append(document.createElement('br'),document.createTextNode('Di -'),document.createElement('br'));const place=document.createElement('u');place.textContent=items[0]?.place||'Tempat';recipientBlock.append(place);target.replaceChildren(recipientBlock);
  }

  function safeFragment(html) {
    const parsed = new DOMParser().parseFromString(html || '', 'text/html');
    parsed.querySelectorAll('script,style,iframe,object,embed,form,input,button,link,meta,base,video,audio,svg,math').forEach((node) => node.remove());
    parsed.body.querySelectorAll('*').forEach((node) => Array.from(node.attributes).forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim().toLowerCase();
      if (name.startsWith('on') || name === 'srcdoc' || ((name === 'href' || name === 'src') && /^(javascript|vbscript):/.test(value))) node.removeAttribute(attribute.name);
    }));
    return parsed.body;
  }

  function indonesianDate(value) {
    if (!value) return '—';
    const date = new Date(`${value}T00:00:00Z`);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('id-ID', { day: '2-digit', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(date);
  }

  const editors = textareas.map((textarea) => {
    const section = textarea.dataset.documentRichEditor;
    const editor = window.Jodit.make(textarea, {
      height: section === 'body' ? 380 : 240, minHeight: 190, maxHeight: 650,
      readonly: !editable, toolbarAdaptive: true, toolbarSticky: false, statusbar: true,
      showCharsCounter: false, showWordsCounter: true, showXPathInStatusbar: false,
      askBeforePasteHTML: false, askBeforePasteFromWord: false, defaultActionOnPaste: 'insert_clear_html',
      buttons: ['undo', 'redo', '|', 'fontsize', '|', 'bold', 'italic', 'underline', '|', 'ol', 'ul', 'table', '|', 'outdent', 'indent', '|', 'left', 'center', 'right', 'justify', '|', 'eraser', 'source']
    });
    editor.editor.style.fontFamily = 'Arial, sans-serif';
    editor.editor.style.fontSize = documentType === 'p18' ? '12pt' : '10pt';
    editor.editor.style.lineHeight = documentType === 'p18' ? '1.5' : '1.15';
    return { section, editor };
  });

  function createPaper(firstPage, barcodeMark) {
    const paper = document.createElement('article');
    paper.className = 'case-doc-paper';
    paper.dataset.documentType = documentType;
    if (firstPage) paper.appendChild(letterhead.content.cloneNode(true));
    const content = document.createElement('section');
    content.className = 'case-doc-page-content';
    paper.appendChild(content);
    if (barcodeMark) paper.appendChild(barcodeMark.cloneNode(true));
    holder.appendChild(paper);
    return { paper, content };
  }

  function flowBlocks(content) {
    const blocks = [];
    Array.from(content.children).forEach((child) => {
      if (child.matches('.case-doc-verification-mark')) return;
      if (!child.matches('.case-doc-body')) {
        blocks.push(child.cloneNode(true));
        return;
      }
      Array.from(child.children).forEach((bodyChild) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'case-doc-body case-doc-flow-block';
        if (bodyChild.tagName === 'OL') {
          const start = Number(bodyChild.getAttribute('start') || 1);
          Array.from(bodyChild.children).forEach((item, index) => {
            const itemWrapper = wrapper.cloneNode(false);
            const list = document.createElement('ol');
            list.start = start + index;
            const clonedItem = item.cloneNode(true);
            clonedItem.dataset.documentListNumber = String(start + index);
            list.appendChild(clonedItem);
            itemWrapper.appendChild(list);
            blocks.push(itemWrapper);
          });
        } else {
          wrapper.appendChild(bodyChild.cloneNode(true));
          blocks.push(wrapper);
        }
      });
    });
    return blocks;
  }

  function paginate(content) {
    holder.replaceChildren();
    const barcodeMark = content.querySelector('.case-doc-verification-mark');
    let page = createPaper(true, barcodeMark);
    let oversized = false;
    flowBlocks(content).forEach((block) => {
      page.content.appendChild(block);
      if (page.paper.scrollHeight <= page.paper.clientHeight + 2) return;
      block.remove();
      if (!page.content.children.length) {
        page.content.appendChild(block);
        oversized = true;
        return;
      }
      page = createPaper(false, barcodeMark);
      page.content.appendChild(block);
      if (page.paper.scrollHeight > page.paper.clientHeight + 2) oversized = true;
    });
    Array.from(holder.querySelectorAll('.case-doc-paper')).forEach((paper, index) => { paper.dataset.pageNumber = String(index + 1); });
    if (warning) warning.hidden = !oversized && holder.children.length === 1;
  }

  function render() {
    frame = 0;
    const content = safeFragment(source.innerHTML);
    const setText = (name, value) => content.querySelectorAll(`[data-document-output="${name}"]`).forEach((node) => { node.textContent = value || '—'; });
    let displayedNumber = numberInput?.value.trim();
    if (['p18', 'p19', 'p20', 'sop07'].includes(documentType) && /^\d+$/.test(displayedNumber || '') && dateInput?.value) {
      const dateParts = dateInput.value.split('-');
      displayedNumber = `B-${displayedNumber}/${form.dataset.numberRegion}/${form.dataset.numberCode}/${dateParts[1]}/${dateParts[0]}`;
    }
    setText('number', displayedNumber);
    setText('date', indonesianDate(dateInput?.value));
    setText('nature', natureInput?.value.trim());
    setText('attachment', attachmentInput?.value.trim());
    const subjectTarget = content.querySelector('[data-document-section="subject"]');
    if (subjectTarget && subjectInput) subjectTarget.textContent = subjectInput.value.trim();
    ['legal-basis', 'body', 'copies'].forEach((section) => {
      const target = content.querySelector(`[data-document-section="${section}"]`);
      const editor = editors.find((record) => record.section === section)?.editor;
      if (target && editor) target.replaceChildren(...Array.from(safeFragment(editor.value).childNodes).map((node) => node.cloneNode(true)));
    });
    applyRecipients(content);
    if (barcodeObjectUrl) {
      content.querySelectorAll('[data-document-barcode-mark]').forEach((mark) => {
        mark.classList.add('has-barcode');
        const image = document.createElement('img');
        image.src = barcodeObjectUrl;
        image.alt = 'Barcode verifikasi P-18';
        mark.replaceChildren(image);
      });
    }
    paginate(content.querySelector('.case-doc-page-content'));
  }

  function queueRender() {
    if (frame) window.cancelAnimationFrame(frame);
    frame = window.requestAnimationFrame(render);
  }

  function syncNumberMode() {
    if (!numberInput || !manualInput) return;
    if (['p18', 'p19', 'p20', 'sop07'].includes(documentType)) {
      numberInput.readOnly = !editable;
      numberInput.value = numberInput.value.replace(/\D/g, '');
      return;
    }
    numberInput.readOnly = !manualInput.checked || !editable;
    const help = form.querySelector('[data-document-number-help]');
    if (help) help.textContent = manualInput.checked ? 'Nomor surat dapat diubah secara manual.' : 'Nomor draf dibuat otomatis.';
  }

  if (!editable) [numberInput, manualInput, dateInput, natureInput, attachmentInput, subjectInput].forEach((input) => { if (input) input.disabled = true; });
  editors.forEach(({ editor }) => editor.events.on('change', queueRender));
  [numberInput, dateInput, natureInput, attachmentInput, subjectInput].forEach((input) => { input?.addEventListener('input', queueRender); input?.addEventListener('change', queueRender); });
  manualInput?.addEventListener('change', () => { syncNumberMode(); queueRender(); });
  form.addEventListener('letter-recipients-change', queueRender);
  barcodeInput?.addEventListener('change', () => {
    const file = barcodeInput.files?.[0];
    if (!file) return;
    if (barcodeObjectUrl) URL.revokeObjectURL(barcodeObjectUrl);
    barcodeObjectUrl = URL.createObjectURL(file);
    if (barcodePreview) {
      const image = document.createElement('img');
      image.src = barcodeObjectUrl;
      image.alt = 'Preview barcode P-18';
      const label = document.createElement('span');
      label.textContent = file.name;
      barcodePreview.replaceChildren(image, label);
    }
    queueRender();
  });
  form.querySelector('[data-document-print]')?.addEventListener('click', () => { render(); requestAnimationFrame(() => requestAnimationFrame(() => window.print())); });
  window.addEventListener('resize', queueRender);
  syncNumberMode();
  render();
})();
