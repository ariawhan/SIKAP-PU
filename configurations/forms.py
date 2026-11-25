from django import forms
from .models import (
    InstitutionConfiguration,
    InvestigatorInstitution,
    InvestigatorUnit,
    IssueCode,
    LetterNumberCaseType,
    LetterNumberCode,
    LetterNumberConfiguration,
)


class SipedeIntegrationForm(forms.Form):
    username = forms.CharField(label="Username SIPede", max_length=150)
    password = forms.CharField(
        label="Password SIPede",
        required=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password", "placeholder": "Masukkan password SIPede"},
        ),
    )

    def __init__(self, *args, has_existing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_existing = has_existing
        if has_existing:
            self.fields["password"].widget.attrs["placeholder"] = "Kosongkan jika tidak diganti"

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if not password and not self.has_existing:
            raise forms.ValidationError("Password SIPede wajib diisi pada konfigurasi pertama.")
        return password


class CMSIntegrationForm(forms.Form):
    username = forms.CharField(label="Username CMS", max_length=150)
    password = forms.CharField(
        label="Password CMS",
        required=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password", "placeholder": "Masukkan password CMS"},
        ),
    )

    def __init__(self, *args, has_existing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_existing = has_existing
        if has_existing:
            self.fields["password"].widget.attrs["placeholder"] = "Kosongkan jika tidak diganti"

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if not password and not self.has_existing:
            raise forms.ValidationError("Password CMS wajib diisi pada konfigurasi pertama.")
        return password


class CMSAddressForm(forms.Form):
    base_url = forms.URLField(
        label="Alamat CMS",
        widget=forms.URLInput(attrs={"placeholder": "https://alamat-cms.kejaksaan.go.id"}),
    )


class InstitutionConfigurationForm(forms.ModelForm):
    class Meta:
        model = InstitutionConfiguration
        exclude = ("updated_at", "updated_by")
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class LetterNumberConfigurationForm(forms.ModelForm):
    class Meta:
        model = LetterNumberConfiguration
        exclude = ("updated_at", "updated_by")


class IssueCodeForm(forms.ModelForm):
    class Meta:
        model = IssueCode
        fields = ("code", "category", "description", "is_active")
        widgets = {
            "code": forms.TextInput(attrs={"placeholder": "Contoh: HK.01"}),
            "category": forms.TextInput(attrs={"placeholder": "Contoh: Hukum"}),
            "description": forms.TextInput(attrs={"placeholder": "Uraian kode masalah"}),
        }

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class LetterNumberCodeForm(forms.ModelForm):
    class Meta:
        model = LetterNumberCode
        fields = ("directorate", "code")
        widgets = {
            "directorate": forms.TextInput(attrs={"placeholder": "Contoh: Dir A", "autocomplete": "off"}),
            "code": forms.TextInput(attrs={"placeholder": "Contoh: Eoh", "autocomplete": "off"}),
        }

    def clean_directorate(self):
        directorate = " ".join(self.cleaned_data["directorate"].split())
        queryset = LetterNumberCode.objects.filter(directorate__iexact=directorate)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("Direktorat ini sudah terdaftar.")
        return directorate

    def clean_code(self):
        return self.cleaned_data["code"].strip()


class LetterNumberCaseTypeForm(forms.ModelForm):
    class Meta:
        model = LetterNumberCaseType
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Contoh: Narkotika", "autocomplete": "off"}),
        }

    def __init__(self, *args, letter_number=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.letter_number = letter_number or getattr(self.instance, "letter_number", None)

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if self.letter_number:
            queryset = LetterNumberCaseType.objects.filter(letter_number=self.letter_number, name__iexact=name)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError("Jenis perkara ini sudah terdaftar untuk nomor surat ini.")
        return name


class InvestigatorInstitutionForm(forms.ModelForm):
    class Meta:
        model = InvestigatorInstitution
        fields = ("name", "is_active")
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Contoh: Kepolisian Negara Republik Indonesia",
                "autocomplete": "off",
            }),
        }

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        queryset = InvestigatorInstitution.objects.filter(name__iexact=name)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("Instansi penyidik ini sudah terdaftar.")
        return name


class InvestigatorUnitForm(forms.ModelForm):
    class Meta:
        model = InvestigatorUnit
        fields = ("institution", "name", "is_active")
        widgets = {
            "institution": forms.HiddenInput(),
            "name": forms.TextInput(attrs={
                "placeholder": "Contoh: Satreskrim Polres Buleleng",
                "autocomplete": "off",
            }),
        }

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())

    def clean(self):
        cleaned = super().clean()
        institution = cleaned.get("institution")
        name = cleaned.get("name")
        if institution and name:
            queryset = InvestigatorUnit.objects.filter(institution=institution, name__iexact=name)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError("Instansi pelaksana penyidik ini sudah terdaftar di instansi tersebut.")
        return cleaned
