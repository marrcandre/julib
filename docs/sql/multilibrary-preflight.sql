-- Read-only preflight for migrations 0010/0011. Run against the target database
-- using a read-only database role. Every row returned is an inconsistency.
BEGIN TRANSACTION READ ONLY;

SELECT 'location.parent' AS relation, count(*) AS inconsistent_rows
FROM library_location child
JOIN library_location parent ON parent.id = child.parent_id
WHERE child.library_id <> parent.library_id
UNION ALL
SELECT 'copy.book', count(*)
FROM library_copy c JOIN library_book b ON b.id = c.book_id
WHERE c.library_id <> b.library_id
UNION ALL
SELECT 'copy.location', count(*)
FROM library_copy c JOIN library_location l ON l.id = c.location_id
WHERE c.library_id <> l.library_id
UNION ALL
SELECT 'loan.copy', count(*)
FROM library_loan loan JOIN library_copy c ON c.id = loan.copy_id
WHERE loan.library_id <> c.library_id
UNION ALL
SELECT 'loan.person', count(*)
FROM library_loan loan JOIN library_person p ON p.id = loan.person_id
WHERE loan.library_id <> p.library_id
UNION ALL
SELECT 'registration.book', count(*)
FROM library_registration r JOIN library_book b ON b.id = r.book_id
WHERE r.library_id <> b.library_id
UNION ALL
SELECT 'registration.copy', count(*)
FROM library_registration r JOIN library_copy c ON c.id = r.copy_id
WHERE r.library_id <> c.library_id
UNION ALL
SELECT 'book.tag', count(*)
FROM library_book_tags bt
JOIN library_book b ON b.id = bt.book_id
JOIN library_tag t ON t.id = bt.tag_id
WHERE b.library_id <> t.library_id
UNION ALL
SELECT 'import_row.copy', count(*)
FROM library_importrow ir
JOIN library_importsession import_session ON import_session.id = ir.session_id
JOIN library_copy c ON c.id = ir.copy_id
WHERE import_session.library_id <> c.library_id
ORDER BY relation;

ROLLBACK;
