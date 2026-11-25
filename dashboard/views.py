import math
from datetime import datetime as dt_class, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import DateTimeField, Exists, OuterRef, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from accounts.forms import StaffCreationForm, StaffPasswordChangeForm, StaffUpdateForm
from accounts.models import Role, User
from cases.models import (
    CaseDocumentDraft, P16Draft, P17Draft, P21Draft, SOPForm02Draft,
    SOPForm03Draft, SPDP, StageOne,
)
from cases.reminders import active_case_deadlines, case_deadline_for_spdp
from cases.workflow_status import spdp_workflow_status
from .decorators import super_admin_required
from .pagination import paginate_queryset

MONTH_LABELS_ID = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)
STAGE_FIELDS = ("p16", "p17", "sop02", "sop03", "stage1", "p18", "p19", "p20", "p21", "sop07")
STAGE_LABELS = {
    "p16": "P-16", "p17": "P-17", "sop02": "SOP Form 2",
    "sop03": "SOP Form 3", "stage1": "Tahap 1", "p18": "P-18", "p19": "P-19",
    "p20": "P-20", "p21": "P-21", "sop07": "SOP Form 7",
}


def _calendar_year_months(year):
    return [(year, month) for month in range(1, 13)]


def _monthly_counts(queryset, date_field):
    # Bucketed in Python (not TruncMonth) so this works without MySQL's optional
    # time zone tables (mysql_tzinfo_to_sql) being loaded on the server.
    counts = {}
    for value in queryset.values_list(date_field, flat=True):
        if value is None:
            continue
        if isinstance(value, dt_class):
            value = (timezone.localtime(value) if timezone.is_aware(value) else value).date()
        key = (value.year, value.month)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _nice_ceiling(value):
    """Round up to a clean axis max (1, 2, 5, 10, 20, 50, 100, ...)."""
    if value <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 5, 10):
        candidate = step * magnitude
        if candidate >= value:
            return int(candidate)
    return int(10 * magnitude)


def _case_development_chart():
    today = timezone.localdate()
    months = _calendar_year_months(today.year)

    spdp_counts = _monthly_counts(SPDP.objects.all(), "received_date")
    stage_counts = {
        "p16": _monthly_counts(P16Draft.objects.all(), "letter_date"),
        "p17": _monthly_counts(P17Draft.objects.all(), "letter_date"),
        "sop02": _monthly_counts(SOPForm02Draft.objects.all(), "letter_date"),
        "sop03": _monthly_counts(SOPForm03Draft.objects.all(), "letter_date"),
        "stage1": _monthly_counts(StageOne.objects.all(), "completed_at"),
        "p18": _monthly_counts(CaseDocumentDraft.objects.filter(document_type="p18"), "letter_date"),
        "p19": _monthly_counts(CaseDocumentDraft.objects.filter(document_type="p19"), "letter_date"),
        "p20": _monthly_counts(CaseDocumentDraft.objects.filter(document_type="p20"), "letter_date"),
        "p21": _monthly_counts(P21Draft.objects.all(), "letter_date"),
        "sop07": _monthly_counts(CaseDocumentDraft.objects.filter(document_type="sop07"), "letter_date"),
    }

    rows = []
    for (year, month) in months:
        key = (year, month)
        label = MONTH_LABELS_ID[month - 1]
        rows.append({
            "label": label,
            "year": year,
            "month": month,
            "total": spdp_counts.get(key, 0),
            "stages": {field: stage_counts[field].get(key, 0) for field in STAGE_FIELDS},
        })

    total_max = _nice_ceiling(max((row["total"] for row in rows), default=0))
    stage_max = _nice_ceiling(max((value for row in rows for value in row["stages"].values()), default=0))

    # Geometry in real pixel units (the <svg> is given explicit width/height
    # attributes, not a stretching viewBox, so a 3-month and a 12-month chart both
    # render at a natural size — a horizontal scroller on the wrapper takes any
    # overflow). A left gutter holds the axis tick labels so they never sit under a
    # bar; everything else is resolved to absolute coordinates here so the template
    # is a plain loop with no arithmetic.
    axis_gutter = 24
    slot_width, chart_height, baseline_pad, top_pad = 64, 160, 28, 14
    plot_height = chart_height - baseline_pad - top_pad
    baseline_y = top_pad + plot_height
    plot_width = slot_width * len(rows)
    chart_width = axis_gutter + plot_width

    for index, row in enumerate(rows):
        slot_x = axis_gutter + index * slot_width
        row["month_label_x"] = round(slot_x + slot_width / 2, 1)

        total_height = round((row["total"] / total_max) * plot_height, 1) if row["total"] else 0
        row["total_point"] = {
            "x": row["month_label_x"],
            "y": round(baseline_y - total_height, 1),
            "value": row["total"],
        }

        points = []
        for stage_index, field in enumerate(STAGE_FIELDS):
            value = row["stages"][field]
            height = round((value / stage_max) * plot_height, 1) if value else 0
            points.append({
                "label": STAGE_LABELS[field],
                "index": stage_index,
                "value": value,
                "x": row["month_label_x"],
                "y": round(baseline_y - height, 1),
            })
        row["stage_points"] = points

    stage_series = []
    for stage_index, field in enumerate(STAGE_FIELDS):
        points = " ".join(
            f"{month['stage_points'][stage_index]['x']},{month['stage_points'][stage_index]['y']}"
            for month in rows
        )
        stage_series.append({
            "label": STAGE_LABELS[field],
            "index": stage_index,
            "points": points,
        })
    total_line_points = " ".join(
        f"{month['total_point']['x']},{month['total_point']['y']}"
        for month in rows
    )

    def _axis_ticks(max_value):
        return [
            {"value": v, "y": round(baseline_y - (v / max_value) * plot_height, 1)}
            for v in (0, max_value // 2 or max_value, max_value)
        ]

    return {
        "months": rows,
        "chart_width": chart_width,
        "chart_height": chart_height,
        "baseline_y": baseline_y,
        "axis_gutter": axis_gutter,
        "plot_right": axis_gutter + plot_width,
        "total_line_points": total_line_points,
        "has_total_values": any(row["total"] for row in rows),
        "stage_series": stage_series,
        "year": today.year,
        "axis_ticks": _axis_ticks(total_max),
        "stage_axis_ticks": _axis_ticks(stage_max),
        "stage_legend": [{"field": f, "label": STAGE_LABELS[f], "index": i} for i, f in enumerate(STAGE_FIELDS)],
    }


def _case_reminders(today):
    return active_case_deadlines(today)


def _period_stats(queryset, date_field, today, *, include_day=True):
    is_datetime_field = isinstance(queryset.model._meta.get_field(date_field), DateTimeField)

    def boundary(day):
        if not is_datetime_field:
            return day
        value = dt_class(day.year, day.month, day.day)
        return timezone.make_aware(value, timezone.get_current_timezone())

    def count_between(start_date, end_date):
        return queryset.filter(**{
            f"{date_field}__gte": boundary(start_date),
            f"{date_field}__lt": boundary(end_date),
        }).count()

    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1)
    values = {
        "total": queryset.count(),
        "year": count_between(
            today.replace(month=1, day=1),
            today.replace(year=today.year + 1, month=1, day=1),
        ),
        "month": count_between(month_start, month_end),
    }
    if include_day:
        values["day"] = count_between(today, today + timedelta(days=1))
    return values


def _countable_p21_queryset():
    issued_terminal_documents = CaseDocumentDraft.objects.filter(
        spdp_id=OuterRef("spdp_id"),
    ).filter(
        Q(
            document_type=CaseDocumentDraft.DocumentType.P20,
            sipede_status=CaseDocumentDraft.SipedeStatus.UPLOADED,
        )
        | (
            Q(
                document_type=CaseDocumentDraft.DocumentType.SOP_FORM_07,
                letter_number__gt="",
            )
            & ~Q(letter_number__istartswith="DRAFT/")
        )
    )
    issued_sop03 = SOPForm03Draft.objects.filter(
        spdp_id=OuterRef("spdp_id"),
        letter_number__gt="",
    ).exclude(letter_number__istartswith="DRAFT/")
    return (
        P21Draft.objects.filter(status=P21Draft.Status.COMPLETED)
        .annotate(
            has_issued_terminal_document=Exists(issued_terminal_documents),
            has_issued_sop03=Exists(issued_sop03),
        )
        .filter(
            has_issued_terminal_document=False,
            has_issued_sop03=False,
        )
    )


def _recent_case_row(spdp):
    assignment = getattr(spdp, "p16_assignment", None)
    prosecutors = list(assignment.prosecutors.all()) if assignment else []
    workflow_status = spdp_workflow_status(spdp)
    return {
        "spdp": spdp,
        "suspects": ", ".join(spdp.suspects.values_list("name", flat=True)) or "Belum ada data pelaku",
        "stage": workflow_status["stage"],
        "prosecutors": ", ".join(user.display_name for user in prosecutors) or "Belum ditunjuk",
        "status": workflow_status["label"],
        "color": workflow_status["badge_class"],
    }


@login_required
def index(request):
    today = timezone.localdate()
    all_cases = SPDP.objects.all()
    unresolved = all_cases.filter(p21_draft__isnull=True)
    stats = {
        "cases": _period_stats(all_cases, "received_date", today),
        "unresolved": _period_stats(unresolved, "received_date", today, include_day=False),
        "p21": _period_stats(
            _countable_p21_queryset(), "created_at", today, include_day=False,
        ),
    }
    returned_sop03 = _period_stats(
        SOPForm03Draft.objects.all(), "created_at", today, include_day=False,
    )
    returned_documents = _period_stats(
        CaseDocumentDraft.objects.filter(
            document_type__in=(
                CaseDocumentDraft.DocumentType.P20,
                CaseDocumentDraft.DocumentType.SOP_FORM_07,
            ),
        ),
        "created_at",
        today,
        include_day=False,
    )
    stats["returned"] = {
        period: returned_sop03[period] + returned_documents[period]
        for period in ("total", "year", "month")
    }
    recent_queryset = (
        SPDP.objects.select_related(
            "stage_one", "p16_assignment__draft", "p21_draft",
            "sop_form_02_draft", "sop_form_03_draft",
        )
        .prefetch_related(
            "suspects", "p16_assignment__prosecutors", "p17_drafts",
            "case_document_drafts",
        )
        .order_by("-created_at", "-id")
    )
    recent_page_obj, recent_page = paginate_queryset(
        request, recent_queryset, per_page=10, page_param="recent_page",
    )
    context = {
        "stats": stats,
        "chart": _case_development_chart(),
        "reminders": _case_reminders(today),
        "recent_cases": [_recent_case_row(spdp) for spdp in recent_page],
        "recent_page_obj": recent_page_obj,
    }
    return render(request, "dashboard/index.html", context)


@login_required
def send_reminder(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    spdp = get_object_or_404(
        SPDP.objects.select_related(
            "stage_one", "sop_form_02_draft", "sop_form_03_draft", "p21_draft",
            "p16_assignment__draft", "p16_assignment__kasi_pidum",
        ).prefetch_related(
            "p17_drafts", "case_document_drafts",
            "p16_assignment__prosecutors", "p16_assignment__administrative_staff",
        ),
        pk=pk,
    )
    deadline = case_deadline_for_spdp(spdp, timezone.localdate())
    next_url = request.POST.get("next", "")
    redirect_target = (
        next_url
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})
        else reverse("dashboard:index")
    )
    if not deadline:
        assignment = getattr(spdp, "p16_assignment", None)
        if assignment:
            from notifications.services import send_p16_assignment_external_notifications
            send_p16_assignment_external_notifications(assignment.pk, request.user.pk)
            messages.success(
                request,
                "Notifikasi P-16 diproses melalui WhatsApp dan Telegram sesuai konfigurasi.",
            )
        else:
            messages.error(request, "Reminder belum memiliki tahapan dan penerima aktif.")
        return redirect(redirect_target)
    from notifications.services import send_case_deadline_reminder
    recipient_count = send_case_deadline_reminder(deadline, request.user)
    messages.success(
        request,
        f"Reminder {deadline.stage_label} diproses melalui WhatsApp dan Telegram untuk {recipient_count} pengguna.",
    )
    return redirect(redirect_target)

@login_required
@super_admin_required
def users(request):
    form = StaffCreationForm()
    edit_form = None
    editing_user = None
    password_form = None
    password_user = None
    if request.method == "POST":
        action = request.POST.get("action", "create")
        if action == "create":
            form = StaffCreationForm(request.POST, request.FILES)
            if form.is_valid():
                form.save()
                messages.success(request, "Pengguna baru berhasil ditambahkan.")
                return redirect("dashboard:users")
        elif action == "edit":
            editing_user = get_object_or_404(User, pk=request.POST.get("user_id"))
            edit_form = StaffUpdateForm(request.POST, request.FILES, instance=editing_user)
            if edit_form.is_valid():
                edit_form.save()
                messages.success(request, "Pengguna berhasil diperbarui.")
                return redirect("dashboard:users")
        elif action == "toggle_active":
            account = get_object_or_404(User, pk=request.POST.get("user_id"))
            if account.pk == request.user.pk:
                messages.error(request, "Akun yang sedang digunakan tidak dapat dinonaktifkan.")
            else:
                account.is_active = not account.is_active
                account.save(update_fields=["is_active"])
                messages.success(request, f"Pengguna {account.display_name} berhasil {'diaktifkan' if account.is_active else 'dinonaktifkan'}.")
            return redirect("dashboard:users")
        elif action == "change_password":
            password_user = get_object_or_404(User, pk=request.POST.get("user_id"))
            password_form = StaffPasswordChangeForm(password_user, request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, f"Password {password_user.display_name} berhasil diubah.")
                return redirect("dashboard:users")
    keyword = request.GET.get("q", "").strip()
    users_qs = User.objects.prefetch_related("roles").order_by("-date_joined")
    if keyword:
        users_qs = users_qs.filter(
            Q(first_name__icontains=keyword)
            | Q(last_name__icontains=keyword)
            | Q(username__icontains=keyword)
            | Q(email__icontains=keyword)
            | Q(nip__icontains=keyword)
            | Q(nrp__icontains=keyword)
            | Q(whatsapp_number__icontains=keyword)
            | Q(telegram_chat_id__icontains=keyword)
            | Q(roles__name__icontains=keyword)
        ).distinct()
    stats = {
        "total": User.objects.count(),
        "jaksa": User.objects.filter(roles__code=Role.PROSECUTOR).distinct().count(),
        "pegawai": User.objects.filter(roles__code=Role.EMPLOYEE).distinct().count(),
    }
    page_obj, users_page = paginate_queryset(request, users_qs, per_page=10)
    return render(request, "dashboard/users.html", {
        "form": form,
        "edit_form": edit_form,
        "editing_user": editing_user,
        "password_form": password_form,
        "password_user": password_user,
        "users": users_page,
        "page_obj": page_obj,
        "roles": Role.objects.all().order_by("sort_order", "name"),
        "stats": stats,
        "keyword": keyword,
    })
