from django.db import migrations, models


def preserve_legacy_administrators(apps, schema_editor):
    Membership = apps.get_model("library", "Membership")
    # Legacy staff memberships represented existing library administrators.
    # Library creation is a separate capability granted by explicit provisioning.
    Membership.objects.filter(user__is_staff=True).update(role="admin")


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0009_alter_library_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="role",
            field=models.CharField(
                choices=[("admin", "Administradora"), ("member", "Membro")],
                db_default="member",
                default="member",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="can_create_libraries",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.RunPython(preserve_legacy_administrators, migrations.RunPython.noop),
    ]
