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
const uploading = ref(false)
const uploadFileNames = ref<string[]>([])
const progress = ref('')

const goodreadsFinished = computed(() => rows.value.length > 0 && rows.value.every(row =>
  ['created', 'existing', 'skipped'].includes(row.result),
))

const libibFinished = computed(() => {
  const candidates = libibRows.value.filter(row => row.data.status === 'valid' && !row.data.already_imported)
  if (candidates.length) {
    return candidates.every(row =>
      ['created', 'copied', 'existing', 'skipped', 'already_imported'].includes(row.result),
    )
  }
  return libibRows.value.some(row => row.data.already_imported || row.result === 'already_imported')
})

const goodreadsResult = computed(() => ({
  created: rows.value.filter(row => row.result === 'created').length,
  existing: rows.value.filter(row => row.result === 'existing').length,
  skipped: rows.value.filter(row => row.result === 'skipped').length,
}))

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
    skipped: libibItems.filter(row =>
      row.data.already_imported || ['existing', 'skipped', 'already_imported'].includes(row.result),
    ).length,
    failed: libibItems.filter(row => row.result === 'error').length,
  }
})

function selectSource(next: Source) {
  if (busy.value || source.value === next) return
  source.value = next
  session.value = null
  rows.value = []
  libibRows.value = []
  files.value = []
  selected.value = []
  copies.value = []
  error.value = ''
  progress.value = ''
  uploadFileNames.value = []
}

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
  uploading.value = true
  uploadFileNames.value = chosen.map(file => file.name)
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
    uploading.value = false
    uploadFileNames.value = []
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
  progress.value = `Processando ${actions.length} registro(s)...`
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
  <div class="import-page">
    <div class="page-heading">
      <div>
        <div class="eyebrow">SUA COLEÇÃO, UM PASSO ADIANTE</div>
        <h1>Importar livros</h1>
        <p class="muted">Escolha uma origem para revisar e importar livros para sua biblioteca.</p>
      </div>
    </div>

    <div class="import-source-selector" role="group" aria-label="Origem da importação">
      <Button
        label="Goodreads"
        icon="pi pi-book"
        class="import-source-option"
        :outlined="source !== 'goodreads'"
        :aria-pressed="source === 'goodreads'"
        :disabled="busy"
        @click="selectSource('goodreads')"
      />
      <Button
        label="Libib"
        icon="pi pi-upload"
        class="import-source-option"
        :outlined="source !== 'libib'"
        :aria-pressed="source === 'libib'"
        :disabled="busy"
        @click="selectSource('libib')"
      />
    </div>

    <section class="import-setup panel" :aria-labelledby="source + '-instructions-title'">
      <div class="import-setup-heading">
        <span class="import-source-icon" aria-hidden="true">
          <i :class="source === 'goodreads' ? 'pi pi-book' : 'pi pi-upload'" />
        </span>
        <div>
          <h2 :id="source + '-instructions-title'">{{ source === 'goodreads' ? 'Importar do Goodreads' : 'Importar do Libib' }}</h2>
          <p class="muted">Siga as etapas e revise a prévia antes de confirmar.</p>
        </div>
      </div>

      <ol v-if="source === 'goodreads'" class="import-instructions">
        <li>
          <strong>Exporte sua biblioteca</strong>
          <span>No Goodreads, acesse My Books → Import and Export → Export Library e baixe o CSV. <a href="https://help.goodreads.com/s/question/0D51H00005UUXHhSAP/exportation-of-the-library" target="_blank" rel="noreferrer">Ajuda oficial do Goodreads</a>.</span>
        </li>
        <li>
          <strong>Selecione o arquivo</strong>
          <span>Envie um CSV UTF-8 de até 3 MiB e 5.000 linhas.</span>
        </li>
        <li>
          <strong>Confira os dados reconhecidos</strong>
          <span>Título, autor, ISBN, editora, ano de publicação e número de páginas.</span>
        </li>
        <li>
          <strong>Revise correspondências e seleção</strong>
          <span>O Julib identifica livros existentes pelo ISBN e, como alternativa, pelo ID do Goodreads (Book Id). Selecione os livros que possui; registros existentes não recebem outro exemplar sem sua escolha explícita.</span>
        </li>
        <li>
          <strong>Confirme a importação</strong>
          <span>Cada livro novo selecionado cria um exemplar. Revise os resultados e retome a sessão se necessário.</span>
        </li>
      </ol>
      <ol v-else class="import-instructions">
        <li>
          <strong>Exporte cada coleção</strong>
          <span>O Libib gera um CSV por coleção. <a href="https://support.libib.com/libib/website/settings.html" target="_blank" rel="noreferrer">Ajuda oficial sobre exportação</a>.</span>
        </li>
        <li>
          <strong>Selecione os arquivos</strong>
          <span>Envie até 5 arquivos, com até 5 MiB cada e 25 MiB no total. Os livros só serão criados após sua confirmação.</span>
        </li>
        <li>
          <strong>Revise a identificação</strong>
          <span>O Julib faz correspondência automática por ISBN válido na biblioteca atual. Sem ISBN, semelhanças aparecem como possíveis duplicidades e não mesclam registros.</span>
        </li>
        <li>
          <strong>Confira livros existentes e exemplares</strong>
          <span>Um livro existente não recebe exemplares por padrão. Marque “Adicionar exemplares” para confirmar a quantidade indicada no CSV.</span>
        </li>
        <li>
          <strong>Confira os campos sem correspondência</strong>
          <span>Descrição, notas, preço, avaliações, resenhas, estado de leitura e campos personalizados não são copiados. A coleção Libib fica como metadado temporário e não vira localização física no Julib. <a href="https://support.libib.com/libib/website/add-items.html" target="_blank" rel="noreferrer">Ajuda oficial sobre campos CSV</a>.</span>
        </li>
      </ol>

      <label class="import-file-picker" for="import-csv-file">
        <span class="import-file-title">{{ source === 'goodreads' ? 'Arquivo CSV do Goodreads' : 'Arquivos CSV das coleções Libib' }}</span>
        <span class="muted">{{ source === 'goodreads' ? 'Escolha um arquivo para enviar e revisar.' : 'Você pode selecionar vários arquivos na mesma sessão.' }}</span>
        <input
          id="import-csv-file"
          type="file"
          accept=".csv,text/csv"
          :multiple="source === 'libib'"
          :disabled="busy"
          @change="upload"
        >
      </label>
      <div v-if="uploading && uploadFileNames.length" class="import-upload-status" role="status">
        <span>Enviando {{ uploadFileNames.length }} arquivo(s):</span>
        <ul class="import-file-list"><li v-for="name in uploadFileNames" :key="name">{{ name }}</li></ul>
      </div>

      <div v-if="source === 'goodreads' && goodreadsSessions.length" class="import-resume" aria-label="Sessões Goodreads para retomar">
        <span class="muted">Retomar uma sessão Goodreads:</span>
        <Button v-for="item in goodreadsSessions" :key="item.id" :label="'Importação #' + item.id" text size="small" :disabled="busy" @click="open(item.id, 'goodreads')" />
      </div>
      <div v-if="source === 'libib' && libibSessions.length" class="import-resume" aria-label="Sessões Libib para retomar">
        <span class="muted">Retomar uma sessão Libib:</span>
        <Button v-for="item in libibSessions" :key="item.id" :label="`Importação #${item.id} · ${item.completed ?? 0}/${item.total ?? 0}`" text size="small" :disabled="busy" @click="open(item.id, 'libib')" />
      </div>
    </section>

    <p v-if="error" class="error import-feedback" role="alert">{{ error }}</p>
    <p v-if="progress" class="notice import-feedback" role="status">{{ progress }}</p>

    <div v-if="source === 'goodreads' && rows.some(row => row.result)" class="panel import-result" role="status">
      <strong>{{ goodreadsFinished ? 'Importação concluída' : 'Resultado parcial desta sessão' }}</strong>
      <p>{{ goodreadsResult.created }} livro(s) criado(s) · {{ goodreadsResult.existing }} já existente(s) ignorado(s) · {{ goodreadsResult.skipped }} ignorado(s).</p>
    </div>

    <template v-if="source === 'goodreads' && rows.length">
      <div class="section-heading import-section-heading">
        <h2>{{ rows.length }} registros para revisar</h2>
        <Button label="Importar selecionados" class="primary" :disabled="!selected.length || busy" :loading="busy" @click="process" />
      </div>
      <p class="muted">Selecione os livros que possui. Para um livro já cadastrado, marque “Outra cópia” se quiser adicionar um exemplar.</p>
      <div class="table-wrap panel">
        <table class="data-table">
          <thead><tr><th>Importar</th><th>Livro</th><th>ISBN</th><th>Correspondência</th><th>Outra cópia</th><th>Resultado</th></tr></thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td><input v-model="selected" type="checkbox" :value="row.id" :disabled="!!row.result || busy" :aria-label="'Importar ' + row.data.title"></td>
              <td><b>{{ row.data.title }}</b><br><span class="muted">{{ row.data.authors.join(', ') }}</span></td>
              <td>{{ row.data.isbn || 'Sem ISBN' }}</td>
              <td>{{ row.existing ? 'Já cadastrado' : 'Novo' }}</td>
              <td><input v-if="row.existing && !row.result" v-model="copies" type="checkbox" :value="row.id" :disabled="busy" :aria-label="'Adicionar outra cópia de ' + row.data.title"></td>
              <td>{{ ({created:'Criado',existing:'Já existente · ignorado',skipped:'Ignorado'} as Record<string,string>)[row.result] || 'Pendente' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <template v-if="source === 'libib' && (libibRows.length || files.length)">
      <div v-if="libibRows.length" class="section-heading import-section-heading">
        <h2>Prévia consolidada · {{ summary.total }} registros</h2>
        <Button label="Confirmar importação" class="primary" :disabled="!selected.length || busy" :loading="busy" @click="process" />
      </div>
      <div v-if="libibRows.length" class="panel import-summary">
        <p><b>{{ summary.valid }}</b> válidos · <b>{{ summary.invalid }}</b> inválidos · <b>{{ summary.incompatible }}</b> incompatíveis · <b>{{ summary.noIsbn }}</b> sem ISBN · <b>{{ summary.invalidIsbn }}</b> com ISBN inválido · <b>{{ summary.existing }}</b> já existentes · <b>{{ summary.duplicates }}</b> possíveis duplicidades nesta seleção.</p>
        <p>Exemplares selecionados para criar: <b>{{ summary.copiesToCreate }}</b></p>
        <p v-if="summary.ignoredFields.length" class="muted">Campos não importados encontrados: {{ summary.ignoredFields.join(', ') }}.</p>
        <p class="muted">A data completa de publicação é reduzida ao ano. Os dados originais permanecem disponíveis na sessão por sete dias.</p>
      </div>
      <div v-if="libibRows.some(row => row.result) || libibFinished" class="panel import-result" role="status">
        <strong>{{ libibFinished ? 'Importação concluída' : 'Resultado parcial desta sessão' }}</strong>
        <p>{{ summary.booksCreated }} livro(s) criado(s) · {{ summary.copiesCreated }} exemplar(es) adicionado(s) · {{ summary.skipped }} ignorado(s) ou já importado(s) · {{ summary.incompatible }} incompatível(is) · {{ summary.failed }} erro(s) que podem ser retomados.</p>
      </div>
      <div v-for="file in files" :key="file.id" class="panel import-file-result">
        <b>{{ file.name }}</b><span v-if="file.collection"> · Coleção: {{ file.collection }}</span><span v-if="file.status === 'ready'"> · {{ file.completed }}/{{ file.total_rows }} concluídos</span>
        <p v-if="file.error" class="error" role="alert">{{ file.error }}</p>
        <p v-if="file.unknown_columns.length" class="muted">Colunas extras preservadas na sessão: {{ file.unknown_columns.join(', ') }}</p>
      </div>
      <p v-if="!importableRows.length && !libibFinished" class="notice import-feedback" role="status">Nenhum registro importável nesta sessão. Confira os erros dos arquivos ou retome uma sessão com registros pendentes.</p>
      <template v-if="libibRows.length">
        <p class="muted">Selecione registros válidos. Para um livro existente, marque “Adicionar exemplares” para confirmar explicitamente a inclusão da quantidade desejada.</p>
        <div class="table-wrap panel">
          <table class="data-table">
            <thead><tr><th>Selecionar</th><th>Livro</th><th>ISBN</th><th>Editora / ano</th><th>Coleção</th><th>Tags</th><th>Exemplares</th><th>Correspondência</th><th>Resultado e avisos</th></tr></thead>
            <tbody>
              <tr v-for="row in libibRows" :key="row.id">
                <td>
                  <input v-model="selected" type="checkbox" :value="row.id" :disabled="row.data.status !== 'valid' || (!!row.result && row.result !== 'error') || row.data.already_imported || busy" :aria-label="'Importar ' + row.data.title">
                  <input v-if="(row.data.existing || (row.data.possible_duplicate && row.data.isbn)) && (!row.result || row.result === 'error') && !row.data.already_imported" v-model="copies" type="checkbox" :value="row.id" :disabled="busy" :aria-label="'Adicionar exemplares de ' + row.data.title">
                  <span v-if="(row.data.existing || (row.data.possible_duplicate && row.data.isbn)) && !row.result" class="muted">Adicionar exemplares</span>
                </td>
                <td><b>{{ row.data.title || 'Sem título' }}</b><br><span class="muted">{{ row.data.authors.join(', ') || 'Sem autor' }}</span></td>
                <td>{{ row.data.isbn || 'Sem ISBN válido' }}</td>
                <td>{{ row.data.publisher || '—' }}<span v-if="row.data.year"> · {{ row.data.year }}</span><span v-if="row.data.page_count"> · {{ row.data.page_count }} p.</span></td>
                <td>{{ row.data.collection || '—' }}</td>
                <td>{{ row.data.tag_names.join(', ') || '—' }}</td>
                <td>{{ row.data.copies || 'Inválido' }}</td>
                <td>{{ row.data.already_imported ? 'Já importado' : row.data.possible_duplicate ? 'Possível duplicidade' : row.data.existing ? 'Já cadastrado por ISBN' : row.data.status === 'valid' ? 'Novo' : statusLabel(row) }}</td>
                <td>{{ statusLabel(row) }}<ul v-if="row.data.errors.length || row.data.warnings.length || row.data.processing_error"><li v-for="message in [...row.data.errors, ...row.data.warnings, row.data.processing_error].filter(Boolean)" :key="message" class="muted">{{ message }}</li></ul></td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.import-page {
  display: grid;
  gap: 20px;
  min-width: 0;
}
.import-page .page-heading {
  margin-bottom: 0;
}
.import-page h2 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.4px;
}
.import-source-selector {
  display: flex;
  gap: 8px;
  width: fit-content;
  padding: 5px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
}
.import-source-selector :deep(.import-source-option.p-button) {
  min-width: 150px;
  justify-content: center;
  border-color: transparent;
}
.import-source-selector :deep(.import-source-option.p-button[aria-pressed="true"]) {
  background: var(--soft);
  color: var(--green);
  border-color: var(--line);
  font-weight: 700;
}
.import-setup {
  display: grid;
  gap: 20px;
}
.import-setup-heading {
  display: flex;
  align-items: center;
  gap: 14px;
}
.import-setup-heading p {
  margin: 5px 0 0;
}
.import-source-icon {
  flex: none;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: var(--soft);
  color: var(--green);
}
.import-instructions {
  display: grid;
  gap: 12px;
  margin: 0;
  padding-left: 24px;
}
.import-instructions li {
  padding-left: 4px;
}
.import-instructions li::marker {
  color: var(--green);
  font-weight: 700;
}
.import-instructions strong,
.import-instructions span {
  display: block;
}
.import-instructions strong {
  margin-bottom: 3px;
}
.import-instructions span {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
}
.import-instructions a {
  text-decoration: underline;
  text-underline-offset: 2px;
}
.import-file-picker {
  display: grid;
  gap: 6px;
  padding: 16px;
  border: 1px dashed var(--line);
  border-radius: 10px;
  background: color-mix(in srgb, var(--soft) 45%, var(--surface));
  cursor: pointer;
}
.import-file-title {
  font-weight: 700;
}
.import-file-picker input[type="file"] {
  width: 100%;
  min-width: 0;
  margin-top: 4px;
}
.import-page input:focus-visible,
.import-page a:focus-visible {
  outline: 3px solid #daaa60;
  outline-offset: 3px;
}
.import-upload-status,
.import-resume,
.import-result,
.import-file-result,
.import-summary {
  min-width: 0;
}
.import-file-list {
  margin: 6px 0 0;
  padding-left: 20px;
  overflow-wrap: anywhere;
}
.import-resume {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.import-feedback,
.import-result,
.import-file-result,
.import-summary {
  margin: 0;
}
.import-result p,
.import-summary p,
.import-file-result p {
  margin-bottom: 0;
}
.import-section-heading {
  margin: 10px 0 0;
}
.import-page .table-wrap {
  max-width: 100%;
  min-width: 0;
  overscroll-behavior-inline: contain;
}
.import-page .data-table {
  min-width: 760px;
}
.import-page .data-table input[type="checkbox"] {
  min-width: 18px;
  min-height: 18px;
  accent-color: var(--green);
}
@media (max-width: 800px) {
  .import-page {
    gap: 16px;
  }
  .import-source-selector {
    width: 100%;
  }
  .import-source-selector :deep(.import-source-option.p-button) {
    flex: 1;
    min-width: 0;
  }
  .import-setup {
    gap: 16px;
  }
  .import-instructions span {
    font-size: 13px;
  }
  .import-section-heading {
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 12px;
  }
}
@media (max-width: 520px) {
  .import-page .page-heading h1 {
    font-size: 28px;
  }
  .import-source-selector :deep(.p-button) {
    padding-inline: 10px;
  }
  .import-setup-heading {
    align-items: flex-start;
  }
  .import-section-heading :deep(.p-button) {
    width: 100%;
  }
  .import-page .panel {
    padding: 16px;
  }
}
</style>
