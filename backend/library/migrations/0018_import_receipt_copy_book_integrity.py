from django.db import migrations

CREATE_RECEIPT_COPY_BOOK_GUARDS = r"""
CREATE FUNCTION public.julib_check_import_receipt_copy_book()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    receipt_library_id bigint;
    receipt_book_id bigint;
    copy_library_id bigint;
    copy_book_id bigint;
BEGIN
    SELECT library_id, book_id INTO receipt_library_id, receipt_book_id
    FROM public.library_importreceipt
    WHERE id = NEW.receipt_id
    FOR UPDATE;

    IF NOT FOUND OR receipt_library_id IS DISTINCT FROM NEW.library_id THEN
        RAISE EXCEPTION 'Import receipt and copy relation must belong to the same library'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.copy_id IS NOT NULL THEN
        SELECT library_id, book_id INTO copy_library_id, copy_book_id
        FROM public.library_copy
        WHERE id = NEW.copy_id
        FOR UPDATE;

        IF NOT FOUND
           OR copy_library_id IS DISTINCT FROM NEW.library_id
           OR copy_book_id IS DISTINCT FROM receipt_book_id THEN
            RAISE EXCEPTION 'Imported copy must belong to the book on its receipt'
                USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;
CREATE TRIGGER import_receipt_copy_book_same_book
BEFORE INSERT OR UPDATE ON public.library_importreceiptcopy
FOR EACH ROW EXECUTE FUNCTION public.julib_check_import_receipt_copy_book();

CREATE FUNCTION public.julib_check_import_receipt_copy_book_parent()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF TG_TABLE_NAME = 'library_importreceipt' AND EXISTS (
        SELECT 1
        FROM public.library_importreceiptcopy rc
        JOIN public.library_copy c ON c.id = rc.copy_id
        WHERE rc.receipt_id = NEW.id
          AND rc.copy_id IS NOT NULL
          AND (NEW.book_id IS NULL OR c.book_id IS DISTINCT FROM NEW.book_id)
    ) THEN
        RAISE EXCEPTION 'Receipt book must match every imported copy'
            USING ERRCODE = '23514';
    ELSIF TG_TABLE_NAME = 'library_copy' AND EXISTS (
        SELECT 1
        FROM public.library_importreceiptcopy rc
        JOIN public.library_importreceipt ir ON ir.id = rc.receipt_id
        WHERE rc.copy_id = NEW.id
          AND (ir.book_id IS DISTINCT FROM NEW.book_id
               OR ir.library_id IS DISTINCT FROM NEW.library_id
               OR rc.library_id IS DISTINCT FROM NEW.library_id)
    ) THEN
        RAISE EXCEPTION 'Imported copy must stay with its receipt book and library'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;
CREATE TRIGGER import_receipt_book_copy_parent_same_book
BEFORE UPDATE OF book_id ON public.library_importreceipt
FOR EACH ROW EXECUTE FUNCTION public.julib_check_import_receipt_copy_book_parent();
CREATE TRIGGER import_receipt_copy_parent_same_book
BEFORE UPDATE OF book_id ON public.library_copy
FOR EACH ROW EXECUTE FUNCTION public.julib_check_import_receipt_copy_book_parent();
"""

DROP_RECEIPT_COPY_BOOK_GUARDS = r"""
DROP TRIGGER import_receipt_copy_parent_same_book ON public.library_copy;
DROP TRIGGER import_receipt_book_copy_parent_same_book ON public.library_importreceipt;
DROP FUNCTION public.julib_check_import_receipt_copy_book_parent();
DROP TRIGGER import_receipt_copy_book_same_book ON public.library_importreceiptcopy;
DROP FUNCTION public.julib_check_import_receipt_copy_book();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0017_libib_file_parse_errors"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_RECEIPT_COPY_BOOK_GUARDS,
            reverse_sql=DROP_RECEIPT_COPY_BOOK_GUARDS,
        ),
    ]
