(function () {
  const form = document.querySelector('[data-coordination-form]');
  const pagesHolder = form?.querySelector('[data-coordination-pages]');
  const source = form?.querySelector('[data-coordination-document-source]');
  const letterhead = form?.querySelector('[data-coordination-letterhead]');
  const bodyTextarea = form?.querySelector('[data-coordination-rich-editor="body"]');
  if (!form || !pagesHolder || !source || !letterhead || !bodyTextarea || typeof window.Jodit === 'undefined') return;

  const canEdit = form.dataset.canEdit === 'true';
  const coordinationType = form.dataset.coordinationType || 'ba1';
  const overflowWarning = form.querySelector('[data-coordination-overflow-warning]');
  const dateInput = form.querySelector('[data-coordination-date]');
  const barcodeInput = form.querySelector('[data-coordination-barcode-input]');
  const imageInputs = Array.from(form.querySelectorAll('[data-coordination-image]'));
  const previewUrls = new Map();
  let barcodePreviewUrl = '';
  let renderFrame = 0;
  let hasOversizedBlock = false;

  const editor = window.Jodit.make(bodyTextarea, {
    height: 430,
    minHeight: 330,
    maxHeight: 720,
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
  editor.editor.style.fontSize = '11pt';
  editor.editor.style.lineHeight = '1.15';

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
    if (!value) return '---';
    const date = new Date(`${value}T00:00:00Z`);
    if (Number.isNaN(date.getTime())) return value;
    const words = ['Nol', 'Satu', 'Dua', 'Tiga', 'Empat', 'Lima', 'Enam', 'Tujuh', 'Delapan', 'Sembilan', 'Sepuluh', 'Sebelas'];
    function numberWords(number) {
      if (number < 12) return words[number];
      if (number < 20) return `${numberWords(number - 10)} Belas`;
      if (number < 100) return `${numberWords(Math.floor(number / 10))} Puluh${number % 10 ? ` ${numberWords(number % 10)}` : ''}`;
      if (number < 200) return `Seratus${number > 100 ? ` ${numberWords(number - 100)}` : ''}`;
      if (number < 1000) return `${numberWords(Math.floor(number / 100))} Ratus${number % 100 ? ` ${numberWords(number % 100)}` : ''}`;
      if (number < 2000) return `Seribu${number > 1000 ? ` ${numberWords(number - 1000)}` : ''}`;
      return `${numberWords(Math.floor(number / 1000))} Ribu${number % 1000 ? ` ${numberWords(number % 1000)}` : ''}`;
    }
    const weekday = new Intl.DateTimeFormat('id-ID', { weekday: 'long', timeZone: 'UTC' }).format(date);
    const month = new Intl.DateTimeFormat('id-ID', { month: 'long', timeZone: 'UTC' }).format(date);
    const numeric = `${String(date.getUTCDate()).padStart(2, '0')}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${date.getUTCFullYear()}`;
    return `${weekday} tanggal ${numberWords(date.getUTCDate())} bulan ${month} tahun ${numberWords(date.getUTCFullYear())} (${numeric})`;
  }

  function synchronizedContent() {
    const fragment = source.content.cloneNode(true);
    form.querySelectorAll('[data-coordination-output-input]').forEach((input) => {
      const key = input.dataset.coordinationOutputInput;
      fragment.querySelectorAll(`[data-coordination-output="${key}"]`).forEach((target) => {
        target.textContent = input.value.trim() || '---';
      });
    });
    fragment.querySelectorAll('[data-coordination-output="date-long"]').forEach((target) => {
      target.textContent = indonesianDate(dateInput?.value || '');
    });
    const body = fragment.querySelector('[data-coordination-section="body"]');
    if (body) body.replaceChildren(...Array.from(safeFragment(editor.value).childNodes));

    imageInputs.forEach((input) => {
      const number = input.dataset.coordinationImage;
      const section = fragment.querySelector(`[data-coordination-documentation="${number}"]`);
      const url = previewUrls.get(number);
      if (!section || !url) return;
      section.classList.remove('is-empty');
      const frame = section.querySelector('.coordination-documentation-frame');
      const image = document.createElement('img');
      image.src = url;
      image.alt = `Dokumentasi koordinasi ${number}`;
      frame?.replaceChildren(image);
    });
    if (barcodePreviewUrl) {
      const mark = fragment.querySelector('[data-coordination-barcode-mark]');
      const image = document.createElement('img');
      image.src = barcodePreviewUrl;
      image.alt = 'Barcode verifikasi koordinasi';
      mark?.replaceChildren(image);
    }
    return fragment;
  }

  function pageSafeBottom(paper) {
    const rect = paper.getBoundingClientRect();
    const paddingBottom = Number.parseFloat(window.getComputedStyle(paper).paddingBottom) || 0;
    return rect.bottom - paddingBottom;
  }

  function deepestFlowBottom(paper) {
    let bottom = 0;
    Array.from(paper.querySelectorAll('.coordination-letterhead,.coordination-page-flow,.coordination-page-flow *')).forEach((node) => {
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
    frame.className = 'coordination-paper-frame';
    frame.style.setProperty('--coord-height', coordinationType === 'ba3' ? '13in' : '14in');
    const paper = document.createElement('article');
    paper.className = 'coordination-paper';
    paper.dataset.coordinationType = coordinationType;
    paper.style.transform = 'none';
    if (firstPage) paper.appendChild(letterhead.content.cloneNode(true));
    const flow = document.createElement('section');
    flow.className = 'coordination-page-flow';
    paper.appendChild(flow);
    if (barcodeMark) paper.appendChild(barcodeMark.cloneNode(true));
    frame.appendChild(paper);
    pagesHolder.appendChild(frame);
    return { frame, paper, flow, firstPage };
  }

  function bodyFlowBlocks(body) {
    const blocks = [];
    Array.from(body.childNodes).filter((node) => node.nodeType !== Node.TEXT_NODE || node.nodeValue.trim()).forEach((child) => {
      if (child.nodeType === Node.ELEMENT_NODE && (child.tagName === 'OL' || child.tagName === 'UL')) {
        const items = Array.from(child.children).filter((item) => item.tagName === 'LI');
        if (items.length) {
          items.forEach((item, index) => {
            const wrapper = body.cloneNode(false);
            wrapper.classList.add('coordination-flow-block');
            const list = child.cloneNode(false);
            if (list.tagName === 'OL') list.start = Number(child.getAttribute('start') || 1) + index;
            const clonedItem = item.cloneNode(true);
            if (list.tagName === 'OL') clonedItem.value = Number(child.getAttribute('start') || 1) + index;
            list.appendChild(clonedItem);
            wrapper.appendChild(list);
            blocks.push(wrapper);
          });
          return;
        }
      }
      const wrapper = body.cloneNode(false);
      wrapper.classList.add('coordination-flow-block');
      if (child.nodeType === Node.TEXT_NODE) {
        const paragraph = document.createElement('p');
        paragraph.textContent = child.nodeValue;
        wrapper.appendChild(paragraph);
      } else {
        wrapper.appendChild(child.cloneNode(true));
      }
      blocks.push(wrapper);
    });
    return blocks;
  }

  function flowBlocks(content) {
    const main = content.querySelector('.coordination-main-content');
    const blocks = [];
    Array.from(main?.children || []).forEach((child) => {
      if (child.matches('.coordination-verification-mark')) return;
      if (child.matches('.coordination-body')) blocks.push(...bodyFlowBlocks(child));
      else blocks.push(child.cloneNode(true));
    });
    return blocks;
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

  function splitBlockToFit(block, page) {
    if (!block.matches('.coordination-body')) return null;
    const text = linearText(block);
    const boundaries = [];
    const matcher = /\s+/g;
    let match;
    while ((match = matcher.exec(text)) !== null) {
      if (match.index > 0 && match.index < text.length) boundaries.push(match.index);
    }
    if (!boundaries.length) return null;
    let low = 0;
    let high = boundaries.length - 1;
    let best = -1;
    while (low <= high) {
      const middle = Math.floor((low + high) / 2);
      const candidate = cloneTextSlice(block, 0, boundaries[middle]);
      if (!candidate) break;
      page.flow.appendChild(candidate);
      const fits = !paperOverflows(page.paper);
      candidate.remove();
      if (fits) { best = middle; low = middle + 1; } else { high = middle - 1; }
    }
    if (best < 0) return null;
    const splitAt = boundaries[best];
    const head = cloneTextSlice(block, 0, splitAt);
    const tail = cloneTextSlice(block, splitAt, text.length);
    if (!head?.textContent.trim() || !tail?.textContent.trim()) return null;
    return { head, tail };
  }

  function paginate(fragment) {
    pagesHolder.replaceChildren();
    hasOversizedBlock = false;
    const content = fragment.querySelector('[data-coordination-document-content]');
    const barcodeMark = content.querySelector('.coordination-verification-mark');
    let page = createPaper(true, barcodeMark);

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
          page = createPaper(false, barcodeMark);
          continue;
        }
        if (page.flow.children.length || page.firstPage) {
          page = createPaper(false, barcodeMark);
          continue;
        }
        page.flow.appendChild(block);
        block.classList.add('coordination-oversized-block');
        hasOversizedBlock = true;
        break;
      }
    });

    Array.from(content.querySelectorAll('.coordination-documentation:not(.is-empty)')).forEach((documentation) => {
      page = createPaper(false, barcodeMark);
      page.flow.appendChild(documentation.cloneNode(true));
      if (paperOverflows(page.paper)) {
        page.flow.firstElementChild?.classList.add('coordination-oversized-block');
        hasOversizedBlock = true;
      }
    });

    pagesHolder.querySelectorAll('.coordination-paper').forEach((paper, index) => {
      paper.dataset.pageNumber = String(index + 1);
    });
    if (overflowWarning) overflowWarning.hidden = !hasOversizedBlock;
    applyPreviewScale();
  }

  function applyPreviewScale() {
    const stage = form.querySelector('.coordination-preview-stage');
    const availableWidth = Math.max(250, (stage?.clientWidth || 816) - 12);
    pagesHolder.querySelectorAll('.coordination-paper-frame').forEach((frame) => {
      const paper = frame.querySelector('.coordination-paper');
      if (!paper) return;
      paper.style.transform = 'none';
      const scale = Math.min(1, availableWidth / paper.offsetWidth);
      paper.style.transform = `scale(${scale})`;
      frame.style.width = `${paper.offsetWidth * scale}px`;
      frame.style.height = `${paper.offsetHeight * scale}px`;
    });
  }

  function render() {
    cancelAnimationFrame(renderFrame);
    renderFrame = requestAnimationFrame(() => paginate(synchronizedContent()));
  }

  form.querySelectorAll('[data-coordination-output-input],[data-coordination-date]').forEach((input) => {
    input.addEventListener('input', render);
    input.addEventListener('change', render);
  });
  editor.events.on('change', render);

  imageInputs.forEach((input) => {
    input.addEventListener('change', () => {
      const number = input.dataset.coordinationImage;
      const file = input.files?.[0];
      if (!file) return;
      if (previewUrls.has(number)) URL.revokeObjectURL(previewUrls.get(number));
      const url = URL.createObjectURL(file);
      previewUrls.set(number, url);
      const card = form.querySelector(`[data-coordination-upload-card="${number}"]`);
      const preview = card?.querySelector('.coordination-upload-preview');
      const image = document.createElement('img');
      image.src = url;
      image.alt = `Dokumentasi ${number}`;
      preview?.replaceChildren(image);
      const title = card?.querySelector('span:nth-child(2) b');
      const status = card?.querySelector('span:nth-child(2) small');
      if (title) title.textContent = `Dokumentasi ${number} siap diunggah`;
      if (status) status.textContent = file.name;
      image.addEventListener('load', render, { once: true });
      render();
    });
  });

  barcodeInput?.addEventListener('change', () => {
    if (barcodePreviewUrl) URL.revokeObjectURL(barcodePreviewUrl);
    barcodePreviewUrl = barcodeInput.files?.[0] ? URL.createObjectURL(barcodeInput.files[0]) : '';
    const preview = form.querySelector('.coordination-barcode-card .coordination-upload-preview');
    const title = form.querySelector('.coordination-barcode-card span:nth-child(2) b');
    const status = form.querySelector('.coordination-barcode-card span:nth-child(2) small');
    if (barcodePreviewUrl) {
      const image = document.createElement('img');
      image.src = barcodePreviewUrl;
      image.alt = 'Barcode/QR koordinasi';
      preview?.replaceChildren(image);
      if (title) title.textContent = 'Barcode/QR siap diunggah';
      if (status) status.textContent = barcodeInput.files[0].name;
    }
    render();
  });

  if (!canEdit) {
    form.querySelectorAll('input,textarea,select').forEach((field) => {
      if (field.name !== 'csrfmiddlewaretoken') field.disabled = true;
    });
  }

  form.addEventListener('submit', () => editor.synchronizeValues());
  form.querySelector('[data-coordination-print]')?.addEventListener('click', () => {
    render();
    requestAnimationFrame(() => requestAnimationFrame(() => window.print()));
  });
  window.addEventListener('resize', () => requestAnimationFrame(applyPreviewScale));
  window.addEventListener('beforeunload', () => {
    previewUrls.forEach((url) => URL.revokeObjectURL(url));
    if (barcodePreviewUrl) URL.revokeObjectURL(barcodePreviewUrl);
  });
  render();
})();
