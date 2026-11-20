import { expect, test } from '@playwright/test'

const validRow = {
  id: 501,
  file_id: 201,
  file_row_number: 1,
  result: '',
  data: {
    title: 'Livro da prévia',
    subtitle: "",
    description: "",
    subjects: [],
    authors: ['Autora da prévia'],
    isbn: '9780306406157',
    publisher: 'Editora',
    year: '2001',
    page_count: 240,
    collection: 'Ficção',
    tag_names: ['Romance'],
    copies: 2,
    not_imported_fields: ['notes'],
    status: 'valid',
    errors: [],
    warnings: [],
    existing: false,
    already_imported: false,
    possible_duplicate: false,
    processing_error: '',
    copies_added: 0,
  },
}

test('opens the unified import screen from the library menu', async ({ page }) => {
  await page.route('**/api/v1/session', route => route.fulfill({ json: {
    user_id: 900,
    name: 'Pessoa de teste',
    email: 'test@example.com',
    catalog_view: 'covers',
    cover_columns: 7,
    avatar_url: '',
    technical: false,
    can_create_libraries: false,
    libraries: [{ id: 77, name: 'Biblioteca de teste', role: 'admin' }],
    library: 'Biblioteca de teste',
    csrf: 'local-csrf',
  } }))
  await page.route('**/api/v1/imports', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/imports/libib/sessions', route => route.fulfill({ json: [] }))

  await page.goto('/livros')
  await page.getByRole('button', { name: 'Mais opções da biblioteca' }).click()

  const importItem = page.getByRole('menuitem', { name: 'Importar livros' })
  await expect(importItem).toHaveCount(1)
  await importItem.click()
  await expect(page).toHaveURL(/\/bibliotecas\/77\/importar$/)
  await expect(page.getByRole('heading', { name: 'Importar livros' })).toBeVisible()
})

test('reviews a Libib CSV and confirms copies without relying on its filename', async ({ page }) => {
  let result = ''
  await page.route('**/api/v1/session', route => route.fulfill({
    json: {
      user_id: 900,
      name: 'Pessoa de teste',
      email: 'test@example.com',
      catalog_view: 'covers',
      cover_columns: 7,
      avatar_url: '',
      technical: false,
      can_create_libraries: false,
      libraries: [{ id: 77, name: 'Biblioteca de teste', role: 'admin' }],
      library: 'Biblioteca de teste',
      csrf: 'local-csrf',
    },
  }))
  await page.route('**/api/v1/imports', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/imports/libib/sessions', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/imports/libib/preview', route => route.fulfill({ json: { id: 100 } }))
  await page.route('**/api/v1/imports/libib/100', route => route.fulfill({
    json: {
      id: 100,
      files: [
        { id: 201, name: 'collection.txt', collection: 'Ficção', total_rows: 1, completed: result ? 1 : 0, status: 'ready', error: '', unknown_columns: [] },
        { id: 202, name: 'broken.csv', collection: '', total_rows: 0, completed: 0, status: 'error', error: 'Cabeçalho Libib inválido ou incompleto.', unknown_columns: [] },
      ],
      rows: [{ ...validRow, result, data: { ...validRow.data, copies_added: result === 'created' ? 2 : 0 } }],
    },
  }))
  await page.route('**/api/v1/imports/libib/100/process', async route => {
    result = 'created'
    await route.fulfill({ json: [{ id: 501, result: 'created', copies_added: 2 }] })
  })
  page.on('dialog', dialog => dialog.accept())

  await page.goto('/importar')
  await expect(page).toHaveURL(/\/bibliotecas\/77\/importar$/)
  await page.getByRole('button', { name: 'Libib' }).click()
  await page.locator('input[type="file"]').setInputFiles([
    {
      name: 'collection.txt',
      mimeType: 'text/csv',
      buffer: Buffer.from('id,item_type,title,creators,collection,copies\n1,book,Book,Author,Fiction,2\n'),
    },
    {
      name: 'broken.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('bad header\n'),
    },
  ])

  await expect(page.getByRole('heading', { name: /Prévia consolidada/ })).toBeVisible()
  await expect(page.getByText('Livro da prévia', { exact: true })).toBeVisible()
  await expect(page.getByText('notes', { exact: false })).toBeVisible()
  await expect(page.getByText('Cabeçalho Libib inválido ou incompleto.')).toBeVisible()
  for (const width of [1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await expect(page.getByRole('group', { name: 'Origem da importação' })).toBeVisible()
    const dimensions = await page.evaluate(() => ({
      page: document.documentElement.scrollWidth,
      viewport: document.documentElement.clientWidth,
    }))
    expect(dimensions.page).toBeLessThanOrEqual(dimensions.viewport)
    if (width <= 768) {
      const table = await page.locator('.table-wrap').evaluate(element => ({
        client: element.clientWidth,
        scroll: element.scrollWidth,
      }))
      expect(table.scroll).toBeGreaterThan(table.client)
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByRole('checkbox', { name: 'Importar Livro da prévia' }).check()
  await page.getByRole('button', { name: 'Confirmar importação' }).click()

  await expect(page.getByText(/2 exemplar\(es\) adicionado\(s\)/)).toBeVisible()
  await expect(page.getByText('Livro criado')).toBeVisible()
})

test('shows all file errors when an upload has no importable rows', async ({ page }) => {
  await page.route('**/api/v1/session', route => route.fulfill({ json: {
    user_id: 900,
    name: 'Pessoa de teste',
    email: 'test@example.com',
    catalog_view: 'covers',
    cover_columns: 7,
    avatar_url: '',
    technical: false,
    can_create_libraries: false,
    libraries: [{ id: 77, name: 'Biblioteca de teste', role: 'admin' }],
    library: 'Biblioteca de teste',
    csrf: 'local-csrf',
  } }))
  await page.route('**/api/v1/imports', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/imports/libib/sessions', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/imports/libib/preview', route => route.fulfill({ json: { id: 101 } }))
  await page.route('**/api/v1/imports/libib/101', route => route.fulfill({ json: {
    id: 101,
    files: [
      { id: 211, name: 'bad-header.csv', collection: '', total_rows: 0, completed: 0, status: 'error', error: 'Cabeçalho Libib inválido ou incompleto.', unknown_columns: [] },
      { id: 212, name: 'bad-encoding.csv', collection: '', total_rows: 0, completed: 0, status: 'error', error: 'Arquivo inválido. Exporte o CSV em UTF-8.', unknown_columns: [] },
    ],
    rows: [],
  } }))

  await page.goto('/importar')
  await page.getByRole('button', { name: 'Libib' }).click()
  await page.locator('input[type="file"]').setInputFiles([
    { name: 'bad-header.csv', mimeType: 'text/csv', buffer: Buffer.from('wrong\n') },
    { name: 'bad-encoding.csv', mimeType: 'text/csv', buffer: Buffer.from([0xff]) },
  ])

  await expect(page.getByText('bad-header.csv')).toBeVisible()
  await expect(page.getByText('Cabeçalho Libib inválido ou incompleto.')).toBeVisible()
  await expect(page.locator('.import-file-result').filter({ hasText: 'bad-encoding.csv' })).toBeVisible()
  await expect(page.getByText('Arquivo inválido. Exporte o CSV em UTF-8.')).toBeVisible()
  await expect(page.getByText('Nenhum registro importável nesta sessão.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Confirmar importação' })).toHaveCount(0)
})
