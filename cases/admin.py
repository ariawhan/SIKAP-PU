from django.contrib import admin
from .models import CoordinationMinutesDraft, P16Assignment, P16Draft, Receipt, SPDP, StageOne, Suspect, Victim


class SuspectInline(admin.TabularInline):
    model = Suspect
    extra = 0


class VictimInline(admin.TabularInline):
    model = Victim
    extra = 0


class ReceiptInline(admin.TabularInline):
    model = Receipt
    extra = 0


@admin.register(SPDP)
class SPDPAdmin(admin.ModelAdmin):
    list_display = ("letter_number", "letter_date", "received_date", "investigator_agency", "status")
    search_fields = ("letter_number", "case_summary", "suspects__name", "victims__name")
    list_filter = ("status", "received_date")
    exclude = ("origin", "criminal_code")
    inlines = (SuspectInline, VictimInline, ReceiptInline)

@admin.register(P16Assignment)
class P16AssignmentAdmin(admin.ModelAdmin):
    list_display = ("spdp", "kasi_pidum", "status", "assigned_at")
    filter_horizontal = ("prosecutors", "administrative_staff")


admin.site.register(P16Draft)
admin.site.register(CoordinationMinutesDraft)
admin.site.register(StageOne)
