from typing import Any, ClassVar

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from . import circulation, invites, services
from .auth import technical
from .models import (
    Book,
    Copy,
    ImportRow,
    ImportSession,
    Library,
    LibraryCreationInvite,
    Loan,
    Location,
    Membership,
    Person,
    ShareLink,
    Tag,
    User,
)


class ProtectedUserAdmin(UserAdmin):
    def delete_model(self, request, obj):
        _admin_guard(lambda: services.delete_users([obj.pk]))

    def delete_queryset(self, request, queryset):
        _admin_guard(lambda: services.delete_users(list(queryset.values_list("pk", flat=True))))


def _admin_guard(operation):
    try:
        return operation()
    except ValidationError as exc:
        raise PermissionDenied(" ".join(exc.messages)) from exc


admin.site.register(User, ProtectedUserAdmin)


class LibraryCreationInviteAdminForm(forms.ModelForm):
    class Meta:
        model = LibraryCreationInvite
        fields = ["email"]


@admin.register(LibraryCreationInvite)
class LibraryCreationInviteAdmin(admin.ModelAdmin):
    form = LibraryCreationInviteAdminForm
    list_display = (
        "email",
        "status_display",
        "created_at",
        "expires_at",
        "accepted_by",
        "created_library",
    )
    list_filter = ("accepted_at", "revoked_at", "created_at")
    search_fields = ("email", "accepted_by__email", "created_library__name")
    actions = ["revoke_selected"]
    readonly_fields = (
        "created_by",
        "created_at",
        "expires_at",
        "accepted_at",
        "accepted_by",
        "revoked_at",
        "revoked_by",
        "created_library",
        "status_display",
    )

    def _owner(self, request):
        return technical(request.user)

    def has_module_permission(self, request):
        return self._owner(request)

    def has_view_permission(self, request, obj=None):
        return self._owner(request)

    def has_add_permission(self, request):
        return self._owner(request)

    def has_change_permission(self, request, obj=None):
        return self._owner(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        return ("email",) if obj is None else self.readonly_fields + ("email",)

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else self.readonly_fields + ("email",)

    @admin.display(description="Estado")
    def status_display(self, obj):
        return invites.invite_status(obj)

    def save_model(self, request, obj, form, change):
        if change:
            raise PermissionDenied("Convites de criação não podem ser editados.")
        invite, invite_url = invites.create_creation_link(request, request.user, obj.email)
        obj.pk = invite.pk
        obj._state.adding = False
        obj._state.db = invite._state.db
        self.message_user(
            request,
            f"Convite criado. Copie este link agora; ele não será exibido novamente: {invite_url}",
            level=messages.SUCCESS,
        )

    @admin.action(description="Revogar convites de criação selecionados")
    def revoke_selected(self, request, queryset):
        revoked = 0
        for invite in queryset:
            try:
                invites.revoke_creation_invite(invite.pk, request.user)
                revoked += 1
            except invites.InviteError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
        if revoked:
            self.message_user(request, f"{revoked} convite(s) revogado(s).", level=messages.SUCCESS)


class BookAdminForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = "__all__"

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        library = data.get("library")
        tags = data.get("tags", [])
        if library and any(tag.library_id != library.pk for tag in tags):
            raise ValidationError("As tags devem pertencer à mesma biblioteca.")
        if data.get("isbn"):
            data["isbn"] = services.normalize_isbn(data["isbn"])
        return data


class LocationAdminForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = "__all__"

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        parent = data.get("parent")
        if parent and data.get("library") and parent.library_id != data["library"].pk:
            raise ValidationError("O local pai deve pertencer à biblioteca.")
        while parent:
            if parent.pk == self.instance.pk:
                raise ValidationError("Um local não pode conter a si mesmo.")
            parent = parent.parent
        return data


class SafeAdmin(admin.ModelAdmin):
    readonly_fields: ClassVar[tuple[str, ...]] = ("created_at",)

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("library",) if obj else ())

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(Book)
class BookAdmin(SafeAdmin):
    form = BookAdminForm
    list_display = ("title", "isbn", "is_desired", "library")
    list_filter = ("is_desired", "library")
    readonly_fields = ("created_at", "is_desired")
    search_fields = ("title", "isbn")
    filter_horizontal = ("tags",)


@admin.register(Copy)
class CopyAdmin(SafeAdmin):
    list_display = ("number", "book", "location", "state")
    list_filter = ("state", "library")
    readonly_fields = ("created_at", "number", "state", "retired_on")
    actions = ["mark_sold", "mark_donated", "mark_lost", "reactivate"]

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("library", "book") if obj else ())

    def save_model(self, request, obj, form, change):
        if change:
            services.locate_copies(obj.library, [obj.pk], obj.location_id)
            Copy.objects.filter(pk=obj.pk).update(acquired_on=obj.acquired_on)
        else:
            saved = services.add_copy(obj.library, obj.book_id, obj.location_id, obj.acquired_on)
            obj.pk = saved.pk
            obj.number = saved.number
            obj.created_at = saved.created_at

    def _retire(self, request, queryset, reason):
        for copy in queryset:
            try:
                circulation.retire_copy(copy.library, copy.pk, reason)
            except ValidationError as exc:
                self.message_user(request, "; ".join(exc.messages), level="error")

    @admin.action(description="Dar baixa por venda")
    def mark_sold(self, request, queryset):
        self._retire(request, queryset, "sold")

    @admin.action(description="Dar baixa por doação")
    def mark_donated(self, request, queryset):
        self._retire(request, queryset, "donated")

    @admin.action(description="Dar baixa por perda")
    def mark_lost(self, request, queryset):
        self._retire(request, queryset, "lost")

    @admin.action(description="Reativar exemplares")
    def reactivate(self, request, queryset):
        self._retire(request, queryset, "active")


class LoanAdminForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = "__all__"

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        copy = data.get("copy")
        person = data.get("person")
        lib = data.get("library")
        if (
            copy
            and lib
            and copy.library_id != lib.pk
            or person
            and lib
            and person.library_id != lib.pk
        ):
            raise ValidationError("Todos os registros devem pertencer à mesma biblioteca.")
        if (
            not self.instance.pk
            and copy
            and (copy.state != "active" or copy.loans.filter(state="open").exists())
        ):
            raise ValidationError("Exemplar indisponível.")
        return data


@admin.register(Loan)
class LoanAdmin(SafeAdmin):
    form = LoanAdminForm
    list_display = ("copy", "person", "started_on", "due_on", "returned_on", "state")
    list_filter = ("state",)
    readonly_fields = ("created_at", "returned_on", "state")
    actions = ["mark_returned", "mark_lost"]

    def get_readonly_fields(self, request, obj=None):
        return tuple(f.name for f in self.model._meta.fields) if obj else self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not change:
            saved = circulation.lend(
                obj.library, obj.copy_id, obj.person_id, obj.started_on, obj.due_on
            )
            obj.pk = saved.pk
            obj.created_at = saved.created_at

    @admin.action(description="Registrar devolução hoje")
    def mark_returned(self, request, queryset):
        for loan in queryset.filter(state="open"):
            try:
                circulation.return_loan(loan.library, loan.pk, timezone.localdate())
            except ValidationError as exc:
                self.message_user(request, "; ".join(exc.messages), level="error")

    @admin.action(description="Registrar perda")
    def mark_lost(self, request, queryset):
        for loan in queryset.filter(state="open"):
            circulation.retire_copy(loan.library, loan.copy_id, "lost")


@admin.register(Location)
class LocationAdmin(SafeAdmin):
    form = LocationAdminForm
    list_display = ("name", "parent", "library")

    def save_model(self, request, obj, form, change):
        saved = services.save_location(
            obj.library, {"name": obj.name, "parent_id": obj.parent_id}, obj.pk
        )
        obj.pk = saved.pk


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "library", "role", "joined_at")
    list_filter = ("role", "library")
    search_fields = ("user__email", "user__username", "library__name")
    readonly_fields = ("joined_at", "invitation")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ("user", "library")
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        if obj and obj.role == Membership.ROLE_ADMIN:
            if (
                Membership.objects.filter(
                    library_id=obj.library_id, role=Membership.ROLE_ADMIN
                ).count()
                <= 1
            ):
                return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if change:
            _admin_guard(lambda: services.change_membership_role(obj.pk, obj.role))
            obj.refresh_from_db()
            return
        obj.full_clean()
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        _admin_guard(lambda: services.delete_memberships([obj.pk]))

    def delete_queryset(self, request, queryset):
        _admin_guard(
            lambda: services.delete_memberships(list(queryset.values_list("pk", flat=True)))
        )


class LibraryAdmin(admin.ModelAdmin):
    readonly_fields = ("next_number",)

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Library, LibraryAdmin)
for model in [Tag, Person]:
    admin.site.register(model, SafeAdmin)


class ReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(f.name for f in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for readonly_model in [ShareLink, ImportSession, ImportRow]:
    admin.site.register(readonly_model, ReadOnlyAdmin)
