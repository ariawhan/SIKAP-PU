from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import Role, User
from dashboard.decorators import super_admin_required
from dashboard.pagination import paginate_queryset
from .forms import (
    CMSAddressForm,
    CMSIntegrationForm,
    InstitutionConfigurationForm,
    InvestigatorInstitutionForm,
    InvestigatorUnitForm,
    LetterNumberCaseTypeForm,
    LetterNumberCodeForm,
    SipedeIntegrationForm,
)
from .layouts import (
    FONT_CHOICES,
    default_document_layout,
    document_layout_style,
    layout_groups_with_values,
    normalize_document_layout,
    validate_document_layout,
)
from .document_templates import DOCUMENT_TEMPLATES, definition_for, template_rows, validate_sources
from .models import CMSIntegration, CMSServiceConfiguration, DocumentLayoutConfiguration, DocumentTemplateConfiguration, InstitutionConfiguration, InvestigatorInstitution, InvestigatorUnit, LetterNumberCaseType, LetterNumberCode, SipedeIntegration
from . import cms, sipede


def _integration_target_user(request, user_id=None):
    """Return the integration owner and prevent non-admin cross-user access."""
    if not user_id or str(user_id) == str(request.user.pk):
        return request.user
    if not (request.user.is_super_admin or request.user.has_role(Role.ADMIN)):
        raise PermissionDenied("Anda tidak dapat mengubah integrasi pengguna lain.")
    return get_object_or_404(User, pk=user_id, is_active=True)


@login_required
@super_admin_required
def institution(request):
    config, _ = InstitutionConfiguration.objects.get_or_create(pk=1)
    form = InstitutionConfigurationForm(request.POST or None, instance=config)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.updated_by = request.user
        saved.save()
        messages.success(request, "Konfigurasi instansi berhasil disimpan.")
        return redirect("configurations:institution")
    return render(request, "configurations/institution.html", {"form": form, "config": config})


@login_required
def sipede_integration(request):
    is_integration_admin = request.user.is_super_admin or request.user.has_role(Role.ADMIN)
    requested_user_id = request.POST.get("target_user_id") or request.GET.get("user")
    managed_user = _integration_target_user(request, requested_user_id)
    integration = SipedeIntegration.objects.filter(user=managed_user).first()
    form = SipedeIntegrationForm(
        request.POST or None,
        initial={"username": integration.username} if integration else None,
        has_existing=bool(integration),
    )
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        credentials_changed = not integration or integration.username != username or bool(password)
        password_encrypted = integration.password_encrypted if integration else ""
        if password:
            password_encrypted = sipede.encrypt(password)
        defaults = {"username": username, "password_encrypted": password_encrypted}
        if credentials_changed:
            defaults.update(session_encrypted="", connected_at=None)
        SipedeIntegration.objects.update_or_create(
            user=managed_user,
            defaults=defaults,
        )
        messages.success(
            request,
            f"Kredensial SIPede {managed_user.display_name} tersimpan terenkripsi. Hubungkan untuk mengambil sesi.",
        )
        return redirect("configurations:sipede_integration")
    sipede_user_rows = []
    if is_integration_admin:
        integrations_by_user = {item.user_id: item for item in SipedeIntegration.objects.all()}
        for user in User.objects.filter(is_active=True).prefetch_related("roles").order_by(
            "first_name", "last_name", "username",
        ):
            sipede_user_rows.append({
                "user": user,
                "roles": ", ".join(role.name for role in user.roles.all()) or "Belum ada role",
                "integration": integrations_by_user.get(user.pk),
            })
    return render(request, "configurations/sipede_integration.html", {
        "form": form,
        "integration": integration,
        "managed_user": managed_user,
        "manage_user_requested": bool(requested_user_id),
        "is_integration_admin": is_integration_admin,
        "sipede_user_rows": sipede_user_rows,
        "sipede_configured_count": sum(1 for row in sipede_user_rows if row["integration"]),
        "sipede_connected_count": sum(
            1 for row in sipede_user_rows
            if row["integration"] and row["integration"].connected_at
        ),
    })


@login_required
def cms_integration(request):
    is_integration_admin = request.user.is_super_admin or request.user.has_role(Role.ADMIN)
    requested_user_id = request.POST.get("target_user_id") or request.GET.get("user")
    managed_user = _integration_target_user(request, requested_user_id)
    integration = CMSIntegration.objects.filter(user=managed_user).first()
    address = CMSServiceConfiguration.objects.first()
    if request.method == "POST" and request.POST.get("action") == "save_cms_address":
        if not is_integration_admin:
            raise PermissionDenied("Alamat CMS hanya dapat diubah oleh admin.")
        address_form = CMSAddressForm(request.POST)
        if address_form.is_valid():
            config = address or CMSServiceConfiguration()
            config.base_url = address_form.cleaned_data["base_url"]
            config.updated_by = request.user
            config.save()
            CMSIntegration.objects.update(session_encrypted="", connected_at=None)
            messages.success(request, "Alamat CMS bersama berhasil disimpan.")
            return redirect("configurations:cms_integration")
    else:
        address_form = CMSAddressForm(
            initial={"base_url": address.base_url} if address else None,
        )
    credential_data = request.POST if request.method == "POST" and request.POST.get("action") != "save_cms_address" else None
    form = CMSIntegrationForm(
        credential_data,
        initial={"username": integration.username} if integration else None,
        has_existing=bool(integration),
    )
    if request.method == "POST" and request.POST.get("action") != "save_cms_address" and form.is_valid():
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        credentials_changed = not integration or integration.username != username or bool(password)
        password_encrypted = integration.password_encrypted if integration else ""
        if password:
            password_encrypted = sipede.encrypt(password)
        defaults = {
            "username": username,
            "password_encrypted": password_encrypted,
        }
        if credentials_changed:
            defaults.update(session_encrypted="", connected_at=None)
        CMSIntegration.objects.update_or_create(
            user=managed_user,
            defaults=defaults,
        )
        messages.success(request, f"Konfigurasi CMS {managed_user.display_name} berhasil disimpan terenkripsi.")
        return redirect("configurations:cms_integration")
    cms_user_rows = []
    if is_integration_admin:
        integrations_by_user = {item.user_id: item for item in CMSIntegration.objects.all()}
        for user in User.objects.filter(is_active=True).prefetch_related("roles").order_by(
            "first_name", "last_name", "username",
        ):
            cms_user_rows.append({
                "user": user,
                "roles": ", ".join(role.name for role in user.roles.all()) or "Belum ada role",
                "integration": integrations_by_user.get(user.pk),
            })
    return render(request, "configurations/cms_integration.html", {
        "form": form,
        "address_form": address_form,
        "cms_address": address.base_url if address else "",
        "integration": integration,
        "managed_user": managed_user,
        "manage_user_requested": bool(requested_user_id),
        "is_integration_admin": is_integration_admin,
        "cms_user_rows": cms_user_rows,
        "cms_configured_count": sum(1 for row in cms_user_rows if row["integration"]),
        "cms_connected_count": sum(
            1 for row in cms_user_rows
            if row["integration"] and row["integration"].connected_at
        ),
    })


@login_required
def cms_connect(request):
    if request.method != "POST":
        return JsonResponse({"message": "Metode tidak diizinkan."}, status=405)
    try:
        target_user = _integration_target_user(request, request.POST.get("target_user_id"))
        return JsonResponse(cms.connect(target_user.pk))
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)


@login_required
def sipede_connect_start(request):
    if request.method != "POST":
        return JsonResponse({"message": "Metode tidak diizinkan."}, status=405)
    try:
        target_user = _integration_target_user(request, request.POST.get("target_user_id"))
        return JsonResponse({"auth_id": sipede.start(target_user.pk)})
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)


@login_required
def sipede_connect_status(request, auth_id):
    target_user = _integration_target_user(request, request.GET.get("target_user_id"))
    state = sipede.state_for(target_user.pk, auth_id)
    if not state:
        return JsonResponse({"message": "Sesi koneksi tidak ditemukan."}, status=404)
    state.pop("user_id", None)
    state.pop("captcha_input", None)
    return JsonResponse(state)


@login_required
def sipede_connect_captcha(request, auth_id):
    if request.method != "POST":
        return JsonResponse({"message": "Metode tidak diizinkan."}, status=405)
    try:
        target_user = _integration_target_user(request, request.POST.get("target_user_id"))
        sipede.submit_captcha(target_user.pk, auth_id, request.POST.get("captcha", "").strip())
        return JsonResponse({"message": "CAPTCHA dikirim."})
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)


@login_required
def sipede_connect_cancel(request, auth_id):
    if request.method != "POST":
        return JsonResponse({"message": "Metode tidak diizinkan."}, status=405)
    try:
        target_user = _integration_target_user(request, request.POST.get("target_user_id"))
        sipede.cancel(target_user.pk, auth_id)
        return JsonResponse({"message": "Koneksi SIPede dibatalkan."})
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=404)


@login_required
@super_admin_required
def document_layout(request):
    template_key = request.POST.get("template_key") or request.GET.get("template") or "p16"
    if template_key != DocumentLayoutConfiguration.TEMPLATE_P16:
        template_key = DocumentLayoutConfiguration.TEMPLATE_P16
    configuration, _ = DocumentLayoutConfiguration.objects.get_or_create(
        template_key=template_key,
        defaults={"settings": default_document_layout(template_key)},
    )
    layout = normalize_document_layout(template_key, configuration.settings)
    errors = {}
    if request.method == "POST":
        layout, errors = validate_document_layout(template_key, request.POST)
        if not errors:
            configuration.settings = layout
            configuration.revision += 1
            configuration.updated_by = request.user
            configuration.save(update_fields=("settings", "revision", "updated_by", "updated_at"))
            messages.success(request, "Tata letak P-16 berhasil disimpan dan langsung diterapkan pada seluruh draf.")
            return redirect("configurations:document_layout")
        messages.error(request, "Periksa kembali nilai tata letak yang ditandai.")

    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    return render(request, "configurations/document_layout.html", {
        "configuration": configuration,
        "template_key": template_key,
        "layout": layout,
        "layout_groups": layout_groups_with_values(layout, errors),
        "layout_style": document_layout_style(template_key, layout),
        "layout_defaults": default_document_layout(template_key),
        "font_choices": [
            {"value": value, "label": details[0], "selected": value == layout["font_family"]}
            for value, details in FONT_CHOICES.items()
        ],
        "font_error": errors.get("font_family", ""),
        "institution": institution,
    })


@login_required
@super_admin_required
def document_template_settings(request):
    template_key = request.POST.get("template_key") or request.GET.get("template") or "p16"
    if template_key not in DOCUMENT_TEMPLATES:
        template_key = "p16"
    definition = definition_for(template_key)
    configuration = DocumentTemplateConfiguration.objects.filter(template_key=template_key).first()
    errors = {}
    posted_sources = None

    if request.method == "POST" and request.POST.get("action") == "reset":
        if configuration:
            configuration.delete()
        messages.success(request, f"Template {definition['label']} dikembalikan ke bawaan aplikasi.")
        return redirect(f"{reverse('configurations:document_template_settings')}?template={template_key}")

    if request.method == "POST":
        posted_sources = {
            field_name: request.POST.get(f"section__{field_name}", "")
            for field_name, _label, _template in definition["sections"]
        }
        errors = validate_sources(template_key, posted_sources)
        if not errors:
            configuration, created = DocumentTemplateConfiguration.objects.get_or_create(
                template_key=template_key,
                defaults={"sections": posted_sources, "updated_by": request.user},
            )
            if not created:
                configuration.sections = posted_sources
                configuration.revision += 1
                configuration.updated_by = request.user
                configuration.save(update_fields=("sections", "revision", "updated_by", "updated_at"))
            messages.success(
                request,
                f"Template generate {definition['label']} berhasil disimpan. Draf baru akan memakai revisi ini.",
            )
            return redirect(f"{reverse('configurations:document_template_settings')}?template={template_key}")
        messages.error(request, "Template belum disimpan. Periksa bagian yang ditandai.")

    return render(request, "configurations/document_template_settings.html", {
        "template_key": template_key,
        "definition": definition,
        "configuration": configuration,
        "template_menus": [
            {"key": key, "label": item["label"], "active": key == template_key}
            for key, item in DOCUMENT_TEMPLATES.items()
        ],
        "section_rows": template_rows(template_key, posted_sources, errors),
    })


@login_required
@super_admin_required
def letter_number(request):
    if request.method == "POST" and request.POST.get("action") == "delete_letter_number":
        letter_number = get_object_or_404(LetterNumberCode, pk=request.POST.get("letter_number_id"))
        label = f"{letter_number.directorate}: {letter_number.code}"
        letter_number.delete()
        messages.success(request, f"Nomor surat {label} berhasil dihapus.")
        return redirect("configurations:letter_number")

    page_obj, letter_numbers = paginate_queryset(
        request,
        LetterNumberCode.objects.select_related("created_by").prefetch_related("case_types").all(),
        per_page=10,
    )
    for letter_number_item in letter_numbers:
        names = [case_type.name for case_type in letter_number_item.case_types.all()]
        letter_number_item.case_type_visible = names[:3]
        letter_number_item.case_type_extra = names[3:]
    return render(request, "configurations/letter_number.html", {
        "letter_numbers": letter_numbers,
        "page_obj": page_obj,
    })


@login_required
@super_admin_required
def letter_number_form(request, pk=None):
    instance = get_object_or_404(LetterNumberCode, pk=pk) if pk else None
    action = request.POST.get("action") if request.method == "POST" else None

    if instance and action == "delete_case_type":
        case_type = get_object_or_404(LetterNumberCaseType, pk=request.POST.get("case_type_id"), letter_number=instance)
        name = case_type.name
        case_type.delete()
        messages.success(request, f"Jenis perkara {name} berhasil dihapus.")
        return redirect("configurations:letter_number_detail", pk=instance.pk)

    case_type_action = action if instance and action in {"add_case_type", "edit_case_type"} else None
    case_type_edit_id = request.POST.get("case_type_id") if case_type_action == "edit_case_type" else ""
    case_type_instance = (
        get_object_or_404(LetterNumberCaseType, pk=case_type_edit_id, letter_number=instance)
        if case_type_edit_id else None
    )
    case_type_form = LetterNumberCaseTypeForm(
        request.POST if case_type_action else None,
        instance=case_type_instance,
        letter_number=instance,
    )
    if case_type_action and case_type_form.is_valid():
        case_type = case_type_form.save(commit=False)
        case_type.letter_number = instance
        case_type.save()
        verb = "ditambahkan" if case_type_action == "add_case_type" else "diperbarui"
        messages.success(request, f"Jenis perkara {case_type.name} berhasil {verb}.")
        return redirect("configurations:letter_number_detail", pk=instance.pk)

    form = LetterNumberCodeForm(
        request.POST if action == "save_letter_number" else None,
        instance=instance,
    )
    if action == "save_letter_number" and form.is_valid():
        letter_number = form.save(commit=False)
        if not instance:
            letter_number.created_by = request.user
        letter_number.save()
        verb = "ditambahkan" if not instance else "diperbarui"
        messages.success(request, f"Nomor surat {letter_number.directorate}: {letter_number.code} berhasil {verb}.")
        return redirect("configurations:letter_number_detail", pk=letter_number.pk)

    case_types_page_obj, case_types_page = (None, None)
    if instance:
        case_types_page_obj, case_types_page = paginate_queryset(
            request, instance.case_types.all(), per_page=10,
        )

    return render(request, "configurations/letter_number_form.html", {
        "form": form,
        "instance": instance,
        "case_type_form": case_type_form,
        "case_type_action": case_type_action or "add_case_type",
        "case_type_edit_id": case_type_edit_id,
        "case_types_page": case_types_page,
        "case_types_page_obj": case_types_page_obj,
    })


@login_required
@super_admin_required
def investigators(request):
    action = request.POST.get("action") if request.method == "POST" else None
    institution_form = InvestigatorInstitutionForm()
    unit_form = InvestigatorUnitForm()
    active_modal = ""

    if action == "delete_institution":
        institution = get_object_or_404(InvestigatorInstitution, pk=request.POST.get("institution_id"))
        label = institution.name
        institution.delete()
        messages.success(request, f"Instansi penyidik {label} berhasil dihapus.")
        return redirect("configurations:investigators")

    if action == "delete_unit":
        unit = get_object_or_404(InvestigatorUnit.objects.select_related("institution"), pk=request.POST.get("unit_id"))
        label = f"{unit.institution.name} - {unit.name}"
        unit.delete()
        messages.success(request, f"Instansi pelaksana penyidik {label} berhasil dihapus.")
        return redirect("configurations:investigators")

    if action in {"add_institution", "edit_institution"}:
        instance = None
        if action == "edit_institution":
            instance = get_object_or_404(InvestigatorInstitution, pk=request.POST.get("institution_id"))
        institution_form = InvestigatorInstitutionForm(request.POST, instance=instance)
        if institution_form.is_valid():
            institution = institution_form.save(commit=False)
            if action == "add_institution":
                institution.created_by = request.user
            institution.save()
            verb = "ditambahkan" if action == "add_institution" else "diperbarui"
            messages.success(request, f"Instansi penyidik {institution.name} berhasil {verb}.")
            return redirect("configurations:investigators")
        active_modal = "institution"

    if action in {"add_unit", "edit_unit"}:
        instance = None
        if action == "edit_unit":
            instance = get_object_or_404(InvestigatorUnit, pk=request.POST.get("unit_id"))
        unit_form = InvestigatorUnitForm(request.POST, instance=instance)
        if unit_form.is_valid():
            unit = unit_form.save(commit=False)
            if action == "add_unit":
                unit.created_by = request.user
            unit.save()
            verb = "ditambahkan" if action == "add_unit" else "diperbarui"
            messages.success(request, f"Instansi pelaksana penyidik {unit.name} berhasil {verb}.")
            return redirect("configurations:investigators")
        active_modal = "unit"

    page_obj, institutions = paginate_queryset(
        request,
        InvestigatorInstitution.objects.select_related("created_by").prefetch_related("units").order_by("name"),
        per_page=8,
    )
    return render(request, "configurations/investigators.html", {
        "institution_form": institution_form,
        "unit_form": unit_form,
        "institutions": institutions,
        "page_obj": page_obj,
        "active_modal": active_modal,
    })
