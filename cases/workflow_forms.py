from django import forms

from accounts.models import Role, User


class SelectKasiPidumForm(forms.Form):
    kasi_pidum = forms.ModelChoiceField(label="Kasi Pidum", queryset=User.objects.none(), empty_label="Pilih Kasi Pidum")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kasi_pidum"].queryset = User.objects.filter(
            is_active=True, roles__code=Role.KASI_PIDUM
        ).distinct().order_by("first_name", "username")


class SelectProsecutorsForm(forms.Form):
    prosecutors = forms.ModelMultipleChoiceField(
        label="Jaksa yang ditunjuk", queryset=User.objects.none(), widget=forms.CheckboxSelectMultiple
    )
    administrative_staff_enabled = forms.BooleanField(label="Penunjukan Petugas Administrasi", required=False)
    administrative_staff = forms.ModelMultipleChoiceField(
        label="Petugas administrasi",
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["prosecutors"].queryset = User.objects.filter(
            is_active=True, roles__code=Role.PROSECUTOR
        ).distinct().order_by("first_name", "username")
        self.fields["administrative_staff"].queryset = User.objects.filter(
            is_active=True, roles__code=Role.EMPLOYEE
        ).distinct().order_by("first_name", "username")

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("administrative_staff_enabled"):
            cleaned_data["administrative_staff"] = []
        elif not cleaned_data.get("administrative_staff"):
            self.add_error("administrative_staff", "Pilih minimal satu petugas administrasi.")
        return cleaned_data
