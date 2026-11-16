from django.db import migrations

SECURE_TRIGGER_FUNCTIONS = r"""
CREATE OR REPLACE FUNCTION public.julib_check_book_tag_library()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp
AS $$
BEGIN
    IF (SELECT library_id FROM public.library_book WHERE id = NEW.book_id)
       IS DISTINCT FROM
       (SELECT library_id FROM public.library_tag WHERE id = NEW.tag_id) THEN
        RAISE EXCEPTION 'Book and tag must belong to the same library'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.julib_check_book_tag_parent_library()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp
AS $$
BEGIN
    IF TG_TABLE_NAME = 'library_book' AND EXISTS (
        SELECT 1 FROM public.library_book_tags bt
        JOIN public.library_tag t ON t.id = bt.tag_id
        WHERE bt.book_id = NEW.id AND t.library_id <> NEW.library_id
    ) THEN
        RAISE EXCEPTION 'Book and tag must belong to the same library'
            USING ERRCODE = '23514';
    ELSIF TG_TABLE_NAME = 'library_tag' AND EXISTS (
        SELECT 1 FROM public.library_book_tags bt
        JOIN public.library_book b ON b.id = bt.book_id
        WHERE bt.tag_id = NEW.id AND b.library_id <> NEW.library_id
    ) THEN
        RAISE EXCEPTION 'Book and tag must belong to the same library'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.julib_check_import_row_copy_library()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp
AS $$
BEGIN
    IF NEW.copy_id IS NOT NULL
       AND (SELECT library_id FROM public.library_importsession WHERE id = NEW.session_id)
           IS DISTINCT FROM
           (SELECT library_id FROM public.library_copy WHERE id = NEW.copy_id) THEN
        RAISE EXCEPTION 'Import row and copy must belong to the same library'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.julib_check_import_row_parent_library()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp
AS $$
BEGIN
    IF TG_TABLE_NAME = 'library_importsession' AND EXISTS (
        SELECT 1 FROM public.library_importrow ir
        JOIN public.library_copy c ON c.id = ir.copy_id
        WHERE ir.session_id = NEW.id AND c.library_id <> NEW.library_id
    ) THEN
        RAISE EXCEPTION 'Import row and copy must belong to the same library'
            USING ERRCODE = '23514';
    ELSIF TG_TABLE_NAME = 'library_copy' AND EXISTS (
        SELECT 1 FROM public.library_importrow ir
        JOIN public.library_importsession s ON s.id = ir.session_id
        WHERE ir.copy_id = NEW.id AND s.library_id <> NEW.library_id
    ) THEN
        RAISE EXCEPTION 'Import row and copy must belong to the same library'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0013_invite_membership_library_constraint"),
    ]

    operations = [
        migrations.RunSQL(SECURE_TRIGGER_FUNCTIONS),
    ]
