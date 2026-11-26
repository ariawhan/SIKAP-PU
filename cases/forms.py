import json
from html import unescape

from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from django.utils.html import strip_tags

from accounts.models import Role, User
from .models import CaseDocumentDraft, CaseInvestigator, CoordinationMinutesDraft, P16Draft, P17Draft, P21Draft, Receipt, SOPForm02Draft, SOPForm03Draft, SOPForm1BDraft, SPDP, StageOne, Suspect, Victim
from .p16_content import sanitize_p16_html
from .p16_numbering import P16NumberingError, build_p16_number, extract_p16_sequence, p16_number_parts
from .p17_numbering import P17NumberingError, build_p17_number, extract_p17_sequence, p17_number_parts
from .p17_content import normalize_p17_recipients, p17_recipients_for_editor, render_p17_recipients


IDENTITY_CHOICES = (
    ("", "---Pilih---"),
    ("KTP", "KTP"),
    ("SIM", "SIM"),
    ("Paspor", "Paspor"),
    ("KITAS", "KITAS"),
    ("KITAP", "KITAP"),
    ("Lainnya", "Lainnya"),
)

RELIGION_CHOICES = (
    ("", "---Pilih---"),
    ("Islam", "Islam"),
    ("Kristen", "Kristen"),
    ("Katolik", "Katolik"),
    ("Hindu", "Hindu"),
    ("Buddha", "Buddha"),
    ("Konghucu", "Konghucu"),
    ("Kepercayaan", "Kepercayaan"),
)

MARITAL_STATUS_CHOICES = (
    ("", "---Pilih---"),
    ("Belum Kawin", "Belum Kawin"),
    ("Kawin", "Kawin"),
    ("Cerai Hidup", "Cerai Hidup"),
    ("Cerai Mati", "Cerai Mati"),
)

EDUCATION_CHOICES = (
    ("", "---Pilih---"),
    ("Tidak Sekolah", "Tidak Sekolah"),
    ("Sekolah Dasar / Sederajat", "Sekolah Dasar / Sederajat"),
    ("Sekolah Menengah Pertama / Sederajat", "Sekolah Menengah Pertama / Sederajat"),
    ("Sekolah Lanjutan Tingkat Atas / Sederajat", "Sekolah Lanjutan Tingkat Atas / Sederajat"),
    ("Akademi / Diploma", "Akademi / Diploma"),
    ("Diploma IV / Strata 1", "Diploma IV / Strata 1"),
    ("Strata II", "Strata II"),
    ("Strata III", "Strata III"),
)

OCCUPATION_CHOICES = (
    ("", "---Pilih---"),
    ("Belum / Tidak Bekerja", "Belum / Tidak Bekerja"),
    ("Mengurus Rumah Tangga", "Mengurus Rumah Tangga"),
    ("Pelajar / Mahasiswa", "Pelajar / Mahasiswa"),
    ("Pegawai Negeri Sipil", "Pegawai Negeri Sipil"),
    ("Tentara Nasional Indonesia", "Tentara Nasional Indonesia"),
    ("Kepolisian RI", "Kepolisian RI"),
    ("Karyawan Swasta", "Karyawan Swasta"),
    ("Karyawan BUMN", "Karyawan BUMN"),
    ("Karyawan BUMD", "Karyawan BUMD"),
    ("Karyawan Honorer", "Karyawan Honorer"),
    ("Buruh Harian Lepas", "Buruh Harian Lepas"),
    ("Petani / Pekebun", "Petani / Pekebun"),
    ("Nelayan / Perikanan", "Nelayan / Perikanan"),
    ("Pedagang", "Pedagang"),
    ("Wiraswasta", "Wiraswasta"),
    ("Guru", "Guru"),
    ("Dosen", "Dosen"),
    ("Dokter", "Dokter"),
    ("Bidan", "Bidan"),
    ("Perawat", "Perawat"),
    ("Pengacara", "Pengacara"),
    ("Notaris", "Notaris"),
    ("Jaksa", "Jaksa"),
    ("Hakim", "Hakim"),
    ("Lainnya", "Lainnya"),
)

COUNTRY_CHOICES = (
    ("", "---Pilih---"),
    ("Indonesia", "Indonesia"),
    ("Afganistan", "Afganistan"),
    ("Afrika Selatan", "Afrika Selatan"),
    ("Albania", "Albania"),
    ("Aljazair", "Aljazair"),
    ("Amerika Serikat", "Amerika Serikat"),
    ("Andorra", "Andorra"),
    ("Angola", "Angola"),
    ("Antigua dan Barbuda", "Antigua dan Barbuda"),
    ("Arab Saudi", "Arab Saudi"),
    ("Argentina", "Argentina"),
    ("Armenia", "Armenia"),
    ("Australia", "Australia"),
    ("Austria", "Austria"),
    ("Azerbaijan", "Azerbaijan"),
    ("Bahama", "Bahama"),
    ("Bahrain", "Bahrain"),
    ("Bangladesh", "Bangladesh"),
    ("Barbados", "Barbados"),
    ("Belanda", "Belanda"),
    ("Belarus", "Belarus"),
    ("Belgia", "Belgia"),
    ("Belize", "Belize"),
    ("Benin", "Benin"),
    ("Bhutan", "Bhutan"),
    ("Bolivia", "Bolivia"),
    ("Bosnia dan Herzegovina", "Bosnia dan Herzegovina"),
    ("Botswana", "Botswana"),
    ("Brasil", "Brasil"),
    ("Brunei Darussalam", "Brunei Darussalam"),
    ("Bulgaria", "Bulgaria"),
    ("Burkina Faso", "Burkina Faso"),
    ("Burundi", "Burundi"),
    ("Chad", "Chad"),
    ("Chili", "Chili"),
    ("China", "China"),
    ("Denmark", "Denmark"),
    ("Djibouti", "Djibouti"),
    ("Dominika", "Dominika"),
    ("Ekuador", "Ekuador"),
    ("El Salvador", "El Salvador"),
    ("Eritrea", "Eritrea"),
    ("Estonia", "Estonia"),
    ("Eswatini", "Eswatini"),
    ("Etiopia", "Etiopia"),
    ("Federasi Rusia", "Federasi Rusia"),
    ("Fiji", "Fiji"),
    ("Filipina", "Filipina"),
    ("Finlandia", "Finlandia"),
    ("Gabon", "Gabon"),
    ("Gambia", "Gambia"),
    ("Georgia", "Georgia"),
    ("Ghana", "Ghana"),
    ("Grenada", "Grenada"),
    ("Guatemala", "Guatemala"),
    ("Guinea", "Guinea"),
    ("Guinea Bissau", "Guinea Bissau"),
    ("Guinea Khatulistiwa", "Guinea Khatulistiwa"),
    ("Guyana", "Guyana"),
    ("Haiti", "Haiti"),
    ("Honduras", "Honduras"),
    ("Hongaria", "Hongaria"),
    ("India", "India"),
    ("Britania Raya", "Britania Raya"),
    ("Irak", "Irak"),
    ("Iran", "Iran"),
    ("Irlandia", "Irlandia"),
    ("Islandia", "Islandia"),
    ("Israel", "Israel"),
    ("Italia", "Italia"),
    ("Jamaika", "Jamaika"),
    ("Jepang", "Jepang"),
    ("Jerman", "Jerman"),
    ("Kamboja", "Kamboja"),
    ("Kamerun", "Kamerun"),
    ("Kanada", "Kanada"),
    ("Kazakhstan", "Kazakhstan"),
    ("Kenya", "Kenya"),
    ("Kirgizstan", "Kirgizstan"),
    ("Kiribati", "Kiribati"),
    ("Kolombia", "Kolombia"),
    ("Komoro", "Komoro"),
    ("Kongo", "Kongo"),
    ("Korea Selatan", "Korea Selatan"),
    ("Korea Utara", "Korea Utara"),
    ("Kosta Rika", "Kosta Rika"),
    ("Kroasia", "Kroasia"),
    ("Kuba", "Kuba"),
    ("Kuwait", "Kuwait"),
    ("Laos", "Laos"),
    ("Latvia", "Latvia"),
    ("Lebanon", "Lebanon"),
    ("Lesotho", "Lesotho"),
    ("Liberia", "Liberia"),
    ("Libya", "Libya"),
    ("Liechtenstein", "Liechtenstein"),
    ("Lituania", "Lituania"),
    ("Luksemburg", "Luksemburg"),
    ("Madagaskar", "Madagaskar"),
    ("Makedonia Utara", "Makedonia Utara"),
    ("Maladewa", "Maladewa"),
    ("Malawi", "Malawi"),
    ("Malaysia", "Malaysia"),
    ("Mali", "Mali"),
    ("Malta", "Malta"),
    ("Maroko", "Maroko"),
    ("Marshall", "Marshall"),
    ("Mauritania", "Mauritania"),
    ("Mauritius", "Mauritius"),
    ("Meksiko", "Meksiko"),
    ("Mesir", "Mesir"),
    ("Mikronesia", "Mikronesia"),
    ("Moldova", "Moldova"),
    ("Monako", "Monako"),
    ("Mongolia", "Mongolia"),
    ("Montenegro", "Montenegro"),
    ("Mozambik", "Mozambik"),
    ("Myanmar", "Myanmar"),
    ("Namibia", "Namibia"),
    ("Nauru", "Nauru"),
    ("Nepal", "Nepal"),
    ("Niger", "Niger"),
    ("Nigeria", "Nigeria"),
    ("Nikaragua", "Nikaragua"),
    ("Norwegia", "Norwegia"),
    ("Oman", "Oman"),
    ("Pakistan", "Pakistan"),
    ("Palau", "Palau"),
    ("Palestina", "Palestina"),
    ("Panama", "Panama"),
    ("Pantai Gading", "Pantai Gading"),
    ("Papua Nugini", "Papua Nugini"),
    ("Paraguay", "Paraguay"),
    ("Perancis", "Perancis"),
    ("Peru", "Peru"),
    ("Polandia", "Polandia"),
    ("Portugal", "Portugal"),
    ("Qatar", "Qatar"),
    ("Republik Afrika Tengah", "Republik Afrika Tengah"),
    ("Republik Ceko", "Republik Ceko"),
    ("Republik Demokratik Kongo", "Republik Demokratik Kongo"),
    ("Republik Dominika", "Republik Dominika"),
    ("Rumania", "Rumania"),
    ("Rwanda", "Rwanda"),
    ("Saint Kitts dan Nevis", "Saint Kitts dan Nevis"),
    ("Saint Lucia", "Saint Lucia"),
    ("Saint Vincent dan Grenadine", "Saint Vincent dan Grenadine"),
    ("Samoa", "Samoa"),
    ("San Marino", "San Marino"),
    ("Sao Tome dan Principe", "Sao Tome dan Principe"),
    ("Selandia Baru", "Selandia Baru"),
    ("Senegal", "Senegal"),
    ("Serbia", "Serbia"),
    ("Seychelles", "Seychelles"),
    ("Sierra Leone", "Sierra Leone"),
    ("Singapura", "Singapura"),
    ("Siprus", "Siprus"),
    ("Slovakia", "Slovakia"),
    ("Slovenia", "Slovenia"),
    ("Solomon", "Solomon"),
    ("Somalia", "Somalia"),
    ("Spanyol", "Spanyol"),
    ("Sri Lanka", "Sri Lanka"),
    ("Sudan", "Sudan"),
    ("Sudan Selatan", "Sudan Selatan"),
    ("Suriah", "Suriah"),
    ("Suriname", "Suriname"),
    ("Swedia", "Swedia"),
    ("Swiss", "Swiss"),
    ("Tajikistan", "Tajikistan"),
    ("Tanjung Verde", "Tanjung Verde"),
    ("Tanzania", "Tanzania"),
    ("Thailand", "Thailand"),
    ("Timor Leste", "Timor Leste"),
    ("Togo", "Togo"),
    ("Tonga", "Tonga"),
    ("Trinidad dan Tobago", "Trinidad dan Tobago"),
    ("Tunisia", "Tunisia"),
    ("Turki", "Turki"),
    ("Turkmenistan", "Turkmenistan"),
    ("Tuvalu", "Tuvalu"),
    ("Uganda", "Uganda"),
    ("Ukraina", "Ukraina"),
    ("Uni Emirat Arab", "Uni Emirat Arab"),
    ("Uruguay", "Uruguay"),
    ("Uzbekistan", "Uzbekistan"),
    ("Vanuatu", "Vanuatu"),
    ("Vatikan", "Vatikan"),
    ("Venezuela", "Venezuela"),
    ("Vietnam", "Vietnam"),
    ("Yaman", "Yaman"),
    ("Yordania", "Yordania"),
    ("Yunani", "Yunani"),
    ("Zambia", "Zambia"),
    ("Zimbabwe", "Zimbabwe"),
)

DISABILITY_CHOICES = (
    ("Bukan Penyandang Disabilitas", "Bukan Penyandang Disabilitas"),
    ("Disabilitas Fisik", "Disabilitas Fisik"),
    ("Disabilitas Intelektual", "Disabilitas Intelektual"),
    ("Disabilitas Mental", "Disabilitas Mental"),
    ("Disabilitas Sensorik", "Disabilitas Sensorik"),
)

VICTIM_RELATIONSHIP_CHOICES = (
    ("", "---Pilih---"),
    ("Keluarga", "Keluarga"),
    ("Bukan Keluarga", "Bukan Keluarga"),
)


class SPDPForm(forms.ModelForm):
    class Meta:
        model = SPDP
        exclude = ("origin", "created_by", "created_at", "updated_at", "status", "criminal_code")
        widgets = {
            "investigation_order_date": forms.DateInput(attrs={"type": "date"}),
            "letter_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "received_date": forms.DateInput(attrs={"type": "date"}),
            "incident_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "incident_place": forms.Textarea(attrs={"rows": 2}),
            "case_summary": forms.Textarea(attrs={"rows": 4}),
            "laws_and_articles": forms.Textarea(attrs={"rows": 3}),
            "document": forms.FileInput(attrs={"accept": "application/pdf,.pdf"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from configurations.models import InstitutionConfiguration, InvestigatorInstitution, LetterNumberCode

        institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration(
            work_unit="Kejaksaan Negeri Buleleng"
        )
        configured_work_unit = institution.work_unit or "Kejaksaan Negeri Buleleng"
        self.configured_work_unit = configured_work_unit
        self.fields["work_area"].label = "Wilayah kerja / Satuan kerja"
        self.fields["work_area"].initial = configured_work_unit
        self.initial["work_area"] = configured_work_unit
        self.fields["work_area"].disabled = True
        self.fields["work_area"].help_text = "Otomatis mengikuti Konfigurasi Instansi dan tidak dapat diedit di input SPDP."
        self.fields["work_area"].widget.attrs.update({
            "readonly": "readonly",
            "class": "locked-field",
        })
        if self.instance and not self.instance.pk:
            self.instance.work_area = configured_work_unit
        self.fields["letter_date"].input_formats = ["%Y-%m-%d"]
        self.fields["incident_at"].input_formats = ["%Y-%m-%dT%H:%M"]

        investigator_institutions = list(
            InvestigatorInstitution.objects.filter(is_active=True)
            .prefetch_related("units")
            .order_by("name")
        )
        self.investigator_units_by_institution = {
            institution.name: [
                unit.name for unit in institution.units.all()
                if unit.is_active
            ]
            for institution in investigator_institutions
        }
        self.fields["investigator_agency"] = forms.ChoiceField(
            label="Instansi penyidik",
            choices=[("", "---Pilih Instansi Penyidik---")] + [
                (institution.name, institution.name) for institution in investigator_institutions
            ],
            help_text="Pilihan ini dikelola dari Settings > Konfigurasi Penyidik.",
        )
        unit_choices = []
        seen_units = set()
        for names in self.investigator_units_by_institution.values():
            for name in names:
                if name.lower() not in seen_units:
                    seen_units.add(name.lower())
                    unit_choices.append((name, name))
        self.fields["investigating_unit"] = forms.ChoiceField(
            label="Instansi pelaksana penyidik",
            choices=[("", "---Pilih Instansi Pelaksana Penyidik---")] + unit_choices,
        )

        letter_numbers = list(LetterNumberCode.objects.prefetch_related("case_types").order_by("directorate"))
        self.case_types_by_directorate = {}
        case_type_names = []
        seen_case_types = set()
        for letter_number in letter_numbers:
            names = [case_type.name for case_type in letter_number.case_types.all()]
            self.case_types_by_directorate[letter_number.directorate] = names
            for name in names:
                if name.lower() not in seen_case_types:
                    seen_case_types.add(name.lower())
                    case_type_names.append(name)

        self.fields["directorate"] = forms.ChoiceField(
            label="Direktorat",
            choices=[("", "---Pilih Direktorat---")] + [(ln.directorate, ln.directorate) for ln in letter_numbers],
            help_text="Menentukan pilihan Jenis Perkara di bawah. Dikelola lewat Konfigurasi Nomor Surat.",
        )
        self.fields["case_type"] = forms.ChoiceField(
            label="Jenis Perkara",
            choices=[("", "---Pilih Jenis Perkara---")] + [(name, name) for name in case_type_names],
        )

    def clean_work_area(self):
        return self.configured_work_unit

    def clean_investigating_unit(self):
        agency = self.cleaned_data.get("investigator_agency")
        unit = self.cleaned_data.get("investigating_unit")
        if agency and unit and unit not in self.investigator_units_by_institution.get(agency, []):
            raise forms.ValidationError("Instansi pelaksana penyidik tidak sesuai dengan instansi penyidik yang dipilih.")
        return unit


class SuspectForm(forms.ModelForm):
    identity_type = forms.ChoiceField(label="Identitas", choices=IDENTITY_CHOICES, required=False)
    religion = forms.ChoiceField(label="Agama", choices=RELIGION_CHOICES, required=False)
    nationality = forms.ChoiceField(label="Kewarganegaraan", choices=COUNTRY_CHOICES, required=False, initial="Indonesia")
    marital_status = forms.ChoiceField(label="Status Nikah", choices=MARITAL_STATUS_CHOICES, required=False)
    education = forms.ChoiceField(label="Pendidikan", choices=EDUCATION_CHOICES, required=False)
    occupation = forms.ChoiceField(label="Pekerjaan", choices=OCCUPATION_CHOICES, required=False)
    disability_types = forms.MultipleChoiceField(
        label="Disabilitas",
        choices=DISABILITY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Suspect
        exclude = ("spdp", "sequence")
        widgets = {
            "decree_date": forms.DateInput(attrs={"type": "date"}),
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "age": forms.NumberInput(attrs={"min": 0, "max": 99, "data-suspect-age": "", "readonly": "readonly"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "corporation_crime_deed_date": forms.DateInput(attrs={"type": "date"}),
            "corporation_other_identity": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["suspect_type"].label = "Jenis Pelaku"
        self.fields["suspect_type"].choices = [("", "---------")] + [
            (value, label.replace("Tersangka", "Pelaku").replace("tersangka", "pelaku"))
            for value, label in Suspect.SuspectType.choices
        ]
        selected = self.instance.disability_types if self.instance and self.instance.pk else self.initial.get("disability_types", "")
        if isinstance(selected, str):
            self.initial["disability_types"] = [item.strip() for item in selected.split(",") if item.strip()]

    def clean_disability_types(self):
        return ", ".join(self.cleaned_data.get("disability_types") or [])


SuspectFormSet = inlineformset_factory(
    SPDP, Suspect, form=SuspectForm, extra=1, can_delete=True, min_num=0, validate_min=False
)


class StageOneForm(forms.ModelForm):
    class Meta:
        model = StageOne
        fields = ("case_file_number", "cover_letter_number", "laws_and_articles", "cover_letter_document")
        widgets = {
            "case_file_number": forms.TextInput(attrs={"placeholder": "Contoh: BP/123/XI/2026/Reskrim"}),
            "cover_letter_number": forms.TextInput(attrs={"placeholder": "Nomor surat pengantar berkas perkara"}),
            "laws_and_articles": forms.Textarea(attrs={"rows": 4, "placeholder": "Masukkan pasal sesuai berkas perkara Tahap I"}),
            "cover_letter_document": forms.FileInput(attrs={"accept": "application/pdf,.pdf"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and not self.instance.pk and self.initial.get("laws_and_articles"):
            self.fields["laws_and_articles"].initial = self.initial["laws_and_articles"]


class VictimForm(forms.ModelForm):
    identity_type = forms.ChoiceField(label="Identitas", choices=IDENTITY_CHOICES, required=False)
    religion = forms.ChoiceField(label="Agama", choices=RELIGION_CHOICES, required=False)
    nationality = forms.ChoiceField(label="Kewarganegaraan", choices=COUNTRY_CHOICES, required=False, initial="Indonesia")
    marital_status = forms.ChoiceField(label="Status Nikah", choices=MARITAL_STATUS_CHOICES, required=False)
    education = forms.ChoiceField(label="Pendidikan", choices=EDUCATION_CHOICES, required=False)
    occupation = forms.ChoiceField(label="Pekerjaan", choices=OCCUPATION_CHOICES, required=False)
    relationship = forms.ChoiceField(label="Hubungan Korban", choices=VICTIM_RELATIONSHIP_CHOICES, required=False)
    disability_types = forms.MultipleChoiceField(
        label="Disabilitas",
        choices=DISABILITY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Victim
        exclude = ("spdp", "sequence")
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        selected = self.instance.disability_types if self.instance and self.instance.pk else self.initial.get("disability_types", "")
        if isinstance(selected, str):
            self.initial["disability_types"] = [item.strip() for item in selected.split(",") if item.strip()]

    def clean_disability_types(self):
        return ", ".join(self.cleaned_data.get("disability_types") or [])


VictimFormSet = inlineformset_factory(
    SPDP, Victim, form=VictimForm, extra=1, can_delete=True, min_num=0, validate_min=False
)


class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipt
        exclude = ("spdp", "sequence")
        widgets = {
            "cover_letter_date": forms.DateInput(attrs={"type": "date"}),
            "received_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "issued_date": forms.DateInput(attrs={"type": "date"}),
            "recipient_name": forms.HiddenInput(),
            "recipient_rank": forms.TextInput(attrs={"readonly": True}),
            "recipient_position": forms.TextInput(attrs={"readonly": True}),
            "recipient_nip": forms.TextInput(attrs={"readonly": True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial["receipt_type"] = ""
        self.fields["recipient_user"].queryset = User.objects.filter(
            is_active=True,
            roles__code=Role.PROSECUTOR,
        ).distinct().order_by("first_name", "last_name", "username")
        self.fields["recipient_user"].empty_label = "--- Pilih Jaksa Penerima ---"
        self.fields["recipient_user"].label_from_instance = lambda user: user.display_name
        self.fields["received_at"].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean(self):
        cleaned_data = super().clean()
        recipient = cleaned_data.get("recipient_user")
        if recipient:
            cleaned_data["recipient_name"] = recipient.display_name
            cleaned_data["recipient_rank"] = recipient.rank
            cleaned_data["recipient_position"] = "Jaksa Penuntut Umum"
            cleaned_data["recipient_nip"] = recipient.nip
            self.instance.recipient_name = recipient.display_name
            self.instance.recipient_rank = recipient.rank
            self.instance.recipient_position = "Jaksa Penuntut Umum"
            self.instance.recipient_nip = recipient.nip
        return cleaned_data

    def has_changed(self):
        changed = super().has_changed()
        if not changed:
            return False
        meaningful_changes = [field for field in self.changed_data if field != "receipt_type"]
        return bool(meaningful_changes)


ReceiptFormSet = inlineformset_factory(
    SPDP, Receipt, form=ReceiptForm, extra=1, can_delete=True, min_num=0, validate_min=False
)


class CaseInvestigatorForm(forms.ModelForm):
    class Meta:
        model = CaseInvestigator
        exclude = ("spdp", "sequence")
        widgets = {
            "name": forms.TextInput(attrs={
                "autocomplete": "name",
                "placeholder": "Nama lengkap penyidik",
            }),
            "phone": forms.TextInput(attrs={
                "autocomplete": "tel",
                "inputmode": "tel",
                "placeholder": "Contoh: 081234567890",
            }),
            "telegram_chat_id": forms.TextInput(attrs={
                "autocomplete": "off",
                "inputmode": "numeric",
                "placeholder": "Opsional, contoh: 123456789",
            }),
        }

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        compact = phone.replace(" ", "").replace("-", "")
        if compact and (not compact.lstrip("+").isdigit() or len(compact.lstrip("+")) < 8):
            raise forms.ValidationError("Nomor HP penyidik tidak valid.")
        return phone


CaseInvestigatorFormSet = inlineformset_factory(
    SPDP, CaseInvestigator, form=CaseInvestigatorForm,
    extra=1, can_delete=True, min_num=0, validate_min=False,
)


class UserDisplayChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        details = [value for value in (user.rank, f"NIP {user.nip}" if user.nip else "") if value]
        return f"{user.display_name}{' — ' + ', '.join(details) if details else ''}"


class ProsecutorMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, user):
        details = [value for value in (user.rank, f"NIP {user.nip}" if user.nip else "") if value]
        return f"{user.display_name}{' — ' + ', '.join(details) if details else ''}"


class P16DraftForm(forms.ModelForm):
    prosecutors = ProsecutorMultipleChoiceField(
        label="Jaksa Penuntut",
        queryset=User.objects.none(),
        required=False,
        widget=forms.MultipleHiddenInput,
    )
    administrative_staff = ProsecutorMultipleChoiceField(
        label="Petugas Administrasi",
        queryset=User.objects.none(),
        required=False,
        widget=forms.MultipleHiddenInput,
    )

    class Meta:
        model = P16Draft
        fields = (
            "draft_number",
            "manual_number",
            "letter_date",
            "acting_type",
            "acting_name",
            "acting_position",
            "acting_nip",
            "consideration_html",
            "legal_basis_html",
            "offense_summary_html",
            "recipient_html",
            "instruction_html",
            "barcode_image",
            "copies_html",
            "administration_legal_basis_html",
            "administration_consideration_html",
            "administration_instruction_html",
            "administration_copies_html",
        )
        widgets = {
            "draft_number": forms.TextInput(attrs={"data-p16-number": "", "autocomplete": "off"}),
            "manual_number": forms.CheckboxInput(attrs={"data-p16-manual-number": ""}),
            "letter_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "acting_type": forms.HiddenInput(attrs={"data-p16-acting-type": ""}),
            "acting_name": forms.TextInput(attrs={"data-p16-acting-input": "name", "placeholder": "Nama lengkap dan gelar"}),
            "acting_position": forms.TextInput(attrs={"data-p16-acting-input": "position", "placeholder": "Contoh: Jaksa Madya"}),
            "acting_nip": forms.TextInput(attrs={"data-p16-acting-input": "nip", "placeholder": "NIP pejabat"}),
            "consideration_html": forms.Textarea(attrs={"data-p16-rich-editor": "consideration", "rows": 8}),
            "legal_basis_html": forms.Textarea(attrs={"data-p16-rich-editor": "legal-basis", "rows": 10}),
            "offense_summary_html": forms.Textarea(attrs={"data-p16-rich-editor": "offense-summary", "rows": 6}),
            "recipient_html": forms.Textarea(attrs={"data-p16-rich-editor": "recipient", "rows": 5}),
            "instruction_html": forms.Textarea(attrs={"data-p16-rich-editor": "instruction", "rows": 12}),
            "barcode_image": forms.ClearableFileInput(attrs={"accept": "image/*", "data-p16-barcode-input": ""}),
            "copies_html": forms.Textarea(attrs={"data-p16-rich-editor": "copies", "rows": 7}),
            "administration_legal_basis_html": forms.Textarea(attrs={"data-p16-rich-editor": "administration-legal-basis", "rows": 10}),
            "administration_consideration_html": forms.Textarea(attrs={"data-p16-rich-editor": "administration-consideration", "rows": 8}),
            "administration_instruction_html": forms.Textarea(attrs={"data-p16-rich-editor": "administration-instruction", "rows": 8}),
            "administration_copies_html": forms.Textarea(attrs={"data-p16-rich-editor": "administration-copies", "rows": 5}),
        }

    def __init__(self, *args, assignment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment or getattr(self.instance, "assignment", None)
        self.fields["letter_date"].input_formats = ["%Y-%m-%d"]
        self.fields["draft_number"].label = "Nomor urut"
        self.fields["draft_number"].widget.attrs.update({
            "inputmode": "numeric",
            "pattern": "[0-9]+[A-Za-z]?",
            "placeholder": "Contoh: 1169",
            "maxlength": "20",
        })
        self.fields["manual_number"].widget = forms.HiddenInput()
        self.number_region_code, self.number_letter_code = p16_number_parts(self.assignment)
        if not self.is_bound:
            self.initial["draft_number"] = extract_p16_sequence(self.instance.draft_number)
        self.fields["barcode_image"].label = "Upload Barcode/QR"
        assigned_ids = []
        administrative_staff_ids = []
        if self.assignment:
            assigned_ids = list(self.assignment.prosecutors.values_list("pk", flat=True))
            administrative_staff_ids = list(self.assignment.administrative_staff.values_list("pk", flat=True))
        self.fields["prosecutors"].queryset = User.objects.filter(
            Q(is_active=True, roles__code=Role.PROSECUTOR) | Q(pk__in=assigned_ids)
        ).distinct().order_by("first_name", "last_name", "username")
        self.fields["administrative_staff"].queryset = User.objects.filter(
            Q(is_active=True, roles__code=Role.EMPLOYEE) | Q(pk__in=administrative_staff_ids)
        ).distinct().order_by("first_name", "last_name", "username")
        if self.assignment and not self.is_bound:
            self.initial["prosecutors"] = assigned_ids
            self.initial["administrative_staff"] = administrative_staff_ids

    def clean(self):
        cleaned_data = super().clean()
        acting_type = cleaned_data.get("acting_type")
        acting_fields = (
            ("acting_name", "Nama pejabat pelaksana wajib diisi saat PLT/PLH dipilih."),
            ("acting_position", "Jabatan/Pangkat pejabat pelaksana wajib diisi saat PLT/PLH dipilih."),
            ("acting_nip", "NIP pejabat pelaksana wajib diisi saat PLT/PLH dipilih."),
        )
        if acting_type:
            for field_name, message in acting_fields:
                if not (cleaned_data.get(field_name) or "").strip():
                    self.add_error(field_name, message)
        else:
            for field_name, _message in acting_fields:
                cleaned_data[field_name] = ""
        try:
            cleaned_data["draft_number"] = build_p16_number(
                cleaned_data.get("draft_number"),
                cleaned_data.get("letter_date"),
                self.assignment,
            )
            cleaned_data["manual_number"] = False
        except P16NumberingError as error:
            self.add_error("draft_number", str(error))
        return cleaned_data

    def _clean_rich_html(self, field_name):
        value = self.cleaned_data.get(field_name, "")
        if len(value.encode("utf-8")) > 1024 * 1024:
            raise forms.ValidationError("Isi bagian ini maksimal 1 MB.")
        cleaned = sanitize_p16_html(value)
        if not strip_tags(cleaned).strip():
            raise forms.ValidationError("Bagian ini tidak boleh kosong.")
        return cleaned

    def clean_consideration_html(self):
        return self._clean_rich_html("consideration_html")

    def clean_legal_basis_html(self):
        return self._clean_rich_html("legal_basis_html")

    def clean_offense_summary_html(self):
        return self._clean_rich_html("offense_summary_html")

    def clean_recipient_html(self):
        return self._clean_rich_html("recipient_html")

    def clean_instruction_html(self):
        return self._clean_rich_html("instruction_html")

    def clean_copies_html(self):
        return self._clean_rich_html("copies_html")

    def clean_administration_legal_basis_html(self):
        return self._clean_rich_html("administration_legal_basis_html")

    def clean_administration_consideration_html(self):
        return self._clean_rich_html("administration_consideration_html")

    def clean_administration_instruction_html(self):
        return self._clean_rich_html("administration_instruction_html")

    def clean_administration_copies_html(self):
        return self._clean_rich_html("administration_copies_html")


class P17SPDPChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, spdp):
        suspects = ", ".join(spdp.suspects.values_list("name", flat=True)) or "Tanpa data pelaku"
        return f"{spdp.letter_number} — {suspects}"


class P17CreateForm(forms.Form):
    spdp = P17SPDPChoiceField(label="Perkara / SPDP", queryset=SPDP.objects.none())

    def __init__(self, *args, queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["spdp"].queryset = queryset if queryset is not None else SPDP.objects.none()


ACTING_SIGNATORY_FIELDS = (
    "acting_type", "acting_name", "acting_position", "acting_nip",
)
ACTING_SIGNATORY_WIDGETS = {
    "acting_type": forms.HiddenInput(attrs={"data-acting-type": ""}),
    "acting_name": forms.TextInput(attrs={
        "data-acting-input": "name", "placeholder": "Nama lengkap dan gelar",
    }),
    "acting_position": forms.TextInput(attrs={
        "data-acting-input": "position", "placeholder": "Contoh: Jaksa Madya",
    }),
    "acting_nip": forms.TextInput(attrs={
        "data-acting-input": "nip", "placeholder": "NIP pejabat",
    }),
}


class ActingSignatoryFormMixin:
    def clean(self):
        cleaned_data = super().clean()
        acting_type = cleaned_data.get("acting_type")
        if acting_type not in ("", "plt", "plh", None):
            self.add_error("acting_type", "Pilihan PLT/PLH tidak valid.")
        if acting_type:
            required_fields = (
                ("acting_name", "Nama pejabat pelaksana wajib diisi saat PLT/PLH dipilih."),
                ("acting_position", "Jabatan/Pangkat wajib diisi saat PLT/PLH dipilih."),
                ("acting_nip", "NIP pejabat pelaksana wajib diisi saat PLT/PLH dipilih."),
            )
            for field_name, message in required_fields:
                if not (cleaned_data.get(field_name) or "").strip():
                    self.add_error(field_name, message)
        else:
            for field_name in ("acting_name", "acting_position", "acting_nip"):
                cleaned_data[field_name] = ""
        return cleaned_data


class P17DraftForm(ActingSignatoryFormMixin, forms.ModelForm):
    recipients_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"data-p17-recipients-json": ""}),
    )

    class Meta:
        model = P17Draft
        fields = (
            "letter_number", "manual_number", "letter_date", "letter_nature",
            "attachment", "subject_html", "recipient_html", "body_html", "copies_html",
            "barcode_image", *ACTING_SIGNATORY_FIELDS,
        )
        widgets = {
            "letter_number": forms.TextInput(attrs={"data-p17-number": "", "autocomplete": "off"}),
            "manual_number": forms.CheckboxInput(attrs={"data-p17-manual-number": ""}),
            "letter_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "subject_html": forms.TextInput(attrs={
                "data-p17-subject": "",
                "autocomplete": "off",
                "placeholder": "Contoh: Permintaan Perkembangan Hasil Penyidikan Pertama...",
            }),
            "recipient_html": forms.HiddenInput(),
            "body_html": forms.Textarea(attrs={"data-p17-rich-editor": "body", "rows": 13}),
            "copies_html": forms.Textarea(attrs={"data-p17-rich-editor": "copies", "rows": 7}),
            "barcode_image": forms.ClearableFileInput(attrs={"accept": "image/*", "data-p17-barcode-input": ""}),
            **ACTING_SIGNATORY_WIDGETS,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["letter_date"].input_formats = ["%Y-%m-%d"]
        self.number_region_code, self.number_letter_code = p17_number_parts(self.instance.spdp)
        self.fields["letter_number"].label = "Nomor urut"
        self.fields["letter_number"].widget.attrs.update({
            "inputmode": "numeric", "pattern": "[0-9]+", "placeholder": "Contoh: 11", "maxlength": "20",
        })
        self.fields["manual_number"].widget = forms.HiddenInput()
        if not self.is_bound:
            self.initial["letter_number"] = extract_p17_sequence(self.instance.letter_number)
        self.fields["barcode_image"].label = "Upload Barcode/QR"
        if self.instance and self.instance.pk and not self.is_bound:
            self.initial["subject_html"] = unescape(strip_tags(self.instance.subject_html or "")).strip()
            self.initial["recipients_json"] = json.dumps(
                p17_recipients_for_editor(self.instance), ensure_ascii=False,
            )

    def clean(self):
        cleaned_data = super().clean()
        try:
            cleaned_data["letter_number"] = build_p17_number(
                cleaned_data.get("letter_number"), cleaned_data.get("letter_date"), self.instance.spdp,
            )
            cleaned_data["manual_number"] = False
        except P17NumberingError as error:
            self.add_error("letter_number", str(error))
        return cleaned_data

    def _clean_rich_html(self, field_name):
        value = self.cleaned_data.get(field_name, "")
        if len(value.encode("utf-8")) > 1024 * 1024:
            raise forms.ValidationError("Isi bagian ini maksimal 1 MB.")
        cleaned = sanitize_p16_html(value)
        if not strip_tags(cleaned).strip():
            raise forms.ValidationError("Bagian ini tidak boleh kosong.")
        return cleaned

    def clean_subject_html(self):
        value = unescape(strip_tags(self.cleaned_data.get("subject_html", ""))).strip()
        if not value:
            raise forms.ValidationError("Perihal tidak boleh kosong.")
        if len(value) > 1000:
            raise forms.ValidationError("Perihal maksimal 1.000 karakter.")
        return value

    def clean_recipient_html(self):
        try:
            raw_recipients = self.data.get("recipients_json")
            if raw_recipients is None:
                recipients = p17_recipients_for_editor(self.instance)
            else:
                recipients = normalize_p17_recipients(json.loads(raw_recipients or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            raise forms.ValidationError("Daftar tujuan surat tidak valid.")
        if not recipients:
            raise forms.ValidationError("Tambahkan minimal satu tujuan surat.")
        return render_p17_recipients(recipients)

    def clean_body_html(self):
        return self._clean_rich_html("body_html")

    def clean_copies_html(self):
        return self._clean_rich_html("copies_html")


class SOPProsecutorSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        prosecutor = getattr(value, "instance", None)
        if prosecutor is not None:
            option["attrs"].update({
                "data-prosecutor-name": prosecutor.display_name,
                "data-prosecutor-rank": prosecutor.rank or "",
                "data-prosecutor-nip": prosecutor.nip or "",
            })
        return option


class SOPProsecutorChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        details = [value for value in (user.rank, f"NIP {user.nip}" if user.nip else "") if value]
        return f"{user.display_name}{' — ' + ', '.join(details) if details else ''}"


class SOPForm1BDraftForm(forms.ModelForm):
    prosecutor_choice = SOPProsecutorChoiceField(
        label="Penandatangan",
        queryset=User.objects.none(),
        required=False,
        empty_label=None,
        widget=SOPProsecutorSelect(attrs={"data-sop1b-prosecutor-choice": ""}),
    )

    class Meta:
        model = SOPForm1BDraft
        fields = (
            "report_date", "recipient", "sender", "attachment", "subject",
            "legal_basis_html", "facts_html", "legal_analysis_html",
            "conclusion_html", "closing", "prosecutor_name", "prosecutor_rank",
            "prosecutor_nip", "kasi_opinion_html", "leader_instruction_html", "barcode_image",
        )
        widgets = {
            "report_date": forms.DateInput(attrs={"type": "date", "data-sop1b-input": "date"}, format="%Y-%m-%d"),
            "recipient": forms.TextInput(attrs={"data-sop1b-input": "recipient"}),
            "sender": forms.Textarea(attrs={"data-sop1b-input": "sender", "rows": 3}),
            "attachment": forms.TextInput(attrs={"data-sop1b-input": "attachment"}),
            "subject": forms.Textarea(attrs={"data-sop1b-input": "subject", "rows": 4}),
            "legal_basis_html": forms.Textarea(attrs={"data-sop1b-rich-editor": "legal-basis", "rows": 10}),
            "facts_html": forms.Textarea(attrs={"data-sop1b-rich-editor": "facts", "rows": 10}),
            "legal_analysis_html": forms.Textarea(attrs={"data-sop1b-rich-editor": "legal-analysis", "rows": 10}),
            "conclusion_html": forms.Textarea(attrs={"data-sop1b-rich-editor": "conclusion", "rows": 10}),
            "closing": forms.Textarea(attrs={"data-sop1b-input": "closing", "rows": 3}),
            "prosecutor_name": forms.TextInput(attrs={"data-sop1b-input": "prosecutor-name"}),
            "prosecutor_rank": forms.TextInput(attrs={"data-sop1b-input": "prosecutor-rank"}),
            "prosecutor_nip": forms.TextInput(attrs={"data-sop1b-input": "prosecutor-nip"}),
            "kasi_opinion_html": forms.Textarea(attrs={"data-sop1b-rich-editor": "kasi-opinion", "rows": 6}),
            "leader_instruction_html": forms.Textarea(attrs={"data-sop1b-rich-editor": "leader-instruction", "rows": 6}),
            "barcode_image": forms.ClearableFileInput(attrs={"accept": "image/*", "data-sop1b-barcode-input": ""}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["report_date"].input_formats = ["%Y-%m-%d"]
        self.fields["barcode_image"].label = "Barcode/QR SOP Form-1B"
        assignment = None
        if self.instance and self.instance.pk:
            assignment = getattr(self.instance.p17_draft.spdp, "p16_assignment", None)
        prosecutors = assignment.prosecutors.order_by("id") if assignment else User.objects.none()
        self.fields["prosecutor_choice"].queryset = prosecutors
        if not self.is_bound:
            selected = None
            if self.instance.prosecutor_nip:
                selected = prosecutors.filter(nip=self.instance.prosecutor_nip).first()
            if selected is None and self.instance.prosecutor_name:
                selected = next(
                    (user for user in prosecutors if user.display_name == self.instance.prosecutor_name),
                    None,
                )
            selected = selected or prosecutors.first()
            if selected:
                self.initial["prosecutor_choice"] = selected.pk

    def clean(self):
        cleaned_data = super().clean()
        prosecutor = cleaned_data.get("prosecutor_choice")
        if prosecutor:
            cleaned_data["prosecutor_name"] = prosecutor.display_name
            cleaned_data["prosecutor_rank"] = prosecutor.rank or ""
            cleaned_data["prosecutor_nip"] = prosecutor.nip or ""
        return cleaned_data

    def _clean_rich_html(self, field_name, required=True):
        value = self.cleaned_data.get(field_name, "")
        if len(value.encode("utf-8")) > 1024 * 1024:
            raise forms.ValidationError("Isi bagian ini maksimal 1 MB.")
        cleaned = sanitize_p16_html(value)
        if required and not strip_tags(cleaned).strip():
            raise forms.ValidationError("Bagian ini tidak boleh kosong.")
        return cleaned

    def clean_legal_basis_html(self):
        return self._clean_rich_html("legal_basis_html")

    def clean_facts_html(self):
        return self._clean_rich_html("facts_html")

    def clean_legal_analysis_html(self):
        return self._clean_rich_html("legal_analysis_html")

    def clean_conclusion_html(self):
        return self._clean_rich_html("conclusion_html")

    def clean_kasi_opinion_html(self):
        return self._clean_rich_html("kasi_opinion_html", required=False)

    def clean_leader_instruction_html(self):
        return self._clean_rich_html("leader_instruction_html", required=False)


def _clean_structured_recipients(form):
    try:
        raw = form.data.get("recipients_json")
        recipients = p17_recipients_for_editor(form.instance) if raw is None else normalize_p17_recipients(json.loads(raw or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        raise forms.ValidationError("Daftar tujuan surat tidak valid.")
    if not recipients:
        raise forms.ValidationError("Tambahkan minimal satu tujuan surat.")
    return render_p17_recipients(recipients)


class P21SPDPChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, spdp):
        suspects = ", ".join(spdp.suspects.values_list("name", flat=True)) or "Tanpa data pelaku"
        return f"{spdp.letter_number} — {suspects}"


class P21CreateForm(forms.Form):
    spdp = P21SPDPChoiceField(label="Perkara / SPDP", queryset=SPDP.objects.none())

    def __init__(self, *args, queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["spdp"].queryset = queryset if queryset is not None else SPDP.objects.none()


class P21DraftForm(ActingSignatoryFormMixin, forms.ModelForm):
    recipients_json = forms.CharField(required=False, widget=forms.HiddenInput(attrs={"data-p21-recipients-json": ""}))

    class Meta:
        model = P21Draft
        fields = (
            "letter_number", "manual_number", "letter_date", "letter_nature", "attachment",
            "subject_html", "recipient_html", "legal_basis_html", "body_html", "copies_html", "barcode_image",
            *ACTING_SIGNATORY_FIELDS,
        )
        widgets = {
            "letter_number": forms.TextInput(attrs={"data-p21-number": "", "autocomplete": "off"}),
            "manual_number": forms.CheckboxInput(attrs={"data-p21-manual-number": ""}),
            "letter_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "subject_html": forms.TextInput(attrs={
                "data-p21-subject": "", "autocomplete": "off", "placeholder": "Masukkan perihal surat",
            }),
            "recipient_html": forms.HiddenInput(),
            "legal_basis_html": forms.Textarea(attrs={"data-p21-rich-editor": "legal-basis", "rows": 12}),
            "body_html": forms.Textarea(attrs={"data-p21-rich-editor": "body", "rows": 16}),
            "copies_html": forms.Textarea(attrs={"data-p21-rich-editor": "copies", "rows": 7}),
            "barcode_image": forms.ClearableFileInput(attrs={"accept": "image/*", "data-p21-barcode-input": ""}),
            **ACTING_SIGNATORY_WIDGETS,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["letter_date"].input_formats = ["%Y-%m-%d"]
        self.number_region_code, self.number_letter_code = p17_number_parts(self.instance.spdp)
        self.fields["letter_number"].label = "Nomor urut"
        self.fields["letter_number"].widget.attrs.update({
            "inputmode": "numeric", "pattern": "[0-9]+",
            "placeholder": "Contoh: 4704", "maxlength": "20",
        })
        self.fields["manual_number"].widget = forms.HiddenInput()
        self.fields["barcode_image"].label = "Upload Barcode/QR"
        if self.instance.pk and not self.is_bound:
            self.initial["letter_number"] = extract_p17_sequence(self.instance.letter_number)
            self.initial["subject_html"] = unescape(strip_tags(self.instance.subject_html or "")).strip()
        if self.instance.pk and not self.is_bound:
            self.initial["recipients_json"] = json.dumps(p17_recipients_for_editor(self.instance), ensure_ascii=False)

    def clean(self):
        cleaned_data = super().clean()
        try:
            cleaned_data["letter_number"] = build_p17_number(
                cleaned_data.get("letter_number"), cleaned_data.get("letter_date"), self.instance.spdp,
            )
            cleaned_data["manual_number"] = False
        except P17NumberingError as error:
            self.add_error("letter_number", str(error))
        return cleaned_data

    def _clean_rich_html(self, field_name):
        value = self.cleaned_data.get(field_name, "")
        if len(value.encode("utf-8")) > 1024 * 1024:
            raise forms.ValidationError("Isi bagian ini maksimal 1 MB.")
        cleaned = sanitize_p16_html(value)
        if not strip_tags(cleaned).strip():
            raise forms.ValidationError("Bagian ini tidak boleh kosong.")
        return cleaned

    def clean_subject_html(self):
        value = unescape(strip_tags(self.cleaned_data.get("subject_html", ""))).strip()
        if not value:
            raise forms.ValidationError("Perihal tidak boleh kosong.")
        if len(value) > 1000:
            raise forms.ValidationError("Perihal maksimal 1.000 karakter.")
        return value

    def clean_legal_basis_html(self):
        return self._clean_rich_html("legal_basis_html")

    def clean_body_html(self):
        return self._clean_rich_html("body_html")

    def clean_copies_html(self):
        return self._clean_rich_html("copies_html")

    def clean_recipient_html(self):
        return _clean_structured_recipients(self)


class SOPFormSPDPChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, spdp):
        suspects = ", ".join(spdp.suspects.values_list("name", flat=True)) or "Tanpa data pelaku"
        return f"{spdp.letter_number} — {suspects}"


class SOPFormCreateForm(forms.Form):
    spdp = SOPFormSPDPChoiceField(label="Perkara / SPDP", queryset=SPDP.objects.none())

    def __init__(self, *args, queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["spdp"].queryset = queryset if queryset is not None else SPDP.objects.none()


class SOPDraftFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["letter_date"].input_formats = ["%Y-%m-%d"]
        self.fields["letter_number"].label = "Nomor urut"
        self.fields["letter_number"].widget.attrs.update({
            "inputmode": "numeric", "pattern": "[0-9]+", "placeholder": "Contoh: 11", "maxlength": "20",
        })
        self.fields["manual_number"].widget = forms.HiddenInput()
        self.number_region_code, self.number_letter_code = p17_number_parts(self.instance.spdp)
        if not self.is_bound:
            self.initial["letter_number"] = extract_p17_sequence(self.instance.letter_number)
            self.initial["subject_html"] = unescape(strip_tags(self.instance.subject_html or "")).strip()
            if self.instance.pk:
                recipients = p17_recipients_for_editor(self.instance)
                if not recipients:
                    recipients = [{
                        "recipient": f"Kepala {self.instance.spdp.investigating_unit or self.instance.spdp.investigator_agency}",
                        "place": "Singaraja",
                    }]
                self.initial["recipients_json"] = json.dumps(recipients, ensure_ascii=False)
        self.fields["barcode_image"].label = "Upload Barcode/QR"

    def clean(self):
        cleaned_data = super().clean()
        submitted_number = (cleaned_data.get("letter_number") or "").strip()
        # Tetap menerima nomor draf lama pada request lama/API, tetapi editor baru
        # selalu menampilkan dan menerima nomor urut seperti P-17.
        if submitted_number == self.instance.letter_number and submitted_number.startswith("DRAFT/"):
            cleaned_data["manual_number"] = False
            return cleaned_data
        sequence = extract_p17_sequence(submitted_number) or submitted_number
        try:
            cleaned_data["letter_number"] = build_p17_number(
                sequence, cleaned_data.get("letter_date"), self.instance.spdp,
            )
            cleaned_data["manual_number"] = False
        except P17NumberingError as error:
            self.add_error("letter_number", str(error))
        return cleaned_data

    def _clean_rich_html(self, field_name):
        value = self.cleaned_data.get(field_name, "")
        if len(value.encode("utf-8")) > 1024 * 1024:
            raise forms.ValidationError("Isi bagian ini maksimal 1 MB.")
        cleaned = sanitize_p16_html(value)
        if not strip_tags(cleaned).strip():
            raise forms.ValidationError("Bagian ini tidak boleh kosong.")
        return cleaned

    def clean_subject_html(self):
        value = unescape(strip_tags(self.cleaned_data.get("subject_html", ""))).strip()
        if not value:
            raise forms.ValidationError("Perihal tidak boleh kosong.")
        if len(value) > 1000:
            raise forms.ValidationError("Perihal maksimal 1.000 karakter.")
        return value

    def clean_body_html(self):
        return self._clean_rich_html("body_html")

    def clean_copies_html(self):
        return self._clean_rich_html("copies_html")

    def clean_recipient_html(self):
        try:
            raw_recipients = self.data.get("recipients_json")
            if raw_recipients is None:
                recipients = p17_recipients_for_editor(self.instance)
            else:
                recipients = normalize_p17_recipients(json.loads(raw_recipients or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            raise forms.ValidationError("Daftar tujuan surat tidak valid.")
        if not recipients:
            raise forms.ValidationError("Tambahkan minimal satu tujuan surat.")
        return render_p17_recipients(recipients)


SOP_DRAFT_WIDGETS = {
    "letter_number": forms.TextInput(attrs={"data-sop-number": "", "autocomplete": "off"}),
    "manual_number": forms.CheckboxInput(attrs={"data-sop-manual-number": ""}),
    "letter_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    "subject_html": forms.TextInput(attrs={
        "data-sop-subject": "", "autocomplete": "off", "placeholder": "Masukkan perihal surat",
    }),
    "recipient_html": forms.HiddenInput(),
    "body_html": forms.Textarea(attrs={"data-sop-rich-editor": "body", "rows": 14}),
    "copies_html": forms.Textarea(attrs={"data-sop-rich-editor": "copies", "rows": 7}),
    "barcode_image": forms.ClearableFileInput(attrs={"accept": "image/*", "data-sop-barcode-input": ""}),
}


class SOPForm02DraftForm(SOPDraftFormMixin, ActingSignatoryFormMixin, forms.ModelForm):
    recipients_json = forms.CharField(required=False, widget=forms.HiddenInput(attrs={"data-sop-recipients-json": ""}))

    class Meta:
        model = SOPForm02Draft
        fields = ("letter_number", "manual_number", "letter_date", "letter_nature", "attachment", "subject_html", "recipient_html", "body_html", "copies_html", "barcode_image", *ACTING_SIGNATORY_FIELDS)
        widgets = {**SOP_DRAFT_WIDGETS, **ACTING_SIGNATORY_WIDGETS}


class SOPForm03DraftForm(SOPDraftFormMixin, ActingSignatoryFormMixin, forms.ModelForm):
    recipients_json = forms.CharField(required=False, widget=forms.HiddenInput(attrs={"data-sop-recipients-json": ""}))

    class Meta:
        model = SOPForm03Draft
        fields = ("letter_number", "manual_number", "letter_date", "letter_nature", "attachment", "subject_html", "recipient_html", "body_html", "copies_html", "barcode_image", *ACTING_SIGNATORY_FIELDS)
        widgets = {**SOP_DRAFT_WIDGETS, **ACTING_SIGNATORY_WIDGETS}


class CaseDocumentDraftForm(ActingSignatoryFormMixin, forms.ModelForm):
    recipients_json = forms.CharField(required=False, widget=forms.HiddenInput(attrs={"data-document-recipients-json": ""}))

    class Meta:
        model = CaseDocumentDraft
        fields = ("letter_number", "manual_number", "letter_date", "letter_nature", "attachment", "subject_html", "recipient_html", "legal_basis_html", "body_html", "copies_html", "barcode_image", *ACTING_SIGNATORY_FIELDS)
        widgets = {
            "letter_number": forms.TextInput(attrs={"data-document-number": "", "autocomplete": "off"}),
            "manual_number": forms.CheckboxInput(attrs={"data-document-manual-number": ""}),
            "letter_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "subject_html": forms.TextInput(attrs={
                "data-document-subject": "", "autocomplete": "off", "placeholder": "Masukkan perihal surat",
            }),
            "recipient_html": forms.HiddenInput(),
            "legal_basis_html": forms.Textarea(attrs={"data-document-rich-editor": "legal-basis", "rows": 11}),
            "body_html": forms.Textarea(attrs={"data-document-rich-editor": "body", "rows": 18}),
            "copies_html": forms.Textarea(attrs={"data-document-rich-editor": "copies", "rows": 7}),
            "barcode_image": forms.ClearableFileInput(attrs={"accept": "image/*", "data-document-barcode-input": ""}),
            **ACTING_SIGNATORY_WIDGETS,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["letter_date"].input_formats = ["%Y-%m-%d"]
        self.number_region_code, self.number_letter_code = p17_number_parts(self.instance.spdp)
        self.fields["barcode_image"].label = "Upload Barcode/QR"
        if self.instance.pk and not self.is_bound:
            self.initial["subject_html"] = unescape(strip_tags(self.instance.subject_html or "")).strip()
        if self.instance.pk and not self.is_bound:
            self.initial["recipients_json"] = json.dumps(p17_recipients_for_editor(self.instance), ensure_ascii=False)
        if self.instance.document_type in (
            CaseDocumentDraft.DocumentType.P18,
            CaseDocumentDraft.DocumentType.P19,
            CaseDocumentDraft.DocumentType.P20,
            CaseDocumentDraft.DocumentType.SOP_FORM_07,
        ):
            self.fields["letter_number"].label = "Nomor urut"
            self.fields["letter_number"].widget.attrs.update({
                "inputmode": "numeric", "pattern": "[0-9]+",
                "placeholder": "Contoh: 3478", "maxlength": "20",
            })
            self.fields["manual_number"].widget = forms.HiddenInput()
            self.fields["barcode_image"].label = "Upload Barcode/QR"
            if not self.is_bound:
                self.initial["letter_number"] = extract_p17_sequence(self.instance.letter_number)

    def clean(self):
        cleaned = super().clean()
        if self.instance.document_type in (
            CaseDocumentDraft.DocumentType.P18,
            CaseDocumentDraft.DocumentType.P19,
            CaseDocumentDraft.DocumentType.P20,
            CaseDocumentDraft.DocumentType.SOP_FORM_07,
        ):
            try:
                cleaned["letter_number"] = build_p17_number(
                    cleaned.get("letter_number"), cleaned.get("letter_date"), self.instance.spdp,
                )
                cleaned["manual_number"] = False
            except P17NumberingError as error:
                self.add_error("letter_number", str(error))
        elif cleaned.get("manual_number"):
            if not cleaned.get("letter_number", "").strip():
                self.add_error("letter_number", "Nomor surat wajib diisi saat mode manual digunakan.")
        else:
            cleaned["letter_number"] = self.initial.get("letter_number", self.instance.letter_number)
        return cleaned

    def _clean_html(self, name):
        value = self.cleaned_data.get(name, "")
        if len(value.encode("utf-8")) > 1024 * 1024:
            raise forms.ValidationError("Isi bagian ini maksimal 1 MB.")
        cleaned = sanitize_p16_html(value)
        if not strip_tags(cleaned).strip():
            raise forms.ValidationError("Bagian ini tidak boleh kosong.")
        return cleaned

    def clean_recipient_html(self):
        return _clean_structured_recipients(self)

    def clean_subject_html(self):
        value = unescape(strip_tags(self.cleaned_data.get("subject_html", ""))).strip()
        if not value:
            raise forms.ValidationError("Perihal tidak boleh kosong.")
        if len(value) > 1000:
            raise forms.ValidationError("Perihal maksimal 1.000 karakter.")
        return value

    def clean_legal_basis_html(self):
        if self.instance.document_type == CaseDocumentDraft.DocumentType.P19:
            return ""
        return self._clean_html("legal_basis_html")
    def clean_body_html(self): return self._clean_html("body_html")
    def clean_copies_html(self): return self._clean_html("copies_html")


class CoordinationMinutesDraftForm(forms.ModelForm):
    class Meta:
        model = CoordinationMinutesDraft
        fields = (
            "meeting_date", "meeting_place",
            "prosecutor_name", "prosecutor_rank", "prosecutor_nip",
            "investigator_name", "investigator_rank", "investigator_nrp", "investigator_position",
            "investigator_supervisor_title", "investigator_supervisor_name",
            "investigator_supervisor_rank", "investigator_supervisor_nrp",
            "prosecutor_supervisor_title", "prosecutor_supervisor_name",
            "prosecutor_supervisor_rank", "prosecutor_supervisor_nip",
            "body_html", "barcode_image", "documentation_image_1", "documentation_image_2", "documentation_image_3",
        )
        widgets = {
            "meeting_date": forms.DateInput(attrs={"type": "date", "data-coordination-date": ""}, format="%Y-%m-%d"),
            "meeting_place": forms.TextInput(attrs={"data-coordination-output-input": "meeting-place"}),
            "prosecutor_name": forms.TextInput(attrs={"data-coordination-output-input": "prosecutor-name"}),
            "prosecutor_rank": forms.TextInput(attrs={"data-coordination-output-input": "prosecutor-rank"}),
            "prosecutor_nip": forms.TextInput(attrs={"data-coordination-output-input": "prosecutor-nip"}),
            "investigator_name": forms.TextInput(attrs={"data-coordination-output-input": "investigator-name"}),
            "investigator_rank": forms.TextInput(attrs={"data-coordination-output-input": "investigator-rank"}),
            "investigator_nrp": forms.TextInput(attrs={"data-coordination-output-input": "investigator-nrp"}),
            "investigator_position": forms.TextInput(attrs={"data-coordination-output-input": "investigator-position"}),
            "investigator_supervisor_title": forms.TextInput(attrs={"data-coordination-output-input": "investigator-supervisor-title"}),
            "investigator_supervisor_name": forms.TextInput(attrs={"data-coordination-output-input": "investigator-supervisor-name"}),
            "investigator_supervisor_rank": forms.TextInput(attrs={"data-coordination-output-input": "investigator-supervisor-rank"}),
            "investigator_supervisor_nrp": forms.TextInput(attrs={"data-coordination-output-input": "investigator-supervisor-nrp"}),
            "prosecutor_supervisor_title": forms.TextInput(attrs={"data-coordination-output-input": "prosecutor-supervisor-title"}),
            "prosecutor_supervisor_name": forms.TextInput(attrs={"data-coordination-output-input": "prosecutor-supervisor-name"}),
            "prosecutor_supervisor_rank": forms.TextInput(attrs={"data-coordination-output-input": "prosecutor-supervisor-rank"}),
            "prosecutor_supervisor_nip": forms.TextInput(attrs={"data-coordination-output-input": "prosecutor-supervisor-nip"}),
            "body_html": forms.Textarea(attrs={"data-coordination-rich-editor": "body", "rows": 24}),
            "barcode_image": forms.FileInput(attrs={"accept": "image/*", "data-coordination-barcode-input": ""}),
            "documentation_image_1": forms.FileInput(attrs={"accept": "image/*", "data-coordination-image": "1"}),
            "documentation_image_2": forms.FileInput(attrs={"accept": "image/*", "data-coordination-image": "2"}),
            "documentation_image_3": forms.FileInput(attrs={"accept": "image/*", "data-coordination-image": "3"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["meeting_date"].input_formats = ["%Y-%m-%d"]

    def clean_body_html(self):
        value = self.cleaned_data.get("body_html", "")
        if len(value.encode("utf-8")) > 2 * 1024 * 1024:
            raise forms.ValidationError("Materi koordinasi maksimal 2 MB.")
        cleaned = sanitize_p16_html(value)
        if not strip_tags(cleaned).strip():
            raise forms.ValidationError("Materi koordinasi tidak boleh kosong.")
        return cleaned
