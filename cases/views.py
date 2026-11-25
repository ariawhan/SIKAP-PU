from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST
from datetime import date, timedelta

from django.utils import timezone
from django.utils.html import strip_tags

from accounts.models import Role, User
from configurations.layouts import document_layout_style, normalize_document_layout
from configurations.models import CMSIntegration, DocumentLayoutConfiguration
from configurations import cms as cms_service
from dashboard.pagination import paginate_queryset
from notifications.services import (
    create_p16_assignment_web_notification,
    send_document_issued_notifications,
    send_p16_assignment_external_notifications,
)
from .forms import CaseDocumentDraftForm, CoordinationMinutesDraftForm, P16DraftForm, P17CreateForm, P17DraftForm, P21CreateForm, P21DraftForm, ReceiptFormSet, SOPForm02DraftForm, SOPForm03DraftForm, SOPForm1BDraftForm, SOPFormCreateForm, SPDPForm, StageOneForm, SuspectFormSet, VictimFormSet
from .models import CaseDocumentDraft, CoordinationMinutesDraft, P16Assignment, P16Draft, P17Draft, P21Draft, SOPForm02Draft, SOPForm03Draft, SPDP, StageOne
from .p16_content import build_default_p16_content, ensure_p16_sections
from .p17_content import build_p17_preview, ensure_p17_sections, p17_recipients_for_editor, request_label
from .p21_content import build_p21_preview, ensure_p21_sections
from .reminders import SPDP_PERIOD_DAYS, active_case_deadlines, case_deadline_for_spdp
from .sop_form_content import build_sop_preview, ensure_sop_form_02_sections, ensure_sop_form_03_sections
from .sop_form_1b_content import build_sop_form_1b_preview, ensure_sop_form_1b
from .case_document_content import build_case_document_preview, ensure_case_document_sections
from .workflow_status import (
    letter_number_is_issued as _letter_number_is_issued,
    spdp_workflow_status as _spdp_workflow_status,
)
from .coordination_content import build_coordination_preview, ensure_coordination_body
from .workflow_forms import SelectKasiPidumForm, SelectProsecutorsForm


def _can_edit_p16(user, draft):
    return (
        user.is_super_admin
        or user.has_role(Role.ADMIN)
        or user.pk == draft.assignment.kasi_pidum_id
        or draft.assignment.prosecutors.filter(pk=user.pk).exists()
        or draft.assignment.administrative_staff.filter(pk=user.pk).exists()
    )


def _can_edit_p17(user, draft):
    assignment = getattr(draft.spdp, "p16_assignment", None)
    return (
        user.is_super_admin or user.has_role(Role.ADMIN)
        or user.pk == draft.created_by_id
        or (assignment and user.pk == assignment.kasi_pidum_id)
        or (assignment and assignment.prosecutors.filter(pk=user.pk).exists())
        or (assignment and assignment.administrative_staff.filter(pk=user.pk).exists())
    )


def _can_edit_p21(user, draft):
    assignment = getattr(draft.spdp, "p16_assignment", None)
    return bool(
        user.is_super_admin or user.has_role(Role.ADMIN)
        or user.pk == draft.created_by_id
        or (assignment and user.pk == assignment.kasi_pidum_id)
        or (assignment and assignment.prosecutors.filter(pk=user.pk).exists())
        or (assignment and assignment.administrative_staff.filter(pk=user.pk).exists())
    )


def _can_manage_stage_one(user, spdp):
    if user.is_super_admin or user.has_role(
        Role.ADMIN, Role.EMPLOYEE, Role.KASI_PIDUM, Role.KASUBSI_PREPROSECUTION,
    ):
        return True
    assignment = getattr(spdp, "p16_assignment", None)
    return bool(
        assignment and (
            user.pk == assignment.kasi_pidum_id
            or assignment.prosecutors.filter(pk=user.pk).exists()
            or assignment.administrative_staff.filter(pk=user.pk).exists()
        )
    )


def _sop_form_03_is_issued(spdp):
    draft = getattr(spdp, "sop_form_03_draft", None)
    return bool(draft and _letter_number_is_issued(draft.letter_number))


def _stage_one_is_blocked(spdp):
    return hasattr(spdp, "sop_form_03_draft")


def _stage_one_accessible_spdps(user, queryset):
    if user.is_super_admin or user.has_role(
        Role.ADMIN, Role.EMPLOYEE, Role.KASI_PIDUM, Role.KASUBSI_PREPROSECUTION,
    ):
        return queryset
    return queryset.filter(
        Q(p16_assignment__kasi_pidum=user)
        | Q(p16_assignment__prosecutors=user)
        | Q(p16_assignment__administrative_staff=user)
    ).distinct()


def _letter_signatory_context(draft, institution, *, include_users=True):
    default_name = (
        draft.acting_name
        if getattr(draft, "acting_type", "") and getattr(draft, "acting_name", "")
        else institution.leader_name
    )
    names = [default_name, institution.leader_name]
    if include_users:
        names.extend(
            user.get_full_name() or user.username
            for user in User.objects.filter(is_active=True).only(
                "first_name", "last_name", "username",
            )
        )
    names = list(dict.fromkeys(name.strip() for name in names if name and name.strip()))
    return {"default_sipede_signatory": default_name, "sipede_signatory_names": names}


def _apply_acting_signatory_post(request, draft):
    if "acting_type" not in request.POST:
        return (), ""
    acting_type = request.POST.get("acting_type", "").strip().lower()
    values = {
        "acting_name": request.POST.get("acting_name", "").strip(),
        "acting_position": request.POST.get("acting_position", "").strip(),
        "acting_nip": request.POST.get("acting_nip", "").strip(),
    }
    if acting_type not in ("", "plt", "plh"):
        return (), "Pilihan PLT/PLH tidak valid."
    if acting_type and not all(values.values()):
        return (), "Nama, Jabatan/Pangkat, dan NIP wajib diisi saat PLT/PLH dipilih."
    limits = {"acting_name": 150, "acting_position": 150, "acting_nip": 30}
    if any(len(values[field]) > limit for field, limit in limits.items()):
        return (), "Identitas pejabat PLT/PLH melebihi batas karakter."
    draft.acting_type = acting_type
    for field_name, value in values.items():
        setattr(draft, field_name, value if acting_type else "")
    return ("acting_type", "acting_name", "acting_position", "acting_nip"), ""


def _schedule_document_issued_notification(
    *, spdp_id, stage_key, document_id, document_number, document_date, actor_id,
):
    """Jadwalkan setelah transaksi sukses; layanan notifikasi menangani deduplikasi."""
    transaction.on_commit(
        lambda: send_document_issued_notifications(
            spdp_id=spdp_id,
            stage_key=stage_key,
            document_id=document_id,
            document_number=document_number,
            document_date=document_date,
            actor_id=actor_id,
        ),
        robust=True,
    )


def enrich_spdp_deadline(spdp, today):
    due_date = spdp.received_date + timedelta(days=SPDP_PERIOD_DAYS)
    has_p16_draft = (
        hasattr(spdp, "p16_assignment")
        and hasattr(spdp.p16_assignment, "draft")
        and not spdp.p16_assignment.draft.draft_number.startswith("DRAFT/")
    )
    remaining_days = (due_date - today).days
    spdp.p16_due_date = due_date
    spdp.p16_remaining_days = remaining_days
    spdp.p16_is_done = has_p16_draft
    if has_p16_draft:
        spdp.p16_deadline_label = "Sudah terbit"
        spdp.p16_deadline_class = "done"
        spdp.p16_deadline_title = "P-16"
        spdp.p16_deadline_value = "Terbit"
    elif remaining_days > 0:
        spdp.p16_deadline_label = f"{remaining_days} hari"
        spdp.p16_deadline_class = "safe" if remaining_days > 2 else "warning"
        spdp.p16_deadline_title = "Sisa" if remaining_days > 2 else "Segera"
        spdp.p16_deadline_value = f"{remaining_days} hari"
    elif remaining_days == 0:
        spdp.p16_deadline_label = "Hari ini"
        spdp.p16_deadline_class = "overdue"
        spdp.p16_deadline_title = "Tenggat"
        spdp.p16_deadline_value = "Hari ini"
    else:
        spdp.p16_deadline_label = f"Lewat {abs(remaining_days)} hari"
        spdp.p16_deadline_class = "overdue"
        spdp.p16_deadline_title = "Lewat"
        spdp.p16_deadline_value = f"{abs(remaining_days)} hari"
    return spdp


def attach_document_deadlines(
    rows,
    today,
    stage_key,
    *,
    spdp_id_getter,
    document_id_getter,
    number_getter,
):
    """Attach the current workflow deadline badge to document-list rows."""
    rows = list(rows)
    spdp_ids = {spdp_id_getter(row) for row in rows}
    spdps = (
        SPDP.objects.filter(pk__in=spdp_ids)
        .select_related(
            "stage_one", "sop_form_02_draft", "sop_form_03_draft",
            "p16_assignment__draft", "p21_draft",
        )
        .prefetch_related("p17_drafts", "case_document_drafts")
    )
    deadlines = {
        spdp.pk: case_deadline_for_spdp(spdp, today)
        for spdp in spdps
    }
    for row in rows:
        deadline = deadlines.get(spdp_id_getter(row))
        if (
            deadline
            and deadline.stage_key == stage_key
            and deadline.document_id == document_id_getter(row)
        ):
            row.deadline_class = deadline.color_class
            if deadline.remaining_days > 2:
                row.deadline_title = "Sisa"
                row.deadline_value = f"{deadline.remaining_days} hari"
            elif deadline.remaining_days > 0:
                row.deadline_title = "Segera"
                row.deadline_value = f"{deadline.remaining_days} hari"
            elif deadline.remaining_days == 0:
                row.deadline_title = "Tenggat"
                row.deadline_value = "Hari ini"
            else:
                row.deadline_title = "Lewat"
                row.deadline_value = f"{abs(deadline.remaining_days)} hari"
            row.deadline_detail = ""
        else:
            row.deadline_class = "done"
            row.deadline_title = "Status"
            row.deadline_value = (
                "Selesai" if _letter_number_is_issued(number_getter(row)) else "Draf"
            )
            row.deadline_detail = ""
    return rows


def attach_activity_deadlines(rows, today, *, spdp_getter=lambda item: item):
    """Expose the active workflow deadline in the activity cards."""
    rows = list(rows)
    spdp_ids = {spdp_getter(row).pk for row in rows}
    spdps = (
        SPDP.objects.filter(pk__in=spdp_ids)
        .select_related(
            "stage_one", "sop_form_02_draft", "sop_form_03_draft",
            "p16_assignment__draft", "p21_draft",
        )
        .prefetch_related("p17_drafts", "case_document_drafts")
    )
    deadlines = {
        spdp.pk: case_deadline_for_spdp(spdp, today)
        for spdp in spdps
    }
    for row in rows:
        row.activity_deadline = deadlines.get(spdp_getter(row).pk)
    return rows


def active_stage_priority_cases(stage_key, today, limit=None):
    detail_routes = {
        "spdp": "cases:spdp_detail",
        "p16": "cases:p16_draft_detail",
        "p17": "cases:p17_draft_detail",
        "sop02": "cases:sop_form_02_detail",
        "stage1": "cases:stage_one_detail",
        "p19": "cases:p19_detail",
        "p21": "cases:p21_draft_detail",
    }
    cases = []
    for deadline in active_case_deadlines(today):
        if deadline.stage_key != stage_key:
            continue
        spdp = deadline.spdp
        spdp.activity_deadline = deadline
        spdp.workflow_detail_pk = (
            spdp.pk if stage_key in ("spdp", "stage1") else deadline.document_id
        )
        spdp.workflow_detail_url_name = detail_routes[stage_key]
        spdp.activity_url = reverse(
            detail_routes[stage_key],
            args=[
                spdp.pk if stage_key in ("spdp", "stage1") else deadline.document_id
            ],
        )
        cases.append(spdp)
        if limit and len(cases) >= limit:
            break
    if stage_key in WORKFLOW_NEXT_ACTIONS:
        return attach_workflow_actions(
            cases,
            stage_key,
            spdp_id_getter=lambda spdp: spdp.pk,
        )
    return cases


WORKFLOW_NEXT_ACTIONS = {
    "p16": (("stage1", "Generate Tahap 1"), ("p17", "Generate P-17")),
    "p17": (("stage1", "Generate Tahap 1"), ("sop02", "Generate SOP Form 2")),
    "sop02": (("stage1", "Generate Tahap 1"), ("sop03", "Generate SOP Form 3")),
    "stage1": (("p21", "Generate P-21"), ("p18", "Generate P-18")),
    "p18": (("p19", "Generate P-19"),),
    "p19": (("p21", "Generate P-21"), ("p20", "Generate P-20")),
    "p21": (("sop07", "Generate SOP Form 7"),),
}


def attach_workflow_actions(
    rows,
    source,
    *,
    spdp_id_getter,
    issued_getter=lambda item: True,
):
    """Attach mutually-exclusive next actions for issued workflow rows."""
    rows = list(rows)
    spdp_ids = {spdp_id_getter(row) for row in rows}
    spdps = (
        SPDP.objects.filter(pk__in=spdp_ids)
        .select_related(
            "stage_one", "sop_form_02_draft", "sop_form_03_draft", "p21_draft",
        )
        .prefetch_related("p17_drafts", "case_document_drafts")
    )
    state_by_spdp = {}
    for spdp in spdps:
        documents = {item.document_type for item in spdp.case_document_drafts.all()}
        state_by_spdp[spdp.pk] = {
            "p17": bool(list(spdp.p17_drafts.all())),
            "sop02": hasattr(spdp, "sop_form_02_draft"),
            "sop03": hasattr(spdp, "sop_form_03_draft"),
            "stage1": hasattr(spdp, "stage_one"),
            "p18": CaseDocumentDraft.DocumentType.P18 in documents,
            "p19": CaseDocumentDraft.DocumentType.P19 in documents,
            "p20": CaseDocumentDraft.DocumentType.P20 in documents,
            "p21": hasattr(spdp, "p21_draft"),
            "sop07": CaseDocumentDraft.DocumentType.SOP_FORM_07 in documents,
        }
    for row in rows:
        spdp_id = spdp_id_getter(row)
        state = state_by_spdp.get(spdp_id, {})
        successors = WORKFLOW_NEXT_ACTIONS[source]
        locked = any(state.get(target, False) for target, _ in successors)
        row.workflow_spdp_id = spdp_id
        row.workflow_detail_pk = getattr(row, "workflow_detail_pk", row.pk)
        row.workflow_is_issued = bool(issued_getter(row))
        row.workflow_next_locked = locked
        row.workflow_actions = [] if locked else [
            {"source": source, "target": target, "label": label}
            for target, label in successors
        ]
    return rows


@login_required
def spdp_list(request):
    queryset = SPDP.objects.select_related(
        "created_by",
        "p16_assignment__kasi_pidum",
        "p16_assignment__draft",
        "stage_one",
        "sop_form_02_draft",
        "sop_form_03_draft",
        "p21_draft",
    ).prefetch_related(
        "suspects",
        "p16_assignment__prosecutors",
        "p16_assignment__administrative_staff",
        "p17_drafts",
        "case_document_drafts",
    ).order_by("-received_date", "-id")
    query = request.GET.get("q", "").strip()
    if query:
        from django.db.models import Q
        queryset = queryset.filter(Q(letter_number__icontains=query) | Q(case_summary__icontains=query) | Q(suspects__name__icontains=query)).distinct()
    can_start_p16 = request.user.is_super_admin or request.user.has_role(Role.ADMIN, Role.EMPLOYEE)
    page_obj, spdp_page = paginate_queryset(request, queryset, per_page=10)
    today = timezone.localdate()
    stats_queryset = SPDP.objects.all()
    case_stats = {
        "total": stats_queryset.count(),
        "year": stats_queryset.filter(received_date__year=today.year).count(),
        "month": stats_queryset.filter(received_date__year=today.year, received_date__month=today.month).count(),
        "day": stats_queryset.filter(received_date=today).count(),
    }
    for spdp in spdp_page:
        enrich_spdp_deadline(spdp, today)
        spdp.workflow_status = _spdp_workflow_status(spdp)
    priority_cases = active_stage_priority_cases("spdp", today)
    return render(request, "cases/spdp_list.html", {
        "spdp_list": spdp_page, "page_obj": page_obj, "query": query, "can_start_p16": can_start_p16,
        "kasi_form": SelectKasiPidumForm(), "prosecutor_form": SelectProsecutorsForm(),
        "case_stats": case_stats, "priority_cases": priority_cases, "current_period": today,
    })


@login_required
def p16_list(request):
    queryset = P16Draft.objects.select_related(
        "assignment__spdp", "assignment__kasi_pidum", "generated_by"
    ).prefetch_related("assignment__prosecutors", "assignment__administrative_staff", "assignment__spdp__suspects").order_by("-created_at", "-id")
    query = request.GET.get("q", "").strip()
    if query:
        from django.db.models import Q
        queryset = queryset.filter(
            Q(draft_number__icontains=query)
            | Q(assignment__spdp__letter_number__icontains=query)
            | Q(assignment__spdp__suspects__name__icontains=query)
            | Q(assignment__prosecutors__first_name__icontains=query)
            | Q(assignment__prosecutors__last_name__icontains=query)
            | Q(assignment__prosecutors__username__icontains=query)
        ).distinct()
    page_obj, drafts_page = paginate_queryset(request, queryset, per_page=10)
    today = timezone.localdate()
    drafts_page = attach_document_deadlines(
        drafts_page,
        today,
        "p16",
        spdp_id_getter=lambda draft: draft.assignment.spdp_id,
        document_id_getter=lambda draft: draft.pk,
        number_getter=lambda draft: draft.draft_number,
    )
    drafts_page = attach_workflow_actions(
        drafts_page,
        "p16",
        spdp_id_getter=lambda draft: draft.assignment.spdp_id,
        issued_getter=lambda draft: draft.is_issued,
    )
    stats_queryset = P16Draft.objects.all()
    case_stats = {
        "total": stats_queryset.count(),
        "year": stats_queryset.filter(created_at__year=today.year).count(),
        "month": stats_queryset.filter(created_at__year=today.year, created_at__month=today.month).count(),
        "day": stats_queryset.filter(created_at__date=today).count(),
    }
    priority_cases = active_stage_priority_cases("p16", today)
    return render(request, "cases/p16_list.html", {
        "drafts": drafts_page, "page_obj": page_obj, "query": query,
        "case_stats": case_stats, "priority_cases": priority_cases, "current_period": today,
    })


@login_required
def stage_one_list(request):
    queryset = (
        SPDP.objects.filter(stage_one__isnull=False)
        .select_related("stage_one", "p16_assignment__kasi_pidum")
        .prefetch_related("suspects", "p16_assignment__prosecutors")
        .order_by("-stage_one__completed_at", "-received_date", "-id")
    )
    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(letter_number__icontains=query)
            | Q(stage_one__case_file_number__icontains=query)
            | Q(stage_one__cover_letter_number__icontains=query)
            | Q(suspects__name__icontains=query)
        ).distinct()
    page_obj, case_page = paginate_queryset(request, queryset, per_page=10)
    today = timezone.localdate()
    case_page = attach_document_deadlines(
        case_page,
        today,
        "stage1",
        spdp_id_getter=lambda spdp: spdp.pk,
        document_id_getter=lambda spdp: spdp.stage_one.pk,
        number_getter=lambda spdp: spdp.stage_one.case_file_number,
    )
    case_page = attach_workflow_actions(
        case_page,
        "stage1",
        spdp_id_getter=lambda spdp: spdp.pk,
    )
    completed = StageOne.objects.all()
    stats = {
        "total": completed.count(),
        "year": completed.filter(completed_at__year=today.year).count(),
        "month": completed.filter(completed_at__year=today.year, completed_at__month=today.month).count(),
        "day": completed.filter(completed_at__date=today).count(),
    }
    priority_cases = active_stage_priority_cases("stage1", today)
    return render(request, "cases/stage_one_list.html", {
        "cases": case_page, "page_obj": page_obj, "query": query, "stats": stats,
        "priority_cases": priority_cases, "current_period": today,
    })


@login_required
def stage_one_select(request):
    query = request.GET.get("q", "").strip()
    page_obj = None
    results = []
    if query:
        queryset = (
            SPDP.objects.select_related(
                "stage_one", "sop_form_03_draft", "p16_assignment__kasi_pidum",
            )
            .prefetch_related(
                "suspects", "p16_assignment__prosecutors",
                "p16_assignment__administrative_staff",
            )
            .filter(
                Q(letter_number__icontains=query)
                | Q(investigation_order_number__icontains=query)
                | Q(suspects__name__icontains=query)
            )
            .distinct()
            .order_by("-received_date", "-id")
        )
        queryset = _stage_one_accessible_spdps(request.user, queryset)
        page_obj, results = paginate_queryset(request, queryset, per_page=10)
        for spdp in results:
            spdp.stage_one_blocked = _stage_one_is_blocked(spdp)
    return render(request, "cases/stage_one_select.html", {
        "query": query, "results": results, "page_obj": page_obj,
    })


@login_required
@transaction.atomic
def stage_one_detail(request, pk):
    spdp = get_object_or_404(
        SPDP.objects.select_related("stage_one", "sop_form_03_draft", "p16_assignment__kasi_pidum")
        .prefetch_related("suspects", "p16_assignment__prosecutors", "p16_assignment__administrative_staff"),
        pk=pk,
    )
    if not _can_manage_stage_one(request.user, spdp):
        raise PermissionDenied
    stage_one = getattr(spdp, "stage_one", None)
    if stage_one is None and _stage_one_is_blocked(spdp):
        messages.error(
            request,
            "Tahap 1 tidak dapat dibuat karena SOP Form 3 untuk perkara ini sudah terbit.",
        )
        return redirect("cases:stage_one_select")
    form = StageOneForm(
        request.POST or None,
        request.FILES or None,
        instance=stage_one,
        initial={"laws_and_articles": spdp.laws_and_articles},
    )
    suspect_formset = SuspectFormSet(request.POST or None, instance=spdp, prefix="suspects")
    if request.method == "POST" and form.is_valid() and suspect_formset.is_valid():
        is_new = stage_one is None
        saved = form.save(commit=False)
        saved.spdp = spdp
        if is_new:
            saved.created_by = request.user
        saved.updated_by = request.user
        saved.save()

        suspects = suspect_formset.save(commit=False)
        for deleted in suspect_formset.deleted_objects:
            deleted.delete()
        next_sequence = (spdp.suspects.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
        for suspect in suspects:
            suspect.spdp = spdp
            if not suspect.pk:
                suspect.sequence = next_sequence
                next_sequence += 1
            suspect.save()
        for index, suspect in enumerate(spdp.suspects.order_by("sequence", "id"), start=1):
            if suspect.sequence != index:
                type(suspect).objects.filter(pk=suspect.pk).update(sequence=index)

        spdp.laws_and_articles = saved.laws_and_articles
        spdp.status = SPDP.Status.PROCESS
        spdp.save(update_fields=("laws_and_articles", "status", "updated_at"))
        from notifications.services import close_case_deadline_notifications
        close_case_deadline_notifications(spdp)
        _schedule_document_issued_notification(
            spdp_id=spdp.pk,
            stage_key="stage1",
            document_id=saved.pk,
            document_number=saved.case_file_number,
            document_date=saved.completed_at,
            actor_id=request.user.pk,
        )
        messages.success(
            request,
            "Tahap 1 berhasil disimpan. Reminder P-16 sampai SOP Form-3 untuk perkara ini telah diselesaikan."
            if is_new else "Data Tahap 1 berhasil diperbarui.",
        )
        return redirect("cases:stage_one_detail", pk=spdp.pk)
    return render(request, "cases/stage_one_detail.html", {
        "spdp": spdp,
        "stage_one": stage_one,
        "form": form,
        "suspect_formset": suspect_formset,
    })


def _workflow_source_is_ready(spdp, source, documents):
    if source == "p16":
        draft = getattr(getattr(spdp, "p16_assignment", None), "draft", None)
        return bool(draft and draft.is_issued)
    if source == "p17":
        return any(_letter_number_is_issued(item.letter_number) for item in spdp.p17_drafts.all())
    if source == "sop02":
        draft = getattr(spdp, "sop_form_02_draft", None)
        return bool(draft and _letter_number_is_issued(draft.letter_number))
    if source == "stage1":
        return hasattr(spdp, "stage_one")
    if source in ("p18", "p19"):
        draft = documents.get(source)
        return bool(draft and _letter_number_is_issued(draft.letter_number))
    if source == "p21":
        draft = getattr(spdp, "p21_draft", None)
        return bool(draft and _letter_number_is_issued(draft.letter_number))
    return False


def _workflow_target_exists(spdp, target, documents):
    if target == "p17":
        return bool(list(spdp.p17_drafts.all()))
    if target == "sop02":
        return hasattr(spdp, "sop_form_02_draft")
    if target == "sop03":
        return hasattr(spdp, "sop_form_03_draft")
    if target == "stage1":
        return hasattr(spdp, "stage_one")
    if target == "p21":
        return hasattr(spdp, "p21_draft")
    return target in documents


@login_required
@require_POST
@transaction.atomic
def workflow_generate(request, source, target, pk):
    if source not in WORKFLOW_NEXT_ACTIONS or target not in {
        item[0] for item in WORKFLOW_NEXT_ACTIONS[source]
    }:
        raise PermissionDenied
    spdp = get_object_or_404(
        SPDP.objects.select_related(
            "stage_one", "sop_form_02_draft", "sop_form_03_draft",
            "p16_assignment__draft", "p16_assignment__kasi_pidum", "p21_draft",
        ).prefetch_related(
            "p17_drafts", "case_document_drafts", "p16_assignment__prosecutors",
            "p16_assignment__administrative_staff",
        ),
        pk=pk,
    )
    if not _can_manage_stage_one(request.user, spdp):
        raise PermissionDenied
    documents = {item.document_type: item for item in spdp.case_document_drafts.all()}
    source_list = {
        "p16": "cases:p16_list", "p17": "cases:p17_list",
        "sop02": "cases:sop_form_02_list", "stage1": "cases:stage_one_list",
        "p18": "cases:p18_list", "p19": "cases:p19_list", "p21": "cases:p21_list",
    }[source]
    if not _workflow_source_is_ready(spdp, source, documents):
        messages.error(request, "Dokumen sumber harus terbit sebelum membuat tahapan berikutnya.")
        return redirect(source_list)
    successors = WORKFLOW_NEXT_ACTIONS[source]
    if any(_workflow_target_exists(spdp, item[0], documents) for item in successors):
        messages.warning(
            request,
            "Salah satu tahapan lanjutan sudah dibuat. Tahapan lain dari menu ini tidak dapat dibuat lagi.",
        )
        return redirect(source_list)

    if target == "stage1":
        return redirect("cases:stage_one_detail", pk=spdp.pk)
    if target == "p17":
        draft = P17Draft.create_for_spdp(spdp, request.user)
        detail_url = "cases:p17_draft_detail"
    elif target == "sop02":
        draft = SOPForm02Draft.create_for_spdp(spdp, request.user)
        detail_url = "cases:sop_form_02_detail"
    elif target == "sop03":
        draft = SOPForm03Draft.create_for_spdp(spdp, request.user)
        detail_url = "cases:sop_form_03_detail"
    elif target == "p21":
        draft = P21Draft.create_for_spdp(spdp, request.user)
        detail_url = "cases:p21_draft_detail"
    else:
        document_type = {
            "p18": CaseDocumentDraft.DocumentType.P18,
            "p19": CaseDocumentDraft.DocumentType.P19,
            "p20": CaseDocumentDraft.DocumentType.P20,
            "sop07": CaseDocumentDraft.DocumentType.SOP_FORM_07,
        }[target]
        draft = CaseDocumentDraft.create_for_spdp(spdp, document_type, request.user)
        detail_url = CASE_DOCUMENT_CONFIG[target]["detail"]
    messages.success(request, f"Draf {dict(successors)[target].replace('Generate ', '')} berhasil dibuat.")
    return redirect(detail_url, pk=draft.pk)


def p17_accessible_spdps(user):
    queryset = SPDP.objects.filter(
        p16_assignment__draft__isnull=False,
        p17_drafts__isnull=True,
        stage_one__isnull=True,
    ).prefetch_related("suspects")
    if user.is_super_admin or user.has_role(Role.ADMIN):
        return queryset.order_by("-received_date", "-id")
    return queryset.filter(
        Q(created_by=user)
        | Q(p16_assignment__kasi_pidum=user)
        | Q(p16_assignment__prosecutors=user)
        | Q(p16_assignment__administrative_staff=user)
    ).distinct().order_by("-received_date", "-id")


@login_required
def p17_list(request):
    queryset = P17Draft.objects.select_related("spdp", "created_by").prefetch_related("spdp__suspects")
    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(letter_number__icontains=query)
            | Q(spdp__letter_number__icontains=query)
            | Q(spdp__suspects__name__icontains=query)
        ).distinct()
    page_obj, drafts_page = paginate_queryset(request, queryset, per_page=10)
    can_create = bool(p17_accessible_spdps(request.user).exists())
    today = timezone.localdate()
    drafts_page = attach_document_deadlines(
        drafts_page,
        today,
        "p17",
        spdp_id_getter=lambda draft: draft.spdp_id,
        document_id_getter=lambda draft: draft.pk,
        number_getter=lambda draft: draft.letter_number,
    )
    drafts_page = attach_workflow_actions(
        drafts_page,
        "p17",
        spdp_id_getter=lambda draft: draft.spdp_id,
        issued_getter=lambda draft: _letter_number_is_issued(draft.letter_number),
    )
    stats_queryset = P17Draft.objects.all()
    case_stats = {
        "total": stats_queryset.count(),
        "year": stats_queryset.filter(created_at__year=today.year).count(),
        "month": stats_queryset.filter(created_at__year=today.year, created_at__month=today.month).count(),
        "day": stats_queryset.filter(created_at__date=today).count(),
    }
    priority_cases = active_stage_priority_cases("p17", today)
    return render(request, "cases/p17_list.html", {
        "drafts": drafts_page,
        "page_obj": page_obj,
        "query": query,
        "can_create": can_create,
        "case_stats": case_stats,
        "priority_cases": priority_cases,
        "current_period": today,
    })


@login_required
@transaction.atomic
def p17_create(request):
    queryset = p17_accessible_spdps(request.user)
    if not queryset.exists():
        raise PermissionDenied
    form = P17CreateForm(request.POST or None, queryset=queryset)
    if request.method == "POST" and form.is_valid():
        draft = P17Draft.create_for_spdp(form.cleaned_data["spdp"], request.user)
        messages.success(request, f"Draf P-17 ke-{draft.sequence} berhasil dibuat.")
        return redirect("cases:p17_draft_detail", pk=draft.pk)
    return render(request, "cases/p17_create.html", {"form": form})


@login_required
@transaction.atomic
def p17_draft_detail(request, pk):
    draft = get_object_or_404(
        P17Draft.objects.select_related(
            "spdp__p16_assignment__kasi_pidum", "created_by", "last_edited_by"
        ).prefetch_related(
            "spdp__suspects",
            "spdp__p16_assignment__prosecutors",
            "spdp__p16_assignment__administrative_staff",
        ),
        pk=pk,
    )
    can_edit = _can_edit_p17(request.user, draft)
    ensure_p17_sections(draft)
    sop_form_1b = ensure_sop_form_1b(draft)
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = P17DraftForm(request.POST, request.FILES, instance=draft)
        sop_submitted = any(key.startswith("sop1b-") for key in request.POST)
        sop_form = SOPForm1BDraftForm(
            request.POST if sop_submitted else None,
            request.FILES if sop_submitted else None,
            instance=sop_form_1b,
            prefix="sop1b",
        )
        if form.is_valid() and (not sop_submitted or sop_form.is_valid()):
            saved = form.save(commit=False)
            saved.last_edited_by = request.user
            saved.save()
            if _letter_number_is_issued(saved.letter_number):
                from notifications.services import close_case_deadline_notifications
                close_case_deadline_notifications(saved.spdp)
                _schedule_document_issued_notification(
                    spdp_id=saved.spdp_id,
                    stage_key="p17",
                    document_id=saved.pk,
                    document_number=saved.letter_number,
                    document_date=saved.letter_date,
                    actor_id=request.user.pk,
                )
            if sop_submitted:
                saved_sop = sop_form.save(commit=False)
                saved_sop.last_edited_by = request.user
                saved_sop.save()
            messages.success(request, "Draf P-17 dan SOP Form-1B berhasil disimpan.")
            return redirect("cases:p17_draft_detail", pk=draft.pk)
    else:
        form = P17DraftForm(instance=draft)
        sop_form = SOPForm1BDraftForm(instance=sop_form_1b, prefix="sop1b")
    from configurations.models import InstitutionConfiguration
    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    signatory_context = _letter_signatory_context(draft, institution)
    from .p17_content import p17_recipients_for_editor
    recipients = p17_recipients_for_editor(draft)
    return render(request, "cases/p17_draft_detail.html", {
        "draft": draft,
        "form": form,
        "can_edit": can_edit,
        "institution": institution,
        "preview_content_html": build_p17_preview(draft),
        "sop_form": sop_form,
        "sop_form_1b": sop_form_1b,
        "sop_preview_content_html": build_sop_form_1b_preview(sop_form_1b),
        **signatory_context,
        "p17_sipede_destination": "; ".join(item["recipient"] for item in recipients),
        "p17_sipede_subject": strip_tags(draft.subject_html).strip(),
    })


@login_required
@require_POST
def p17_sipede_upload(request, pk):
    draft = get_object_or_404(
        P17Draft.objects.select_related("spdp__p16_assignment__kasi_pidum", "created_by")
        .prefetch_related("spdp__p16_assignment__prosecutors", "spdp__p16_assignment__administrative_staff"),
        pk=pk,
    )
    action = request.POST.get("action", "number").strip()
    if action != "pdf" and not _can_edit_p17(request.user, draft):
        raise PermissionDenied
    if action != "pdf" and draft.sipede_status == P17Draft.SipedeStatus.UPLOADED:
        return JsonResponse({"message": "P-17 ini sudah diunggah ke SIPede.", "uploaded": True, "number": draft.letter_number})

    from .sipede_p17 import (
        P17_SIFAT, P17SipedeError, P17SipedeLoginRequired, acquire_number,
        disposition_options, render_document_pdf, session_available, upload_document,
    )
    from .p17_numbering import P17NumberingError, build_p17_number, p17_number_parts

    session_key, payload_key = f"p17_sipede_number_{draft.pk}", f"p17_sipede_payload_{draft.pk}"
    try:
        if action == "session":
            session_available(request.user)
            return JsonResponse({"message": "Sesi SIPede aktif.", "session_active": True})
        if action == "dispositions":
            options = disposition_options(request.user)
            if not options:
                return JsonResponse({"message": "Daftar tujuan disposisi SIPede masih kosong."}, status=422)
            return JsonResponse({"options": options})
        if action == "pdf":
            pdf = render_document_pdf(request.POST.get("document_html", ""))
            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="P-17-{draft.pk}.pdf"'
            return response
        if action == "number":
            sifat = request.POST.get("sifat", P17_SIFAT).strip().upper()
            _, default_code = p17_number_parts(draft.spdp)
            issue_code = request.POST.get("kode_masalah", default_code).strip()
            destination = request.POST.get("tujuan", "").strip()
            subject = request.POST.get("perihal", "").strip()
            signatory = request.POST.get("penandatangan", "").strip()
            acting_fields, acting_error = _apply_acting_signatory_post(request, draft)
            if acting_error:
                return JsonResponse({"message": acting_error}, status=400)
            if not issue_code or len(issue_code) > 50 or not destination or len(destination) > 500 or not subject or len(subject) > 500:
                return JsonResponse({"message": "Kode masalah, tujuan, dan perihal wajib diisi dengan benar."}, status=400)
            requested_date = request.POST.get("letter_date", "").strip()
            if requested_date:
                try:
                    draft.letter_date = date.fromisoformat(requested_date)
                except ValueError:
                    return JsonResponse({"message": "Tanggal surat P-17 tidak valid."}, status=400)
            result = acquire_number(request.user, draft, sifat=sifat, issue_code=issue_code, signatory_name=signatory or None)
            raw_number = str(result.get("number") or "").strip()
            try:
                number = raw_number if raw_number.upper().startswith("B-") else build_p17_number(raw_number, draft.letter_date, draft.spdp)
            except P17NumberingError as exc:
                raise P17SipedeError(f"Format nomor SIPede tidak valid: {raw_number}") from exc
            if P17Draft.objects.exclude(pk=draft.pk).filter(letter_number=number).exists():
                raise P17SipedeError(f"Nomor SIPede {number} sudah digunakan oleh draf P-17 lain.")
            draft.letter_number = number
            draft.last_edited_by = request.user
            draft.save(update_fields=(
                "letter_number", "letter_date", "last_edited_by", *acting_fields, "updated_at",
            ))
            from notifications.services import close_case_deadline_notifications
            close_case_deadline_notifications(draft.spdp)
            request.session[session_key] = number
            request.session[payload_key] = {"sifat": sifat, "issue_code": issue_code, "destination": destination, "subject": subject, "signatory_name": signatory}
            return JsonResponse({"message": "Nomor P-17 berhasil diperoleh dari SIPede.", "number": number, "ready_for_upload": True}, status=202)
        if action != "upload":
            return JsonResponse({"message": "Aksi SIPede tidak dikenal."}, status=400)
        expected = str(request.session.get(session_key) or "").strip()
        if not expected or expected != draft.letter_number:
            return JsonResponse({"message": "Ambil nomor surat dari SIPede terlebih dahulu sebelum upload."}, status=409)
        payload = request.session.get(payload_key) or {}
        result = upload_document(
            request.user, draft, request.POST.get("document_html", ""),
            sifat=payload.get("sifat", P17_SIFAT), issue_code=payload.get("issue_code"),
            destination=payload.get("destination", ""), subject=payload.get("subject", ""),
            signatory_name=payload.get("signatory_name") or None,
            disposition_ids=request.POST.getlist("disposition_ids"),
        )
        draft.sipede_status = P17Draft.SipedeStatus.UPLOADED
        draft.sipede_uploaded_at = timezone.now()
        draft.save(update_fields=("sipede_status", "sipede_uploaded_at", "updated_at"))
        _schedule_document_issued_notification(
            spdp_id=draft.spdp_id,
            stage_key="p17",
            document_id=draft.pk,
            document_number=draft.letter_number,
            document_date=draft.letter_date,
            actor_id=request.user.pk,
        )
        request.session.pop(session_key, None)
        request.session.pop(payload_key, None)
        return JsonResponse({"message": "P-17 berhasil diunggah ke SIPede.", "uploaded": True, "number": result["number"]})
    except P17SipedeLoginRequired as exc:
        return JsonResponse({"message": str(exc), "requires_sipede_login": True, "integration_url": reverse("configurations:sipede_integration")}, status=401)
    except P17SipedeError as exc:
        return JsonResponse({"message": str(exc)}, status=422)
    except Exception as exc:
        return JsonResponse({"message": f"Proses P-17 ke SIPede gagal: {type(exc).__name__}: {exc}"}, status=502)


def p21_accessible_spdps(user):
    queryset = (
        SPDP.objects.filter(p16_assignment__draft__isnull=False, p21_draft__isnull=True)
        .filter(
            Q(stage_one__isnull=False, case_document_drafts__document_type__isnull=True)
            | Q(case_document_drafts__document_type=CaseDocumentDraft.DocumentType.P19)
        )
        .exclude(case_document_drafts__document_type=CaseDocumentDraft.DocumentType.P20)
        .prefetch_related("suspects")
        .distinct()
    )
    if user.is_super_admin or user.has_role(Role.ADMIN):
        return queryset.order_by("-received_date", "-id")
    return queryset.filter(
        Q(created_by=user)
        | Q(p16_assignment__kasi_pidum=user)
        | Q(p16_assignment__prosecutors=user)
        | Q(p16_assignment__administrative_staff=user)
    ).distinct().order_by("-received_date", "-id")


@login_required
def p21_list(request):
    queryset = P21Draft.objects.select_related(
        "spdp", "created_by", "spdp__p16_assignment__kasi_pidum",
    ).prefetch_related(
        "spdp__suspects", "spdp__p16_assignment__prosecutors",
        "spdp__p16_assignment__administrative_staff",
    )
    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(letter_number__icontains=query)
            | Q(spdp__letter_number__icontains=query)
            | Q(spdp__suspects__name__icontains=query)
        ).distinct()
    page_obj, drafts_page = paginate_queryset(request, queryset, per_page=10)
    today = timezone.localdate()
    drafts_page = attach_document_deadlines(
        drafts_page,
        today,
        "p21",
        spdp_id_getter=lambda draft: draft.spdp_id,
        document_id_getter=lambda draft: draft.pk,
        number_getter=lambda draft: draft.letter_number,
    )
    drafts_page = attach_workflow_actions(
        drafts_page,
        "p21",
        spdp_id_getter=lambda draft: draft.spdp_id,
        issued_getter=lambda draft: _letter_number_is_issued(draft.letter_number),
    )
    for draft in drafts_page:
        draft.can_mark_p21_completed = _can_edit_p21(request.user, draft)
    stats_queryset = P21Draft.objects.all()
    priority_cases = active_stage_priority_cases("p21", today)
    return render(request, "cases/p21_list.html", {
        "drafts": drafts_page,
        "page_obj": page_obj,
        "query": query,
        "can_create": p21_accessible_spdps(request.user).exists(),
        "case_stats": {
            "total": stats_queryset.count(),
            "year": stats_queryset.filter(created_at__year=today.year).count(),
            "month": stats_queryset.filter(created_at__year=today.year, created_at__month=today.month).count(),
            "day": stats_queryset.filter(created_at__date=today).count(),
        },
        "priority_cases": priority_cases,
        "current_period": today,
        "document_label": "P-21",
        "create_url_name": "cases:p21_create",
    })


@login_required
@require_POST
@transaction.atomic
def p21_mark_completed(request, pk):
    draft = get_object_or_404(
        P21Draft.objects.select_related(
            "spdp__p16_assignment__kasi_pidum", "created_by",
        ).prefetch_related(
            "spdp__p16_assignment__prosecutors",
            "spdp__p16_assignment__administrative_staff",
        ),
        pk=pk,
    )
    if not _can_edit_p21(request.user, draft):
        raise PermissionDenied
    if not _letter_number_is_issued(draft.letter_number):
        messages.error(request, "P-21 harus terbit sebelum ditandai sudah dilaksanakan.")
    elif draft.status == P21Draft.Status.COMPLETED:
        messages.info(request, "P-21 sudah tercatat dilaksanakan.")
    else:
        draft.status = P21Draft.Status.COMPLETED
        draft.save(update_fields=("status", "updated_at"))
        from notifications.services import close_p21_deadline_notifications
        close_p21_deadline_notifications(draft.spdp)
        messages.success(
            request,
            "P-21 ditandai sudah dilaksanakan. Reminder P-21 telah dihentikan.",
        )
    return redirect("cases:p21_list")


@login_required
@transaction.atomic
def p21_create(request):
    queryset = p21_accessible_spdps(request.user)
    if not queryset.exists():
        raise PermissionDenied
    form = P21CreateForm(request.POST or None, queryset=queryset)
    if request.method == "POST" and form.is_valid():
        draft = P21Draft.create_for_spdp(form.cleaned_data["spdp"], request.user)
        messages.success(request, "Draf P-21 berhasil dibuat.")
        return redirect("cases:p21_draft_detail", pk=draft.pk)
    return render(request, "cases/p21_create.html", {"form": form})


@login_required
@transaction.atomic
def p21_draft_detail(request, pk):
    draft = get_object_or_404(
        P21Draft.objects.select_related(
            "spdp__p16_assignment__kasi_pidum", "created_by", "last_edited_by",
        ).prefetch_related(
            "spdp__suspects", "spdp__p16_assignment__prosecutors",
            "spdp__p16_assignment__administrative_staff",
        ),
        pk=pk,
    )
    can_edit = _can_edit_p21(request.user, draft)
    ensure_p21_sections(draft)
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = P21DraftForm(request.POST, request.FILES, instance=draft)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.last_edited_by = request.user
            saved.save()
            if _letter_number_is_issued(saved.letter_number):
                from notifications.services import close_case_deadline_notifications
                close_case_deadline_notifications(saved.spdp)
                _schedule_document_issued_notification(
                    spdp_id=saved.spdp_id,
                    stage_key="p21",
                    document_id=saved.pk,
                    document_number=saved.letter_number,
                    document_date=saved.letter_date,
                    actor_id=request.user.pk,
                )
            messages.success(request, "Draf P-21 berhasil disimpan.")
            return redirect("cases:p21_draft_detail", pk=draft.pk)
    else:
        form = P21DraftForm(instance=draft)
    from configurations.models import InstitutionConfiguration
    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    signatory_context = _letter_signatory_context(draft, institution)
    return render(request, "cases/p21_draft_detail.html", {
        "draft": draft,
        "form": form,
        "can_edit": can_edit,
        "institution": institution,
        "preview_content_html": build_p21_preview(draft),
        "sipede_url_name": "cases:p21_sipede_upload",
        "document_label": "P-21",
        **signatory_context,
        "sipede_destination": "; ".join(item["recipient"] for item in p17_recipients_for_editor(draft)),
        "sipede_subject": strip_tags(draft.subject_html).strip(),
        "sipede_issue_code": __import__("cases.p17_numbering", fromlist=["p17_number_parts"]).p17_number_parts(draft.spdp)[1],
    })


def sop_accessible_spdps(user, form_number):
    if form_number == "02":
        queryset = SPDP.objects.filter(
            p17_drafts__isnull=False,
            sop_form_02_draft__isnull=True,
            stage_one__isnull=True,
        )
    else:
        queryset = SPDP.objects.filter(
            sop_form_02_draft__isnull=False,
            sop_form_03_draft__isnull=True,
            stage_one__isnull=True,
        )
    queryset = queryset.prefetch_related("suspects").distinct()
    if user.is_super_admin or user.has_role(Role.ADMIN):
        return queryset.order_by("-received_date", "-id")
    return queryset.filter(
        Q(created_by=user) | Q(p16_assignment__kasi_pidum=user)
        | Q(p16_assignment__prosecutors=user) | Q(p16_assignment__administrative_staff=user)
    ).distinct().order_by("-received_date", "-id")


def _sop_list(request, model, form_number):
    form_display_number = str(int(form_number))
    queryset = model.objects.select_related("spdp", "created_by").prefetch_related("spdp__suspects")
    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(Q(letter_number__icontains=query) | Q(spdp__letter_number__icontains=query) | Q(spdp__suspects__name__icontains=query)).distinct()
    page_obj, drafts_page = paginate_queryset(request, queryset, per_page=10)
    today = timezone.localdate()
    if form_number == "02":
        drafts_page = attach_document_deadlines(
            drafts_page,
            today,
            "sop02",
            spdp_id_getter=lambda draft: draft.spdp_id,
            document_id_getter=lambda draft: draft.pk,
            number_getter=lambda draft: draft.letter_number,
        )
        drafts_page = attach_workflow_actions(
            drafts_page,
            "sop02",
            spdp_id_getter=lambda draft: draft.spdp_id,
            issued_getter=lambda draft: _letter_number_is_issued(draft.letter_number),
        )
    stats_queryset = model.objects.all()
    priority_cases = (
        active_stage_priority_cases("sop02", today)
        if form_number == "02" else []
    )
    return render(request, "cases/sop_form_list.html", {
        "drafts": drafts_page, "page_obj": page_obj, "query": query,
        "form_number": form_number, "form_display_number": form_display_number,
        "can_create": sop_accessible_spdps(request.user, form_number).exists(),
        "case_stats": {
            "total": stats_queryset.count(),
            "year": stats_queryset.filter(created_at__year=today.year).count(),
            "month": stats_queryset.filter(created_at__year=today.year, created_at__month=today.month).count(),
            "day": stats_queryset.filter(created_at__date=today).count(),
        },
        "priority_cases": priority_cases,
        "current_period": today,
        "document_label": f"SOP Form {form_display_number}",
        "create_url_name": f"cases:sop_form_{form_number}_create",
    })


@login_required
def sop_form_02_list(request):
    return _sop_list(request, SOPForm02Draft, "02")


@login_required
def sop_form_03_list(request):
    return _sop_list(request, SOPForm03Draft, "03")


def _sop_create(request, model, form_number):
    form_display_number = str(int(form_number))
    queryset = sop_accessible_spdps(request.user, form_number)
    if not queryset.exists():
        raise PermissionDenied
    form = SOPFormCreateForm(request.POST or None, queryset=queryset)
    if request.method == "POST" and form.is_valid():
        draft = model.create_for_spdp(form.cleaned_data["spdp"], request.user)
        messages.success(request, f"Draf SOP Form {form_display_number} berhasil dibuat.")
        return redirect(f"cases:sop_form_{form_number}_detail", pk=draft.pk)
    return render(request, "cases/sop_form_create.html", {
        "form": form, "form_number": form_number,
        "form_display_number": form_display_number,
    })


@login_required
@transaction.atomic
def sop_form_02_create(request):
    return _sop_create(request, SOPForm02Draft, "02")


@login_required
@transaction.atomic
def sop_form_03_create(request):
    return _sop_create(request, SOPForm03Draft, "03")


def _sop_detail(request, pk, model, form_class, form_number):
    form_display_number = str(int(form_number))
    draft = get_object_or_404(
        model.objects.select_related("spdp__p16_assignment__kasi_pidum", "created_by", "last_edited_by").prefetch_related(
            "spdp__suspects", "spdp__p16_assignment__prosecutors", "spdp__p16_assignment__administrative_staff",
        ), pk=pk,
    )
    assignment = getattr(draft.spdp, "p16_assignment", None)
    can_edit = request.user.is_super_admin or request.user.has_role(Role.ADMIN) or request.user.pk == draft.created_by_id or (assignment and request.user.pk == assignment.kasi_pidum_id) or (assignment and assignment.prosecutors.filter(pk=request.user.pk).exists()) or (assignment and assignment.administrative_staff.filter(pk=request.user.pk).exists())
    if form_number == "02":
        ensure_sop_form_02_sections(draft)
    else:
        ensure_sop_form_03_sections(draft)
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = form_class(request.POST, request.FILES, instance=draft)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.last_edited_by = request.user
            saved.save()
            if _letter_number_is_issued(saved.letter_number):
                from notifications.services import close_case_deadline_notifications
                close_case_deadline_notifications(saved.spdp)
                _schedule_document_issued_notification(
                    spdp_id=saved.spdp_id,
                    stage_key=f"sop{form_number}",
                    document_id=saved.pk,
                    document_number=saved.letter_number,
                    document_date=saved.letter_date,
                    actor_id=request.user.pk,
                )
            messages.success(request, f"Draf SOP Form {form_display_number} berhasil disimpan.")
            return redirect(f"cases:sop_form_{form_number}_detail", pk=draft.pk)
    else:
        form = form_class(instance=draft)
    from configurations.models import InstitutionConfiguration
    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    from .p17_content import p17_recipients_for_editor
    recipients = p17_recipients_for_editor(draft)
    signatory_context = _letter_signatory_context(draft, institution)
    return render(request, "cases/sop_form_draft_detail.html", {
        "draft": draft, "form": form, "can_edit": can_edit, "institution": institution,
        "form_number": form_number, "form_display_number": form_display_number,
        "preview_content_html": build_sop_preview(draft, f"SOP FORM-{'2' if form_number == '02' else '03'}", form_number == "03"),
        **signatory_context,
        "sop_sipede_destination": "; ".join(item["recipient"] for item in recipients),
        "sop_sipede_subject": strip_tags(draft.subject_html).strip(),
    })


@login_required
@transaction.atomic
def sop_form_02_detail(request, pk):
    return _sop_detail(request, pk, SOPForm02Draft, SOPForm02DraftForm, "02")


@login_required
@transaction.atomic
def sop_form_03_detail(request, pk):
    return _sop_detail(request, pk, SOPForm03Draft, SOPForm03DraftForm, "03")


@login_required
@require_POST
def sop_form_sipede_upload(request, pk, form_number):
    configs = {
        "02": (SOPForm02Draft, "SOP Form 2", settings.SIPEDE_SOP_FORM_02_ID, "administrasiperkara"),
        "03": (SOPForm03Draft, "SOP Form 3", settings.SIPEDE_SOP_FORM_03_ID, "suratkeluar"),
        "p18": (CaseDocumentDraft, "P-18", settings.SIPEDE_P18_ID, "administrasiperkara"),
        "p19": (CaseDocumentDraft, "P-19", settings.SIPEDE_P19_ID, "suratkeluar"),
        "p20": (CaseDocumentDraft, "P-20", settings.SIPEDE_P20_ID, "suratkeluar"),
        "p21": (P21Draft, "P-21", settings.SIPEDE_P21_ID, "administrasiperkara"),
        "sop07": (CaseDocumentDraft, "SOP Form 7", settings.SIPEDE_SOP_FORM_07_ID, "suratkeluar"),
    }
    model, label, id_surat, form_route = configs[form_number]
    queryset = model.objects
    if model is CaseDocumentDraft:
        queryset = queryset.filter(document_type=form_number)
    draft = get_object_or_404(
        queryset.select_related("spdp__p16_assignment__kasi_pidum", "created_by")
        .prefetch_related("spdp__p16_assignment__prosecutors", "spdp__p16_assignment__administrative_staff"),
        pk=pk,
    )
    action = request.POST.get("action", "number").strip()
    if action != "pdf" and not _can_edit_p17(request.user, draft):
        raise PermissionDenied
    if action != "pdf" and draft.sipede_status == model.SipedeStatus.UPLOADED:
        return JsonResponse({"message": f"{label} sudah diunggah ke SIPede.", "uploaded": True, "number": draft.letter_number})
    from .sipede_p17 import (
        P17_SIFAT, P17SipedeError, P17SipedeLoginRequired, acquire_number,
        disposition_options, render_document_pdf, session_available, upload_document,
    )
    from .p17_numbering import P17NumberingError, build_p17_number, p17_number_parts
    session_key = f"sop_{form_number}_sipede_number_{draft.pk}"
    payload_key = f"sop_{form_number}_sipede_payload_{draft.pk}"
    service_kwargs = {
        "id_surat": id_surat,
        "document_label": label,
        "form_route": form_route,
    }
    try:
        if action == "session":
            session_available(request.user, **service_kwargs)
            return JsonResponse({"message": "Sesi SIPede aktif.", "session_active": True})
        if action == "dispositions":
            options = disposition_options(request.user, **service_kwargs)
            return JsonResponse({"options": options}) if options else JsonResponse({"message": "Daftar tujuan disposisi SIPede masih kosong."}, status=422)
        if action == "pdf":
            pdf = render_document_pdf(request.POST.get("document_html", ""), document_label=label)
            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{label.replace(" ", "-")}-{draft.pk}.pdf"'
            return response
        if action == "number":
            sifat = request.POST.get("sifat", P17_SIFAT).strip().upper()
            _, default_code = p17_number_parts(draft.spdp)
            issue_code = request.POST.get("kode_masalah", default_code).strip()
            destination = request.POST.get("tujuan", "").strip()
            subject = request.POST.get("perihal", "").strip()
            signatory = request.POST.get("penandatangan", "").strip()
            acting_fields, acting_error = _apply_acting_signatory_post(request, draft)
            if acting_error:
                return JsonResponse({"message": acting_error}, status=400)
            if not issue_code or not destination or not subject:
                return JsonResponse({"message": "Kode masalah, tujuan, dan perihal wajib diisi."}, status=400)
            requested_date = request.POST.get("letter_date", "").strip()
            if requested_date:
                try: draft.letter_date = date.fromisoformat(requested_date)
                except ValueError: return JsonResponse({"message": "Tanggal surat tidak valid."}, status=400)
            jenis_surat = (
                settings.SIPEDE_SURATKELUAR_JENIS
                if form_route == "suratkeluar" else None
            )
            result = acquire_number(
                request.user, draft, sifat=sifat, issue_code=issue_code,
                signatory_name=signatory or None, jenis_surat=jenis_surat,
                **service_kwargs,
            )
            raw_number = str(result.get("number") or "").strip()
            try: number = raw_number if raw_number.upper().startswith("B-") else build_p17_number(raw_number, draft.letter_date, draft.spdp)
            except P17NumberingError as exc: raise P17SipedeError(f"Format nomor SIPede tidak valid: {raw_number}") from exc
            if model.objects.exclude(pk=draft.pk).filter(letter_number=number).exists():
                raise P17SipedeError(f"Nomor SIPede {number} sudah digunakan.")
            draft.letter_number = number; draft.last_edited_by = request.user
            draft.save(update_fields=(
                "letter_number", "letter_date", "last_edited_by", *acting_fields, "updated_at",
            ))
            from notifications.services import close_case_deadline_notifications
            close_case_deadline_notifications(draft.spdp)
            request.session[session_key] = number
            request.session[payload_key] = {
                "sifat": sifat,
                "issue_code": issue_code,
                "destination": destination,
                "subject": subject,
                "signatory_name": signatory,
                "jenis_surat": result.get("jenis_surat"),
            }
            return JsonResponse({"message": f"Nomor {label} berhasil diperoleh.", "number": number, "ready_for_upload": True}, status=202)
        if action != "upload": return JsonResponse({"message": "Aksi SIPede tidak dikenal."}, status=400)
        expected = str(request.session.get(session_key) or "").strip()
        if not expected or expected != draft.letter_number:
            return JsonResponse({"message": "Ambil nomor surat dari SIPede terlebih dahulu."}, status=409)
        payload = request.session.get(payload_key) or {}
        jenis_surat = payload.get("jenis_surat") or (
            settings.SIPEDE_SURATKELUAR_JENIS
            if form_route == "suratkeluar" else None
        )
        result = upload_document(
            request.user, draft, request.POST.get("document_html", ""),
            sifat=payload.get("sifat", P17_SIFAT),
            issue_code=payload.get("issue_code"),
            destination=payload.get("destination", ""),
            subject=payload.get("subject", ""),
            signatory_name=payload.get("signatory_name") or None,
            disposition_ids=request.POST.getlist("disposition_ids"),
            jenis_surat=jenis_surat,
            **service_kwargs,
        )
        draft.sipede_status = model.SipedeStatus.UPLOADED; draft.sipede_uploaded_at = timezone.now()
        draft.save(update_fields=("sipede_status", "sipede_uploaded_at", "updated_at"))
        stage_key = {"02": "sop02", "03": "sop03"}.get(form_number, form_number)
        _schedule_document_issued_notification(
            spdp_id=draft.spdp_id,
            stage_key=stage_key,
            document_id=draft.pk,
            document_number=draft.letter_number,
            document_date=draft.letter_date,
            actor_id=request.user.pk,
        )
        request.session.pop(session_key, None); request.session.pop(payload_key, None)
        return JsonResponse({"message": f"{label} berhasil diunggah ke SIPede.", "uploaded": True, "number": result["number"]})
    except P17SipedeLoginRequired as exc:
        return JsonResponse({"message": str(exc), "requires_sipede_login": True}, status=401)
    except P17SipedeError as exc:
        return JsonResponse({"message": str(exc)}, status=422)
    except Exception as exc:
        return JsonResponse({"message": f"Proses {label} ke SIPede gagal: {type(exc).__name__}: {exc}"}, status=502)


CASE_DOCUMENT_CONFIG = {
    "p18": {"label": "P-18", "short": "P-18", "description": "Surat pengantar pengembalian berkas perkara dan petunjuk Penuntut Umum.", "list": "cases:p18_list", "create": "cases:p18_create", "detail": "cases:p18_detail"},
    "p19": {"label": "P-19", "short": "P-19", "description": "Petunjuk mengenai kelengkapan formil dan materiil berkas perkara.", "list": "cases:p19_list", "create": "cases:p19_create", "detail": "cases:p19_detail"},
    "p20": {"label": "P-20", "short": "P-20", "description": "Pemberitahuan bahwa waktu penyidikan tambahan telah habis.", "list": "cases:p20_list", "create": "cases:p20_create", "detail": "cases:p20_detail"},
    "sop07": {"label": "SOP Form 7", "short": "SOP FORM-7", "description": "Pengembalian SPDP dan berkas perkara setelah P-21 karena Tahap II belum dilaksanakan.", "list": "cases:sop_form_07_list", "create": "cases:sop_form_07_create", "detail": "cases:sop_form_07_detail"},
}


def case_document_accessible_spdps(user, document_type):
    if document_type == "p18":
        queryset = SPDP.objects.filter(stage_one__isnull=False, p21_draft__isnull=True)
    elif document_type == "p19":
        queryset = SPDP.objects.filter(
            case_document_drafts__document_type=CaseDocumentDraft.DocumentType.P18,
        )
    elif document_type == "p20":
        queryset = SPDP.objects.filter(
            case_document_drafts__document_type=CaseDocumentDraft.DocumentType.P19,
            p21_draft__isnull=True,
        )
    else:
        queryset = SPDP.objects.filter(p21_draft__isnull=False)
    queryset = queryset.exclude(case_document_drafts__document_type=document_type).prefetch_related("suspects").distinct()
    if user.is_super_admin or user.has_role(Role.ADMIN):
        return queryset.order_by("-received_date", "-id")
    return queryset.filter(Q(created_by=user) | Q(p16_assignment__kasi_pidum=user) | Q(p16_assignment__prosecutors=user) | Q(p16_assignment__administrative_staff=user)).distinct().order_by("-received_date", "-id")


def case_document_context(document_type):
    config = CASE_DOCUMENT_CONFIG[document_type]
    return {"document_type": document_type, "document_label": config["label"], "short_code": config["short"], "document_description": config["description"], "list_url_name": config["list"], "create_url_name": config["create"], "detail_url_name": config["detail"], "sipede_url_name": f"cases:{'sop_form_07' if document_type == 'sop07' else document_type}_sipede_upload"}


@login_required
def case_document_list(request, document_type):
    config = case_document_context(document_type)
    queryset = CaseDocumentDraft.objects.filter(document_type=document_type).select_related("spdp", "created_by").prefetch_related("spdp__suspects")
    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(Q(letter_number__icontains=query) | Q(spdp__letter_number__icontains=query) | Q(spdp__suspects__name__icontains=query)).distinct()
    page_obj, drafts_page = paginate_queryset(request, queryset, per_page=10)
    today = timezone.localdate()
    if document_type == CaseDocumentDraft.DocumentType.SOP_FORM_07:
        for draft in drafts_page:
            draft.workflow_is_issued = _letter_number_is_issued(draft.letter_number)
    if document_type not in (
        CaseDocumentDraft.DocumentType.P18,
        CaseDocumentDraft.DocumentType.P20,
        CaseDocumentDraft.DocumentType.SOP_FORM_07,
    ):
        drafts_page = attach_document_deadlines(
            drafts_page,
            today,
            document_type,
            spdp_id_getter=lambda draft: draft.spdp_id,
            document_id_getter=lambda draft: draft.pk,
            number_getter=lambda draft: draft.letter_number,
        )
    if document_type in (
        CaseDocumentDraft.DocumentType.P18,
        CaseDocumentDraft.DocumentType.P19,
    ):
        drafts_page = attach_workflow_actions(
            drafts_page,
            document_type,
            spdp_id_getter=lambda draft: draft.spdp_id,
            issued_getter=lambda draft: _letter_number_is_issued(draft.letter_number),
        )
    show_overview = True
    stats_queryset = CaseDocumentDraft.objects.filter(document_type=document_type)
    case_stats = {
        "total": stats_queryset.count(),
        "year": stats_queryset.filter(created_at__year=today.year).count(),
        "month": stats_queryset.filter(created_at__year=today.year, created_at__month=today.month).count(),
        "day": stats_queryset.filter(created_at__date=today).count(),
    }
    priority_cases = (
        active_stage_priority_cases("p19", today)
        if document_type == CaseDocumentDraft.DocumentType.P19 else []
    )
    return render(request, "cases/case_document_list.html", {
        **config, "drafts": drafts_page, "page_obj": page_obj, "query": query,
        "can_create": case_document_accessible_spdps(request.user, document_type).exists(),
        "show_overview": show_overview, "case_stats": case_stats,
        "priority_cases": priority_cases, "current_period": today,
    })


@login_required
@transaction.atomic
def case_document_create(request, document_type):
    config = case_document_context(document_type)
    queryset = case_document_accessible_spdps(request.user, document_type)
    if not queryset.exists():
        raise PermissionDenied
    form = SOPFormCreateForm(request.POST or None, queryset=queryset)
    if request.method == "POST" and form.is_valid():
        draft = CaseDocumentDraft.create_for_spdp(form.cleaned_data["spdp"], document_type, request.user)
        messages.success(request, f"Draf {config['document_label']} berhasil dibuat.")
        return redirect(config["detail_url_name"], pk=draft.pk)
    return render(request, "cases/case_document_create.html", {**config, "form": form})


@login_required
@transaction.atomic
def case_document_detail(request, document_type, pk):
    config = case_document_context(document_type)
    draft = get_object_or_404(CaseDocumentDraft.objects.select_related("spdp__p16_assignment__kasi_pidum", "created_by", "last_edited_by").prefetch_related("spdp__suspects", "spdp__p16_assignment__prosecutors", "spdp__p16_assignment__administrative_staff"), pk=pk, document_type=document_type)
    assignment = getattr(draft.spdp, "p16_assignment", None)
    can_edit = request.user.is_super_admin or request.user.has_role(Role.ADMIN) or request.user.pk == draft.created_by_id or (assignment and request.user.pk == assignment.kasi_pidum_id) or (assignment and assignment.prosecutors.filter(pk=request.user.pk).exists()) or (assignment and assignment.administrative_staff.filter(pk=request.user.pk).exists())
    ensure_case_document_sections(draft)
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = CaseDocumentDraftForm(request.POST, request.FILES, instance=draft)
        if form.is_valid():
            saved = form.save(commit=False); saved.last_edited_by = request.user; saved.save()
            if _letter_number_is_issued(saved.letter_number):
                from notifications.services import close_case_deadline_notifications
                close_case_deadline_notifications(saved.spdp)
                _schedule_document_issued_notification(
                    spdp_id=saved.spdp_id,
                    stage_key=document_type,
                    document_id=saved.pk,
                    document_number=saved.letter_number,
                    document_date=saved.letter_date,
                    actor_id=request.user.pk,
                )
            messages.success(request, f"Draf {config['document_label']} berhasil disimpan.")
            return redirect(config["detail_url_name"], pk=draft.pk)
    else:
        form = CaseDocumentDraftForm(instance=draft)
    from configurations.models import InstitutionConfiguration
    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    from .p17_numbering import p17_number_parts
    signatory_context = _letter_signatory_context(draft, institution)
    return render(request, "cases/case_document_detail.html", {**config, **signatory_context, "draft": draft, "form": form, "can_edit": can_edit, "institution": institution, "preview_content_html": build_case_document_preview(draft), "sipede_destination": "; ".join(item["recipient"] for item in p17_recipients_for_editor(draft)), "sipede_subject": strip_tags(draft.subject_html).strip(), "sipede_issue_code": p17_number_parts(draft.spdp)[1]})


COORDINATION_CONFIG = {
    "ba1": {"label": "BA Koordinasi I", "roman": "I", "list": "cases:coordination_1_list", "create": "cases:coordination_1_create", "detail": "cases:coordination_1_detail"},
    "ba2": {"label": "BA Koordinasi II", "roman": "II", "list": "cases:coordination_2_list", "create": "cases:coordination_2_create", "detail": "cases:coordination_2_detail"},
    "ba3": {"label": "BA Koordinasi III", "roman": "III", "list": "cases:coordination_3_list", "create": "cases:coordination_3_create", "detail": "cases:coordination_3_detail"},
}


def coordination_config(coordination_type):
    config = COORDINATION_CONFIG[coordination_type]
    return {
        "coordination_type": coordination_type,
        "document_label": config["label"],
        "coordination_roman": config["roman"],
        "list_url_name": config["list"],
        "create_url_name": config["create"],
        "detail_url_name": config["detail"],
    }


def coordination_accessible_spdps(user, coordination_type):
    queryset = (
        SPDP.objects.filter(p16_assignment__draft__isnull=False)
        .exclude(coordination_minutes_drafts__coordination_type=coordination_type)
        .prefetch_related("suspects")
        .distinct()
    )
    if user.is_super_admin or user.has_role(Role.ADMIN):
        return queryset.order_by("-received_date", "-id")
    return queryset.filter(
        Q(created_by=user)
        | Q(p16_assignment__kasi_pidum=user)
        | Q(p16_assignment__prosecutors=user)
        | Q(p16_assignment__administrative_staff=user)
    ).distinct().order_by("-received_date", "-id")


@login_required
def coordination_list(request, coordination_type):
    config = coordination_config(coordination_type)
    queryset = (
        CoordinationMinutesDraft.objects.filter(coordination_type=coordination_type)
        .select_related("spdp", "created_by")
        .prefetch_related("spdp__suspects")
    )
    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(draft_number__icontains=query)
            | Q(spdp__letter_number__icontains=query)
            | Q(spdp__suspects__name__icontains=query)
            | Q(prosecutor_name__icontains=query)
            | Q(investigator_name__icontains=query)
        ).distinct()
    page_obj, drafts_page = paginate_queryset(request, queryset, per_page=10)
    return render(request, "cases/coordination_list.html", {
        **config,
        "drafts": drafts_page,
        "page_obj": page_obj,
        "query": query,
        "can_create": coordination_accessible_spdps(request.user, coordination_type).exists(),
    })


@login_required
@transaction.atomic
def coordination_create(request, coordination_type):
    config = coordination_config(coordination_type)
    queryset = coordination_accessible_spdps(request.user, coordination_type)
    if not queryset.exists():
        raise PermissionDenied
    form = SOPFormCreateForm(request.POST or None, queryset=queryset)
    if request.method == "POST" and form.is_valid():
        draft = CoordinationMinutesDraft.create_for_spdp(
            form.cleaned_data["spdp"], coordination_type, request.user,
        )
        messages.success(request, f"Draf {config['document_label']} berhasil dibuat.")
        return redirect(config["detail_url_name"], pk=draft.pk)
    return render(request, "cases/coordination_create.html", {**config, "form": form})


@login_required
@transaction.atomic
def coordination_detail(request, coordination_type, pk):
    config = coordination_config(coordination_type)
    draft = get_object_or_404(
        CoordinationMinutesDraft.objects.select_related(
            "spdp__p16_assignment__kasi_pidum", "created_by", "last_edited_by",
        ).prefetch_related(
            "spdp__suspects", "spdp__p16_assignment__prosecutors",
            "spdp__p16_assignment__administrative_staff",
        ),
        pk=pk,
        coordination_type=coordination_type,
    )
    assignment = getattr(draft.spdp, "p16_assignment", None)
    can_edit = (
        request.user.is_super_admin
        or request.user.has_role(Role.ADMIN)
        or request.user.pk == draft.created_by_id
        or (assignment and request.user.pk == assignment.kasi_pidum_id)
        or (assignment and assignment.prosecutors.filter(pk=request.user.pk).exists())
        or (assignment and assignment.administrative_staff.filter(pk=request.user.pk).exists())
    )
    ensure_coordination_body(draft)
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = CoordinationMinutesDraftForm(request.POST, request.FILES, instance=draft)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.last_edited_by = request.user
            saved.save()
            messages.success(request, f"Draf {config['document_label']} berhasil disimpan.")
            return redirect(config["detail_url_name"], pk=draft.pk)
    else:
        form = CoordinationMinutesDraftForm(instance=draft)
    from configurations.models import InstitutionConfiguration
    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    return render(request, "cases/coordination_detail.html", {
        **config,
        "draft": draft,
        "form": form,
        "can_edit": can_edit,
        "institution": institution,
        "preview_content_html": build_coordination_preview(draft),
    })


@login_required
@transaction.atomic
def spdp_create(request):
    instance = SPDP(created_by=request.user)
    form = SPDPForm(request.POST or None, request.FILES or None, instance=instance)
    formset = SuspectFormSet(request.POST or None, instance=instance, prefix="suspects")
    victim_formset = VictimFormSet(request.POST or None, instance=instance, prefix="victims")
    receipt_formset = ReceiptFormSet(request.POST or None, instance=instance, prefix="receipts")
    if request.method == "POST" and form.is_valid() and formset.is_valid() and victim_formset.is_valid() and receipt_formset.is_valid():
        spdp = form.save(commit=False)
        spdp.created_by = request.user
        spdp.save()
        suspects = formset.save(commit=False)
        for deleted in formset.deleted_objects:
            deleted.delete()
        for index, suspect in enumerate(suspects, start=1):
            suspect.spdp = spdp
            suspect.sequence = index
            suspect.save()
        victims = victim_formset.save(commit=False)
        for deleted in victim_formset.deleted_objects:
            deleted.delete()
        for index, victim in enumerate(victims, start=1):
            victim.spdp = spdp
            victim.sequence = index
            victim.save()
        receipts = receipt_formset.save(commit=False)
        for deleted in receipt_formset.deleted_objects:
            deleted.delete()
        for index, receipt in enumerate(receipts, start=1):
            receipt.spdp = spdp
            receipt.sequence = index
            receipt.save()
        messages.success(request, f"SPDP {spdp.letter_number} berhasil disimpan.")
        return redirect("cases:spdp_detail", pk=spdp.pk)
    receipt_prosecutor_profiles = [
        {
            "id": str(user.pk),
            "name": user.display_name,
            "rank": user.rank,
            "position": "Jaksa Penuntut Umum",
            "nip": user.nip,
        }
        for user in User.objects.filter(
            is_active=True,
            roles__code=Role.PROSECUTOR,
        ).distinct().order_by("first_name", "last_name", "username")
    ]
    return render(request, "cases/spdp_form.html", {
        "form": form, "formset": formset, "victim_formset": victim_formset, "receipt_formset": receipt_formset,
        "case_types_by_directorate": form.case_types_by_directorate,
        "investigator_units_by_institution": form.investigator_units_by_institution,
        "receipt_prosecutor_profiles": receipt_prosecutor_profiles,
        "is_edit": False,
    })


@login_required
@transaction.atomic
def spdp_edit(request, pk):
    if not (
        request.user.is_super_admin
        or request.user.has_role(Role.ADMIN, Role.EMPLOYEE)
    ):
        raise PermissionDenied
    spdp = get_object_or_404(SPDP, pk=pk)
    form = SPDPForm(request.POST or None, request.FILES or None, instance=spdp)
    formset = SuspectFormSet(request.POST or None, instance=spdp, prefix="suspects")
    victim_formset = VictimFormSet(
        request.POST or None, instance=spdp, prefix="victims",
    )
    receipt_formset = ReceiptFormSet(
        request.POST or None, instance=spdp, prefix="receipts",
    )
    if (
        request.method == "POST"
        and form.is_valid()
        and formset.is_valid()
        and victim_formset.is_valid()
        and receipt_formset.is_valid()
    ):
        form.save()
        _save_spdp_related_formset(formset, spdp)
        _save_spdp_related_formset(victim_formset, spdp)
        _save_spdp_related_formset(receipt_formset, spdp)
        messages.success(request, f"Data perkara {spdp.letter_number} berhasil diperbarui.")
        return redirect("cases:spdp_detail", pk=spdp.pk)

    receipt_prosecutor_profiles = [
        {
            "id": str(user.pk),
            "name": user.display_name,
            "rank": user.rank,
            "position": "Jaksa Penuntut Umum",
            "nip": user.nip,
        }
        for user in User.objects.filter(
            is_active=True, roles__code=Role.PROSECUTOR,
        ).distinct().order_by("first_name", "last_name", "username")
    ]
    return render(request, "cases/spdp_form.html", {
        "form": form,
        "formset": formset,
        "victim_formset": victim_formset,
        "receipt_formset": receipt_formset,
        "case_types_by_directorate": form.case_types_by_directorate,
        "investigator_units_by_institution": form.investigator_units_by_institution,
        "receipt_prosecutor_profiles": receipt_prosecutor_profiles,
        "is_edit": True,
    })


def _save_spdp_related_formset(formset, spdp):
    objects = formset.save(commit=False)
    for deleted in formset.deleted_objects:
        deleted.delete()
    next_sequence = (
        formset.model.objects.filter(spdp=spdp)
        .order_by("-sequence")
        .values_list("sequence", flat=True)
        .first()
        or 0
    )
    for item in objects:
        item.spdp = spdp
        if not item.pk:
            next_sequence += 1
            item.sequence = next_sequence
        item.save()


@login_required
def spdp_detail(request, pk):
    spdp = get_object_or_404(
        SPDP.objects.select_related(
            "created_by",
            "p16_assignment__draft",
            "stage_one",
            "sop_form_02_draft",
            "sop_form_03_draft",
            "p21_draft",
        ).prefetch_related(
            "suspects",
            "victims",
            "receipts",
            "p17_drafts",
            "case_document_drafts",
        ),
        pk=pk,
    )
    spdp.workflow_status = _spdp_workflow_status(spdp)
    history = [{
        "icon": "▤",
        "title": "SPDP diterima",
        "subtitle": spdp.letter_number,
        "date": spdp.received_date,
        "url": "",
    }]

    def add_history(icon, title, subtitle, event_date, url):
        history.append({
            "icon": icon,
            "title": title,
            "subtitle": subtitle,
            "date": event_date,
            "url": url,
        })

    p16_draft = getattr(getattr(spdp, "p16_assignment", None), "draft", None)
    if p16_draft and _letter_number_is_issued(p16_draft.draft_number):
        add_history(
            "⚖", "P-16 diterbitkan", p16_draft.draft_number,
            p16_draft.letter_date,
            reverse("cases:p16_draft_detail", args=[p16_draft.pk]),
        )
    for p17_draft in spdp.p17_drafts.order_by("sequence"):
        if _letter_number_is_issued(p17_draft.letter_number):
            add_history(
                "✉",
                f"P-17 Permintaan {request_label(p17_draft.sequence)}",
                p17_draft.letter_number,
                p17_draft.letter_date,
                reverse("cases:p17_draft_detail", args=[p17_draft.pk]),
            )

    sop02 = getattr(spdp, "sop_form_02_draft", None)
    if sop02 and _letter_number_is_issued(sop02.letter_number):
        add_history(
            "▣", "SOP Form 2 diterbitkan", sop02.letter_number,
            sop02.letter_date,
            reverse("cases:sop_form_02_detail", args=[sop02.pk]),
        )
    sop03 = getattr(spdp, "sop_form_03_draft", None)
    if sop03 and _letter_number_is_issued(sop03.letter_number):
        add_history(
            "▣", "SOP Form 3 diterbitkan", sop03.letter_number,
            sop03.letter_date,
            reverse("cases:sop_form_03_detail", args=[sop03.pk]),
        )

    stage_one = getattr(spdp, "stage_one", None)
    if stage_one:
        add_history(
            "▤", "Tahap 1 diterima", stage_one.case_file_number,
            timezone.localtime(stage_one.completed_at).date(),
            reverse("cases:stage_one_detail", args=[stage_one.pk]),
        )

    case_document_history = (
        (
            CaseDocumentDraft.DocumentType.P18, "P-18 diterbitkan",
            "⚖", "cases:p18_detail",
        ),
        (
            CaseDocumentDraft.DocumentType.P19, "P-19 diterbitkan",
            "✉", "cases:p19_detail",
        ),
        (
            CaseDocumentDraft.DocumentType.P20, "P-20 diterbitkan",
            "✉", "cases:p20_detail",
        ),
    )
    documents = {
        draft.document_type: draft
        for draft in spdp.case_document_drafts.all()
    }
    for document_type, title, icon, route_name in case_document_history:
        draft = documents.get(document_type)
        if draft and _letter_number_is_issued(draft.letter_number):
            subtitle = draft.letter_number
            if (
                document_type == CaseDocumentDraft.DocumentType.P20
                and draft.sipede_status == CaseDocumentDraft.SipedeStatus.UPLOADED
            ):
                subtitle = f"{subtitle} · Diberhentikan"
            add_history(
                icon, title, subtitle, draft.letter_date,
                reverse(route_name, args=[draft.pk]),
            )

    p21_draft = getattr(spdp, "p21_draft", None)
    if p21_draft and _letter_number_is_issued(p21_draft.letter_number):
        subtitle = p21_draft.letter_number
        if p21_draft.status == P21Draft.Status.COMPLETED:
            subtitle = f"{subtitle} · Sudah dilaksanakan"
        add_history(
            "⚖", "P-21 diterbitkan", subtitle,
            p21_draft.letter_date,
            reverse("cases:p21_draft_detail", args=[p21_draft.pk]),
        )

    sop07 = documents.get(CaseDocumentDraft.DocumentType.SOP_FORM_07)
    if sop07 and _letter_number_is_issued(sop07.letter_number):
        add_history(
            "▣", "SOP Form 7 diterbitkan", sop07.letter_number,
            sop07.letter_date,
            reverse("cases:sop_form_07_detail", args=[sop07.pk]),
        )

    history.sort(key=lambda item: item["date"])
    can_edit = request.user.is_super_admin or request.user.has_role(
        Role.ADMIN, Role.EMPLOYEE,
    )
    return render(request, "cases/spdp_detail.html", {
        "spdp": spdp, "history": history, "can_edit": can_edit,
    })


@login_required
@transaction.atomic
def start_p16(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    if not (request.user.is_super_admin or request.user.has_role(Role.ADMIN, Role.EMPLOYEE)):
        raise PermissionDenied
    spdp = get_object_or_404(SPDP, pk=pk)
    if hasattr(spdp, "p16_assignment"):
        messages.warning(request, "SPDP tersebut sudah masuk proses P-16.")
        return redirect("cases:spdp_list")
    form = SelectKasiPidumForm(request.POST)
    if form.is_valid():
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=form.cleaned_data["kasi_pidum"], started_by=request.user
        )
        spdp.status = SPDP.Status.PROCESS
        spdp.save(update_fields=("status", "updated_at"))
        create_p16_assignment_web_notification(assignment, request.user)
        transaction.on_commit(
            lambda assignment_id=assignment.pk, actor_id=request.user.pk: send_p16_assignment_external_notifications(
                assignment_id, actor_id
            ),
            robust=True,
        )
        messages.success(
            request,
            f"P-16 diteruskan kepada {form.cleaned_data['kasi_pidum'].display_name}. Notifikasi otomatis diproses.",
        )
    else:
        messages.error(request, "Kasi Pidum tidak valid atau belum dipilih.")
    return redirect("cases:spdp_list")


@login_required
@transaction.atomic
def assign_prosecutors(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    assignment = get_object_or_404(P16Assignment.objects.select_related("kasi_pidum", "spdp"), spdp_id=pk)
    if not (request.user.is_super_admin or request.user.pk == assignment.kasi_pidum_id):
        raise PermissionDenied
    if assignment.status == P16Assignment.Status.ASSIGNED:
        messages.warning(request, "Jaksa P-16 sudah ditunjuk dan tidak dapat ditunjuk ulang.")
        return redirect("cases:spdp_list")
    form = SelectProsecutorsForm(request.POST)
    if form.is_valid():
        assignment.prosecutors.set(form.cleaned_data["prosecutors"])
        assignment.appointed_prosecutors.set(form.cleaned_data["prosecutors"])
        assignment.administrative_staff.set(form.cleaned_data["administrative_staff"])
        assignment.status = P16Assignment.Status.ASSIGNED
        assignment.assigned_at = timezone.now()
        assignment.save(update_fields=("status", "assigned_at"))
        names = ", ".join(user.display_name for user in form.cleaned_data["prosecutors"])
        draft, _ = P16Draft.create_for_assignment(assignment, request.user)
        messages.success(request, f"Jaksa P-16 berhasil ditunjuk: {names}. Draf P-16 otomatis dibuat.")
        return redirect("cases:p16_draft_detail", pk=draft.pk)
    else:
        messages.error(request, "Pilih minimal satu Jaksa yang aktif.")
    return redirect("cases:spdp_list")


@login_required
@transaction.atomic
def p16_draft_detail(request, pk):
    draft = get_object_or_404(
        P16Draft.objects.select_related(
            "assignment__spdp",
            "assignment__kasi_pidum",
            "generated_by",
            "signatory",
        ).prefetch_related(
            "assignment__prosecutors",
            "assignment__appointed_prosecutors",
            "assignment__administrative_staff__roles",
            "assignment__spdp__suspects",
        ),
        pk=pk,
    )
    can_edit = _can_edit_p16(request.user, draft)
    ensure_p16_sections(draft)
    if not draft.content_html:
        draft.content_html = build_default_p16_content(draft)
        draft.save(update_fields=("content_html", "updated_at"))
    spdp = draft.assignment.spdp
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = P16DraftForm(request.POST, request.FILES, instance=draft, assignment=draft.assignment)
        has_suspect_payload = "suspects-TOTAL_FORMS" in request.POST
        suspect_formset = SuspectFormSet(request.POST if has_suspect_payload else None, instance=spdp, prefix="suspects")
        if form.is_valid() and (not has_suspect_payload or suspect_formset.is_valid()):
            saved = form.save(commit=False)
            saved.last_edited_by = request.user
            saved.save()
            draft.assignment.prosecutors.set(form.cleaned_data["prosecutors"])
            draft.assignment.administrative_staff.set(form.cleaned_data["administrative_staff"])
            if has_suspect_payload:
                suspects = suspect_formset.save(commit=False)
                for deleted in suspect_formset.deleted_objects:
                    deleted.delete()
                next_sequence = (spdp.suspects.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
                for suspect in suspects:
                    suspect.spdp = spdp
                    if not suspect.pk:
                        suspect.sequence = next_sequence
                        next_sequence += 1
                    suspect.save()
                for index, suspect in enumerate(spdp.suspects.order_by("sequence", "id"), start=1):
                    if suspect.sequence != index:
                        type(suspect).objects.filter(pk=suspect.pk).update(sequence=index)
                spdp._prefetched_objects_cache.pop("suspects", None)
            saved.content_html = build_default_p16_content(saved)
            saved.save(update_fields=("content_html", "updated_at"))
            if _letter_number_is_issued(saved.draft_number):
                from notifications.services import close_case_deadline_notifications
                close_case_deadline_notifications(saved.assignment.spdp)
                _schedule_document_issued_notification(
                    spdp_id=saved.assignment.spdp_id,
                    stage_key="p16",
                    document_id=saved.pk,
                    document_number=saved.draft_number,
                    document_date=saved.letter_date,
                    actor_id=request.user.pk,
                )
            messages.success(request, "Draf P-16, penunjukan petugas administrasi, dan data pelaku berhasil disimpan.")
            return redirect("cases:p16_draft_detail", pk=draft.pk)
    else:
        form = P16DraftForm(instance=draft, assignment=draft.assignment)
        suspect_formset = SuspectFormSet(instance=spdp, prefix="suspects")
    from configurations.models import CMSIntegration, InstitutionConfiguration
    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    layout_configuration = DocumentLayoutConfiguration.objects.filter(
        template_key=DocumentLayoutConfiguration.TEMPLATE_P16,
    ).first()
    p16_layout = normalize_document_layout(
        "p16", layout_configuration.settings if layout_configuration else {},
    )
    preview_content_html = build_default_p16_content(draft)
    appointed_ids = set(draft.assignment.appointed_prosecutors.values_list("pk", flat=True))
    selected_ids = {str(value) for value in (form["prosecutors"].value() or [])}
    prosecutor_options = [
        {
            "user": prosecutor,
            "selected": str(prosecutor.pk) in selected_ids,
            "status": "appointed" if prosecutor.pk in appointed_ids else "additional",
        }
        for prosecutor in form.fields["prosecutors"].queryset
    ]
    selected_administrative_staff_ids = {
        str(value) for value in (form["administrative_staff"].value() or [])
    }
    administrative_staff_options = [
        {
            "user": employee,
            "selected": str(employee.pk) in selected_administrative_staff_ids,
        }
        for employee in form.fields["administrative_staff"].queryset
    ]
    default_sipede_signatory = (
        draft.signatory.display_name if draft.signatory_id else institution.leader_name
    )
    cms_can_choose_account = request.user.is_super_admin or request.user.has_role(
        Role.ADMIN, Role.EMPLOYEE,
    )
    assigned_prosecutor_ids = set(draft.assignment.prosecutors.values_list("pk", flat=True))
    cms_candidate_ids = {request.user.pk}
    if cms_can_choose_account:
        cms_candidate_ids.update(assigned_prosecutor_ids)
        cms_candidate_ids.update(
            User.objects.filter(
                is_active=True,
                roles__code=Role.PROSECUTOR,
            ).values_list("pk", flat=True)
        )
    cms_accounts = [
        {
            "user_id": integration.user_id,
            "name": integration.user.display_name,
            "username": integration.username,
            "is_self": integration.user_id == request.user.pk,
            "is_assigned": integration.user_id in assigned_prosecutor_ids,
        }
        for integration in CMSIntegration.objects.select_related("user").filter(
            user_id__in=cms_candidate_ids,
        ).order_by("user__first_name", "user__last_name", "user__username")
    ]
    cms_own_account = next((account for account in cms_accounts if account["is_self"]), None)
    cms_default_account = cms_own_account or next(
        (account for account in cms_accounts if account["is_assigned"]),
        cms_accounts[0] if cms_accounts else None,
    )
    for account in cms_accounts:
        account["is_default"] = account is cms_default_account
    sipede_signatory_names = []
    for name in [default_sipede_signatory, institution.leader_name, *User.objects.filter(
        is_active=True,
    ).order_by("first_name", "last_name", "username").values_list("first_name", "last_name", "username")]:
        if isinstance(name, tuple):
            first_name, last_name, username = name
            name = f"{first_name} {last_name}".strip() or username
        name = (name or "").strip()
        if name and name.casefold() not in {item.casefold() for item in sipede_signatory_names}:
            sipede_signatory_names.append(name)
    return render(request, "cases/p16_draft_detail.html", {
        "draft": draft,
        "form": form,
        "can_edit": can_edit,
        "institution": institution,
        "preview_content_html": preview_content_html,
        "prosecutor_options": prosecutor_options,
        "administrative_staff_options": administrative_staff_options,
        "sipede_signatory_names": sipede_signatory_names,
        "default_sipede_signatory": default_sipede_signatory,
        "cms_accounts": cms_accounts,
        "cms_can_choose_account": cms_can_choose_account,
        "cms_own_account": cms_own_account,
        "cms_default_account": cms_default_account,
        "suspect_formset": suspect_formset,
        "p16_layout_style": document_layout_style("p16", p16_layout),
    })


@login_required
@require_POST
def p16_cms_prepare(request, pk):
    draft = get_object_or_404(
        P16Draft.objects.select_related("assignment").prefetch_related("assignment__prosecutors"),
        pk=pk,
    )
    if not _can_edit_p16(request.user, draft):
        return JsonResponse({"message": "Anda tidak memiliki akses ke draf P-16 ini."}, status=403)

    try:
        account_user_id = int(request.POST.get("account_user_id", ""))
    except (TypeError, ValueError):
        return JsonResponse({"message": "Pilih akun CMS yang akan digunakan."}, status=400)

    can_choose_account = request.user.is_super_admin or request.user.has_role(
        Role.ADMIN, Role.EMPLOYEE,
    )
    if account_user_id != request.user.pk:
        target_is_prosecutor = User.objects.filter(
            pk=account_user_id,
            is_active=True,
            roles__code=Role.PROSECUTOR,
        ).exists()
        if not can_choose_account or not target_is_prosecutor:
            return JsonResponse({"message": "Akun CMS tersebut tidak dapat digunakan."}, status=403)
    if not CMSIntegration.objects.filter(user_id=account_user_id).exists():
        return JsonResponse({"message": "Akun CMS yang dipilih belum dikonfigurasi."}, status=400)

    try:
        return JsonResponse(cms_service.open_spdp_create(account_user_id))
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)


@login_required
@require_POST
def p16_sipede_upload(request, pk):
    draft = get_object_or_404(
        P16Draft.objects.select_related(
            "assignment__spdp", "assignment__kasi_pidum", "signatory",
        ).prefetch_related("assignment__prosecutors", "assignment__administrative_staff"),
        pk=pk,
    )
    action = request.POST.get("action", "number").strip()
    if action != "pdf" and not _can_edit_p16(request.user, draft):
        raise PermissionDenied
    if action != "pdf" and draft.sipede_status == P16Draft.SipedeStatus.UPLOADED:
        return JsonResponse({
            "message": "P-16 ini sudah diunggah ke SIPede.",
            "uploaded": True,
            "number": draft.draft_number,
        })

    from .sipede_p16 import (
        P16_ALLOWED_SIFAT, P16_PERIHAL, P16_SIFAT, P16_TUJUAN,
        P16SipedeError, P16SipedeLoginRequired, acquire_number,
        disposition_options, render_document_pdf, session_available, upload_document,
    )

    session_key = f"p16_sipede_number_{draft.pk}"
    payload_key = f"p16_sipede_payload_{draft.pk}"
    try:
        if action == "session":
            session_available(request.user)
            return JsonResponse({"message": "Sesi SIPede aktif.", "session_active": True})

        if action == "dispositions":
            options = disposition_options(request.user)
            if not options:
                return JsonResponse({
                    "message": "Daftar tujuan disposisi SIPede masih kosong. Tambahkan tujuan di SIPede terlebih dahulu."
                }, status=422)
            return JsonResponse({"options": options})

        if action == "pdf":
            document_html = request.POST.get("document_html", "")
            pdf = render_document_pdf(document_html)
            filename = f"P-16-{draft.pk}.pdf"
            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        if action == "number":
            sifat = request.POST.get("sifat", P16_SIFAT).strip().upper()
            from .p16_numbering import p16_number_parts
            _, default_issue_code = p16_number_parts(draft.assignment)
            issue_code = request.POST.get("kode_masalah", default_issue_code).strip()
            destination = request.POST.get("tujuan", P16_TUJUAN).strip()
            subject = request.POST.get("perihal", P16_PERIHAL).strip()
            signatory_name = request.POST.get("penandatangan", "").strip()
            acting_type = request.POST.get("acting_type", "").strip().lower()
            acting_name = request.POST.get("acting_name", "").strip()
            acting_position = request.POST.get("acting_position", "").strip()
            acting_nip = request.POST.get("acting_nip", "").strip()
            if sifat not in P16_ALLOWED_SIFAT:
                return JsonResponse({"message": "Sifat surat P-16 tidak valid."}, status=400)
            if not issue_code or len(issue_code) > 50 or "\n" in issue_code or "\r" in issue_code:
                return JsonResponse({"message": "Kode masalah wajib diisi dan maksimal 50 karakter."}, status=400)
            if not destination or len(destination) > 500:
                return JsonResponse({"message": "Tujuan wajib diisi dan maksimal 500 karakter."}, status=400)
            if not subject or len(subject) > 500:
                return JsonResponse({"message": "Perihal wajib diisi dan maksimal 500 karakter."}, status=400)
            if len(signatory_name) > 150:
                return JsonResponse({"message": "Nama penandatangan maksimal 150 karakter."}, status=400)
            if acting_type not in {"", P16Draft.ActingType.PLT, P16Draft.ActingType.PLH}:
                return JsonResponse({"message": "Pilihan PLT/PLH tidak valid."}, status=400)
            if acting_type and not all((acting_name, acting_position, acting_nip)):
                return JsonResponse({
                    "message": "Nama, Jabatan/Pangkat, dan NIP wajib diisi saat PLT/PLH dipilih."
                }, status=400)
            if len(acting_name) > 150 or len(acting_position) > 150 or len(acting_nip) > 30:
                return JsonResponse({"message": "Identitas pejabat PLT/PLH melebihi batas karakter."}, status=400)
            if acting_type:
                signatory_name = acting_name
            else:
                acting_name = acting_position = acting_nip = ""
            sipede_payload = {
                "sifat": sifat,
                "issue_code": issue_code,
                "destination": destination,
                "subject": subject,
                "signatory_name": signatory_name,
            }
            requested_date = request.POST.get("letter_date", "").strip()
            parsed_date = None
            if requested_date:
                try:
                    parsed_date = date.fromisoformat(requested_date)
                except ValueError:
                    return JsonResponse({"message": "Tanggal surat P-16 tidak valid."}, status=400)
            existing_number = str(request.session.get(session_key) or "").strip()
            normalized_existing_number = existing_number
            if existing_number and not existing_number.upper().startswith("PRINT-"):
                from .p16_numbering import build_p16_number, P16NumberingError
                try:
                    normalized_existing_number = build_p16_number(
                        existing_number, parsed_date or draft.letter_date, draft.assignment,
                    )
                except P16NumberingError as exc:
                    raise P16SipedeError(f"Format nomor SIPede tidak valid: {existing_number}") from exc
            if existing_number and draft.draft_number in {existing_number, normalized_existing_number}:
                if parsed_date and parsed_date != draft.letter_date:
                    return JsonResponse({
                        "message": "Tanggal tidak dapat diubah setelah nomor SIPede diperoleh. Muat ulang draf terlebih dahulu."
                    }, status=409)
                acting_identity = (acting_type, acting_name, acting_position, acting_nip)
                current_acting_identity = (
                    draft.acting_type, draft.acting_name, draft.acting_position, draft.acting_nip,
                )
                number_was_normalized = draft.draft_number != normalized_existing_number
                if current_acting_identity != acting_identity or number_was_normalized:
                    draft.acting_type = acting_type
                    draft.acting_name = acting_name
                    draft.acting_position = acting_position
                    draft.acting_nip = acting_nip
                    draft.draft_number = normalized_existing_number
                    draft.content_html = build_default_p16_content(draft)
                    draft.save(update_fields=(
                        "acting_type", "acting_name", "acting_position", "acting_nip",
                        "draft_number", "content_html", "updated_at",
                    ))
                request.session[session_key] = normalized_existing_number
                request.session[payload_key] = sipede_payload
                return JsonResponse({
                    "message": "Nomor P-16 SIPede sudah diperoleh.",
                    "number": normalized_existing_number,
                    "ready_for_upload": True,
                }, status=202)
            if parsed_date:
                draft.letter_date = parsed_date
            draft.acting_type = acting_type
            draft.acting_name = acting_name
            draft.acting_position = acting_position
            draft.acting_nip = acting_nip
            acquire_kwargs = {"sifat": sifat, "issue_code": issue_code}
            if signatory_name:
                acquire_kwargs["signatory_name"] = signatory_name
            result = acquire_number(request.user, draft, **acquire_kwargs)
            raw_number = str(result["number"] or "").strip()
            if raw_number.upper().startswith("PRINT-"):
                number = raw_number
            else:
                from .p16_numbering import build_p16_number, P16NumberingError
                try:
                    number = build_p16_number(raw_number, draft.letter_date, draft.assignment)
                except P16NumberingError as exc:
                    raise P16SipedeError(f"Format nomor SIPede tidak valid: {raw_number}") from exc
            if P16Draft.objects.exclude(pk=draft.pk).filter(draft_number=number).exists():
                raise P16SipedeError(f"Nomor SIPede {number} sudah digunakan oleh draf P-16 lain.")
            draft.draft_number = number
            draft.content_html = build_default_p16_content(draft)
            draft.last_edited_by = request.user
            draft.save(update_fields=(
                "draft_number", "letter_date", "acting_type", "acting_name", "acting_position",
                "acting_nip", "content_html", "last_edited_by", "updated_at",
            ))
            request.session[session_key] = number
            request.session[payload_key] = sipede_payload
            return JsonResponse({
                "message": "Nomor sequence P-16 berhasil diperoleh dari SIPede.",
                "number": number,
                "signatory_name": result["signatory_name"],
                "issue_code": result["issue_code"],
                "ready_for_upload": True,
            }, status=202)

        if action != "upload":
            return JsonResponse({"message": "Aksi SIPede tidak dikenal."}, status=400)
        expected_number = str(request.session.get(session_key) or "").strip()
        if not expected_number or expected_number != draft.draft_number:
            return JsonResponse({
                "message": "Ambil nomor surat dari SIPede terlebih dahulu sebelum upload."
            }, status=409)
        sipede_payload = request.session.get(payload_key)
        if not isinstance(sipede_payload, dict):
            from .p16_numbering import p16_number_parts
            _, default_issue_code = p16_number_parts(draft.assignment)
            sipede_payload = {
                "sifat": P16_SIFAT,
                "issue_code": default_issue_code,
                "destination": P16_TUJUAN,
                "subject": P16_PERIHAL,
            }
        document_html = request.POST.get("document_html", "")
        disposition_ids = request.POST.getlist("disposition_ids")
        upload_kwargs = {
            "sifat": sipede_payload.get("sifat", P16_SIFAT),
            "issue_code": sipede_payload.get("issue_code"),
            "destination": sipede_payload.get("destination", P16_TUJUAN),
            "subject": sipede_payload.get("subject", P16_PERIHAL),
        }
        if sipede_payload.get("signatory_name"):
            upload_kwargs["signatory_name"] = sipede_payload["signatory_name"]
        if disposition_ids:
            upload_kwargs["disposition_ids"] = disposition_ids
        result = upload_document(request.user, draft, document_html, **upload_kwargs)
        draft.sipede_status = P16Draft.SipedeStatus.UPLOADED
        draft.sipede_uploaded_at = timezone.now()
        draft.save(update_fields=("sipede_status", "sipede_uploaded_at", "updated_at"))
        _schedule_document_issued_notification(
            spdp_id=draft.assignment.spdp_id,
            stage_key="p16",
            document_id=draft.pk,
            document_number=draft.draft_number,
            document_date=draft.letter_date,
            actor_id=request.user.pk,
        )
        request.session.pop(session_key, None)
        request.session.pop(payload_key, None)
        return JsonResponse({
            "message": "P-16 berhasil diunggah sebagai draf Administrasi Perkara SIPede.",
            "uploaded": True,
            "number": result["number"],
        })
    except P16SipedeLoginRequired as exc:
        return JsonResponse({
            "message": str(exc), "requires_sipede_login": True,
            "integration_url": reverse("configurations:sipede_integration"),
        }, status=401)
    except P16SipedeError as exc:
        return JsonResponse({"message": str(exc)}, status=422)
    except Exception as exc:
        return JsonResponse({
            "message": f"Proses P-16 ke SIPede gagal: {type(exc).__name__}: {exc}"
        }, status=502)
