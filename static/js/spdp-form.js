(() => {
  const form = document.querySelector('[data-spdp-form]');
  if (!form) return;

  function setupPersonCollection(config) {
    const list = document.querySelector(config.list);
    const summary = document.querySelector(config.summary);
    const emptyMessage = document.querySelector(config.empty);
    const addButton = document.querySelector(config.addButton);
    const dialog = document.querySelector(config.dialog);
    const totalInput = document.querySelector(config.totalInput);
    const template = document.querySelector(config.template);
    if (!list || !summary || !emptyMessage || !addButton || !dialog || !totalInput || !template) return;

    let activeDraftCard = null;
    let activeDraftSnapshot = null;

    const allCards = () => [...list.querySelectorAll(config.card)];
    const activeCards = () => allCards().filter(card => !card.hidden && !card.querySelector('input[name$="-DELETE"]')?.checked);
    const cardInputs = card => [...card.querySelectorAll('input:not([type="hidden"]), select, textarea')];
    const fieldSuffix = input => input.name.split('-').pop();
    const value = (card, suffix) => card.querySelector(`[name$="-${suffix}"]`)?.value.trim() || '';

    const hasMeaningfulValue = input => {
      if (input.type === 'checkbox') return input.checked;
      const currentValue = input.value.trim();
      if (!currentValue) return false;
      if (fieldSuffix(input) === 'nationality' && currentValue.toLowerCase() === 'indonesia') return false;
      if (config.ignoredDefaultValues?.[fieldSuffix(input)] === currentValue) return false;
      return true;
    };
    const hasData = card => cardInputs(card).some(hasMeaningfulValue);

    function snapshotCard(card) {
      return cardInputs(card).map(input => ({
        input,
        checked: input.checked,
        value: input.value,
        committed: card.dataset.committed || '',
      }));
    }

    function restoreSnapshot(snapshot) {
      if (!snapshot) return;
      snapshot.forEach(item => {
        if (item.input.type === 'checkbox') item.input.checked = item.checked;
        else item.input.value = item.value;
        item.input.dispatchEvent(new Event('change', { bubbles: true }));
      });
      const card = snapshot[0]?.input.closest(config.card);
      if (card) {
        card.dataset.committed = snapshot[0].committed;
        if (!card.dataset.committed) delete card.dataset.committed;
        renderDynamicFields(card);
      }
    }

    function initializeCommittedCards() {
      activeCards().forEach(card => {
        if (hasData(card)) card.dataset.committed = '1';
      });
    }

    function renumber() {
      activeCards().forEach((card, index) => {
        const number = card.querySelector(config.number);
        if (number) number.textContent = index + 1;
      });
    }

    function calculateAge(card) {
      if (!config.calculateAge) return;
      const birthInput = card.querySelector('[name$="-birth_date"]');
      const ageInput = card.querySelector('[name$="-age"]');
      if (!birthInput || !ageInput || !birthInput.value) return;
      const birthDate = new Date(`${birthInput.value}T00:00:00`);
      if (Number.isNaN(birthDate.getTime())) return;
      const today = new Date();
      let age = today.getFullYear() - birthDate.getFullYear();
      const monthDiff = today.getMonth() - birthDate.getMonth();
      if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) age -= 1;
      if (age >= 0 && age <= 99) ageInput.value = age;
    }

    function renderDynamicFields(scope = list) {
      const cards = scope.matches?.(config.card) ? [scope] : [...scope.querySelectorAll(config.card)];
      cards.forEach(card => {
        if (config.renderDynamicFields) config.renderDynamicFields(card, value);
        calculateAge(card);
      });
    }

    function detailsFor(card) {
      const details = config.detailFields.map(item => {
        const fieldValue = value(card, item.field);
        if (!fieldValue) return '';
        return item.label ? `${item.label}: ${fieldValue}` : fieldValue;
      });
      return details.filter(Boolean).join(' - ') || config.emptyDetails;
    }

    function renderSummary() {
      renumber();
      renderDynamicFields();
      summary.querySelectorAll(config.summaryItem).forEach(item => item.remove());
      const committedCards = activeCards().filter(card => card.dataset.committed === '1' && hasData(card));
      emptyMessage.hidden = committedCards.length > 0;

      committedCards.forEach((card, index) => {
        const name = value(card, config.nameField || 'name') || config.fallbackName;
        const row = document.createElement('article');
        row.className = 'suspect-summary-item';
        row.dataset[config.summaryDataset] = '';
        row.innerHTML = `<span class="suspect-summary-number">${index + 1}</span><div class="suspect-summary-copy"><b></b><small></small></div><div class="suspect-summary-actions"><button type="button" data-edit-person>Edit</button><button type="button" class="danger" data-delete-person>Hapus</button></div>`;
        row.querySelector('.suspect-summary-copy b').textContent = name;
        row.querySelector('.suspect-summary-copy small').textContent = detailsFor(card);
        row.querySelector('[data-edit-person]').addEventListener('click', () => openCard(card));
        row.querySelector('[data-delete-person]').addEventListener('click', () => removeCard(card));
        summary.appendChild(row);
      });
      if (config.changeEvent) form.dispatchEvent(new CustomEvent(config.changeEvent));
    }

    function showOnlyCardInDialog(cardToShow) {
      allCards().forEach(card => {
        const shouldHide = card !== cardToShow;
        card.classList.toggle('dialog-card-hidden', shouldHide);
        card.style.display = shouldHide ? 'none' : '';
      });
    }

    function resetDialogCardVisibility() {
      allCards().forEach(card => {
        card.classList.remove('dialog-card-hidden');
        card.style.display = '';
      });
    }

    function closeDialog() {
      resetDialogCardVisibility();
      activeDraftCard = null;
      activeDraftSnapshot = null;
      if (dialog.open) dialog.close();
    }

    function finishDialog() {
      if (activeDraftCard && hasData(activeDraftCard)) {
        activeDraftCard.dataset.committed = '1';
      }
      closeDialog();
      renderSummary();
    }

    function cancelDialog() {
      restoreSnapshot(activeDraftSnapshot);
      closeDialog();
      renderSummary();
    }

    function removeCard(card) {
      const deleteInput = card.querySelector('input[name$="-DELETE"]');
      if (deleteInput) deleteInput.checked = true;
      card.hidden = true;
      delete card.dataset.committed;
      renderSummary();
    }

    function appendCard() {
      const index = Number(totalInput.value);
      const wrapper = document.createElement('div');
      wrapper.innerHTML = template.innerHTML.replaceAll('__prefix__', index).replaceAll('__number__', activeCards().length + 1).trim();
      const card = wrapper.firstElementChild;
      list.appendChild(card);
      totalInput.value = index + 1;
      renderDynamicFields(card);
      return card;
    }

    function openCard(card) {
      activeDraftCard = card;
      activeDraftSnapshot = snapshotCard(card);
      showOnlyCardInDialog(card);
      dialog.showModal();
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      card.querySelector('input:not([type="hidden"])')?.focus({ preventScroll: true });
    }

    function openForNew() {
      const unusedCard = activeCards().find(card => card.dataset.committed !== '1' && !hasData(card));
      openCard(unusedCard || appendCard());
    }

    addButton.addEventListener('click', openForNew);
    dialog.querySelector(config.finishButton)?.addEventListener('click', finishDialog);
    dialog.querySelector(config.cancelButton)?.addEventListener('click', cancelDialog);
    dialog.addEventListener('cancel', event => {
      event.preventDefault();
      cancelDialog();
    });
    dialog.addEventListener('click', event => {
      if (event.target === dialog) cancelDialog();
    });
    list.addEventListener('input', event => {
      const card = event.target.closest(config.card);
      if (card) renderDynamicFields(card);
    });
    list.addEventListener('change', event => {
      const card = event.target.closest(config.card);
      if (card) renderDynamicFields(card);
    });

    initializeCommittedCards();
    renderSummary();
    if (list.querySelector('.errorlist')) {
      const errorCard = list.querySelector('.errorlist')?.closest(config.card);
      if (errorCard) openCard(errorCard);
    }
  }

  setupPersonCollection({
    list: '[data-suspect-list]',
    summary: '[data-suspect-summary]',
    empty: '[data-suspect-empty]',
    addButton: '[data-add-suspect]',
    dialog: '[data-suspect-dialog]',
    totalInput: '#id_suspects-TOTAL_FORMS',
    template: '#empty-suspect-form',
    card: '[data-suspect-form]',
    number: '[data-suspect-number]',
    finishButton: '[data-finish-suspect-dialog]',
    cancelButton: '[data-cancel-suspect-dialog]',
    summaryItem: '[data-suspect-summary-item]',
    summaryDataset: 'suspectSummaryItem',
    fallbackName: 'Nama pelaku belum diisi',
    emptyDetails: 'Detail pelaku',
    calculateAge: true,
    changeEvent: 'p16:suspects-changed',
    detailFields: [
      { field: 'suspect_type' },
      { field: 'identity_number', label: 'Identitas' },
      { field: 'occupation' },
    ],
    renderDynamicFields(card, value) {
      const type = value(card, 'suspect_type').toUpperCase();
      const showCorporation = type === 'KORPORASI' || type === 'PENGURUS KORPORASI';
      const showPosition = type === 'PENGURUS KORPORASI';
      const corporationFields = card.querySelector('[data-corporation-fields]');
      const positionField = card.querySelector('[data-corporate-position]');
      if (corporationFields) corporationFields.hidden = !showCorporation;
      if (positionField) positionField.hidden = !showPosition;
    },
  });

  setupPersonCollection({
    list: '[data-victim-list]',
    summary: '[data-victim-summary]',
    empty: '[data-victim-empty]',
    addButton: '[data-add-victim]',
    dialog: '[data-victim-dialog]',
    totalInput: '#id_victims-TOTAL_FORMS',
    template: '#empty-victim-form',
    card: '[data-victim-form]',
    number: '[data-victim-number]',
    finishButton: '[data-finish-victim-dialog]',
    cancelButton: '[data-cancel-victim-dialog]',
    summaryItem: '[data-victim-summary-item]',
    summaryDataset: 'victimSummaryItem',
    fallbackName: 'Nama korban belum diisi',
    emptyDetails: 'Detail korban',
    detailFields: [
      { field: 'relationship' },
      { field: 'identity_number', label: 'Identitas' },
      { field: 'occupation' },
    ],
  });

  setupPersonCollection({
    list: '[data-receipt-list]',
    summary: '[data-receipt-summary]',
    empty: '[data-receipt-empty]',
    addButton: '[data-add-receipt]',
    dialog: '[data-receipt-dialog]',
    totalInput: '#id_receipts-TOTAL_FORMS',
    template: '#empty-receipt-form',
    card: '[data-receipt-form]',
    number: '[data-receipt-number]',
    finishButton: '[data-finish-receipt-dialog]',
    cancelButton: '[data-cancel-receipt-dialog]',
    summaryItem: '[data-receipt-summary-item]',
    summaryDataset: 'receiptSummaryItem',
    nameField: 'recipient_name',
    fallbackName: 'Tanda terima belum lengkap',
    emptyDetails: 'Detail tanda terima',
    detailFields: [
      { field: 'received_at', label: 'Diterima' },
      { field: 'investigator_name', label: 'Penyidik' },
      { field: 'investigator_nrp', label: 'NRP' },
    ],
    ignoredDefaultValues: {
      receipt_type: 'hasil_penyidikan',
    },
    renderDynamicFields(card) {
      const dataScript = document.getElementById('receipt-prosecutor-profiles');
      let profiles = [];
      try { profiles = JSON.parse(dataScript?.textContent || '[]'); } catch (error) { profiles = []; }
      const recipientSelect = card.querySelector('[name$="-recipient_user"]');
      const selectedId = recipientSelect?.value || '';
      if (!selectedId && recipientSelect?.dataset.recipientBound !== '1') return;
      const profile = profiles.find(item => String(item.id) === String(selectedId));
      const values = profile || { name: '', rank: '', position: '', nip: '' };
      if (recipientSelect) recipientSelect.dataset.recipientBound = selectedId ? '1' : '';
      const fieldValues = {
        recipient_name: values.name,
        recipient_rank: values.rank,
        recipient_position: values.position,
        recipient_nip: values.nip,
      };
      Object.entries(fieldValues).forEach(([field, fieldValue]) => {
        const input = card.querySelector(`[name$="-${field}"]`);
        if (input && input.value !== fieldValue) input.value = fieldValue || '';
      });
    },
  });

  setupPersonCollection({
    list: '[data-investigator-list]',
    summary: '[data-investigator-summary]',
    empty: '[data-investigator-empty]',
    addButton: '[data-add-investigator]',
    dialog: '[data-investigator-dialog]',
    totalInput: '#id_investigators-TOTAL_FORMS',
    template: '#empty-investigator-form',
    card: '[data-investigator-form]',
    number: '[data-investigator-number]',
    finishButton: '[data-finish-investigator-dialog]',
    cancelButton: '[data-cancel-investigator-dialog]',
    summaryItem: '[data-investigator-summary-item]',
    summaryDataset: 'investigatorSummaryItem',
    fallbackName: 'Nama penyidik belum diisi',
    emptyDetails: 'Nomor HP belum diisi',
    detailFields: [
      { field: 'phone', label: 'Nomor HP' },
      { field: 'telegram_chat_id', label: 'ID Telegram' },
    ],
  });

  function setupInvestigatorCascade() {
    const agencySelect = form.querySelector('[name="investigator_agency"]');
    const unitSelect = form.querySelector('[name="investigating_unit"]');
    const dataScript = document.getElementById('investigator-units-by-institution');
    if (!agencySelect || !unitSelect || !dataScript) return;

    let unitsByInstitution = {};
    try { unitsByInstitution = JSON.parse(dataScript.textContent); } catch (error) { unitsByInstitution = {}; }

    function populateUnits(agency, preselected) {
      const options = unitsByInstitution[agency] || [];
      unitSelect.innerHTML = '';
      const placeholder = document.createElement('option');
      placeholder.value = '';
      if (!agency) placeholder.textContent = '---Pilih Instansi Penyidik terlebih dahulu---';
      else if (!options.length) placeholder.textContent = 'Belum ada Instansi Pelaksana Penyidik';
      else placeholder.textContent = '---Pilih Instansi Pelaksana Penyidik---';
      unitSelect.appendChild(placeholder);
      options.forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        if (name === preselected) option.selected = true;
        unitSelect.appendChild(option);
      });
      unitSelect.disabled = !agency || !options.length;
    }

    const initialUnit = unitSelect.value;
    populateUnits(agencySelect.value, initialUnit);
    agencySelect.addEventListener('change', () => populateUnits(agencySelect.value, ''));
  }

  function setupCaseTypeCascade() {
    const directorateSelect = form.querySelector('[name="directorate"]');
    const caseTypeSelect = form.querySelector('[name="case_type"]');
    const dataScript = document.getElementById('case-types-by-directorate');
    if (!directorateSelect || !caseTypeSelect || !dataScript) return;

    let caseTypesByDirectorate = {};
    try { caseTypesByDirectorate = JSON.parse(dataScript.textContent); } catch (error) { caseTypesByDirectorate = {}; }

    function populateCaseTypes(directorate, preselected) {
      const options = caseTypesByDirectorate[directorate] || [];
      caseTypeSelect.innerHTML = '';
      const placeholder = document.createElement('option');
      placeholder.value = '';
      if (!directorate) placeholder.textContent = '---Pilih Direktorat terlebih dahulu---';
      else if (!options.length) placeholder.textContent = 'Belum ada jenis perkara';
      else placeholder.textContent = '---Pilih Jenis Perkara---';
      caseTypeSelect.appendChild(placeholder);
      options.forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        if (name === preselected) option.selected = true;
        caseTypeSelect.appendChild(option);
      });
      caseTypeSelect.disabled = !directorate || !options.length;
    }

    const initialCaseType = caseTypeSelect.value;
    populateCaseTypes(directorateSelect.value, initialCaseType);
    directorateSelect.addEventListener('change', () => populateCaseTypes(directorateSelect.value, ''));
  }

  setupInvestigatorCascade();
  setupCaseTypeCascade();

  form.addEventListener('submit', () => document.querySelector('[data-submit-spdp]')?.setAttribute('disabled', 'disabled'));
})();
