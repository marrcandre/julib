<script setup lang="ts">
import SourceAttribution from "../components/SourceAttribution.vue";
import { ref, onMounted, onUnmounted, nextTick } from "vue";
import { canonicalIsbn } from "../isbn";
import { useRoute } from "vue-router";
import Button from "primevue/button";
import Dialog from "primevue/dialog";
import InputText from "primevue/inputtext";
import Select from "primevue/select";
import MultiSelect from "primevue/multiselect";
import BookCard from "../components/BookCard.vue";
import {
  api,
  ApiError,
  post,
  locationLabel,
  type Copy,
  type Book,
  type Location,
  type Tag,
  type Loan,
} from "../api";
import {
  BrowserMultiFormatReader,
  type IScannerControls,
} from "@zxing/browser";
const pendingRegistration = ref<Record<string, unknown> | null>(null);
const operationKey = ref(crypto.randomUUID());
const duplicateKey = ref(crypto.randomUUID());
const route = useRoute(),
  books = ref<Book[]>([]),
  locations = ref<Location[]>([]),
  tags = ref<Tag[]>([]);
const q = ref(""),
  tag = ref<number | null>(null),
  loc = ref<number | null>(null),
  available = ref<boolean | null>(null),
  page = ref(1),
  total = ref(0);
const error = ref(""),
  message = ref(""),
  busy = ref(false),
  formOpen = ref(false),
  detail = ref<Book | null>(null),
  editing = ref<number | null>(null),
  copyLocation = ref<number | null>(null),
  acquired = ref(""),
  selectedCopies = ref<number[]>([]),
  history = ref<Loan[]>([]);
const bulkOpen = ref(false),
  missingLocation = ref(false);
const external = ref(""),
  candidates = ref<Partial<Book>[]>([]),
  searching = ref(false),
  camera = ref(false),
  video = ref<HTMLVideoElement | null>(null);
let controls: IScannerControls | undefined,
  scanLocked = false;
const stateLabels: Record<string, string> = {
  sold: "Vendido",
  donated: "Doado",
  lost: "Perdido",
};
function confirmMove() {
  if (window.confirm("Confirmar mudança dos exemplares selecionados?"))
    void moveCopies();
}
async function saveAcquisition(copy: Copy) {
  await run(async () => {
    await api("/copies/" + copy.id, {
      method: "PUT",
      body: JSON.stringify({
        acquired_on: copy.acquired_on,
        location_id: copy.location_id,
      }),
    });
    message.value = "Data atualizada.";
    await load();
  });
}
async function showHistory(copyId: number) {
  await run(async () => {
    history.value = await api<Loan[]>("/loans?copy_id=" + copyId);
  });
}
const blank = () => ({
  title: "",
  authors: "",
  isbn: "",
  publisher: "",
  edition: "",
  year: "",
  language: "",
  cover_url: "",
  source: "",
  source_id: "",
  tag_ids: [] as number[],
});
const form = ref(blank()),
  newTag = ref(""),
  shareUrl = ref("");
async function run(fn: () => Promise<void>) {
  error.value = "";
  busy.value = true;
  try {
    await fn();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function load() {
  const params = new URLSearchParams({ q: q.value, page: String(page.value) });
  if (missingLocation.value) params.set("missing_location", "true");
  if (tag.value) params.set("tag_id", String(tag.value));
  if (loc.value) params.set("location_id", String(loc.value));
  if (available.value !== null)
    params.set("available", String(available.value));
  const data = await api<{ items: Book[]; total: number }>("/books?" + params);
  books.value = data.items;
  total.value = data.total;
}
async function refresh() {
  await run(load);
}
function newBook() {
  pendingRegistration.value = null;
  operationKey.value = crypto.randomUUID();
  editing.value = null;
  form.value = blank();
  candidates.value = [];
  formOpen.value = true;
}
function edit(book: Book) {
  editing.value = book.id;
  form.value = {
    ...blank(),
    ...book,
    authors: book.authors.join("; "),
    tag_ids: book.tags.map((t) => t.id),
    source: book.source || "",
    source_id: book.source_id || "",
  };
  detail.value = null;
  formOpen.value = true;
}
async function open(book: Book) {
  await run(async () => {
    detail.value = await api<Book>("/books/" + book.id);
    selectedCopies.value = [];
    history.value = [];
  });
}
async function find() {
  searching.value = true;
  error.value = "";
  try {
    candidates.value = await api<Partial<Book>[]>(
      "/search?q=" + encodeURIComponent(external.value),
    );
    if (!candidates.value.length)
      message.value = "Nenhum resultado. Você pode cadastrar manualmente.";
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    searching.value = false;
  }
}
function useCandidate(candidate: Partial<Book>) {
  form.value = {
    ...blank(),
    ...candidate,
    authors: (candidate.authors || []).join("; "),
    source: candidate.source || "",
    source_id: candidate.source_id || "",
    tag_ids: [],
  };
  candidates.value = [];
  scanLocked = false;
}
async function save() {
  await run(async () => {
    const payload = {
      ...form.value,
      authors: form.value.authors
        .split(";")
        .map((a) => a.trim())
        .filter(Boolean),
    };
    if (editing.value) {
      await api<Book>("/books/" + editing.value, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    } else {
      if (!pendingRegistration.value) {
        let existing: Book | undefined;
        if (form.value.isbn) {
          const data = await api<{ items: Book[] }>(
            "/books?q=" + encodeURIComponent(canonicalIsbn(form.value.isbn)),
          );
          existing = data.items.find(
            (b) => b.isbn === canonicalIsbn(form.value.isbn),
          );
        }
        if (
          existing &&
          !confirm(
            `Este livro já tem ${existing.copies.length} exemplar(es). Adicionar outra cópia?`,
          )
        )
          return;
        pendingRegistration.value = {
          key: operationKey.value,
          book: payload,
          existing_book_id: existing?.id || null,
          location_id: copyLocation.value,
          acquired_on: acquired.value || null,
        };
      }
      try {
        await post("/registrations", pendingRegistration.value);
      } catch (e) {
        if (e instanceof ApiError && e.status && e.status < 500)
          pendingRegistration.value = null;
        throw e;
      }
      pendingRegistration.value = null;
      operationKey.value = crypto.randomUUID();
    }
    message.value = editing.value
      ? "Dados atualizados."
      : "Exemplar cadastrado.";
    if (camera.value) {
      form.value = blank();
      scanLocked = false;
    } else formOpen.value = false;
    await load();
  });
}
async function addCopy() {
  if (!detail.value) return;
  if (!confirm("Adicionar outra cópia desta edição?")) return;
  await run(async () => {
    await post("/registrations", {
      key: duplicateKey.value,
      book: { ...detail.value!, tag_ids: detail.value!.tags.map((t) => t.id) },
      existing_book_id: detail.value!.id,
      location_id: copyLocation.value,
      acquired_on: acquired.value || null,
    });
    duplicateKey.value = crypto.randomUUID();
    await open(detail.value!);
    await load();
  });
}
async function moveCopies() {
  await run(async () => {
    await post("/copies/locate", {
      copy_ids: selectedCopies.value,
      location_id: copyLocation.value,
    });
    if (detail.value)
      detail.value = await api<Book>("/books/" + detail.value.id);
    selectedCopies.value = [];
    await load();
  });
}
async function retire(id: number, reason: string) {
  if (
    !confirm(
      reason === "active"
        ? "Reativar exemplar?"
        : "Confirmar baixa do exemplar? O histórico será preservado.",
    )
  )
    return;
  await run(async () => {
    await post("/copies/" + id + "/retire", { reason });
    if (detail.value)
      detail.value = await api<Book>("/books/" + detail.value.id);
    await load();
  });
}
async function addTag() {
  await run(async () => {
    const created = await post<Tag>("/tags", { name: newTag.value });
    tags.value.push(created);
    form.value.tag_ids.push(created.id);
    newTag.value = "";
  });
}
async function share() {
  if (
    !confirm(
      "Gerar novo link de consulta? Um link anterior deixará de funcionar.",
    )
  )
    return;
  await run(async () => {
    const data = await post<{ token: string }>("/share/manage");
    shareUrl.value = location.origin + "/colecao/" + data.token;
  });
}
async function disableShare() {
  await run(async () => {
    await api("/share/manage", { method: "DELETE" });
    shareUrl.value = "";
    message.value = "Link de consulta desativado.";
  });
}
async function startCamera() {
  camera.value = true;
  formOpen.value = true;
  await nextTick();
  try {
    if (!video.value) return;
    controls = await new BrowserMultiFormatReader().decodeFromVideoDevice(
      undefined,
      video.value,
      (result) => {
        if (result && !scanLocked) {
          scanLocked = true;
          external.value = "isbn:" + result.getText();
          void find();
        }
      },
    );
  } catch {
    error.value =
      "Não foi possível acessar a câmera. Permita o acesso ou digite o ISBN.";
    camera.value = false;
  }
}
function stopCamera() {
  controls?.stop();
  camera.value = false;
  scanLocked = false;
}
async function upload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file || !detail.value) return;
  if (file.size > 5 * 1024 * 1024) {
    error.value = "A imagem deve ter até 5 MB.";
    return;
  }
  await run(async () => {
    const signed = await post<Record<string, string>>("/media/sign");
    const body = new FormData();
    for (const [key, value] of Object.entries(signed)) {
      if (key !== "cloud_name") body.append(key, String(value));
    }
    body.append("file", file);
    const response = await fetch(
      `https://api.cloudinary.com/v1_1/${signed.cloud_name}/image/upload`,
      { method: "POST", body },
    );
    const data = await response.json();
    if (!response.ok) throw new Error("Não foi possível enviar a imagem.");
    await post("/books/" + detail.value!.id + "/cover", {
      public_id: data.public_id,
    });
    detail.value = await api<Book>("/books/" + detail.value!.id);
    await load();
  });
}
onMounted(() =>
  run(async () => {
    [locations.value, tags.value] = await Promise.all([
      api<Location[]>("/locations"),
      api<Tag[]>("/tags"),
    ]);
    await load();
    if (route.query.novo) newBook();
    if (route.query.livro)
      detail.value = await api<Book>("/books/" + route.query.livro);
  }),
);
onUnmounted(stopCamera);
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">HISTÓRIAS NA SUA ESTANTE</div>
      <h1>Livros</h1>
      <p class="muted">{{ total }} edições na sua biblioteca.</p>
    </div>
    <div class="actions">
      <Button
        label="Câmera"
        icon="pi pi-camera"
        severity="secondary"
        @click="
          newBook();
          startCamera();
        "
      /><Button
        label="Adicionar livro"
        icon="pi pi-plus"
        class="primary"
        @click="newBook"
      />
    </div>
  </div>
  <div class="actions">
    <RouterLink to="/importar">Importar Goodreads</RouterLink
    ><Button
      label="Localização em lote"
      text
      @click="
        bulkOpen = true;
        selectedCopies = [];
      "
    /><Button
      label="Gerar link de consulta"
      size="small"
      text
      @click="share"
    /><Button label="Desativar link" size="small" text @click="disableShare" />
  </div>
  <div v-if="shareUrl" class="notice">
    <label
      >Seu link somente leitura
      <input :value="shareUrl" readonly aria-label="Link de consulta"
    /></label>
    <p>Qualquer pessoa com o link pode consultar a coleção.</p>
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="message" class="notice" role="status">{{ message }}</p>
  <form
    class="toolbar"
    @submit.prevent="
      page = 1;
      refresh();
    "
  >
    <InputText
      v-model="q"
      placeholder="Título, autor ou ISBN"
      aria-label="Buscar no acervo"
    /><Select
      v-model="tag"
      :options="tags"
      option-label="name"
      option-value="id"
      placeholder="Todas as tags"
      show-clear
      aria-label="Filtrar por tag"
    /><Select
      v-model="loc"
      :options="
        locations.map((l) => ({
          id: l.id,
          name: locationLabel(locations, l.id),
        }))
      "
      option-label="name"
      option-value="id"
      placeholder="Todos os locais"
      show-clear
      aria-label="Filtrar por local"
    /><Select
      v-model="available"
      :options="[
        { name: 'Disponíveis', value: true },
        { name: 'Indisponíveis', value: false },
      ]"
      option-label="name"
      option-value="value"
      placeholder="Disponibilidade"
      show-clear
      aria-label="Disponibilidade"
    /><label
      style="display: flex; gap: 5px; align-items: center; font-size: 12px"
      ><input type="checkbox" v-model="missingLocation" />Sem localização</label
    ><Button type="submit" label="Buscar" :loading="busy" />
  </form>
  <div v-if="!books.length" class="empty">
    <i class="pi pi-book" />Nenhum livro encontrado. Cadastre um livro ou altere
    os filtros.
  </div>
  <div v-else class="book-grid">
    <div v-for="book in books" :key="book.id">
      <button
        style="
          width: 100%;
          text-align: left;
          border: 0;
          padding: 0;
          background: none;
          color: inherit;
        "
        @click="open(book)"
      >
        <BookCard :book="book" /></button
      ><SourceAttribution
        :name="book.attribution_name"
        :url="book.attribution_url"
      />
    </div>
  </div>
  <div class="pagination">
    <Button
      label="Anterior"
      text
      :disabled="page === 1"
      @click="
        page--;
        refresh();
      "
    /><span>Página {{ page }}</span
    ><Button
      label="Próxima"
      text
      :disabled="page * 24 >= total"
      @click="
        page++;
        refresh();
      "
    />
  </div>
  <Dialog
    v-model:visible="bulkOpen"
    modal
    header="Localização em lote"
    :style="{ width: '750px' }"
    ><p class="muted">
      Selecione exemplares dos livros da página atual e confirme o destino.
    </p>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Selecionar</th>
            <th>Livro</th>
            <th>Exemplar</th>
            <th>Local atual</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="book in books" :key="book.id"
            ><tr
              v-for="copy in book.copies?.filter((c) => c.state === 'active')"
              :key="copy.id"
            >
              <td>
                <input
                  type="checkbox"
                  v-model="selectedCopies"
                  :value="copy.id"
                  :aria-label="'Selecionar exemplar ' + copy.number"
                />
              </td>
              <td>{{ book.title }}</td>
              <td>#{{ copy.number }}</td>
              <td>{{ locationLabel(locations, copy.location_id) }}</td>
            </tr></template
          >
        </tbody>
      </table>
    </div>
    <div class="toolbar">
      <Select
        v-model="copyLocation"
        :options="
          locations.map((l) => ({
            id: l.id,
            name: locationLabel(locations, l.id),
          }))
        "
        option-label="name"
        option-value="id"
        placeholder="Sem localização"
        show-clear
        aria-label="Destino dos exemplares"
      /><Button
        :label="'Mover ' + selectedCopies.length + ' selecionados'"
        :disabled="!selectedCopies.length || busy"
        @click="confirmMove"
      /></div></Dialog
  ><Dialog
    v-model:visible="formOpen"
    modal
    :header="editing ? 'Editar livro' : 'Cadastrar livro'"
    :style="{ width: '650px' }"
    @hide="stopCamera"
    ><p v-if="error" class="error" role="alert">{{ error }}</p>
    <video v-if="camera" ref="video" autoplay playsinline />
    <form class="toolbar" @submit.prevent="find">
      <InputText
        v-model="external"
        placeholder="Buscar por título, autor ou ISBN"
        aria-label="Buscar em APIs"
      /><Button label="Buscar dados" type="submit" :loading="searching" />
    </form>
    <p v-if="candidates.some((c) => c.source === 'google')" class="muted">
      <img
        src="https://books.google.com/googlebooks/images/poweredby.png"
        alt="Powered by Google"
        style="background: white; padding: 3px; border-radius: 3px; width: 88px"
      />
      Google Books search results
    </p>
    <div v-if="candidates.length" class="panel">
      <div v-for="(candidate, i) in candidates" :key="i">
        <button
          class="loan-row"
          style="
            width: 100%;
            background: none;
            color: inherit;
            text-align: left;
            border: 0;
          "
          @click="useCandidate(candidate)"
        >
          <span
            ><b>{{ candidate.title }}</b
            ><br />{{ candidate.authors?.join(", ") }} ·
            {{ candidate.isbn }}</span
          ><i class="pi pi-plus" /></button
        ><SourceAttribution
          v-if="candidate.source === 'google'"
          name="Google Books"
          :url="
            'https://books.google.com/books?id=' +
            encodeURIComponent(candidate.source_id || '')
          "
        /><SourceAttribution
          v-else-if="candidate.source === 'openlibrary'"
          name="Open Library"
          :url="'https://openlibrary.org' + candidate.source_id"
        />
      </div>
    </div>
    <p v-if="pendingRegistration" class="notice">
      Uma tentativa está aguardando confirmação. Salvar novamente repete a mesma
      operação com segurança.
    </p>
    <form class="fields" @submit.prevent="save">
      <label>Título *<InputText v-model="form.title" required /></label
      ><label
        >Autores * (separe por ponto e vírgula)<InputText
          v-model="form.authors"
          required
      /></label>
      <div class="row">
        <label>ISBN<InputText v-model="form.isbn" /></label
        ><label>Editora<InputText v-model="form.publisher" /></label>
      </div>
      <div class="row">
        <label>Edição<InputText v-model="form.edition" /></label
        ><label>Ano<InputText v-model="form.year" /></label>
      </div>
      <div class="row">
        <label>Idioma<InputText v-model="form.language" /></label
        ><label
          >URL da capa (HTTPS)<InputText v-model="form.cover_url"
        /></label>
      </div>
      <label
        >Tags<MultiSelect
          v-model="form.tag_ids"
          :options="tags"
          option-label="name"
          option-value="id"
          display="chip"
      /></label>
      <div class="actions">
        <InputText
          v-model="newTag"
          placeholder="Nova tag"
          aria-label="Nova tag"
        /><Button
          label="Criar tag"
          text
          :disabled="!newTag.trim()"
          @click="addTag"
        />
      </div>
      <template v-if="!editing"
        ><label
          >Localização<Select
            v-model="copyLocation"
            :options="
              locations.map((l) => ({
                id: l.id,
                name: locationLabel(locations, l.id),
              }))
            "
            option-label="name"
            option-value="id"
            placeholder="Sem localização"
            show-clear /></label
        ><label
          >Data de aquisição (opcional)<InputText
            type="date"
            v-model="acquired"
          /><small class="muted"
            >Em branco, usamos a data do cadastro.</small
          ></label
        ></template
      ><Button
        type="submit"
        :label="camera ? 'Salvar e continuar' : 'Salvar'"
        class="primary"
        :loading="busy"
      /></form
  ></Dialog>
  <Dialog
    :visible="!!detail"
    modal
    :header="detail?.title"
    :style="{ width: '850px' }"
    @update:visible="detail = null"
    ><template v-if="detail"
      ><p v-if="error" class="error">{{ error }}</p>
      <p>{{ detail.authors.join(", ") }}</p>
      <p class="muted">
        {{ detail.isbn }} · {{ detail.publisher }} · {{ detail.year }} ·
        {{ detail.edition }}
      </p>
      <div class="tag-list">
        <span v-for="t in detail.tags" :key="t.id" class="tag-pill">{{
          t.name
        }}</span>
      </div>
      <div class="actions">
        <Button label="Editar dados" text @click="edit(detail)" /><label
          class="tag-pill"
          >Enviar capa<input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            @change="upload"
            style="max-width: 200px"
        /></label>
      </div>
      <SourceAttribution
        :name="detail.attribution_name"
        :url="detail.attribution_url"
      />
      <h3>Exemplares</h3>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Selecionar</th>
              <th>Número</th>
              <th>Local</th>
              <th>Aquisição</th>
              <th>Situação</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="copy in detail.copies" :key="copy.id">
              <td>
                <input
                  type="checkbox"
                  v-model="selectedCopies"
                  :value="copy.id"
                  :aria-label="'Selecionar exemplar ' + copy.number"
                />
              </td>
              <td>#{{ copy.number }}</td>
              <td>{{ locationLabel(locations, copy.location_id) }}</td>
              <td>
                <input
                  type="date"
                  v-model="copy.acquired_on"
                  :aria-label="'Aquisição do exemplar ' + copy.number"
                /><Button
                  label="Salvar data"
                  text
                  size="small"
                  @click="saveAcquisition(copy)"
                />
              </td>
              <td>
                {{
                  copy.state === "active"
                    ? copy.on_loan
                      ? "Emprestado"
                      : "Disponível"
                    : stateLabels[copy.state]
                }}
              </td>
              <td>
                <Button
                  label="Histórico"
                  text
                  size="small"
                  @click="showHistory(copy.id)"
                /><select
                  v-if="copy.state === 'active'"
                  aria-label="Dar baixa"
                  @change="
                    retire(copy.id, ($event.target as HTMLSelectElement).value);
                    ($event.target as HTMLSelectElement).value = '';
                  "
                >
                  <option value="">Dar baixa…</option>
                  <option value="sold">Venda</option>
                  <option value="donated">Doação</option>
                  <option value="lost">Perda</option></select
                ><Button
                  v-else
                  label="Reativar"
                  text
                  size="small"
                  @click="retire(copy.id, 'active')"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="toolbar">
        <Select
          v-model="copyLocation"
          :options="
            locations.map((l) => ({
              id: l.id,
              name: locationLabel(locations, l.id),
            }))
          "
          option-label="name"
          option-value="id"
          placeholder="Sem localização"
          show-clear
          aria-label="Local de destino"
        /><Button
          label="Mover selecionados"
          :disabled="!selectedCopies.length || busy"
          @click="moveCopies"
        /><Button
          label="Adicionar exemplar"
          text
          :disabled="busy"
          @click="addCopy"
        />
      </div>
      <div v-if="history.length" class="panel">
        <h3>Histórico do exemplar</h3>
        <div v-for="loan in history" :key="loan.id" class="loan-row">
          <span>{{ loan.person_name }} · {{ loan.started_on }}</span
          ><span>{{
            loan.state === "returned"
              ? "Devolvido em " + loan.returned_on
              : loan.state === "lost"
                ? "Encerrado por perda"
                : "Em aberto"
          }}</span>
        </div>
      </div></template
    ></Dialog
  >
</template>
