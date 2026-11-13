from django.db import migrations, models

ADD_RELATIONSHIPS = (
    'ALTER TABLE "library_location" ADD CONSTRAINT "location_parent_library_fk" '
    'FOREIGN KEY ("parent_id", "library_id") REFERENCES "library_location" '
    '("id", "library_id") DEFERRABLE INITIALLY DEFERRED NOT VALID',
    'ALTER TABLE "library_copy" ADD CONSTRAINT "copy_book_library_fk" '
    'FOREIGN KEY ("book_id", "library_id") REFERENCES "library_book" '
    '("id", "library_id") DEFERRABLE INITIALLY DEFERRED NOT VALID',
    'ALTER TABLE "library_copy" ADD CONSTRAINT "copy_location_library_fk" '
    'FOREIGN KEY ("location_id", "library_id") REFERENCES "library_location" '
    '("id", "library_id") DEFERRABLE INITIALLY DEFERRED NOT VALID',
    'ALTER TABLE "library_loan" ADD CONSTRAINT "loan_copy_library_fk" '
    'FOREIGN KEY ("copy_id", "library_id") REFERENCES "library_copy" '
    '("id", "library_id") DEFERRABLE INITIALLY DEFERRED NOT VALID',
    'ALTER TABLE "library_loan" ADD CONSTRAINT "loan_person_library_fk" '
    'FOREIGN KEY ("person_id", "library_id") REFERENCES "library_person" '
    '("id", "library_id") DEFERRABLE INITIALLY DEFERRED NOT VALID',
    'ALTER TABLE "library_registration" ADD CONSTRAINT "registration_book_library_fk" '
    'FOREIGN KEY ("book_id", "library_id") REFERENCES "library_book" '
    '("id", "library_id") DEFERRABLE INITIALLY DEFERRED NOT VALID',
    'ALTER TABLE "library_registration" ADD CONSTRAINT "registration_copy_library_fk" '
    'FOREIGN KEY ("copy_id", "library_id") REFERENCES "library_copy" '
    '("id", "library_id") DEFERRABLE INITIALLY DEFERRED NOT VALID',
)

VALIDATE_RELATIONSHIPS = (
    'ALTER TABLE "library_location" VALIDATE CONSTRAINT "location_parent_library_fk"',
    'ALTER TABLE "library_copy" VALIDATE CONSTRAINT "copy_book_library_fk"',
    'ALTER TABLE "library_copy" VALIDATE CONSTRAINT "copy_location_library_fk"',
    'ALTER TABLE "library_loan" VALIDATE CONSTRAINT "loan_copy_library_fk"',
    'ALTER TABLE "library_loan" VALIDATE CONSTRAINT "loan_person_library_fk"',
    'ALTER TABLE "library_registration" VALIDATE CONSTRAINT "registration_book_library_fk"',
    'ALTER TABLE "library_registration" VALIDATE CONSTRAINT "registration_copy_library_fk"',
)

DROP_RELATIONSHIPS = (
    'ALTER TABLE "library_registration" DROP CONSTRAINT "registration_copy_library_fk"',
    'ALTER TABLE "library_registration" DROP CONSTRAINT "registration_book_library_fk"',
    'ALTER TABLE "library_loan" DROP CONSTRAINT "loan_person_library_fk"',
    'ALTER TABLE "library_loan" DROP CONSTRAINT "loan_copy_library_fk"',
    'ALTER TABLE "library_copy" DROP CONSTRAINT "copy_location_library_fk"',
    'ALTER TABLE "library_copy" DROP CONSTRAINT "copy_book_library_fk"',
    'ALTER TABLE "library_location" DROP CONSTRAINT "location_parent_library_fk"',
)

ADD_RELATION_CHECKS = r"""
CREATE FUNCTION julib_check_book_tag_library() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT library_id FROM library_book WHERE id = NEW.book_id)
       IS DISTINCT FROM
       (SELECT library_id FROM library_tag WHERE id = NEW.tag_id) THEN
        RAISE EXCEPTION 'Book and tag must belong to the same library'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER book_tag_same_library
BEFORE INSERT OR UPDATE ON library_book_tags
FOR EACH ROW EXECUTE FUNCTION julib_check_book_tag_library();
CREATE FUNCTION julib_check_book_tag_parent_library() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'library_book' AND EXISTS (
        SELECT 1 FROM library_book_tags bt
        JOIN library_tag t ON t.id = bt.tag_id
        WHERE bt.book_id = NEW.id AND t.library_id <> NEW.library_id
    ) THEN
        RAISE EXCEPTION 'Book and tag must belong to the same library'
            USING ERRCODE = '23514';
    ELSIF TG_TABLE_NAME = 'library_tag' AND EXISTS (
        SELECT 1 FROM library_book_tags bt
        JOIN library_book b ON b.id = bt.book_id
        WHERE bt.tag_id = NEW.id AND b.library_id <> NEW.library_id
    ) THEN
        RAISE EXCEPTION 'Book and tag must belong to the same library'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER book_tag_parent_same_library
BEFORE UPDATE OF library_id ON library_book
FOR EACH ROW EXECUTE FUNCTION julib_check_book_tag_parent_library();
CREATE TRIGGER tag_book_parent_same_library
BEFORE UPDATE OF library_id ON library_tag
FOR EACH ROW EXECUTE FUNCTION julib_check_book_tag_parent_library();

CREATE FUNCTION julib_check_import_row_copy_library() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.copy_id IS NOT NULL
       AND (SELECT library_id FROM library_importsession WHERE id = NEW.session_id)
           IS DISTINCT FROM
           (SELECT library_id FROM library_copy WHERE id = NEW.copy_id) THEN
        RAISE EXCEPTION 'Import row and copy must belong to the same library'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER import_row_copy_same_library
BEFORE INSERT OR UPDATE ON library_importrow
FOR EACH ROW EXECUTE FUNCTION julib_check_import_row_copy_library();
CREATE FUNCTION julib_check_import_row_parent_library() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'library_importsession' AND EXISTS (
        SELECT 1 FROM library_importrow ir
        JOIN library_copy c ON c.id = ir.copy_id
        WHERE ir.session_id = NEW.id AND c.library_id <> NEW.library_id
    ) THEN
        RAISE EXCEPTION 'Import row and copy must belong to the same library'
            USING ERRCODE = '23514';
    ELSIF TG_TABLE_NAME = 'library_copy' AND EXISTS (
        SELECT 1 FROM library_importrow ir
        JOIN library_importsession s ON s.id = ir.session_id
        WHERE ir.copy_id = NEW.id AND s.library_id <> NEW.library_id
    ) THEN
        RAISE EXCEPTION 'Import row and copy must belong to the same library'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER import_row_session_same_library
BEFORE UPDATE OF library_id ON library_importsession
FOR EACH ROW EXECUTE FUNCTION julib_check_import_row_parent_library();
CREATE TRIGGER import_row_copy_parent_same_library
BEFORE UPDATE OF library_id ON library_copy
FOR EACH ROW EXECUTE FUNCTION julib_check_import_row_parent_library();
"""

DROP_RELATION_CHECKS = r"""
DROP TRIGGER import_row_copy_same_library ON library_importrow;
DROP FUNCTION julib_check_import_row_copy_library();
DROP TRIGGER import_row_copy_parent_same_library ON library_copy;
DROP TRIGGER import_row_session_same_library ON library_importsession;
DROP FUNCTION julib_check_import_row_parent_library();
DROP TRIGGER book_tag_same_library ON library_book_tags;
DROP FUNCTION julib_check_book_tag_library();
DROP TRIGGER tag_book_parent_same_library ON library_tag;
DROP TRIGGER book_tag_parent_same_library ON library_book;
DROP FUNCTION julib_check_book_tag_parent_library();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0010_membership_role_user_can_create_libraries"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="location",
            constraint=models.UniqueConstraint(
                fields=("id", "library"), name="unique_location_library_id"
            ),
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(
                fields=("id", "library"), name="unique_tag_library_id"
            ),
        ),
        migrations.AddConstraint(
            model_name="book",
            constraint=models.UniqueConstraint(
                fields=("id", "library"), name="unique_book_library_id"
            ),
        ),
        migrations.AddConstraint(
            model_name="copy",
            constraint=models.UniqueConstraint(
                fields=("id", "library"), name="unique_copy_library_id"
            ),
        ),
        migrations.AddConstraint(
            model_name="person",
            constraint=models.UniqueConstraint(
                fields=("id", "library"), name="unique_person_library_id"
            ),
        ),
        migrations.AddConstraint(
            model_name="registration",
            constraint=models.UniqueConstraint(
                fields=("id", "library"), name="unique_registration_library_id"
            ),
        ),
        migrations.RunSQL(ADD_RELATIONSHIPS, reverse_sql=DROP_RELATIONSHIPS),
        migrations.RunSQL(VALIDATE_RELATIONSHIPS, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(ADD_RELATION_CHECKS, reverse_sql=DROP_RELATION_CHECKS),
    ]
