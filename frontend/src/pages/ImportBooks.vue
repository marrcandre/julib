<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import { api, post, type Book } from '../api'

type Source = 'goodreads' | 'libib'
interface GoodreadsRow { id: number; data: Book; result: string; existing: boolean }
interface LibibData {
  title: string
  authors: string[]
  isbn: string
  publisher: string
  year: string
  page_count: number | null
  collection: string
  tag_names: string[]
  copies: number
  not_imported_fields: string[]
  status: 'valid' | 'invalid' | 'incompatible'
  errors: string[]
  warnings: string[]
  existing: boolean
  already_imported: boolean
  possible_duplicate: boolean
  processing_error: string
  copies_added: number
}
interface LibibRow { id: number; file_id: number; file_row_number: number; data: LibibData; result: string }
interface ImportFile { id: number; name: string; collection: string; total_rows: number; completed: number; status: 'ready' | 'error'; error: string; unknown_columns: string[] }
interface ImportSessionOption { id: number; created_at: string; total?: number; completed?: number }

const source = ref<Source>('goodreads')
const session = ref<number | null>(null)
const rows = ref<GoodreadsRow[]>([])
const libibRows = ref<LibibRow[]>([])
const files = ref<ImportFile[]>([])
const goodreadsSessions = ref<ImportSessionOption[]>([])
const libibSessions = ref<ImportSessionOption[]>([])
const selected = ref<number[]>([])
const copies = ref<number[]>([])
const error = ref('')
const busy = ref(false)
const progress = ref('')

const importableRows = computed(() => libibRows.value.filter(row =>
  row.data.status === 'valid'
  && !row.data.already_imported
  && (!row.result || row.result === 'error'),
))

const summary = computed(() => {
  const libibItems = libibRows.value
  const valid = libibItems.filter(row => row.data.status === 'valid')
  return {
    total: libibItems.length,
    valid: valid.length,
    invalid: libibItems.filter(row => row.data.status === 'invalid').length,
    incompatible: libibItems.filter(row => row.data.status === 'incompatible').length,
    noIsbn: valid.filter(row => !row.data.isbn).length,
    invalidIsbn: valid.filter(row => row.data.warnings.some(message => message.includes('ISBN informados'))).length,
    existing: valid.filter(row => row.data.existing).length,
    duplicates: libibItems.filter(row => row.data.possible_duplicate).length,
    copiesToCreate: selected.value.reduce((total, id) => {
      const row = libibItems.find(item => item.id === id)
      if (!row) return total
      if (row.data.existing || (row.data.possible_duplicate && row.data.isbn)) {
        return total + (copies.value.includes(id) ? row.data.copies : 0)
      }
      return total + row.data.copies
    }, 0),
    ignoredFields: [...new Set(libibItems.flatMap(row => row.data.not_imported_fields))].sort(),
    booksCreated: libibItems.filter(row => row.result === 'created').length,
    copiesCreated: libibItems.reduce((total, row) => total + row.data.copies_added, 0),
    skipped: libibItems.filter(row => ['existing', 'skipped', 'already_imported'].includes(row.result)).length,
    failed: libibItems.filter(row => row.result === 'error').length,
  }
})

async function sessionsLoad() {
  ;[goodreadsSessions.value, libibSessions.value] = await Promise.all([
    api<ImportSessionOption[]>('/imports'),
    api<ImportSessionOption[]>('/imports/libib/sessions'),
  ])
}

async function open(id: number, selectedSource: Source = source.value) {
  busy.value = true
  error.value = ''
  source.value = selectedSource
  session.value = id
  selected.value = []
  copies.value = []
  try {
    if (selectedSource === 'goodreads') {
      rows.value = (await api<{ rows: GoodreadsRow[] }>('/imports/' + id)).rows
      libibRows.value = []
      files.value = []
    } else {
      const details = await api<{ rows: LibibRow[]; files: ImportFile[] }>(`/imports/libib/${id}`)
      libibRows.value = details.rows
      files.value = details.files
      rows.value = []
    }
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const chosen = Array.from(input.files ?? [])
  if (!chosen.length) return
  const operationSource = source.value
  busy.value = true
  error.value = ''
  progress.value = ''
  try {
    const body = new FormData()
    let route = '/imports'
    if (operationSource === 'goodreads') {
      if (chosen.length !== 1) throw new Error('O Goodreads aceita um arquivo por vez.')
      if (chosen[0].size > 3 * 1024 * 1024) throw new Error('O CSV deve ter até 3 MiB.')
      body.append('file', chosen[0])
    } else {
      if (chosen.length > 5) throw new Error('Selecione até 5 arquivos Libib por sessão.')
      if (chosen.some(file => file.size > 5 * 1024 * 1024)) throw new Error('Cada arquivo deve ter até 5 MiB.')
      if (chosen.reduce((size, file) => size + file.size, 0) > 25 * 1024 * 1024) throw new Error('O total deve ter até 25 MiB.')
      chosen.forEach(file => body.append('files', file))
      route = '/imports/libib/preview'
    }
    const data = await api<{ id: number }>(route, { method: 'POST', body })
    await open(data.id, operationSource)
    await sessionsLoad()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    input.value = ''
    busy.value = false
  }
}

async function process() {
  const operationSource = source.value
  const operationSession = session.value
  if (operationSession === null || !selected.value.length) return
  const quantity = operationSource === 'libib' ? summary.value.copiesToCreate : selected.value.length
  if (!confirm(`Processar ${selected.value.length} registro(s) e criar ${quantity} exemplar(es)?`)) return
  busy.value = true
  error.value = ''
  let completed = 0
  const actions = selected.value.map(id => ({ id, action: copies.value.includes(id) ? 'copy' : 'import' }))
  try {
    for (let index = 0; index < actions.length; index += 25) {
      const batch = actions.slice(index, index + 25)
      const route = operationSource === 'libib' ? `/imports/libib/${operationSession}/process` : `/imports/${operationSession}/process`
      const result = await post<Array<{ id: number; result: string; message?: string }>>(route, { actions: batch })
      for (const item of result) {
        const row = operationSource === 'libib'
          ? libibRows.value.find(candidate => candidate.id === item.id)
          : rows.value.find(candidate => candidate.id === item.id)
        if (row) {
          row.result = item.result
          if (operationSource === 'libib' && item.message) (row as LibibRow).data.processing_error = item.message
        }
      }
      completed += result.length
      progress.value = `${completed} de ${actions.length} registros processados.`
    }
    await open(operationSession, operationSource)
    await sessionsLoad()
  } catch (e) {
    error.value = (e as Error).message
    progress.value = `${completed} de ${actions.length} registros processados. Você pode retomar a sessão sem duplicar registros concluídos.`
  } finally {
    busy.value = false
  }
}

function statusLabel(row: LibibRow) {
  if (row.result === 'created') return 'Livro criado'
  if (row.result === 'copied') return 'Exemplares adicionados'
  if (row.result === 'already_imported') return 'Já importado · sem alterações'
  if (row.result === 'existing') return 'Livro existente · ignorado'
  if (row.result === 'skipped') return 'Ignorado'
  if (row.result === 'error') return 'Erro · pode tentar novamente'
  if (row.data.already_imported) return 'Já importado · sem alterações'
  if (row.data.status === 'incompatible') return 'Incompatível'
  if (row.data.status === 'invalid') return 'Inválido'
  return row.data.existing ? 'Já cadastrado' : 'Novo'
}

onMounted(async () => {
  try { await sessionsLoad() } catch (e) { error.value = (e as Error).message }
})
</script>

<template>
  <div class="page-heading"><div><div class="eyebrow">SUA COLEÇÃO, UM PASSO ADIANTE</div><h1>Importar livros</h1><p class="muted">Revise os registros antes de adicionar livros ou exemplares.</p></div></div>
  <div class="actions" role="group" aria-label="Origem da importação">
    <Button label="Goodreads" :outlined="source !== 'goodreads'" :disabled="busy" @click="source = 'goodreads'; session = null; rows = []; libibRows = []; files = []; progress = ''" />
    <Button label="Libib" :outlined="source !== 'libib'" :disabled="busy" @click="source = 'libib'; session = null; rows = []; libibRows = []; files = []; progress = ''" />
  </div>

  <div class="panel">
    <template v-if="source === 'goodreads'">
      <p>Exporte no Goodreads: <b>My Books → Import and Export → Export Library</b>.</p>
      <label>Enviar CSV (até 3 MiB / 5.000 linhas)<input type="file" accept=".csv,text/csv" :disabled="busy" @change="upload"></label>
      <p class="muted">Criamos um exemplar por livro escolhido. Depois você pode informar a localização e adicionar outras cópias.</p>
      <div v-if="goodreadsSessions.length" class="actions"><span class="muted">Retomar Goodreads:</span><Button v-for="item in goodreadsSessions" :key="item.id" :label="'Importação #'+item.id" text size="small" :disabled="busy" @click="open(item.id, 'goodreads')" /></div>
    </template>
    <template v-else>
      <p>Envie uma ou mais exportações CSV do Libib. Os livros não serão criados até você confirmar a seleção.</p>
      <label>Selecionar arquivos (até 5 arquivos, 5 MiB cada e 25 MiB no total)<input type="file" accept=".csv,text/csv" multiple :disabled="busy" @change="upload"></label>
      <p class="muted">Somente registros do tipo livro são compatíveis. A coleção Libib fica como metadado da importação e não vira localização no Julib.</p>
      <div v-if="libibSessions.length" class="actions"><span class="muted">Retomar Libib:</span><Button v-for="item in libibSessions" :key="item.id" :label="`Importação #${item.id} · ${item.completed ?? 0}/${item.total ?? 0}`" text size="small" :disabled="busy" @click="open(item.id, 'libib')" /></div>
    </template>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="progress" class="notice" role="status">{{ progress }}</p>

  <template v-if="source === 'goodreads' && rows.length">
    <div class="section-heading"><h2>{{ rows.length }} registros para revisar</h2><Button label="Importar selecionados" class="primary" :disabled="!selected.length || busy" :loading="busy" @click="process" /></div>
    <p class="muted">Selecione os livros possuídos. “Outra cópia” só é necessária para adicionar um exemplar de livro já cadastrado.</p>
    <div class="table-wrap panel"><table class="data-table"><thead><tr><th>Importar</th><th>Livro</th><th>ISBN</th><th>Correspondência</th><th>Outra cópia</th><th>Resultado</th></tr></thead><tbody><tr v-for="row in rows" :key="row.id"><td><input v-model="selected" type="checkbox" :value="row.id" :disabled="!!row.result || busy" :aria-label="'Importar '+row.data.title"></td><td><b>{{ row.data.title }}</b><br><span class="muted">{{ row.data.authors.join(', ') }}</span></td><td>{{ row.data.isbn || 'Sem ISBN' }}</td><td>{{ row.existing ? 'Já cadastrado' : 'Novo' }}</td><td><input v-if="row.existing && !row.result" v-model="copies" type="checkbox" :value="row.id" :aria-label="'Adicionar outra cópia de '+row.data.title"></td><td>{{ ({created:'Criado',existing:'Já existente · ignorado',skipped:'Ignorado'} as Record<string,string>)[row.result] || 'Pendente' }}</td></tr></tbody></table></div>
  </template>

  <template v-if="source === 'libib' && (libibRows.length || files.length)">
    <div v-if="libibRows.length" class="section-heading"><h2>Prévia consolidada · {{ summary.total }} registros</h2><Button label="Confirmar importação" class="primary" :disabled="!selected.length || busy" :loading="busy" @click="process" /></div>
    <div v-if="libibRows.length" class="panel"><p><b>{{ summary.valid }}</b> válidos · <b>{{ summary.invalid }}</b> inválidos · <b>{{ summary.incompatible }}</b> incompatíveis · <b>{{ summary.noIsbn }}</b> sem ISBN · <b>{{ summary.invalidIsbn }}</b> com ISBN inválido · <b>{{ summary.existing }}</b> já existentes · <b>{{ summary.duplicates }}</b> possíveis duplicidades nesta seleção.</p><p>Exemplares selecionados para criar: <b>{{ summary.copiesToCreate }}</b></p><p v-if="summary.ignoredFields.length" class="muted">Campos não importados encontrados: {{ summary.ignoredFields.join(', ') }}.</p><p class="muted">A data completa de publicação é reduzida ao ano. Os dados originais permanecem disponíveis na sessão por sete dias.</p></div>
    <div v-if="libibRows.some(row => row.result)" class="panel" role="status"><b>Resultado desta sessão</b><p>{{ summary.booksCreated }} livro(s) criado(s) · {{ summary.copiesCreated }} exemplar(es) adicionado(s) · {{ summary.skipped }} ignorado(s) ou já importado(s) · {{ summary.incompatible }} incompatível(is) · {{ summary.failed }} erro(s) que podem ser retomados.</p></div>
    <div v-for="file in files" :key="file.id" class="panel"><b>{{ file.name }}</b><span v-if="file.collection"> · Coleção: {{ file.collection }}</span><span v-if="file.status === 'ready'"> · {{ file.completed }}/{{ file.total_rows }} concluídos</span><p v-if="file.error" class="error" role="alert">{{ file.error }}</p><p v-if="file.unknown_columns.length" class="muted">Colunas extras preservadas na sessão: {{ file.unknown_columns.join(', ') }}</p></div>
    <p v-if="!importableRows.length" class="notice" role="status">Nenhum registro importável nesta sessão. Confira os erros dos arquivos ou retome uma sessão com registros pendentes.</p>
    <template v-if="libibRows.length">
      <p class="muted">Selecione registros válidos. Para um livro existente, marque “Adicionar exemplares” para confirmar explicitamente a inclusão da quantidade desejada.</p>
      <div class="table-wrap panel"><table class="data-table"><thead><tr><th>Selecionar</th><th>Livro</th><th>ISBN</th><th>Editora / ano</th><th>Coleção</th><th>Tags</th><th>Exemplares</th><th>Correspondência</th><th>Resultado e avisos</th></tr></thead><tbody><tr v-for="row in libibRows" :key="row.id"><td><input v-model="selected" type="checkbox" :value="row.id" :disabled="row.data.status !== 'valid' || (!!row.result && row.result !== 'error') || row.data.already_imported || busy" :aria-label="'Importar '+row.data.title"><input v-if="(row.data.existing || (row.data.possible_duplicate && row.data.isbn)) && (!row.result || row.result === 'error') && !row.data.already_imported" v-model="copies" type="checkbox" :value="row.id" :disabled="busy" :aria-label="'Adicionar exemplares de '+row.data.title"><span v-if="(row.data.existing || (row.data.possible_duplicate && row.data.isbn)) && !row.result" class="muted">Adicionar exemplares</span></td><td><b>{{ row.data.title || 'Sem título' }}</b><br><span class="muted">{{ row.data.authors.join(', ') || 'Sem autor' }}</span></td><td>{{ row.data.isbn || 'Sem ISBN válido' }}</td><td>{{ row.data.publisher || '—' }}<span v-if="row.data.year"> · {{ row.data.year }}</span><span v-if="row.data.page_count"> · {{ row.data.page_count }} p.</span></td><td>{{ row.data.collection || '—' }}</td><td>{{ row.data.tag_names.join(', ') || '—' }}</td><td>{{ row.data.copies || 'Inválido' }}</td><td>{{ row.data.already_imported ? 'Já importado' : row.data.possible_duplicate ? 'Possível duplicidade' : row.data.existing ? 'Já cadastrado por ISBN' : row.data.status === 'valid' ? 'Novo' : statusLabel(row) }}</td><td>{{ statusLabel(row) }}<ul v-if="row.data.errors.length || row.data.warnings.length || row.data.processing_error"><li v-for="message in [...row.data.errors, ...row.data.warnings, row.data.processing_error].filter(Boolean)" :key="message" class="muted">{{ message }}</li></ul></td></tr></tbody></table></div>
    </template>
  </template>
</template>
