from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm, UserCreationForm
from .models import Role

User = get_user_model()


GRADE_CHOICES = (
    ("", "Pilih golongan"),
    ("I/a", "I/a"),
    ("I/b", "I/b"),
    ("I/c", "I/c"),
    ("I/d", "I/d"),
    ("II/a", "II/a"),
    ("II/b", "II/b"),
    ("II/c", "II/c"),
    ("II/d", "II/d"),
    ("III/a", "III/a"),
    ("III/b", "III/b"),
    ("III/c", "III/c"),
    ("III/d", "III/d"),
    ("IV/a", "IV/a"),
    ("IV/b", "IV/b"),
    ("IV/c", "IV/c"),
    ("IV/d", "IV/d"),
    ("IV/e", "IV/e"),
)


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username atau email")
    def clean(self):
        identity, password = self.cleaned_data.get("username"), self.cleaned_data.get("password")
        if identity and password:
            self.user_cache = authenticate(self.request, username=identity, password=password)
            if self.user_cache is None: raise forms.ValidationError("Username/email atau kata sandi tidak sesuai.")
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data

class StaffCreationForm(UserCreationForm):
    first_name = forms.CharField(label="Nama")
    nip = forms.CharField(label="NIP", required=False)
    nrp = forms.CharField(label="NRP", required=False)
    rank = forms.CharField(label="Pangkat", required=False, widget=forms.TextInput(attrs={"placeholder": "cth. Jaksa Utama Pratama"}))
    grade = forms.ChoiceField(label="Golongan", required=False, choices=GRADE_CHOICES)
    position = forms.CharField(label="Jabatan", required=False, widget=forms.TextInput(attrs={"placeholder": "cth. Pengelola Penanganan Perkara"}))
    email = forms.EmailField(label="Email")
    whatsapp_number = forms.CharField(label="Nomor WhatsApp", required=False, widget=forms.TextInput(attrs={"placeholder": "cth. 62812xxxx"}))
    telegram_chat_id = forms.CharField(label="ID Telegram", required=False, widget=forms.TextInput(attrs={"placeholder": "Chat ID Telegram"}))
    photo = forms.ImageField(label="Foto", required=False)
    photo_position_x = forms.IntegerField(required=False, min_value=0, max_value=100, widget=forms.HiddenInput)
    photo_position_y = forms.IntegerField(required=False, min_value=0, max_value=100, widget=forms.HiddenInput)
    roles = forms.ModelMultipleChoiceField(label="Role", queryset=Role.objects.all(), widget=forms.CheckboxSelectMultiple, help_text="Pilih satu atau beberapa role.")

    class Meta:
        model = User
        fields = ("first_name", "nip", "nrp", "rank", "grade", "position", "username", "email", "whatsapp_number", "telegram_chat_id", "photo", "photo_position_x", "photo_position_y", "roles")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"].queryset = Role.objects.all().order_by("sort_order", "name")
        self.fields["username"].help_text = "Username dicek otomatis agar tidak double."
        for name, field in self.fields.items():
            css_class = "user-field"
            if name == "roles":
                css_class = "role-choice-list"
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css_class}".strip()
        self.fields["photo"].widget.attrs.update({"accept": "image/*"})

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Username sudah digunakan. Pilih username lain.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email sudah digunakan.")
        return email

    def clean_photo_position_x(self):
        return self.cleaned_data.get("photo_position_x") or 50

    def clean_photo_position_y(self):
        return self.cleaned_data.get("photo_position_y") or 50


class StaffUpdateForm(forms.ModelForm):
    first_name = forms.CharField(label="Nama")
    nip = forms.CharField(label="NIP", required=False)
    nrp = forms.CharField(label="NRP", required=False)
    rank = forms.CharField(label="Pangkat", required=False, widget=forms.TextInput(attrs={"placeholder": "cth. Jaksa Utama Pratama"}))
    grade = forms.ChoiceField(label="Golongan", required=False, choices=GRADE_CHOICES)
    position = forms.CharField(label="Jabatan", required=False, widget=forms.TextInput(attrs={"placeholder": "cth. Pengelola Penanganan Perkara"}))
    email = forms.EmailField(label="Email")
    whatsapp_number = forms.CharField(label="Nomor WhatsApp", required=False, widget=forms.TextInput(attrs={"placeholder": "cth. 62812xxxx"}))
    telegram_chat_id = forms.CharField(label="ID Telegram", required=False, widget=forms.TextInput(attrs={"placeholder": "Chat ID Telegram"}))
    photo = forms.ImageField(label="Foto", required=False)
    photo_position_x = forms.IntegerField(required=False, min_value=0, max_value=100, widget=forms.HiddenInput)
    photo_position_y = forms.IntegerField(required=False, min_value=0, max_value=100, widget=forms.HiddenInput)
    roles = forms.ModelMultipleChoiceField(label="Role", queryset=Role.objects.all(), widget=forms.CheckboxSelectMultiple, help_text="Pilih satu atau beberapa role.")

    class Meta:
        model = User
        fields = ("first_name", "nip", "nrp", "rank", "grade", "position", "username", "email", "whatsapp_number", "telegram_chat_id", "photo", "photo_position_x", "photo_position_y", "roles")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"].queryset = Role.objects.all().order_by("sort_order", "name")
        self.fields["username"].help_text = "Username dicek otomatis agar tidak double."
        for name, field in self.fields.items():
            css_class = "user-field"
            if name == "roles":
                css_class = "role-choice-list"
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css_class}".strip()
        self.fields["photo"].widget.attrs.update({"accept": "image/*"})

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        exists = User.objects.exclude(pk=self.instance.pk).filter(username__iexact=username).exists()
        if exists:
            raise forms.ValidationError("Username sudah digunakan. Pilih username lain.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        exists = User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists()
        if exists:
            raise forms.ValidationError("Email sudah digunakan.")
        return email

    def clean_photo_position_x(self):
        return self.cleaned_data.get("photo_position_x") or self.instance.photo_position_x or 50

    def clean_photo_position_y(self):
        return self.cleaned_data.get("photo_position_y") or self.instance.photo_position_y or 50


class StaffPasswordChangeForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="Sandi Baru",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "user-field"}),
    )
    new_password2 = forms.CharField(
        label="Konfirmasi Sandi Baru",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "user-field"}),
    )


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(label="Nama Lengkap")
    nip = forms.CharField(label="NIP", required=False)
    nrp = forms.CharField(label="NRP", required=False)
    rank = forms.CharField(
        label="Pangkat",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "cth. Jaksa Utama Pratama"}),
    )
    grade = forms.ChoiceField(label="Golongan", required=False, choices=GRADE_CHOICES)
    email = forms.EmailField(label="Email")
    whatsapp_number = forms.CharField(
        label="Nomor WhatsApp", required=False,
        widget=forms.TextInput(attrs={"placeholder": "cth. 62812xxxx"}),
    )
    telegram_chat_id = forms.CharField(
        label="ID Telegram", required=False,
        widget=forms.TextInput(attrs={"placeholder": "Chat ID Telegram"}),
    )
    photo = forms.ImageField(label="Foto Profil", required=False)
    photo_position_x = forms.IntegerField(required=False, min_value=0, max_value=100, widget=forms.HiddenInput)
    photo_position_y = forms.IntegerField(required=False, min_value=0, max_value=100, widget=forms.HiddenInput)

    class Meta:
        model = User
        fields = (
            "first_name", "nip", "nrp", "rank", "grade", "email",
            "whatsapp_number", "telegram_chat_id", "photo",
            "photo_position_x", "photo_position_y",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} profile-field".strip()
        self.fields["photo"].widget.attrs.update({"accept": "image/*"})

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("Email sudah digunakan oleh pengguna lain.")
        return email

    def clean_photo_position_x(self):
        value = self.cleaned_data.get("photo_position_x")
        return self.instance.photo_position_x if value is None else value

    def clean_photo_position_y(self):
        value = self.cleaned_data.get("photo_position_y")
        return self.instance.photo_position_y if value is None else value
