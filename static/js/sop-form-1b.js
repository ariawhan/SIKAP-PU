(function () {
  const form = document.querySelector('[data-p17-form]');
  const pagesHolder = form?.querySelector('[data-sop1b-pages]');
  const source = form?.querySelector('[data-sop1b-document-source]');
  const letterhead = form?.querySelector('[data-sop1b-letterhead]');
  if (!form || !pagesHolder || !source || !letterhead) return;

  const canEdit = form.dataset.canEdit === 'true';
  const overflowWarning = form.querySelector('[data-sop1b-overflow-warning]');
  const barcodeInput = form.querySelector('[data-sop1b-barcode-input]');
  const editorPanels = Array.from(form.querySelectorAll('[data-document-editor]'));
  const previewPanels = Array.from(form.querySelectorAll('[data-document-preview]'));
  const editorTabs = Array.from(form.querySelectorAll('[data-document-tab]'));
  const previewTabs = Array.from(form.querySelectorAll('[data-preview-tab]'));
  const plainInputs = Array.from(form.querySelectorAll('[data-sop1b-input]'));
  const prosecutorChoice = form.querySelector('[data-sop1b-prosecutor-choice]');
  const textareas = Array.from(form.querySelectorAll('[data-sop1b-rich-editor]'));
  let editors = [];
  let editorsReady = false;
  let renderFrame = 0;
  let hasOversizedBlock = false;
  let barcodePreviewUrl = '';

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

  function initEditors() {
    if (editorsReady || typeof window.Jodit === 'undefined') return;
    editors = textareas.map((textarea) => {
      const section = textarea.dataset.sop1bRichEditor;
      const compact = section === 'kasi-opinion' || section === 'leader-instruction';
      const editor = window.Jodit.make(textarea, {
        height: compact ? 190 : 270,
        minHeight: compact ? 140 : 210,
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
        buttons: [
          'undo', 'redo', '|', 'paragraph', 'fontsize', '|',
          'bold', 'italic', 'underline', '|', 'ol', 'ul', '|',
          'outdent', 'indent', '|', 'left', 'center', 'right', 'justify', '|',
          'link', 'table', 'hr', '|', 'eraser', 'source', 'fullsize'
        ]
      });
      editor.editor.style.fontFamily = 'Arial, sans-serif';
      editor.editor.style.fontSize = '9pt';
      editor.editor.style.lineHeight = '1.15';
      editor.events.on('change', queueRender);
      return { textarea, section, editor };
    });
    editorsReady = true;
  }

  function editorFor(section) {
    return editors.find((record) => record.section === section)?.editor;
  }

  function activatePreview(name) {
    previewPanels.forEach((panel) => {
      const active = panel.dataset.documentPreview === name;
      panel.hidden = !active;
      panel.classList.toggle('active', active);
    });
    previewTabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.previewTab === name));
    if (name === 'sop1b') {
      initEditors();
      window.requestAnimationFrame(renderPreview);
    }
  }

  function activateDocument(name) {
    editorPanels.forEach((panel) => {
      const active = panel.dataset.documentEditor === name;
      panel.hidden = !active;
      panel.classList.toggle('active', active);
    });
    editorTabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.documentTab === name));
    activatePreview(name);
  }

  function pageSafeBottom(paper) {
    const rect = paper.getBoundingClientRect();
    const paddingBottom = Number.parseFloat(window.getComputedStyle(paper).paddingBottom) || 0;
    return rect.bottom - paddingBottom;
  }

  function deepestFlowBottom(paper) {
    let bottom = 0;
    Array.from(paper.querySelectorAll('.sop1b-letterhead,.p17-page-flow,.p17-page-flow *')).forEach((node) => {
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
    paper.className = 'p17-paper sop1b-paper';
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

  function appendSectionBlocks(blocks, section) {
    const heading = section.querySelector(':scope > h3');
    const content = section.querySelector(':scope > div');
    const children = Array.from(content?.children || []);
    let headingPending = Boolean(heading);
    if (!children.length) {
      const wrapper = section.cloneNode(true);
      wrapper.classList.add('sop1b-flow-block');
      blocks.push(wrapper);
      return;
    }
    children.forEach((child) => {
      if (child.matches('ol,ul') && child.children.length) {
        Array.from(child.children).forEach((item, index) => {
          const wrapper = document.createElement('section');
          wrapper.className = 'sop1b-section sop1b-flow-block sop1b-splittable sop1b-list-item-block';
          if (headingPending && heading) {
            wrapper.appendChild(heading.cloneNode(true));
            if (section.previousElementSibling?.matches('.sop1b-section')) {
              wrapper.classList.add('sop1b-section-gap');
            }
          }
          const list = child.cloneNode(false);
          if (child.matches('ol') && index > 0) list.start = index + 1;
          list.appendChild(item.cloneNode(true));
          wrapper.appendChild(list);
          blocks.push(wrapper);
          headingPending = false;
        });
        return;
      }
      const wrapper = document.createElement('section');
      wrapper.className = 'sop1b-section sop1b-flow-block sop1b-splittable';
      if (child.matches('p')) wrapper.classList.add('sop1b-paragraph-block');
      if (headingPending && heading) {
        wrapper.appendChild(heading.cloneNode(true));
        if (section.previousElementSibling?.matches('.sop1b-section')) {
          wrapper.classList.add('sop1b-section-gap');
        }
      }
      wrapper.appendChild(child.cloneNode(true));
      blocks.push(wrapper);
      headingPending = false;
    });
  }

  function flowBlocks(content) {
    const blocks = [];
    Array.from(content.children).forEach((child) => {
      if (child.matches('.sop1b-verification-mark')) return;
      if (child.matches('.sop1b-section')) appendSectionBlocks(blocks, child);
      else {
        const clone = child.cloneNode(true);
        clone.classList.add('sop1b-flow-block');
        blocks.push(clone);
      }
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
    if (!block.matches('.sop1b-splittable')) return null;
    const text = linearText(block);
    const boundaries = [];
    const matcher = /\s+/g;
    let match;
    while ((match = matcher.exec(text)) !== null) {
      if (match.index > 0 && match.index < text.length) boundaries.push(match.index);
    }
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

  function paginate(content) {
    pagesHolder.replaceChildren();
    hasOversizedBlock = false;
    const barcodeMark = content.querySelector('.sop1b-verification-mark');
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
        if (page.flow.children.length) {
          page = createPaper(false, barcodeMark);
          continue;
        }
        page.flow.appendChild(block);
        block.classList.add('p17-oversized-block');
        hasOversizedBlock = true;
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

  function renderPreview() {
    renderFrame = 0;
    const previewPanel = form.querySelector('[data-document-preview="sop1b"]');
    if (previewPanel?.hidden) return;
    const content = safeFragment(source.innerHTML);
    plainInputs.forEach((input) => {
      const name = input.dataset.sop1bInput;
      const value = name === 'date' ? indonesianDate(input.value) : input.value.trim();
      content.querySelectorAll(`[data-sop1b-output="${name}"]`).forEach((node) => {
        node.textContent = value || '—';
      });
    });
    const prosecutorOption = prosecutorChoice?.selectedOptions?.[0];
    if (prosecutorOption) {
      const prosecutorValues = {
        'prosecutor-name': prosecutorOption.dataset.prosecutorName || '',
        'prosecutor-rank': prosecutorOption.dataset.prosecutorRank || '',
        'prosecutor-nip': prosecutorOption.dataset.prosecutorNip || ''
      };
      Object.entries(prosecutorValues).forEach(([name, value]) => {
        content.querySelectorAll(`[data-sop1b-output="${name}"]`).forEach((node) => {
          node.textContent = value || '—';
        });
      });
    }
    editors.forEach(({ section, editor }) => {
      const target = content.querySelector(`[data-sop1b-section="${section}"]`);
      if (target) target.replaceChildren(...Array.from(safeFragment(editor.value).childNodes).map((node) => node.cloneNode(true)));
    });
    if (barcodePreviewUrl) {
      const mark = content.querySelector('[data-sop1b-barcode-mark]');
      const image = document.createElement('img');
      image.src = barcodePreviewUrl;
      image.alt = 'Barcode verifikasi SOP Form-1B';
      mark?.replaceChildren(image);
    }
    paginate(content.querySelector('.sop1b-page-content'));
  }

  function queueRender() {
    if (renderFrame) window.cancelAnimationFrame(renderFrame);
    renderFrame = window.requestAnimationFrame(renderPreview);
  }

  editorTabs.forEach((tab) => tab.addEventListener('click', () => activateDocument(tab.dataset.documentTab)));
  previewTabs.forEach((tab) => tab.addEventListener('click', () => activatePreview(tab.dataset.previewTab)));
  plainInputs.forEach((input) => {
    input.addEventListener('input', queueRender);
    input.addEventListener('change', queueRender);
    if (!canEdit) input.disabled = true;
  });
  prosecutorChoice?.addEventListener('change', queueRender);
  barcodeInput?.addEventListener('change', () => {
    if (barcodePreviewUrl) URL.revokeObjectURL(barcodePreviewUrl);
    barcodePreviewUrl = barcodeInput.files?.[0] ? URL.createObjectURL(barcodeInput.files[0]) : '';
    queueRender();
  });
  if (!canEdit && prosecutorChoice) prosecutorChoice.disabled = true;
  if (!canEdit && barcodeInput) barcodeInput.disabled = true;
  form.querySelector('[data-sop1b-print]')?.addEventListener('click', () => {
    activatePreview('sop1b');
    window.requestAnimationFrame(() => {
      renderPreview();
      if (hasOversizedBlock) {
        window.alert('Masih ada satu blok SOP Form-1B yang terlalu panjang. Pisahkan paragraf tersebut sebelum mencetak.');
        return;
      }
      window.print();
    });
  });
  window.addEventListener('resize', applyPreviewScale);
  window.addEventListener('beforeunload', () => {
    if (barcodePreviewUrl) URL.revokeObjectURL(barcodePreviewUrl);
  });
  form.addEventListener('submit', () => {
    editors.forEach(({ textarea, editor }) => { textarea.value = editor.value; });
  });
  new MutationObserver(() => {
    const theme = document.documentElement.classList.contains('dark') ? 'dark' : 'default';
    editors.forEach(({ editor }) => editor.setOptions({ theme }));
  }).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

  const sopPanel = form.querySelector('[data-document-editor="sop1b"]');
  if (sopPanel?.querySelector('.errorlist')) activateDocument('sop1b');
})();
