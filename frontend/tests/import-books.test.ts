import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { api, post } = vi.hoisted(() => ({ api: vi.fn(), post: vi.fn() }))
vi.mock('../src/api', () => ({ api, post }))

import ImportBooks from '../src/pages/ImportBooks.vue'

const row = (id: number, title: string, status: 'valid' | 'incompatible') => ({
  id,
  file_id: 1,
  file_row_number: id,
  result: '',
  data: {
    title,
    authors: ['Author'],
    isbn: '9780306406157',
    publisher: 'Press',
    year: '2000',
    page_count: 123,
    collection: 'Fiction',
    tag_names: [],
    copies: 2,
    not_imported_fields: ['notes'],
    status,
    errors: status === 'valid' ? [] : ['Tipo de mídia incompatível.'],
    warnings: [],
    existing: false,
    already_imported: false,
    possible_duplicate: false,
    processing_error: '',
    copies_added: 0,
  },
})

beforeEach(() => {
  vi.clearAllMocks()
  let completed = ''
  api.mockImplementation(async (path: string) => {
    if (path === '/imports' || path === '/imports/libib/sessions') return []
    if (path === '/imports/libib/preview') return { id: 11 }
    if (path === '/imports/libib/11') {
      const valid = row(1, 'Book', 'valid')
      const incompatible = row(2, 'Movie', 'incompatible')
      valid.result = completed
      return {
        id: 11,
        files: [{ id: 1, name: 'collection.csv', collection: 'Fiction', total_rows: 2, completed: completed ? 1 : 0, status: 'ready', error: '', unknown_columns: ['custom'] }],
        rows: [valid, incompatible],
      }
    }
    throw new Error(`Unexpected API route ${path}`)
  })
  post.mockImplementation(async (_path: string, body: { actions: { id: number }[] }) => {
    completed = 'created'
    return body.actions.map(action => ({ id: action.id, result: 'created', copies_added: 2 }))
  })
})

it('previews multiple Libib rows and keeps incompatible media visible but unselectable', async () => {
  const wrapper = mount(ImportBooks)
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text().includes('Libib'))!.trigger('click')
  const input = wrapper.get('input[type="file"]')
  const upload = Object.defineProperty(input.element, 'files', {
    value: [new File(['csv'], 'collection.csv', { type: 'text/csv' })],
    configurable: true,
  })
  await input.trigger('change')
  await flushPromises()

  expect(upload).toBeDefined()
  expect(wrapper.text()).toContain('2 registros')
  expect(wrapper.text()).toContain('Incompatível')
  expect(wrapper.text()).toContain('notes')
  expect(wrapper.get('input[aria-label="Importar Movie"]').attributes('disabled')).toBeDefined()
})

it('processes selected rows in bounded batches and reports created copies', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  const wrapper = mount(ImportBooks)
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text().includes('Libib'))!.trigger('click')
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', {
    value: [new File(['csv'], 'collection.csv', { type: 'text/csv' })],
    configurable: true,
  })
  await input.trigger('change')
  await flushPromises()
  await wrapper.get('input[aria-label="Importar Book"]').setValue(true)
  await wrapper.get('button.primary').trigger('click')
  await flushPromises()

  expect(confirm).toHaveBeenCalled()
  expect(post).toHaveBeenCalledWith('/imports/libib/11/process', {
    actions: [{ id: 1, action: 'import' }],
  })
  expect(wrapper.text()).toContain('Livro criado')
  expect(wrapper.text()).toContain('1 de 1 registros processados')
})

it('shows one invalid file and an empty importable state when it has no rows', async () => {
  api.mockImplementation(async (path: string) => {
    if (path === '/imports' || path === '/imports/libib/sessions') return []
    if (path === '/imports/libib/preview') return { id: 12 }
    if (path === '/imports/libib/12') return {
      id: 12,
      files: [{ id: 1, name: 'bad.csv', collection: '', total_rows: 0, completed: 0, status: 'error', error: 'Cabeçalho Libib inválido ou incompleto.', unknown_columns: [] }],
      rows: [],
    }
    throw new Error(`Unexpected API route ${path}`)
  })
  const wrapper = mount(ImportBooks)
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text().includes('Libib'))!.trigger('click')
  Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', {
    value: [new File(['bad'], 'bad.csv', { type: 'text/csv' })], configurable: true,
  })
  await wrapper.get('input[type="file"]').trigger('change')
  await flushPromises()

  expect(wrapper.text()).toContain('bad.csv')
  expect(wrapper.text()).toContain('Cabeçalho Libib inválido ou incompleto.')
  expect(wrapper.text()).toContain('Nenhum registro importável')
  expect(wrapper.text()).not.toContain('Importação concluída')
})

it('shows every invalid file and preserves multiple-file upload when none has rows', async () => {
  api.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path === '/imports' || path === '/imports/libib/sessions') return []
    if (path === '/imports/libib/preview') {
      expect((options?.body as FormData).getAll('files')).toHaveLength(2)
      return { id: 13 }
    }
    if (path === '/imports/libib/13') return {
      id: 13,
      files: [
        { id: 1, name: 'bad-header.csv', collection: '', total_rows: 0, completed: 0, status: 'error', error: 'Cabeçalho inválido.', unknown_columns: [] },
        { id: 2, name: 'bad-encoding.csv', collection: '', total_rows: 0, completed: 0, status: 'error', error: 'Arquivo inválido em UTF-8.', unknown_columns: [] },
      ],
      rows: [],
    }
    throw new Error(`Unexpected API route ${path}`)
  })
  const wrapper = mount(ImportBooks)
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text().includes('Libib'))!.trigger('click')
  Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', {
    value: [
      new File(['bad'], 'bad-header.csv', { type: 'text/csv' }),
      new File(['bad'], 'bad-encoding.csv', { type: 'text/csv' }),
    ], configurable: true,
  })
  await wrapper.get('input[type="file"]').trigger('change')
  await flushPromises()

  expect(wrapper.text()).toContain('bad-header.csv')
  expect(wrapper.text()).toContain('Cabeçalho inválido.')
  expect(wrapper.text()).toContain('bad-encoding.csv')
  expect(wrapper.text()).toContain('Arquivo inválido em UTF-8.')
  expect(wrapper.text()).toContain('Nenhum registro importável')
})

it('shows a no-importable-records message when rows exist but all are incompatible', async () => {
  api.mockImplementation(async (path: string) => {
    if (path === '/imports' || path === '/imports/libib/sessions') return []
    if (path === '/imports/libib/preview') return { id: 11 }
    if (path === '/imports/libib/11') return {
      id: 11,
      files: [{ id: 1, name: 'movie.csv', collection: 'Fiction', total_rows: 1, completed: 0, status: 'ready', error: '', unknown_columns: [] }],
      rows: [row(3, 'Movie', 'incompatible')],
    }
    throw new Error(`Unexpected API route ${path}`)
  })
  const wrapper = mount(ImportBooks)
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text().includes('Libib'))!.trigger('click')
  Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', {
    value: [new File(['csv'], 'collection.csv', { type: 'text/csv' })], configurable: true,
  })
  await wrapper.get('input[type="file"]').trigger('change')
  await flushPromises()

  expect(wrapper.text()).toContain('Nenhum registro importável')
  expect(wrapper.find('button.primary').attributes('disabled')).toBeDefined()
})

it('keeps the source selectors disabled during an upload', async () => {
  let finishPreview!: (value: { id: number }) => void
  api.mockImplementation((path: string) => {
    if (path === '/imports' || path === '/imports/libib/sessions') return Promise.resolve([])
    if (path === '/imports/libib/preview') return new Promise(resolve => { finishPreview = resolve })
    if (path === '/imports/libib/14') return Promise.resolve({ id: 14, files: [], rows: [] })
    throw new Error(`Unexpected API route ${path}`)
  })
  const wrapper = mount(ImportBooks)
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text().includes('Libib'))!.trigger('click')
  Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', {
    value: [new File(['csv'], 'collection.csv', { type: 'text/csv' })], configurable: true,
  })
  await wrapper.get('input[type="file"]').trigger('change')
  await flushPromises()

  expect(wrapper.findAll('button').filter(button => ['Libib', 'Goodreads'].includes(button.text())).every(button => button.attributes('disabled') !== undefined)).toBe(true)
  finishPreview({ id: 14 })
  await flushPromises()
})

it('keeps the source selectors disabled during processing', async () => {
  let finishProcess!: (value: { id: number; result: string; copies_added: number }[]) => void
  post.mockImplementation(() => new Promise(resolve => { finishProcess = resolve }))
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const wrapper = mount(ImportBooks)
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text().includes('Libib'))!.trigger('click')
  Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', {
    value: [new File(['csv'], 'collection.csv', { type: 'text/csv' })], configurable: true,
  })
  await wrapper.get('input[type="file"]').trigger('change')
  await flushPromises()
  await wrapper.get('input[aria-label="Importar Book"]').setValue(true)
  await wrapper.get('button.primary').trigger('click')
  await flushPromises()

  expect(wrapper.findAll('button').filter(button => ['Libib', 'Goodreads'].includes(button.text())).every(button => button.attributes('disabled') !== undefined)).toBe(true)
  finishProcess([{ id: 1, result: 'created', copies_added: 2 }])
  await flushPromises()
})

it('reports partial batch progress and a resumable session after a later batch fails', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  const manyRows = Array.from({ length: 26 }, (_, index) => row(index + 1, `Book ${index + 1}`, 'valid'))
  let postCount = 0
  api.mockImplementation(async (path: string) => {
    if (path === '/imports' || path === '/imports/libib/sessions') return []
    if (path === '/imports/libib/preview') return { id: 15 }
    if (path === '/imports/libib/15') return {
      id: 15,
      files: [{ id: 1, name: 'collection.csv', collection: 'Fiction', total_rows: 26, completed: 0, status: 'ready', error: '', unknown_columns: [] }],
      rows: manyRows,
    }
    throw new Error(`Unexpected API route ${path}`)
  })
  post.mockImplementation(async (_path: string, body: { actions: { id: number }[] }) => {
    postCount += 1
    if (postCount === 2) throw new Error('Conexão interrompida')
    return body.actions.map(action => ({ id: action.id, result: 'created', copies_added: 1 }))
  })
  const wrapper = mount(ImportBooks)
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text().includes('Libib'))!.trigger('click')
  Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', {
    value: [new File(['csv'], 'collection.csv', { type: 'text/csv' })], configurable: true,
  })
  await wrapper.get('input[type="file"]').trigger('change')
  await flushPromises()
  for (const checkbox of wrapper.findAll('input[aria-label^="Importar Book "]')) {
    await checkbox.setValue(true)
  }
  await wrapper.get('button.primary').trigger('click')
  await flushPromises()

  expect(confirm).toHaveBeenCalled()
  expect(post).toHaveBeenCalledTimes(2)
  expect(wrapper.text()).toContain('25 de 26 registros processados')
  expect(wrapper.text()).toContain('Você pode retomar a sessão sem duplicar registros concluídos.')
  expect(wrapper.text()).not.toContain('Importação concluída')
})

it('shows the expiration message when reopening a stale session link', async () => {
  api.mockImplementation(async (path: string) => {
    if (path === '/imports') return [{ id: 21, created_at: '2026-01-01T00:00:00Z' }]
    if (path === '/imports/libib/sessions') return []
    if (path === '/imports/21') throw new Error('Importação expirada. Envie o arquivo novamente.')
    throw new Error(`Unexpected API route ${path}`)
  })
  const wrapper = mount(ImportBooks)
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text().includes('Goodreads'))!.trigger('click')
  await wrapper.findAll('button').find(button => button.text().includes('Importação #21'))!.trigger('click')
  await flushPromises()

  expect(wrapper.find('[role="alert"]').text()).toContain('Importação expirada')
})
