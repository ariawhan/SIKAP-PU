(function () {
  const form = document.querySelector('[data-p16-form]');
  const textareas = Array.from(document.querySelectorAll('[data-p16-rich-editor]'));
  const pagesHolder = document.querySelector('[data-p16-preview-pages]');
  const sourceTemplate = form?.querySelector('[data-p16-document-source]');
  if (!form || !textareas.length || !pagesHolder || !sourceTemplate || typeof window.Jodit === 'undefined') return;

  const canEdit = form.dataset.canEdit === 'true';
  const cmsSyncButton = form.querySelector('[data-p16-cms-sync]');
  const cmsModal = form.querySelector('[data-p16-cms-modal]');
  const cmsContinue = form.querySelector('[data-p16-cms-continue]');
  const cmsMessage = form.querySelector('[data-p16-cms-message]');
  const cmsContinueLabel = cmsContinue?.textContent || 'Lanjut';
  const cmsHasAccounts = cmsContinue ? !cmsContinue.disabled : false;
  let cmsBusy = false;
  const letterheadTemplate = form.querySelector('[data-p16-letterhead]');
  const numberInput = form.querySelector('[name="draft_number"]');
  const numberPreview = form.querySelector('[data-p16-number-preview]');
  const numberRegionCode = form.dataset.p16NumberRegion || '';
  const numberLetterCode = form.dataset.p16NumberCode || '';
  const dateInput = form.querySelector('[name="letter_date"]');
  const actingTypeInput = form.querySelector('[data-p16-acting-type]');
  const actingChoices = Array.from(form.querySelectorAll('[data-p16-acting-choice]'));
  const actingFields = form.querySelector('[data-p16-acting-fields]');
  const actingInputs = {
    name: form.querySelector('[data-p16-acting-input="name"]'),
    position: form.querySelector('[data-p16-acting-input="position"]'),
    nip: form.querySelector('[data-p16-acting-input="nip"]'),
  };
  const barcodeInput = form.querySelector('[data-p16-barcode-input]');
  const barcodeDropzone = form.querySelector('[data-p16-barcode-dropzone]');
  const barcodePreview = form.querySelector('[data-p16-barcode-preview]');
  const barcodeTitle = form.querySelector('[data-p16-barcode-title]');
  const barcodeStatus = form.querySelector('[data-p16-barcode-status]');
  const prosecutorPicker = form.querySelector('[data-p16-prosecutor-picker]');
  const administrativeStaffPicker = form.querySelector('[data-p16-administrative-staff-picker]');
  const tabs = Array.from(form.querySelectorAll('[data-p16-tab]'));
  const overflowWarning = form.querySelector('[data-p16-overflow-warning]');
  const overflowPagesLabel = form.querySelector('[data-p16-overflow-pages]');
  let activeGroup = 'naskah';
  let renderFrame = 0;
  let barcodePreviewUrl = '';
  let sipedeNumber = form.dataset.p16SipedeNumber || '';

  function closeCmsModal() {
    if (!cmsModal) return;
    cmsModal.hidden = true;
    document.body.classList.remove('p16-sipede-open');
  }

  cmsSyncButton?.addEventListener('click', () => {
    if (!cmsModal) return;
    if (cmsMessage) {
      cmsMessage.hidden = true;
      cmsMessage.classList.remove('success');
    }
    if (cmsContinue && !cmsBusy) {
      cmsContinue.disabled = !cmsHasAccounts;
      cmsContinue.textContent = cmsContinueLabel;
    }
    cmsModal.hidden = false;
    document.body.classList.add('p16-sipede-open');
    cmsModal.querySelector('input[name="cms_account_user"]:checked')?.focus();
  });

  cmsModal?.querySelectorAll('[data-p16-cms-close]').forEach((button) => {
    button.addEventListener('click', closeCmsModal);
  });

  cmsContinue?.addEventListener('click', async () => {
    const selected = cmsModal?.querySelector('input[name="cms_account_user"]:checked')?.value
      || cmsModal?.dataset.defaultAccount || '';
    if (!selected) {
      if (cmsMessage) {
        cmsMessage.textContent = 'Pilih akun CMS yang akan digunakan sebelum melanjutkan.';
        cmsMessage.hidden = false;
      }
      return;
    }
    cmsBusy = true;
    cmsContinue.disabled = true;
    cmsContinue.textContent = 'Membuka CMS…';
    if (cmsMessage) {
      cmsMessage.hidden = false;
      cmsMessage.classList.remove('success');
      cmsMessage.textContent = 'Memeriksa sesi dan membuka halaman Tambah SPDP CMS…';
    }
    const body = new FormData();
    body.set('account_user_id', selected);
    try {
      const response = await fetch(cmsModal.dataset.syncUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]')?.value || '' },
        body,
      });
      const result = await response.json().catch(() => ({ message: 'Respons CMS tidak dapat dibaca.' }));
      if (!response.ok) throw new Error(result.message || 'Halaman Tambah SPDP CMS belum dapat dibuka.');
      cmsSyncButton.dataset.cmsAccount = selected;
      if (cmsMessage) {
        const sessionInfo = result.session_reused ? 'Sesi aktif digunakan.' : 'Login baru berhasil.';
        const formInfo = result.form_found
          ? `Form Tambah SPDP ditemukan (${result.field_count} field).`
          : 'Halaman terbuka, tetapi form Tambah SPDP belum ditemukan.';
        cmsMessage.textContent = `${result.message} HTTP ${result.http_status}. ${sessionInfo} ${formInfo}`;
        cmsMessage.classList.add('success');
      }
      cmsContinue.textContent = 'Berhasil';
      window.dispatchEvent(new CustomEvent('p16-cms-sync-confirmed', {
        detail: { accountUserId: selected, response: result },
      }));
    } catch (error) {
      if (cmsMessage) {
        cmsMessage.textContent = error.message;
        cmsMessage.classList.remove('success');
      }
      cmsContinue.disabled = false;
      cmsContinue.textContent = 'Coba Lagi';
    } finally {
      cmsBusy = false;
    }
  });

  function normalizeInstructionMarkup(html) {
    const parsed = new DOMParser().parseFromString(html || '', 'text/html');
    Array.from(parsed.body.querySelectorAll('ol')).forEach((list) => {
      let next = list.nextElementSibling;
      while (next?.tagName === 'OL') {
        const following = next.nextElementSibling;
        Array.from(next.children).forEach((item) => list.appendChild(item));
        next.remove();
        next = following;
      }
    });
    return parsed.body.innerHTML;
  }

  const editorRecords = textareas.map((textarea) => {
    const section = textarea.dataset.p16RichEditor;
    if (section === 'instruction') textarea.value = normalizeInstructionMarkup(textarea.value);
    const isLargeSection = [
      'legal-basis', 'instruction', 'administration-legal-basis',
      'administration-consideration', 'administration-instruction'
    ].includes(section);
    const isOffenseSummary = section === 'offense-summary';
    const editor = window.Jodit.make(textarea, {
      height: isLargeSection ? 310 : (isOffenseSummary ? 200 : 230),
      minHeight: isLargeSection ? 250 : (isOffenseSummary ? 170 : 190),
      maxHeight: 520,
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
      indentMargin: 30,
      buttons: [
        'undo', 'redo', '|', 'fontsize', '|', 'bold', 'italic', 'underline', '|',
        'ol', 'ul', '|', 'outdent', 'indent', '|',
        'left', 'center', 'right', 'justify', '|', 'eraser', 'source'
      ]
    });
    editor.editor.style.fontFamily = 'Arial, sans-serif';
    editor.editor.style.fontSize = '10pt';
    editor.editor.style.lineHeight = '1.15';
    if ([
      'consideration', 'legal-basis', 'offense-summary', 'recipient', 'instruction',
      'administration-legal-basis', 'administration-consideration',
      'administration-instruction', 'administration-copies'
    ].includes(section)) {
      editor.editor.style.textAlign = 'justify';
    }
    return { textarea, section, editor };
  });

  function safePreviewFragment(html) {
    const parsed = new DOMParser().parseFromString(html || '', 'text/html');
    parsed.querySelectorAll('script,style,iframe,object,embed,form,input,button,link,meta,base,video,audio,source,track,svg,math').forEach((node) => node.remove());
    parsed.body.querySelectorAll('*').forEach((node) => {
      Array.from(node.attributes).forEach((attribute) => {
        const name = attribute.name.toLowerCase();
        const value = attribute.value.trim().toLowerCase();
        if (name.startsWith('on') || name === 'srcdoc') node.removeAttribute(attribute.name);
        if ((name === 'href' || name === 'src') && (value.startsWith('javascript:') || value.startsWith('vbscript:'))) node.removeAttribute(attribute.name);
        if (['srcset', 'poster', 'formaction', 'xlink:href'].includes(name)) node.removeAttribute(attribute.name);
        if (name === 'style' && /(url\s*\(|expression\s*\(|@import)/i.test(attribute.value)) node.removeAttribute(attribute.name);
        if (name === 'src' && !value.startsWith('data:image/')) {
          try {
            if (new URL(attribute.value, window.location.origin).origin !== window.location.origin) node.removeAttribute(attribute.name);
          } catch {
            node.removeAttribute(attribute.name);
          }
        }
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

  function completeP16Number() {
    if (sipedeNumber) return sipedeNumber;
    const sequence = numberInput?.value.trim() || '';
    const dateParts = (dateInput?.value || '').split('-');
    if (!/^\d+[A-Z]?$/i.test(sequence) || dateParts.length !== 3 || !numberRegionCode || !numberLetterCode) return '';
    return `PRINT-${sequence}/${numberRegionCode}/${numberLetterCode}/${dateParts[1]}/${dateParts[0]}`;
  }

  function applyProsecutorTeam(root) {
    const teamBody = root.querySelector('[data-p16-team-body]');
    const select = prosecutorPicker?.querySelector('[data-p16-prosecutor-select]');
    const inputs = prosecutorPicker?.querySelector('[data-p16-prosecutor-inputs]');
    if (!teamBody || !select || !inputs) return;
    const selectedValues = Array.from(inputs.querySelectorAll('input[name="prosecutors"]')).map((input) => input.value);
    teamBody.replaceChildren();
    if (!selectedValues.length) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 3;
      cell.textContent = 'Jaksa belum ditunjuk.';
      row.appendChild(cell);
      teamBody.appendChild(row);
      return;
    }
    selectedValues.forEach((value, index) => {
      const option = Array.from(select.options).find((entry) => entry.value === value);
      if (!option) return;
      const row = document.createElement('tr');
      const numberCell = document.createElement('td');
      numberCell.textContent = String(index + 1);
      const identityCell = document.createElement('td');
      const name = document.createElement('strong');
      name.textContent = (option.dataset.name || option.textContent.trim()).toUpperCase();
      const identifier = option.dataset.nip
        ? `NIP. ${option.dataset.nip}`
        : (option.dataset.nrp ? `NRP. ${option.dataset.nrp}` : 'NIP/NRP belum diisi');
      identityCell.append(
        name,
        document.createElement('br'),
        document.createTextNode(option.dataset.rank || 'Pangkat belum diisi'),
        document.createElement('br'),
        document.createTextNode(identifier)
      );
      const positionCell = document.createElement('td');
      positionCell.textContent = 'Selaku Penuntut Umum';
      row.append(numberCell, identityCell, positionCell);
      teamBody.appendChild(row);
    });
  }

  function applyAdministrativeStaff(root) {
    const staffList = root.querySelector('[data-p16-admin-staff]');
    const select = administrativeStaffPicker?.querySelector('[data-p16-administrative-staff-select]');
    const inputs = administrativeStaffPicker?.querySelector('[data-p16-administrative-staff-inputs]');
    if (!staffList || !select || !inputs) return;
    const selectedValues = Array.from(inputs.querySelectorAll('input[name="administrative_staff"]'))
      .map((input) => input.value);
    staffList.replaceChildren();
    staffList.classList.toggle('single', selectedValues.length <= 1);
    if (!selectedValues.length) {
      const item = document.createElement('li');
      item.textContent = 'Petugas administrasi belum ditunjuk.';
      staffList.appendChild(item);
      return;
    }
    const appendLine = (item, label, value, strong = false) => {
      const line = document.createElement('p');
      const labelNode = document.createElement('span');
      labelNode.textContent = label;
      const colon = document.createElement('span');
      colon.textContent = ':';
      const valueNode = document.createElement(strong ? 'strong' : 'span');
      valueNode.textContent = value || '---';
      line.append(labelNode, colon, valueNode);
      item.appendChild(line);
    };
    selectedValues.forEach((value) => {
      const option = Array.from(select.options).find((entry) => entry.value === value);
      if (!option) return;
      const item = document.createElement('li');
      appendLine(item, 'Nama', (option.dataset.name || option.textContent.trim()).toUpperCase(), true);
      appendLine(item, 'Pangkat / NIP', `${option.dataset.rank || '---'} / ${option.dataset.nip || '---'}`);
      appendLine(item, 'Jabatan', option.dataset.roles || 'Petugas Administrasi');
      staffList.appendChild(item);
    });
  }

  function applySuspectData(root) {
    const outputs = Array.from(root.querySelectorAll('[data-p16-suspect-output]'));
    const output = outputs[0];
    const suspectList = form.querySelector('[data-suspect-list]');
    if (!output || !suspectList) return;
    const syncOutputs = () => {
      outputs.slice(1).forEach((target) => {
        target.replaceChildren(...Array.from(output.childNodes).map((node) => node.cloneNode(true)));
      });
    };
    const fieldValue = (card, suffix) => card.querySelector(`[name$="-${suffix}"]`)?.value.trim() || '';
    const fieldLabel = (card, suffix) => {
      const field = card.querySelector(`[name$="-${suffix}"]`);
      return field?.value ? field.selectedOptions?.[0]?.textContent.trim() || field.value : '';
    };
    const cards = Array.from(suspectList.querySelectorAll('[data-suspect-form]')).filter((card) => {
      const deleted = card.querySelector('input[name$="-DELETE"]')?.checked;
      const persisted = Boolean(fieldValue(card, 'id'));
      return !card.hidden && !deleted && (persisted || card.dataset.committed === '1') && fieldValue(card, 'name');
    });
    output.replaceChildren();
    const appendLine = (block, label, value, strongLabel = false, extraClass = '', numberLabel = '') => {
      const line = document.createElement('p');
      if (extraClass) line.className = extraClass;
      const numberNode = document.createElement('span');
      numberNode.textContent = numberLabel;
      const labelNode = strongLabel ? document.createElement('strong') : document.createElement('span');
      label.split('\n').forEach((part, partIndex) => {
        if (partIndex) labelNode.appendChild(document.createElement('br'));
        labelNode.appendChild(document.createTextNode(part));
      });
      const colon = document.createElement('span');
      colon.textContent = ':';
      const content = document.createElement('span');
      content.textContent = value || '---';
      line.append(numberNode, labelNode, colon, content);
      block.appendChild(line);
    };
    const appendEmptySuspectBlock = () => {
      const block = document.createElement('div');
      block.className = 'p16-suspect-block';
      appendLine(block, 'Nama Lengkap', '---', true);
      appendLine(block, 'Nomor Identitas', '---');
      appendLine(block, 'Tempat lahir', '---');
      appendLine(block, 'Umur/tanggal lahir', '---');
      appendLine(block, 'Jenis Kelamin', '---');
      appendLine(block, 'Kebangsaan/\nKewarganegaraan', '---', false, 'p16-nationality-line');
      appendLine(block, 'Tempat Tinggal', '---');
      appendLine(block, 'A g a m a', '---');
      appendLine(block, 'Pekerjaan', '---');
      appendLine(block, 'Pendidikan', '---');
      appendLine(block, 'Lain-lain', '---');
      output.appendChild(block);
    };
    if (!cards.length) {
      appendEmptySuspectBlock();
      syncOutputs();
      return;
    }

    cards.forEach((card, index) => {
      const block = document.createElement('div');
      block.className = `p16-suspect-block${index ? ' p16-additional-suspect' : ''}`;
      const frontTitle = fieldValue(card, 'front_title');
      const name = fieldValue(card, 'name');
      const backTitle = fieldValue(card, 'back_title');
      const fullName = `${frontTitle ? `${frontTitle} ` : ''}${name}${backTitle ? `, ${backTitle}` : ''}`.trim();
      const age = fieldValue(card, 'age');
      const birthDate = fieldValue(card, 'birth_date');
      const ageAndBirth = [age ? `${age} Tahun` : '', birthDate ? indonesianDate(birthDate) : ''].filter(Boolean).join(' / ');
      appendLine(block, 'Nama Lengkap', fullName, true, 'p16-suspect-name-line', cards.length > 1 ? `${index + 1}.` : '');
      appendLine(block, 'Nomor Identitas', fieldValue(card, 'identity_number'));
      appendLine(block, 'Tempat lahir', fieldValue(card, 'birth_place'));
      appendLine(block, 'Umur/tanggal lahir', ageAndBirth);
      appendLine(block, 'Jenis Kelamin', fieldLabel(card, 'gender'));
      appendLine(block, 'Kebangsaan/\nKewarganegaraan', fieldValue(card, 'nationality'), false, 'p16-nationality-line');
      appendLine(block, 'Tempat Tinggal', fieldValue(card, 'address'));
      appendLine(block, 'A g a m a', fieldLabel(card, 'religion'));
      appendLine(block, 'Pekerjaan', fieldLabel(card, 'occupation'));
      appendLine(block, 'Pendidikan', fieldLabel(card, 'education'));
      appendLine(block, 'Lain-lain', '---');
      output.appendChild(block);
    });
    syncOutputs();
  }

  function applyStructuredValues(root) {
    const completeNumber = completeP16Number();
    if (numberPreview) numberPreview.textContent = completeNumber || 'Lengkapi nomor urut dan konfigurasi nomor surat';
    root.querySelectorAll('[data-p16-output="number"]').forEach((node) => {
      node.textContent = completeNumber || '—';
    });
    root.querySelectorAll('[data-p16-output="date"]').forEach((node) => {
      node.textContent = indonesianDate(dateInput?.value);
    });
    const actingPrefix = actingTypeInput?.value === 'plt'
      ? 'Plt. '
      : (actingTypeInput?.value === 'plh' ? 'Plh. ' : '');
    root.querySelectorAll('[data-p16-signature-position]').forEach((node) => {
      const baseTitle = node.textContent.replace(/^(Plt\.|Plh\.)\s*/i, '').trim();
      node.textContent = `${actingPrefix}${baseTitle}`;
    });
    if (actingPrefix) {
      root.querySelectorAll('[data-p16-signer-name]').forEach((node) => {
        node.textContent = actingInputs.name?.value.trim() || 'Nama pejabat belum diisi';
      });
      root.querySelectorAll('[data-p16-signer-identity]').forEach((node) => {
        const position = actingInputs.position?.value.trim() || 'Jabatan belum diisi';
        const nip = actingInputs.nip?.value.trim() || 'belum diisi';
        node.textContent = `${position} NIP.${nip}`;
      });
    }
    if (barcodePreviewUrl) {
      root.querySelectorAll('[data-p16-barcode-mark]').forEach((mark) => {
        mark.classList.add('has-barcode');
        mark.replaceChildren();
        const image = document.createElement('img');
        image.src = barcodePreviewUrl;
        image.alt = 'Barcode verifikasi SIKAP-PU';
        mark.appendChild(image);
      });
    }
    applyProsecutorTeam(root);
    applyAdministrativeStaff(root);
    applySuspectData(root);
  }

  function injectEditableSections(root) {
    editorRecords.forEach(({ section, editor }) => {
      root.querySelectorAll(`[data-p16-section="${section}"]`).forEach((target) => {
        const safeSection = safePreviewFragment(editor.value);
        target.replaceChildren(...Array.from(safeSection.childNodes).map((node) => node.cloneNode(true)));
      });
    });
  }

  function applyPreviewScale() {
    pagesHolder.querySelectorAll('.p16-paper-frame.active').forEach((frame) => {
      const paper = frame.querySelector('.p16-paper');
      if (!paper) return;
      const naturalWidth = paper.offsetWidth;
      const naturalHeight = paper.offsetHeight;
      if (!naturalWidth || !naturalHeight) return;
      const scale = Math.min(1, frame.clientWidth / naturalWidth);
      paper.style.transform = scale < 1 ? `scale(${scale})` : 'none';
      frame.style.height = `${Math.round(naturalHeight * scale)}px`;
    });
  }

  function pageSafeBottom(paper, extraReserve = 0) {
    const paperBox = paper.getBoundingClientRect();
    const paperStyle = window.getComputedStyle(paper);
    const paddingBottom = Number.parseFloat(paperStyle.paddingBottom) || 0;
    const naturalWidth = paper.offsetWidth || paperBox.width || 1;
    const renderedScale = paperBox.width / naturalWidth;
    return paperBox.bottom - (paddingBottom * renderedScale) - extraReserve;
  }

  function deepestFlowBottom(paper) {
    let bottom = 0;
    const flowRoots = Array.from(paper.children).filter((child) => {
      if (child.matches('.p16-verification-mark')) return false;
      const style = window.getComputedStyle(child);
      return style.position !== 'absolute' && style.display !== 'none' && style.visibility !== 'hidden';
    });
    flowRoots.forEach((root) => {
      [root, ...Array.from(root.querySelectorAll('*'))].forEach((node) => {
        if (node.closest('.p16-verification-mark')) return;
        const style = window.getComputedStyle(node);
        if (style.position === 'absolute' || style.display === 'none' || style.visibility === 'hidden') return;
        const rect = node.getBoundingClientRect();
        if (rect.height > 0) bottom = Math.max(bottom, rect.bottom);
      });
    });
    return bottom;
  }

  function paperOverflows(paper, extraReserve = 0) {
    if (paper.scrollHeight > paper.clientHeight + 2) return true;
    return deepestFlowBottom(paper) > pageSafeBottom(paper, extraReserve) + 1;
  }

  function flowContentForPaper(paper) {
    return paper.querySelector('.p16-page-content');
  }

  function movableChildren(content) {
    return Array.from(content?.children || []).filter((node) => !node.matches('.p16-verification-mark'));
  }

  function cloneTableForContinuation(table) {
    const clone = table.cloneNode(false);
    Array.from(table.children).forEach((child) => {
      if (child.tagName !== 'TBODY') clone.appendChild(child.cloneNode(true));
    });
    const sourceBody = table.tBodies[0];
    const body = sourceBody ? sourceBody.cloneNode(false) : document.createElement('tbody');
    clone.appendChild(body);
    return { table: clone, body };
  }

  function splitListTail(list) {
    const items = Array.from(list.children).filter((child) => child.tagName === 'LI');
    if (items.length <= 1) return null;
    const continuation = list.cloneNode(false);
    if (list.tagName === 'OL') {
      const start = Number.parseInt(list.getAttribute('start') || '1', 10);
      continuation.setAttribute('start', String(start + items.length - 1));
    }
    continuation.appendChild(items[items.length - 1]);
    return continuation;
  }

  function splitTableTail(table) {
    const sourceBody = table.tBodies[0];
    const rows = Array.from(sourceBody?.rows || []);
    if (!rows.length) return null;
    const sourceRow = rows[rows.length - 1];
    const sourceCells = Array.from(sourceRow.cells);
    const sourceValueCell = sourceCells[sourceCells.length - 1];
    if (!sourceValueCell) return null;
    const valueChildren = Array.from(sourceValueCell.children);
    const valueTail = valueChildren.length
      ? extractTailFragment(valueChildren[valueChildren.length - 1])
      : null;
    if (valueTail) {
      const continuation = cloneTableForContinuation(table);
      const continuedRow = sourceRow.cloneNode(false);
      sourceCells.forEach((cell, index) => {
        const continuedCell = cell.cloneNode(false);
        if (index === sourceCells.length - 1) {
          continuedCell.appendChild(valueTail);
        } else {
          // Kolom label dan titik dua tetap mengambil ruang yang sama, tetapi
          // tidak diulang pada halaman lanjutan.
          continuedCell.innerHTML = '&nbsp;';
        }
        continuedRow.appendChild(continuedCell);
      });
      continuation.body.appendChild(continuedRow);
      return continuation.table;
    }

    if (rows.length > 1) {
      const continuation = cloneTableForContinuation(table);
      continuation.body.appendChild(sourceRow);
      return continuation.table;
    }
    return null;
  }

  function splitContainerTail(container) {
    const children = Array.from(container.children).filter((child) => !child.matches('.p16-verification-mark'));
    if (!children.length) return null;
    const lastChild = children[children.length - 1];
    const nestedTail = extractTailFragment(lastChild);
    const continuation = container.cloneNode(false);
    if (nestedTail) {
      continuation.appendChild(nestedTail);
      return continuation;
    }
    if (children.length <= 1) return null;
    continuation.appendChild(lastChild);
    return continuation;
  }

  function extractTailFragment(node) {
    if (!(node instanceof HTMLElement)) return null;
    if (node.matches('.p16-suspect-block,.p16-signature-block,.p16-document-title,.p16-command-title')) return null;
    if (node.matches('ol,ul')) return splitListTail(node);
    if (node.matches('table')) return splitTableTail(node);
    if (node.matches('[data-p16-suspect-output],[data-p16-section],.p16-continuation,.p16-copies')) {
      return splitContainerTail(node);
    }
    return null;
  }

  function createFlowPageAfter(frame, group) {
    const paper = document.createElement('article');
    // Harus terlihat selama fase pengukuran. showGroup() akan menetapkan ulang
    // status aktif sesuai tab setelah pagination selesai.
    paper.className = 'p16-paper active';
    paper.dataset.p16Group = group || 'naskah';
    const content = document.createElement('section');
    content.className = 'p16-page-content p16-auto-flow-page';
    paper.appendChild(content);
    const barcodeMark = pagesHolder.querySelector('.p16-paper .p16-verification-mark')?.cloneNode(true);
    if (barcodeMark) paper.appendChild(barcodeMark);
    const newFrame = document.createElement('div');
    newFrame.className = 'p16-paper-frame active';
    newFrame.appendChild(paper);
    frame.after(newFrame);
    return newFrame;
  }

  function nextFlowFrame(frame, group) {
    let cursor = frame.nextElementSibling;
    while (cursor) {
      const paper = cursor.querySelector('.p16-paper');
      if (!paper) {
        cursor = cursor.nextElementSibling;
        continue;
      }
      if (paper.dataset.p16Group !== group) return null;
      return cursor;
    }
    return null;
  }

  function renumberPages() {
    pagesHolder.querySelectorAll('.p16-paper').forEach((paper, index) => {
      paper.dataset.pageNumber = String(index + 1);
    });
  }

  function removeEmptyContinuationPages() {
    pagesHolder.querySelectorAll('.p16-paper-frame').forEach((frame) => {
      const paper = frame.querySelector('.p16-paper');
      const content = paper && flowContentForPaper(paper);
      if (!paper || !content || paper.dataset.p16Group === 'lampiran') return;
      if (paper.querySelector('.p16-letterhead')) return;
      if (!movableChildren(content).length) frame.remove();
    });
  }

  function paginateOverflowingPages() {
    let safety = 0;
    let frame = pagesHolder.querySelector('.p16-paper-frame');
    while (frame && safety < 200) {
      safety += 1;
      const paper = frame.querySelector('.p16-paper');
      if (!paper || paper.dataset.p16Group === 'lampiran') {
        frame = frame.nextElementSibling;
        continue;
      }
      const content = flowContentForPaper(paper);
      if (!content || !paperOverflows(paper)) {
        frame = frame.nextElementSibling;
        continue;
      }
      const children = movableChildren(content);
      if (!children.length) {
        frame = frame.nextElementSibling;
        continue;
      }
      let targetFrame = nextFlowFrame(frame, paper.dataset.p16Group);
      if (!targetFrame) targetFrame = createFlowPageAfter(frame, paper.dataset.p16Group);
      const targetContent = flowContentForPaper(targetFrame.querySelector('.p16-paper'));
      if (!targetContent) {
        frame = frame.nextElementSibling;
        continue;
      }
      const lastChild = children[children.length - 1];
      const fragment = extractTailFragment(lastChild);
      if (fragment) {
        targetContent.prepend(fragment);
        continue;
      }
      // Jika satu blok utuh sudah berada di halaman lanjutan tetapi masih
      // lebih tinggi daripada area cetak, jangan membuat halaman tanpa batas.
      if (children.length === 1 && content.classList.contains('p16-auto-flow-page')) {
        frame = frame.nextElementSibling;
        continue;
      }
      targetContent.prepend(lastChild);
    }
    removeEmptyContinuationPages();
    renumberPages();
  }

  function showGroup(group) {
    const pages = Array.from(pagesHolder.querySelectorAll('.p16-paper'));
    const availableGroups = [...new Set(pages.map((page) => page.dataset.p16Group))];
    activeGroup = availableGroups.includes(group) ? group : (availableGroups[0] || 'naskah');
    pages.forEach((page) => {
      const isActive = page.dataset.p16Group === activeGroup;
      page.classList.toggle('active', isActive);
      page.closest('.p16-paper-frame')?.classList.toggle('active', isActive);
    });
    tabs.forEach((tab) => {
      tab.classList.toggle('active', tab.dataset.p16Tab === activeGroup);
      tab.hidden = !availableGroups.includes(tab.dataset.p16Tab);
    });
    applyPreviewScale();
  }

  function overflowingPageIndexes() {
    return Array.from(pagesHolder.querySelectorAll('.p16-paper'))
      .map((page, index) => {
        const probe = page.cloneNode(true);
        probe.classList.remove('active');
        probe.classList.add('p16-overflow-probe');
        document.body.appendChild(probe);
        const overflows = paperOverflows(probe);
        probe.remove();
        return overflows ? index : -1;
      })
      .filter((index) => index >= 0);
  }

  function updateOverflowWarning() {
    const overflowing = overflowingPageIndexes();
    if (overflowWarning) overflowWarning.hidden = overflowing.length === 0;
    if (overflowPagesLabel) overflowPagesLabel.textContent = overflowing.map((index) => `halaman ${index + 1}`).join(' dan ');
    return overflowing;
  }

  function renderPreview() {
    const safeBody = safePreviewFragment(sourceTemplate.innerHTML);
    injectEditableSections(safeBody);
    let sections = Array.from(safeBody.children).filter((node) => node.matches('.p16-page-content,[data-p16-page]'));
    if (!sections.length) {
      const section = document.createElement('section');
      section.className = 'p16-page-content';
      while (safeBody.firstChild) section.appendChild(safeBody.firstChild);
      sections = [section];
    }
    const groupOrder = { naskah: 0, lampiran: 1, administrasi: 2 };
    sections.sort((left, right) => {
      const leftGroup = left.dataset.p16Group || 'naskah';
      const rightGroup = right.dataset.p16Group || 'naskah';
      const groupDifference = (groupOrder[leftGroup] ?? 99) - (groupOrder[rightGroup] ?? 99);
      if (groupDifference) return groupDifference;
      return Number.parseInt(left.dataset.p16Page || '0', 10) - Number.parseInt(right.dataset.p16Page || '0', 10);
    });
    pagesHolder.replaceChildren();
    sections.forEach((section, index) => {
      const paper = document.createElement('article');
      // CSS menyembunyikan kertas yang belum aktif. Aktifkan sementara agar
      // browser dapat mengukur tinggi riil sebelum konten dibagi per halaman.
      paper.className = 'p16-paper active';
      paper.dataset.pageNumber = String(index + 1);
      paper.dataset.p16Group = section.dataset.p16Group || (index < 2 ? 'naskah' : 'lampiran');
      if ((index === 0 || section.hasAttribute('data-p16-letterhead')) && letterheadTemplate?.content) {
        const letterhead = letterheadTemplate.content.cloneNode(true);
        paper.appendChild(letterhead);
      }
      paper.appendChild(section.cloneNode(true));
      applyStructuredValues(paper);
      const frame = document.createElement('div');
      frame.className = 'p16-paper-frame active';
      frame.appendChild(paper);
      pagesHolder.appendChild(frame);
    });
    paginateOverflowingPages();
    showGroup(activeGroup);
    updateOverflowWarning();
  }

  function schedulePreview() {
    cancelAnimationFrame(renderFrame);
    renderFrame = requestAnimationFrame(renderPreview);
  }

  function updateBarcodeWidget(file) {
    if (barcodePreviewUrl) URL.revokeObjectURL(barcodePreviewUrl);
    barcodePreviewUrl = file ? URL.createObjectURL(file) : '';
    if (file && barcodePreview) {
      barcodePreview.innerHTML = '';
      const image = document.createElement('img');
      image.src = barcodePreviewUrl;
      image.alt = 'Preview barcode P-16';
      barcodePreview.appendChild(image);
    }
    if (file && barcodeTitle) barcodeTitle.textContent = 'Barcode siap disimpan';
    if (file && barcodeStatus) barcodeStatus.textContent = `${file.name} - ${Math.max(1, Math.round(file.size / 1024))} KB`;
    schedulePreview();
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

  function setupProsecutorPicker() {
    if (!prosecutorPicker) return;
    const select = prosecutorPicker.querySelector('[data-p16-prosecutor-select]');
    const addButton = prosecutorPicker.querySelector('[data-p16-prosecutor-add]');
    const list = prosecutorPicker.querySelector('[data-p16-prosecutor-list]');
    const inputs = prosecutorPicker.querySelector('[data-p16-prosecutor-inputs]');
    if (!select || !list || !inputs) return;

    const hiddenInputs = () => Array.from(inputs.querySelectorAll('input[name="prosecutors"]'));
    const syncAddButton = () => { if (addButton) addButton.disabled = !select.value; };
    const renderEmpty = () => {
      list.querySelector('.p16-prosecutor-empty')?.remove();
      if (list.querySelector('.p16-prosecutor-selected-item')) return;
      const empty = document.createElement('div');
      empty.className = 'p16-prosecutor-empty';
      empty.textContent = list.dataset.empty || 'Belum ada pilihan.';
      list.appendChild(empty);
    };
    const appendItem = (value) => {
      if (list.querySelector(`[data-value="${CSS.escape(value)}"]`)) return;
      const option = Array.from(select.options).find((entry) => entry.value === value);
      if (!option) return;
      option.disabled = true;
      list.querySelector('.p16-prosecutor-empty')?.remove();

      const item = document.createElement('div');
      item.className = 'p16-prosecutor-selected-item';
      item.dataset.value = value;
      const avatar = document.createElement('span');
      avatar.className = 'p16-prosecutor-selected-avatar';
      avatar.textContent = option.dataset.initials || option.textContent.trim().slice(0, 2).toUpperCase();
      const copy = document.createElement('span');
      copy.className = 'p16-prosecutor-selected-text';
      const name = document.createElement('b');
      name.textContent = option.textContent.trim();
      const subtitle = document.createElement('small');
      subtitle.textContent = option.dataset.subtitle || 'Jaksa Penuntut Umum';
      copy.append(name, subtitle);
      item.append(avatar, copy);
      const status = document.createElement('span');
      const isAppointed = option.dataset.status === 'appointed';
      status.className = `p16-prosecutor-status ${isAppointed ? 'appointed' : 'additional'}`;
      status.textContent = isAppointed ? 'Ditunjuk' : 'Tambahan';
      item.appendChild(status);
      if (canEdit) {
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.dataset.p16ProsecutorRemove = '';
        remove.setAttribute('aria-label', `Hapus ${name.textContent}`);
        remove.textContent = '\u00d7';
        item.appendChild(remove);
      }
      list.appendChild(item);
    };
    const addSelected = () => {
      const value = select.value;
      if (!value || hiddenInputs().some((input) => input.value === value)) return;
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'prosecutors';
      input.value = value;
      inputs.appendChild(input);
      appendItem(value);
      select.value = '';
      syncAddButton();
      schedulePreview();
    };

    hiddenInputs().forEach((input) => appendItem(input.value));
    renderEmpty();
    syncAddButton();
    addButton?.addEventListener('click', addSelected);
    select.addEventListener('change', syncAddButton);
    select.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      addSelected();
    });
    list.addEventListener('click', (event) => {
      const remove = event.target.closest('[data-p16-prosecutor-remove]');
      if (!remove) return;
      const item = remove.closest('.p16-prosecutor-selected-item');
      const value = item?.dataset.value;
      hiddenInputs().find((input) => input.value === value)?.remove();
      const option = Array.from(select.options).find((entry) => entry.value === value);
      if (option) option.disabled = false;
      item?.remove();
      renderEmpty();
      syncAddButton();
      schedulePreview();
    });
  }

  function setupAdministrativeStaffPicker() {
    if (!administrativeStaffPicker) return;
    const select = administrativeStaffPicker.querySelector('[data-p16-administrative-staff-select]');
    const addButton = administrativeStaffPicker.querySelector('[data-p16-administrative-staff-add]');
    const list = administrativeStaffPicker.querySelector('[data-p16-administrative-staff-list]');
    const inputs = administrativeStaffPicker.querySelector('[data-p16-administrative-staff-inputs]');
    if (!select || !list || !inputs) return;

    const hiddenInputs = () => Array.from(inputs.querySelectorAll('input[name="administrative_staff"]'));
    const syncAddButton = () => { if (addButton) addButton.disabled = !select.value; };
    const renderEmpty = () => {
      list.querySelector('.p16-prosecutor-empty')?.remove();
      if (list.querySelector('.p16-prosecutor-selected-item')) return;
      const empty = document.createElement('div');
      empty.className = 'p16-prosecutor-empty';
      empty.textContent = list.dataset.empty || 'Belum ada petugas administrasi.';
      list.appendChild(empty);
    };
    const appendItem = (value) => {
      if (list.querySelector(`[data-value="${CSS.escape(value)}"]`)) return;
      const option = Array.from(select.options).find((entry) => entry.value === value);
      if (!option) return;
      option.disabled = true;
      list.querySelector('.p16-prosecutor-empty')?.remove();

      const item = document.createElement('div');
      item.className = 'p16-prosecutor-selected-item';
      item.dataset.value = value;
      const avatar = document.createElement('span');
      avatar.className = 'p16-prosecutor-selected-avatar';
      avatar.textContent = option.dataset.initials || option.textContent.trim().slice(0, 2).toUpperCase();
      const copy = document.createElement('span');
      copy.className = 'p16-prosecutor-selected-text';
      const name = document.createElement('b');
      name.textContent = option.dataset.name || option.textContent.trim();
      const subtitle = document.createElement('small');
      subtitle.textContent = `${option.dataset.rank || 'Pangkat belum diisi'}${option.dataset.nip ? ` · NIP ${option.dataset.nip}` : ''}`;
      copy.append(name, subtitle);
      const status = document.createElement('span');
      status.className = 'p16-prosecutor-status appointed';
      status.textContent = 'Ditunjuk';
      item.append(avatar, copy, status);
      if (canEdit) {
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.dataset.p16AdministrativeStaffRemove = '';
        remove.setAttribute('aria-label', `Hapus ${name.textContent}`);
        remove.textContent = '\u00d7';
        item.appendChild(remove);
      }
      list.appendChild(item);
    };
    const addSelected = () => {
      const value = select.value;
      if (!value || hiddenInputs().some((input) => input.value === value)) return;
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'administrative_staff';
      input.value = value;
      inputs.appendChild(input);
      appendItem(value);
      select.value = '';
      syncAddButton();
      schedulePreview();
    };

    hiddenInputs().forEach((input) => appendItem(input.value));
    renderEmpty();
    syncAddButton();
    addButton?.addEventListener('click', addSelected);
    select.addEventListener('change', syncAddButton);
    select.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      addSelected();
    });
    list.addEventListener('click', (event) => {
      const remove = event.target.closest('[data-p16-administrative-staff-remove]');
      if (!remove) return;
      const item = remove.closest('.p16-prosecutor-selected-item');
      const value = item?.dataset.value;
      hiddenInputs().find((input) => input.value === value)?.remove();
      const option = Array.from(select.options).find((entry) => entry.value === value);
      if (option) option.disabled = false;
      item?.remove();
      renderEmpty();
      syncAddButton();
      schedulePreview();
    });
  }

  tabs.forEach((tab) => tab.addEventListener('click', () => showGroup(tab.dataset.p16Tab)));
  numberInput?.addEventListener('input', () => {
    const cleanedNumber = numberInput.value.toUpperCase().replace(/[^0-9A-Z]/g, '');
    numberInput.value = cleanedNumber.match(/^\d+[A-Z]?/)?.[0] || cleanedNumber.replace(/\D/g, '');
    const sipedeSequence = sipedeNumber.match(/^PRINT-(\d+[A-Z]?)\//i)?.[1] || '';
    if (numberInput.value !== sipedeSequence) sipedeNumber = '';
    schedulePreview();
  });
  dateInput?.addEventListener('input', schedulePreview);
  function syncActingFields() {
    const enabled = actingTypeInput?.value === 'plt' || actingTypeInput?.value === 'plh';
    if (actingFields) actingFields.hidden = !enabled;
    Object.values(actingInputs).forEach((input) => {
      if (input) input.required = enabled;
    });
  }
  actingChoices.forEach((choice) => {
    choice.addEventListener('change', () => {
      if (choice.checked) {
        actingChoices.forEach((other) => { if (other !== choice) other.checked = false; });
      }
      if (actingTypeInput) {
        actingTypeInput.value = actingChoices.find((item) => item.checked)?.value || '';
      }
      syncActingFields();
      schedulePreview();
    });
  });
  Object.values(actingInputs).forEach((input) => input?.addEventListener('input', schedulePreview));
  syncActingFields();
  barcodeInput?.addEventListener('change', () => {
    const file = barcodeInput.files?.[0];
    updateBarcodeWidget(file);
  });
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
  form.addEventListener('p16:suspects-changed', schedulePreview);
  editorRecords.forEach(({ editor }) => editor.events.on('change', schedulePreview));
  window.addEventListener('resize', schedulePreview);
  window.addEventListener('load', schedulePreview, { once: true });
  if (document.fonts?.ready) document.fonts.ready.then(schedulePreview);
  if (typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(() => applyPreviewScale()).observe(pagesHolder);
  }
  form.querySelector('[data-p16-content-group]')?.addEventListener('toggle', function () {
    if (!this.open) return;
    // Jodit editors 03-07 initialize while this group is closed (zero-width
    // container), so nudge them to recompute their layout now that it's visible.
    requestAnimationFrame(() => {
      editorRecords.forEach(({ editor }) => {
        try { editor.events.fire('resize'); } catch (error) { /* noop */ }
      });
    });
  });
  form.addEventListener('submit', () => {
    editorRecords.forEach(({ textarea, editor }) => { textarea.value = editor.value; });
  });
  form.querySelector('[data-p16-print]')?.addEventListener('click', () => {
    renderPreview();
    const overflowing = updateOverflowWarning();
    if (overflowing.length) {
      const page = pagesHolder.querySelectorAll('.p16-paper')[overflowing[0]];
      showGroup(page?.dataset.p16Group || 'naskah');
      window.alert('Isi P-16 melewati batas halaman dan dapat terpotong. Rapikan bagian yang ditandai sebelum mencetak.');
      return;
    }
    window.print();
  });

  const sipedeButton = form.querySelector('[data-p16-sipede]');
  const sipedeModal = form.querySelector('[data-p16-sipede-modal]');
  const sipedeMessage = form.querySelector('[data-p16-sipede-message]');
  const sipedeProgress = form.querySelector('[data-p16-sipede-progress]');
  const sipedeConfirm = form.querySelector('[data-p16-sipede-confirm]');
  const sipedeFields = Array.from(form.querySelectorAll('[data-p16-sipede-field]'));
  const dispositionPicker = form.querySelector('[data-p16-disposition-picker]');
  const dispositionOptions = form.querySelector('[data-p16-disposition-options]');
  const dispositionAll = form.querySelector('[data-p16-disposition-all]');
  const dispositionModal = form.querySelector('[data-p16-disposition-modal]');
  const dispositionConfirm = form.querySelector('[data-p16-disposition-confirm]');
  const pdfDownloadButton = form.querySelector('[data-p16-pdf-download]');
  let waitingForDisposition = false;

  function selectedDispositionIds() {
    return Array.from(form.querySelectorAll('[data-p16-disposition-choice]:checked'))
      .map((input) => input.value);
  }

  function showDispositionOptions(options) {
    dispositionOptions?.replaceChildren();
    (options || []).forEach((option) => {
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = option.value;
      checkbox.dataset.p16DispositionChoice = '';
      label.append(checkbox, document.createTextNode(option.label));
      dispositionOptions?.appendChild(label);
    });
    if (dispositionPicker) dispositionPicker.hidden = false;
    if (dispositionAll) dispositionAll.checked = false;
  }

  dispositionAll?.addEventListener('change', () => {
    form.querySelectorAll('[data-p16-disposition-choice]').forEach((input) => {
      input.checked = dispositionAll.checked;
    });
  });

  dispositionModal?.querySelectorAll('[data-p16-disposition-close]').forEach((button) => {
    button.addEventListener('click', () => {
      dispositionModal.hidden = true;
      waitingForDisposition = false;
      document.body.classList.remove('p16-sipede-open');
    });
  });

  dispositionConfirm?.addEventListener('click', () => {
    if (!selectedDispositionIds().length) {
      window.alert('Pilih minimal satu tujuan disposisi sebelum mengirim P-16.');
      return;
    }
    dispositionModal.hidden = true;
    if (sipedeModal) {
      sipedeModal.classList.add('is-finalizing');
      sipedeModal.hidden = false;
    }
    sipedeConfirm?.click();
  });

  function closeSipedeModal() {
    if (!sipedeModal || sipedeProgress?.hidden === false) return;
    sipedeModal.hidden = true;
    document.body.classList.remove('p16-sipede-open');
  }

  function openSipedeModal() {
    if (!sipedeModal) return;
    sipedeModal.classList.remove('is-finalizing');
    sipedeModal.hidden = false;
    document.body.classList.add('p16-sipede-open');
    waitingForDisposition = false;
    if (dispositionPicker) dispositionPicker.hidden = true;
    sipedeFields.forEach((field) => { field.disabled = false; });
    if (sipedeConfirm) sipedeConfirm.textContent = 'Ambil Nomor & Upload';
    sipedeConfirm?.focus();
  }

  function setSipedeBusy(busy, message) {
    if (sipedeProgress) sipedeProgress.hidden = !busy;
    if (sipedeConfirm) sipedeConfirm.disabled = busy;
    sipedeModal?.querySelectorAll('[data-p16-sipede-close]').forEach((button) => { button.disabled = busy; });
    if (sipedeMessage && message) sipedeMessage.textContent = message;
  }

  async function readJson(response) {
    const text = await response.text();
    try { return text ? JSON.parse(text) : {}; }
    catch (_error) { return { message: text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() }; }
  }

  function requestSipedeLogin() {
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        window.removeEventListener('sipede-auth-success', onSuccess);
        window.removeEventListener('sipede-auth-cancelled', onCancelled);
      };
      const onSuccess = (event) => { cleanup(); resolve(event.detail || {}); };
      const onCancelled = () => {
        cleanup();
        const error = new Error('Login SIPede dibatalkan.');
        error.cancelled = true;
        reject(error);
      };
      window.addEventListener('sipede-auth-success', onSuccess);
      window.addEventListener('sipede-auth-cancelled', onCancelled);
      window.dispatchEvent(new CustomEvent('sipede-auth-start'));
    });
  }

  async function postSipede(data, allowLogin = true) {
    const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
    const response = await fetch(sipedeButton.dataset.url, {
      method: 'POST',
      headers: { 'Accept': 'application/json', 'X-CSRFToken': csrfToken },
      body: data
    });
    const result = await readJson(response);
    if (result.requires_sipede_login) {
      if (allowLogin) {
        setSipedeBusy(false, result.message || 'Sesi SIPede belum aktif. Silakan login.');
        await requestSipedeLogin();
        setSipedeBusy(true, 'Sesi SIPede aktif. Melanjutkan proses...');
        return postSipede(data, false);
      }
      throw new Error(result.message || 'Sesi SIPede belum aktif.');
    }
    if (!response.ok) throw new Error(result.message || `Proses SIPede gagal (HTTP ${response.status}).`);
    return result;
  }

  function blobAsDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  async function imageAsDataUrl(image) {
    if (!image.src || image.src.startsWith('data:image/')) return image.src;
    const response = await fetch(image.src, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Gambar dokumen gagal dimuat: ${image.alt || image.src}`);
    return blobAsDataUrl(await response.blob());
  }

  async function sipedeDocumentHtml(expectedNumber) {
    renderPreview();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const renderedNumbers = Array.from(
      pagesHolder.querySelectorAll('[data-p16-output="number"]')
    ).map((node) => node.textContent.trim());
    if (!expectedNumber || !renderedNumbers.length || renderedNumbers.some((number) => number !== expectedNumber)) {
      throw new Error('Nomor SIPede belum berhasil dimasukkan ke seluruh halaman P-16. PDF belum dikirim.');
    }
    const clone = pagesHolder.cloneNode(true);
    const images = Array.from(clone.querySelectorAll('img'));
    const sources = await Promise.all(images.map(imageAsDataUrl));
    images.forEach((image, index) => { image.src = sources[index]; });
    const layoutVariables = form.getAttribute('style') || '';
    clone.querySelectorAll('.p16-paper').forEach((paper) => {
      paper.style.cssText = `${layoutVariables};${paper.style.cssText || ''}`;
      paper.style.transform = 'none';
    });
    clone.querySelectorAll('.p16-paper-frame').forEach((frame) => { frame.style.height = ''; });
    return clone.innerHTML;
  }

  pdfDownloadButton?.addEventListener('click', async () => {
    const number = completeP16Number();
    if (!number) {
      window.alert('Lengkapi atau ambil nomor surat terlebih dahulu sebelum mengunduh PDF.');
      return;
    }
    const originalText = pdfDownloadButton.textContent;
    pdfDownloadButton.disabled = true;
    pdfDownloadButton.textContent = 'Membuat PDF…';
    try {
      const data = new FormData();
      data.append('action', 'pdf');
      data.append('document_html', await sipedeDocumentHtml(number));
      const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
      const response = await fetch(pdfDownloadButton.dataset.url, {
        method: 'POST',
        headers: { 'Accept': 'application/pdf', 'X-CSRFToken': csrfToken },
        body: data,
      });
      if (!response.ok) {
        const result = await readJson(response);
        throw new Error(result.message || 'PDF P-16 gagal dibuat.');
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `P-16-${number.replace(/[^A-Z0-9.-]+/gi, '-')}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      window.alert(error.message || 'PDF P-16 gagal diunduh.');
    } finally {
      pdfDownloadButton.disabled = false;
      pdfDownloadButton.textContent = originalText;
    }
  });

  sipedeButton?.addEventListener('click', async () => {
    const originalText = sipedeButton.textContent;
    sipedeButton.disabled = true;
    sipedeButton.textContent = 'Memeriksa sesi SIPede...';
    try {
      const sessionData = new FormData();
      sessionData.append('action', 'session');
      await postSipede(sessionData);
      // The login popup may have set the P-16 popup to busy while it refreshed
      // the session. Reset it before showing the editable P-16 details.
      setSipedeBusy(false, 'Sesi SIPede aktif. Periksa data surat sebelum mengambil nomor.');
      openSipedeModal();
    } catch (error) {
      if (!error.cancelled) window.alert(error.message || 'Sesi SIPede tidak dapat diperiksa.');
    } finally {
      if (sipedeButton.textContent !== 'Sudah di SIPede') {
        sipedeButton.disabled = false;
        sipedeButton.textContent = originalText;
      }
    }
  });
  sipedeModal?.querySelectorAll('[data-p16-sipede-close]').forEach((button) => {
    button.addEventListener('click', closeSipedeModal);
  });
  sipedeConfirm?.addEventListener('click', async () => {
    const invalidField = sipedeFields.find((field) => !field.checkValidity());
    if (invalidField) {
      invalidField.reportValidity();
      invalidField.focus();
      return;
    }
    try {
      if (waitingForDisposition) {
        const dispositionIds = selectedDispositionIds();
        if (!dispositionIds.length) {
          throw new Error('Pilih minimal satu tujuan disposisi sebelum mengirim P-16.');
        }
        setSipedeBusy(true, `Nomor ${sipedeNumber} sudah dimasukkan. Membuat PDF baru…`);
        const uploadData = new FormData();
        uploadData.append('action', 'upload');
        uploadData.append('document_html', await sipedeDocumentHtml(sipedeNumber));
        dispositionIds.forEach((value) => uploadData.append('disposition_ids', value));
        setSipedeBusy(true, 'Mengunggah PDF dan meneruskan P-16 sesuai disposisi');
        const result = await postSipede(uploadData);
        if (sipedeButton) {
          sipedeButton.disabled = true;
          sipedeButton.textContent = 'Sudah di SIPede';
        }
        setSipedeBusy(false, result.message || 'P-16 berhasil dikirim dan diteruskan di SIPede.');
        if (sipedeConfirm) sipedeConfirm.hidden = true;
        if (sipedeModal) sipedeModal.hidden = true;
        if (dispositionModal) dispositionModal.hidden = true;
        document.body.classList.remove('p16-sipede-open');
        waitingForDisposition = false;
        sipedeModal?.querySelectorAll('[data-p16-sipede-close]').forEach((button) => { button.disabled = false; });
        return;
      }

      setSipedeBusy(true, 'Mencocokkan penanda tangan dan mengambil nomor dari SIPede…');
      const numberData = new FormData();
      numberData.append('action', 'number');
      numberData.append('letter_date', dateInput?.value || '');
      numberData.append('acting_type', actingTypeInput?.value || '');
      numberData.append('acting_name', actingInputs.name?.value.trim() || '');
      numberData.append('acting_position', actingInputs.position?.value.trim() || '');
      numberData.append('acting_nip', actingInputs.nip?.value.trim() || '');
      sipedeFields.forEach((field) => {
        numberData.append(field.dataset.p16SipedeField, field.value.trim());
      });
      const numberResult = await postSipede(numberData);
      const returnedNumber = String(numberResult.number || '').trim().toUpperCase();
      if (/^\d+[A-Z]?$/.test(returnedNumber)) {
        const dateParts = (dateInput?.value || '').split('-');
        if (dateParts.length !== 3 || !numberRegionCode || !numberLetterCode) {
          throw new Error('Kode wilayah, kode surat, atau tanggal belum lengkap untuk menyusun nomor SIPede.');
        }
        sipedeNumber = `PRINT-${returnedNumber}/${numberRegionCode}/${numberLetterCode}/${dateParts[1]}/${dateParts[0]}`;
      } else {
        sipedeNumber = returnedNumber;
      }
      if (!sipedeNumber) throw new Error('SIPede tidak mengembalikan nomor surat. Proses dihentikan sebelum membuat PDF.');
      const sequence = sipedeNumber.match(/^PRINT-(\d+[A-Z]?)\//i)?.[1];
      if (!sequence) throw new Error(`Format nomor SIPede tidak valid: ${sipedeNumber}`);
      if (numberInput) numberInput.value = sequence;
      renderPreview();
      const dispositionData = new FormData();
      dispositionData.append('action', 'dispositions');
      const dispositionResult = await postSipede(dispositionData);
      showDispositionOptions(dispositionResult.options);
      waitingForDisposition = true;
      sipedeFields.forEach((field) => { field.disabled = true; });
      if (sipedeConfirm) sipedeConfirm.textContent = 'Buat PDF & Kirim';
      setSipedeBusy(false, `Nomor ${sipedeNumber} sudah dimasukkan.`);
      if (sipedeModal) sipedeModal.hidden = true;
      if (dispositionModal) dispositionModal.hidden = false;
    } catch (error) {
      setSipedeBusy(false, error.message || 'Proses SIPede gagal.');
      if (!error.cancelled) window.alert(error.message || 'Proses SIPede gagal.');
    }
  });

  if (!canEdit) form.querySelectorAll('input:not([type="hidden"]),select,textarea').forEach((field) => { field.disabled = true; });
  new MutationObserver(() => {
    const theme = document.documentElement.classList.contains('dark') ? 'dark' : 'default';
    editorRecords.forEach(({ editor }) => editor.setOptions({ theme }));
  }).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

  setupProsecutorPicker();
  setupAdministrativeStaffPicker();
  renderPreview();
})();
