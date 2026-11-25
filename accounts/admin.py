from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Role, User

admin.site.register(Role)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Identitas SIKAP-PU", {"fields": ("nip", "nrp", "rank", "grade", "whatsapp_number", "photo", "photo_position_x", "photo_position_y")}),)
    fieldsets = fieldsets + (("Hak akses SIKAP-PU", {"fields": ("roles",)}),)
    fieldsets = fieldsets + (("Notifikasi", {"fields": ("telegram_chat_id",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Hak akses SIKAP-PU", {"fields": ("email", "nip", "nrp", "rank", "grade", "whatsapp_number", "photo", "photo_position_x", "photo_position_y", "roles", "telegram_chat_id")}),)
    list_display = ("username", "email", "first_name", "nip", "role_list", "telegram_chat_id", "is_active")
    list_filter = ("roles", "is_active")
    filter_horizontal = ("roles", "groups", "user_permissions")

    @admin.display(description="Role")
    def role_list(self, obj):
        return obj.role_labels
