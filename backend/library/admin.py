from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from .models import User, Library, Membership, Book, Copy, Location, Tag, Person, Loan, ShareLink, ImportSession, ImportRow

admin.site.register(User, UserAdmin)
admin.site.site_header = 'Julib · Administração'

class SafeAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at',)
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Book)
class BookAdmin(SafeAdmin):
    list_display = ('title','isbn','library')
    search_fields = ('title','isbn')
    filter_horizontal = ('tags',)
    def save_model(self, request, obj, form, change):
        from .services import normalize_isbn
        obj.isbn = normalize_isbn(obj.isbn)
        super().save_model(request, obj, form, change)

@admin.register(Copy)
class CopyAdmin(SafeAdmin):
    list_display = ('number','book','location','state')
    list_filter = ('state','library')
    def get_readonly_fields(self, request, obj=None):
        return tuple(f.name for f in self.model._meta.fields)
    def has_add_permission(self, request):
        return False

@admin.register(Loan)
class LoanAdmin(CopyAdmin):
    list_display = ('copy','person','started_on','due_on','returned_on','state')
    list_filter = ('state',)
    actions = ['mark_returned','mark_lost']
    @admin.action(description='Registrar devolução hoje')
    def mark_returned(self, request, queryset):
        from django.utils import timezone
        from .circulation import return_loan
        for loan in queryset.filter(state='open'):
            return_loan(loan.library, loan.pk, timezone.localdate())
    @admin.action(description='Registrar perda')
    def mark_lost(self, request, queryset):
        from .circulation import retire_copy
        for loan in queryset.filter(state='open'):
            retire_copy(loan.library, loan.copy_id, 'lost')

@admin.register(Location)
class LocationAdmin(SafeAdmin):
    list_display = ('name','parent','library')
    def save_model(self, request, obj, form, change):
        from .services import save_location
        saved = save_location(obj.library, {'name': obj.name, 'parent_id': obj.parent_id}, obj.pk)
        obj.pk = saved.pk

for model in [Library, Membership, Tag, Person, ShareLink, ImportSession, ImportRow]:
    admin.site.register(model)
