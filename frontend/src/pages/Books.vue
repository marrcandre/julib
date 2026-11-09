<script setup lang="ts">
import {
  readCatalogOrder,
  writeCatalogOrder,
  type Situation,
} from "../catalog-options";
import CatalogPagination from "../components/CatalogPagination.vue";
import {
  pageForOffset,
  sizeForLayout,
  readPagePreferences,
  savePagePreferences,
} from "../pagination";
import BookCredits from "../components/BookCredits.vue";
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
import { useRoute, useRouter, onBeforeRouteLeave } from "vue-router";
import {
  readCatalogQuery,
  catalogQuery,
  saveCatalogPosition,
  catalogPosition,
} from "../catalog-navigation";
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
  type Book,
  type Location,
  type Tag,
  type Session,
} from "../api";
import {
  BrowserMultiFormatReader,
  type IScannerControls,
} from "@zxing/browser";
const session = inject<Ref<Session | null>>("session");
const gridMedia = window.matchMedia("(max-width: 800px)");
const gridMobile = ref(gridMedia.matches);
const savedPagination = readPagePreferences(session?.value?.user_id);
const rows = ref(savedPagination.rows),
  listSize = ref(savedPagination.listSize);
const resultsRoot = ref<HTMLElement>();
let catalogReady = false;
const updateGridMedia = () => {
  gridMobile.value = gridMedia.matches;
};
onMounted(() => gridMedia.addEventListener("change", updateGridMedia));
onUnmounted(() => gridMedia.removeEventListener("change", updateGridMedia));
const catalogView = ref<CatalogView>(session?.value?.catalog_view || "covers");
const coverColumns = ref(
  readCoverColumns(
    session?.value?.user_id,
    window.matchMedia("(max-width: 800px)").matches,
  ),
);
const requestedSize = computed(() =>
  sizeForLayout(
    catalogView.value,
    rows.value,
    coverColumns.value,
    gridMobile.value,
    listSize.value,
  ),
);
const pageSize = ref(requestedSize.value);
watch([rows, listSize], () =>
  savePagePreferences(session?.value?.user_id, {
    rows: rows.value,
    listSize: listSize.value,
  }),
);
const scope = computed(() =>
  statuses.value.length === 1 && statuses.value[0] === "wishlist"
    ? ("wishlist" as const)
    : ("collection" as const),
);
const registrationTarget = ref<"collection" | "wishlist">("collection");
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
let selectionVersion = 0;
const enriching = ref(false);
const pendingRegistration = ref<Record<string, unknown> | null>(null);
const operationKey = ref(crypto.randomUUID());
const router = useRouter();
const route = useRoute(),
  books = ref<Book[]>([]),
  locations = ref<Location[]>([]),
  tags = ref<Tag[]>([]);
const initialCatalog = readCatalogQuery(
  route.query,
  readCatalogOrder(session?.value?.user_id),
);
const startNew = !!route.query.novo;
const q = ref(initialCatalog.q),
  tag = ref<number | null>(initialCatalog.tag),
  loc = ref<number | null>(initialCatalog.location),
  statuses = ref<Situation[]>(initialCatalog.statuses),
  order = ref(initialCatalog.order),
  page = ref(
    pageForOffset(
      (initialCatalog.page - 1) * initialCatalog.pageSize,
      pageSize.value,
    ),
  ),
  total = ref(0);
watch(order, (value) => {
  writeCatalogOrder(session?.value?.user_id, value);
  if (route.query.ordem !== value) searchNow();
});
const error = ref(""),
  message = ref(""),
  busy = ref(false),
  formOpen = ref(false),
  copyLocation = ref<number | null>(null),
  acquired = ref(""),
  selectedCopies = ref<number[]>([]);
const bulkOpen = ref(false),
  missingLocation = ref(initialCatalog.missing);
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
    severity: value.startsWith("Não foi possível complementar")
      ? "warn"
      : value.startsWith("Nenhum")
        ? "info"
        : "success",
    summary: value,
    life: 3500,
  });
  message.value = "";
});
const currentFilters = computed<CatalogFilters>(() => ({
  tag: tag.value,
  location: loc.value,
  statuses: statuses.value,
  missingLocation: missingLocation.value,
}));
function applyFilters(filters: CatalogFilters) {
  tag.value = filters.tag;
  loc.value = filters.location;
  statuses.value = filters.statuses;
  selectedCopies.value = [];
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
  provenance: {} as Book["provenance"],
  metadata_attribution_name: "",
  metadata_attribution_url: "",
  attribution_name: "",
  attribution_url: "",
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
watch(requestedSize, async (size) => {
  const elements = [
    ...(resultsRoot.value?.querySelectorAll<HTMLElement>("[data-book-id]") ||
      []),
  ];
  const index = Math.max(
    0,
    elements.findIndex((el) => {
      const box = el.getBoundingClientRect();
      return box.bottom > 0 && box.top < innerHeight;
    }),
  );
  const anchor = books.value[index]?.id;
  const offset = (page.value - 1) * pageSize.value + index;
  pageSize.value = size;
  page.value = pageForOffset(offset, size);
  selectedCopies.value = [];
  if (catalogReady) {
    await refresh();
    await nextTick();
    if (pageSize.value === size && anchor)
      resultsRoot.value
        ?.querySelector<HTMLElement>(`[data-book-id="${anchor}"]`)
        ?.scrollIntoView({ block: "nearest" });
  }
});
function pageHref(target: number) {
  return router.resolve({
    path: "/livros",
    query: catalogQuery({ ...catalogState(), page: target }),
  }).fullPath;
}
async function selectPage(target: number) {
  if (busy.value || target === page.value) return;
  page.value = target;
  selectedCopies.value = [];
  await router.push(pageHref(target));
  await refresh();
  await nextTick();
  resultsRoot.value?.scrollIntoView({ block: "start" });
}
function catalogState() {
  return {
    q: q.value,
    tag: tag.value,
    location: loc.value,
    statuses: statuses.value,
    missing: missingLocation.value,
    page: page.value,
    order: order.value,
    pageSize: pageSize.value,
  };
}
const catalogUrl = computed(
  () =>
    router.resolve({ path: "/livros", query: catalogQuery(catalogState()) })
      .fullPath,
);
function bookLink(book: Book) {
  return { path: "/livros/" + book.id, query: { voltar: catalogUrl.value } };
}
onBeforeRouteLeave(() => {
  saveCatalogPosition(catalogUrl.value);
});
watch(
  () => route.query,
  (query) => {
    if (route.path !== "/livros") return;
    const state = readCatalogQuery(
      query,
      readCatalogOrder(session?.value?.user_id),
    );
    state.page = pageForOffset(
      (state.page - 1) * state.pageSize,
      requestedSize.value,
    );
    state.pageSize = requestedSize.value;
    if (
      JSON.stringify(catalogQuery(state)) ===
      JSON.stringify(catalogQuery(catalogState()))
    )
      return;
    const changedPage = state.page !== page.value;
    selectedCopies.value = [];
    clearTimeout(searchTimer);
    q.value = state.q;
    tag.value = state.tag;
    loc.value = state.location;
    statuses.value = state.statuses;
    order.value = state.order;
    missingLocation.value = state.missing;
    page.value = state.page;
    pageSize.value = state.pageSize;
    void refresh().then(async () => {
      if (changedPage) {
        await nextTick();
        resultsRoot.value?.scrollIntoView({ block: "start" });
      }
    });
  },
);
async function load() {
  const version = ++loadVersion;
  const path = catalogUrl.value;
  if (route.path === "/livros" && route.fullPath !== path)
    void router.replace(path);
  const searchValue = q.value;
  const params = new URLSearchParams({
    q: q.value,
    page: String(page.value),
    page_size: String(pageSize.value),
    statuses: statuses.value.join(","),
    order: order.value,
  });
  if (missingLocation.value) params.set("missing_location", "true");
  if (tag.value) params.set("tag_id", String(tag.value));
  if (loc.value) params.set("location_id", String(loc.value));
  try {
    const data = await api<{ items: Book[]; total: number; page?: number }>(
      "/books?" + params,
    );
    if (version !== loadVersion || searchValue !== q.value) return;
    books.value = data.items;
    total.value = data.total;
    const clamped =
      data.page ||
      Math.min(page.value, Math.max(1, Math.ceil(data.total / pageSize.value)));
    if (clamped !== page.value) {
      page.value = clamped;
      void router.replace(catalogUrl.value);
    }
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
  ++selectionVersion;
  enriching.value = false;
  pendingRegistration.value = null;
  operationKey.value = crypto.randomUUID();
  registrationTarget.value = scope.value;
  form.value = blank();
  candidates.value = [];
  formOpen.value = true;
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
async function useCandidate(candidate: Partial<Book>) {
  form.value = {
    ...blank(),
    ...candidate,
    authors: (candidate.authors || []).join("; "),
    source: candidate.source || "",
    source_id: candidate.source_id || "",
    tag_ids: [],
  };
  candidates.value = [];
  const key = operationKey.value;
  const snapshot = JSON.stringify(form.value);
  const version = ++selectionVersion;
  enriching.value = true;
  try {
    const enriched = await post<Partial<Book>>("/search/enrich", {
      ...form.value,
      authors: (candidate.authors || []).filter(Boolean),
    });
    if (
      formOpen.value &&
      key === operationKey.value &&
      version === selectionVersion &&
      JSON.stringify(form.value) === snapshot
    ) {
      form.value = {
        ...form.value,
        ...enriched,
        authors: (enriched.authors || candidate.authors || []).join("; "),
        provenance: enriched.provenance || form.value.provenance,
      };
    }
  } catch {
    if (
      version === selectionVersion &&
      formOpen.value &&
      key === operationKey.value
    )
      message.value =
        "Não foi possível complementar os dados. Confira o cadastro antes de salvar.";
  } finally {
    if (version === selectionVersion) enriching.value = false;
  }
}
async function save() {
  if (enriching.value) return;
  await run(async () => {
    const payload = {
      ...form.value,
      authors: form.value.authors
        .split(";")
        .map((a) => a.trim())
        .filter(Boolean),
    };
    if (!pendingRegistration.value) {
      let existing: Book | undefined;
      if (form.value.isbn) {
        const data = await api<{ items: Book[] }>(
          "/books?scope=all&q=" +
            encodeURIComponent(canonicalIsbn(form.value.isbn)),
        );
        existing = data.items.find(
          (b) => b.isbn === canonicalIsbn(form.value.isbn),
        );
      }
      if (
        existing &&
        !confirm(
          registrationTarget.value === "wishlist"
            ? "Este livro já está cadastrado. Mantê-lo nos desejados? Livros do acervo precisam ser movidos pelos detalhes."
            : existing.is_desired
              ? "Este livro está nos desejados. Adicionar um exemplar ao acervo?"
              : `Este livro já tem ${existing.copies.length} exemplar(es). Adicionar outra cópia?`,
        )
      )
        return;
      pendingRegistration.value = {
        key: operationKey.value,
        target: registrationTarget.value,
        book: payload,
        existing_book_id: existing?.id || null,
        location_id:
          registrationTarget.value === "collection" ? copyLocation.value : null,
        acquired_on:
          registrationTarget.value === "collection"
            ? acquired.value || null
            : null,
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
    message.value =
      registrationTarget.value === "wishlist"
        ? "Livro adicionado aos desejados."
        : "Exemplar cadastrado.";
    if (camera.value) {
      form.value = blank();
      scanLocked = false;
    } else formOpen.value = false;
    await load();
  });
}
async function moveCopies() {
  await run(async () => {
    await post("/copies/locate", {
      copy_ids: selectedCopies.value,
      location_id: copyLocation.value,
    });
    selectedCopies.value = [];
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
function searchNow() {
  clearTimeout(searchTimer);
  page.value = 1;
  void refresh();
}
watch(q, (value) => {
  clearTimeout(searchTimer);
  if (value === readCatalogQuery(route.query).q) return;
  ++loadVersion;
  if (!value) searchNow();
  else searchTimer = setTimeout(searchNow, 300);
});
onMounted(() =>
  run(async () => {
    if (route.query.livro) {
      await router.replace({
        path: "/livros/" + String(route.query.livro),
        query: { voltar: catalogUrl.value },
      });
      return;
    }
    [locations.value, tags.value] = await Promise.all([
      api<Location[]>("/locations"),
      api<Tag[]>("/tags"),
    ]);
    catalogReady = true;
    await load();
    await nextTick();
    requestAnimationFrame(() =>
      window.scrollTo({ top: catalogPosition(catalogUrl.value) }),
    );
    if (startNew) newBook();
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
    v-model:order="order"
    v-model:query="q"
    v-model:view="catalogView"
    v-model:columns="coverColumns"
    v-model:rows="rows"
    v-model:list-size="listSize"
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
  <section
    ref="resultsRoot"
    class="catalog-results"
    aria-label="Resultados dos livros"
  >
    <div v-if="!books.length" class="empty">
      <i class="pi pi-book" />Nenhum livro encontrado. Cadastre um livro ou
      altere os filtros.
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
      <div
        v-for="book in books"
        :key="book.id"
        :data-book-id="book.id"
        class="catalog-item"
      >
        <RouterLink
          :to="bookLink(book)"
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
        >
          <BookCard :book="book" :variant="catalogView" /></RouterLink
        ><BookCredits :item="book" compact />
      </div>
    </div>
  </section>
  <div
    v-if="
      books.some(
        (book) => book.metadata_attribution_url || book.attribution_url,
      )
    "
    class="catalog-google-credit"
  >
    <SourceAttribution
      name="Google Books"
      url="https://books.google.com/"
      compact
    />
  </div>
  <CatalogPagination
    :page="page"
    :page-size="pageSize"
    :total="total"
    :compact="gridMobile"
    :busy="busy"
    :href="pageHref"
    @select="selectPage"
  />
  <Dialog
    v-model:visible="shareOpen"
    modal
    header="Compartilhar coleção"
    :style="{ width: '500px' }"
  >
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p class="muted">
      Consulta somente leitura, sem contatos, histórico de empréstimos ou
      localizações. Livros desejados não são compartilhados.
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
    header="Cadastrar livro"
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
            ><i class="pi pi-plus" />
          </button>
          <a
            v-if="candidate.source === 'google'"
            :href="
              'https://books.google.com/books?id=' +
              encodeURIComponent(candidate.source_id || '')
            "
            target="_blank"
            rel="noopener noreferrer"
            class="muted"
            >Ver no Google Books ↗</a
          >
        </div>
      </div>
    </template>
    <p v-if="pendingRegistration" class="notice">
      Uma tentativa está aguardando confirmação. Salvar novamente repete a mesma
      operação com segurança.
    </p>
    <form class="fields" @submit.prevent="save">
      <label
        >Salvar em<select
          v-model="registrationTarget"
          aria-label="Destino do cadastro"
          :disabled="!!pendingRegistration"
        >
          <option value="collection">Acervo — já possuo</option>
          <option value="wishlist">Desejados — quero adquirir</option>
        </select></label
      >
      <figure v-if="form.cover_url" class="edit-cover">
        <img
          :src="form.cover_url"
          alt="Capa atual"
          referrerpolicy="no-referrer"
        />
        <figcaption class="muted">Capa atual</figcaption>
      </figure>
      <p v-if="enriching" role="status" class="muted">
        Complementando dados e procurando capa…
      </p>
      <BookCredits :item="form" />
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
      <template v-if="registrationTarget === 'collection'"
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
        :loading="busy || enriching"
        :disabled="enriching"
      /></form
  ></Dialog>
</template>
