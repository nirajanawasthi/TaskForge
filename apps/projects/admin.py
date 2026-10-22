from django.contrib import admin

from .models import Project, ProjectMember


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "is_private", "created_by", "created_at")
    list_filter = ("is_private",)
    search_fields = ("name",)
    inlines = [ProjectMemberInline]
