<script setup lang="ts">
import SourceAttribution from "../components/SourceAttribution.vue";
import CatalogToolbar, {
  type CatalogView,
  type CatalogFilters,
} from "../components/CatalogToolbar.vue";
import { readCoverColumns, writeCoverColumns } from "../catalog-preferences";
import { useToast } from "primevue/usetoast";
import {
  ref,
  onMounted,
  onUnmounted,
  nextTick,
  watch,
  inject,
  computed,
  type Ref,
} from "vue";
import { canonicalIsbn, isbnFromBarcode } from "../isbn";
import { useRoute } from "vue-router";
import Button from "primevue/button";
import Dialog from "primevue/dialog";
import InputText from "primevue/inputtext";
import InputNumber from "primevue/inputnumber";
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
  type Session,
} from "../api";
import {
  BrowserMultiFormatReader,
  type IScannerControls,
} from "@zxing/browser";
const session = inject<Ref<Session | null>>("session");
const catalogView = ref<CatalogView>(session?.value?.catalog_view || "covers");
const coverColumns = ref(
  readCoverColumns(
    session?.value?.user_id,
    window.matchMedia("(max-width: 800px)").matches,
  ),
);
const densitySaved = ref(true);
watch(coverColumns, (value) => {
  densitySaved.value = writeCoverColumns(session?.value?.user_id, value);
});
let preferenceSave = Promise.resolve();
let preferenceVersion = 0;
watch(catalogView, (view) => {
  const version = ++preferenceVersion;
  preferenceSave = preferenceSave
    .then(async () => {
      const saved = await api<{
        catalog_view: CatalogView;
        cover_columns: number;
      }>("/preferences/catalog", {
        method: "PUT",
        body: JSON.stringify({
          catalog_view: view,
          cover_columns: session?.value?.cover_columns || 7,
        }),
      });
      if (session?.value && version === preferenceVersion)
        Object.assign(session.value, saved);
    })
    .catch(() => {
      error.value =
        "Não foi possível salvar sua preferência de visualização. Tente novamente.";
    });
});
let searchTimer: ReturnType<typeof setTimeout> | undefined;
let loadVersion = 0;
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
  scanLocked = false,
  cameraAttempt = 0;
const entryMethod = ref<"camera" | "search" | "manual">("search");
const shareOpen = ref(false),
  shareActive = ref(false);
const toast = useToast();
watch(message, (value) => {
  if (!value) return;
  toast.removeAllGroups();
  toast.add({
    severity: value.startsWith("Nenhum") ? "info" : "success",
    summary: value,
    life: 3500,
  });
  message.value = "";
});
const currentFilters = computed<CatalogFilters>(() => ({
  tag: tag.value,
  location: loc.value,
  available: available.value,
  missingLocation: missingLocation.value,
}));
function applyFilters(filters: CatalogFilters) {
  tag.value = filters.tag;
  loc.value = filters.location;
  available.value = filters.available;
  missingLocation.value = filters.missingLocation;
  searchNow();
}
function addBook(method: "camera" | "search" | "manual") {
  entryMethod.value = method;
  newBook();
  if (method === "camera") void startCamera();
}
async function openShare() {
  shareUrl.value = "";
  shareOpen.value = true;
  shareActive.value = false;
  await run(async () => {
    const data = await api<{ active: boolean }>("/share/manage");
    shareActive.value = data.active;
  });
}
async function copyShareLink() {
  try {
    await navigator.clipboard.writeText(shareUrl.value);
    message.value = "Link copiado.";
  } catch {
    error.value =
      "Não foi possível copiar. Selecione o link e copie manualmente.";
  }
}
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
  page_count: null as number | null,
  language: "",
  cover_url: "",
  source: "",
  source_id: "",
  tag_ids: [] as number[],
});
const formAttribution = ref({ name: "", url: "" });
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
  const version = ++loadVersion;
  const searchValue = q.value;
  const params = new URLSearchParams({ q: q.value, page: String(page.value) });
  if (missingLocation.value) params.set("missing_location", "true");
  if (tag.value) params.set("tag_id", String(tag.value));
  if (loc.value) params.set("location_id", String(loc.value));
  if (available.value !== null)
    params.set("available", String(available.value));
  try {
    const data = await api<{ items: Book[]; total: number }>(
      "/books?" + params,
    );
    if (version !== loadVersion || searchValue !== q.value) return;
    books.value = data.items;
    total.value = data.total;
  } catch (cause) {
    if (version !== loadVersion || searchValue !== q.value) return;
    throw cause;
  }
}
async function refresh() {
  clearTimeout(searchTimer);
  await run(load);
}
function newBook() {
  pendingRegistration.value = null;
  operationKey.value = crypto.randomUUID();
  editing.value = null;
  form.value = blank();
  formAttribution.value = { name: "", url: "" };
  candidates.value = [];
  formOpen.value = true;
}
function edit(book: Book) {
  formAttribution.value = {
    name: book.attribution_name || "",
    url: book.attribution_url || "",
  };
  entryMethod.value = "manual";
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
  formAttribution.value =
    candidate.source === "google"
      ? {
          name: "Google Books",
          url:
            "https://books.google.com/books?id=" +
            encodeURIComponent(candidate.source_id || ""),
        }
      : candidate.source === "openlibrary"
        ? {
            name: "Open Library",
            url: "https://openlibrary.org" + candidate.source_id,
          }
        : candidate.source === "brasilapi"
          ? {
              name: "BrasilAPI (CBL)",
              url:
                "https://brasilapi.com.br/api/isbn/v1/" +
                encodeURIComponent(candidate.source_id || "") +
                "?providers=cbl",
            }
          : { name: "", url: "" };
  form.value = {
    ...blank(),
    ...candidate,
    authors: (candidate.authors || []).join("; "),
    source: candidate.source || "",
    source_id: candidate.source_id || "",
    tag_ids: [],
  };
  candidates.value = [];
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
    shareActive.value = true;
  });
}
async function disableShare() {
  if (
    !confirm("Desativar o link de consulta? Quem o recebeu perderá o acesso.")
  )
    return;
  await run(async () => {
    await api("/share/manage", { method: "DELETE" });
    shareUrl.value = "";
    shareActive.value = false;
    message.value = "Link de consulta desativado.";
  });
}
async function startCamera() {
  const attempt = ++cameraAttempt;
  camera.value = true;
  formOpen.value = true;
  await nextTick();
  try {
    if (!video.value) return;
    const startedControls =
      await new BrowserMultiFormatReader().decodeFromVideoDevice(
        undefined,
        video.value,
        (result) => {
          if (
            result &&
            !scanLocked &&
            camera.value &&
            attempt === cameraAttempt
          ) {
            const isbn = isbnFromBarcode(result.getText());
            if (!isbn) return;
            scanLocked = true;
            external.value = "isbn:" + isbn;
            void find();
          }
        },
      );
    if (attempt !== cameraAttempt || !camera.value) startedControls.stop();
    else controls = startedControls;
  } catch {
    if (attempt !== cameraAttempt) return;
    error.value =
      "Não foi possível acessar a câmera. Permita o acesso ou digite o ISBN.";
    camera.value = false;
  }
}
function stopCamera() {
  ++cameraAttempt;
  controls?.stop();
  controls = undefined;
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
function searchNow() {
  clearTimeout(searchTimer);
  page.value = 1;
  void refresh();
}
watch(q, (value) => {
  clearTimeout(searchTimer);
  ++loadVersion;
  if (!value) searchNow();
  else searchTimer = setTimeout(searchNow, 300);
});
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
onUnmounted(() => {
  clearTimeout(searchTimer);
  ++loadVersion;
  stopCamera();
});
</script>
<template>
  <CatalogToolbar
    v-model:query="q"
    v-model:view="catalogView"
    v-model:columns="coverColumns"
    :total="total"
    :tags="tags"
    :locations="locations"
    :filters="currentFilters"
    :density-saved="densitySaved"
    @filters="applyFilters"
    @add="addBook"
    @bulk="
      bulkOpen = true;
      selectedCopies = [];
    "
    @share="openShare"
  />
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div v-if="!books.length" class="empty">
    <i class="pi pi-book" />Nenhum livro encontrado. Cadastre um livro ou altere
    os filtros.
  </div>
  <div
    v-else
    :class="
      catalogView === 'list'
        ? 'catalog-list'
        : ['book-grid', { 'catalog-covers': catalogView === 'covers' }]
    "
    :style="{ '--cover-columns': coverColumns }"
  >
    <div v-for="book in books" :key="book.id" class="catalog-item">
      <button
        :aria-label="'Abrir ' + book.title"
        :title="book.title"
        class="book-open"
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
        <BookCard :book="book" :variant="catalogView" /></button
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
    v-model:visible="shareOpen"
    modal
    header="Compartilhar coleção"
    :style="{ width: '500px' }"
  >
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p class="muted">
      Consulta somente leitura, sem contatos, histórico de empréstimos ou
      localizações.
    </p>
    <p v-if="shareActive && !shareUrl" class="notice">
      Um link está ativo. Para compartilhar outro, renove o link; o anterior
      deixará de funcionar.
    </p>
    <label v-if="shareUrl" class="share-link-field"
      >Seu link somente leitura<InputText
        :model-value="shareUrl"
        readonly
        aria-label="Link de consulta" /><Button
        label="Copiar link"
        icon="pi pi-copy"
        @click="copyShareLink"
    /></label>
    <div class="actions">
      <Button
        :label="shareActive ? 'Renovar link' : 'Gerar link de consulta'"
        icon="pi pi-share-alt"
        :loading="busy"
        :disabled="busy"
        @click="share"
      /><Button
        v-if="shareActive"
        label="Desativar link"
        severity="danger"
        text
        :disabled="busy"
        @click="disableShare"
      />
    </div>
  </Dialog>
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
    <template v-if="camera">
      <p class="muted">
        Aponte para o código de barras ISBN do livro. A busca começa
        automaticamente; confira os dados antes de salvar.
      </p>
      <video ref="video" autoplay playsinline muted />
      <Button label="Ler outro código" text @click="scanLocked = false" />
    </template>
    <template v-if="entryMethod !== 'manual'">
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
          style="
            background: white;
            padding: 3px;
            border-radius: 3px;
            width: 88px;
          "
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
          /><SourceAttribution
            v-else-if="candidate.source === 'brasilapi'"
            name="BrasilAPI (CBL)"
            :url="
              'https://brasilapi.com.br/api/isbn/v1/' +
              encodeURIComponent(candidate.source_id || '') +
              '?providers=cbl'
            "
          />
        </div>
      </div>
    </template>
    <p v-if="pendingRegistration" class="notice">
      Uma tentativa está aguardando confirmação. Salvar novamente repete a mesma
      operação com segurança.
    </p>
    <form class="fields" @submit.prevent="save">
      <figure v-if="form.cover_url" class="edit-cover">
        <img
          :src="form.cover_url"
          alt="Capa atual"
          referrerpolicy="no-referrer"
        />
        <figcaption class="muted">Capa atual</figcaption>
      </figure>
      <SourceAttribution
        :name="formAttribution.name"
        :url="formAttribution.url"
      />
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
        <label
          >Número de páginas<InputNumber
            v-model="form.page_count"
            :min="1"
            :max="2147483647"
            :use-grouping="false"
            input-id="page-count"
            :max-fraction-digits="0"
        /></label>
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
      <p v-if="detail.page_count" class="muted">
        {{ detail.page_count }} páginas
      </p>
      <div class="detail-cover-actions">
        <div class="actions">
          <Button label="Editar dados" text @click="edit(detail)" /><label
            class="tag-pill cover-upload"
            >Enviar capa<input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              @change="upload"
          /></label>
        </div>
        <img
          v-if="detail.cover_url"
          class="detail-cover"
          :src="detail.cover_url"
          alt="Capa do livro"
          referrerpolicy="no-referrer"
        />
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
