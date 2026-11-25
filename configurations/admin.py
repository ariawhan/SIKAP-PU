from django.contrib import admin
from .models import (
    DocumentLayoutConfiguration,
    DocumentTemplateConfiguration,
    InstitutionConfiguration,
    InvestigatorInstitution,
    InvestigatorUnit,
    IssueCode,
    LetterNumberCaseType,
    LetterNumberCode,
    LetterNumberConfiguration,
)

admin.site.register(InstitutionConfiguration)
admin.site.register(LetterNumberConfiguration)
admin.site.register(IssueCode)
admin.site.register(LetterNumberCode)
admin.site.register(LetterNumberCaseType)
admin.site.register(InvestigatorInstitution)
admin.site.register(InvestigatorUnit)
admin.site.register(DocumentLayoutConfiguration)
admin.site.register(DocumentTemplateConfiguration)
