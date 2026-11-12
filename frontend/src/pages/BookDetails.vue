<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from "vue";
import {
  useRoute,
  useRouter,
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
} from "vue-router";
import Button from "primevue/button";
import Menu from "primevue/menu";
import Dialog from "primevue/dialog";
import Select from "primevue/select";
import InputText from "primevue/inputtext";
import { useToast } from "primevue/usetoast";
import BookSources from "../components/BookSources.vue";
import BookEditor from "../components/BookEditor.vue";
import BookEditActions from "../components/BookEditActions.vue";
import SourceAttribution from "../components/SourceAttribution.vue";
import {
  api,
  post,
  ApiError,
  locationLabel,
  type Book,
  type Copy,
  type Tag,
  type Location,
  type Loan,
} from "../api";
import { safeCatalogReturn } from "../catalog-navigation";
const route = useRoute(),
  router = useRouter(),
  toast = useToast();
const book = ref<Book | null>(null),
  locations = ref<Location[]>([]),
  tags = ref<Tag[]>([]),
  loading = ref(true),
  error = ref(""),
  busy = ref(false),
  editing = ref(false),
  dirty = ref(false),
  coverFailed = ref(false);
const menu = ref<InstanceType<typeof Menu>>();
const histories = ref<Record<number, Loan[]>>({}),
  historyOpen = ref<number | null>(null),
  historyLoading = ref<number | null>(null);
const editingCopy = ref<number | null>(null),
  copyLocation = ref<number | null>(null),
  copyDate = ref("");
const addOpen = ref(false),
  deleteOpen = ref(false),
  deleteConfirmation = ref(""),
  newLocation = ref<number | null>(null),
  newDate = ref(""),
  pendingCopy = ref<Record<string, unknown> | null>(null);
let version = 0;
const backUrl = computed(() => safeCatalogReturn(route.query.voltar));
const unsaved = computed(() => {
  const copy = book.value?.copies.find((c) => c.id === editingCopy.value);
  return (
    dirty.value ||
    !!(
      copy &&
      (copy.location_id !== copyLocation.value ||
        copy.acquired_on !== copyDate.value)
    )
  );
});
const collectionLabel = computed(() => {
  const count =
    book.value?.copies.filter((c) => c.state === "active").length || 0;
  return `No acervo · ${count} ${count === 1 ? "exemplar" : "exemplares"}`;
});
const labels: Record<string, string> = {
  sold: "Vendido",
  donated: "Doado",
  lost: "Perdido",
};
const status = (copy: Copy) =>
  copy.state === "active"
    ? copy.on_loan
      ? "Emprestado"
      : "Disponível"
    : labels[copy.state] || copy.state;
const date = (value: string | null) =>
  value ? value.split("-").reverse().join("/") : "Não informada";
function success(text: string) {
  toast.removeAllGroups();
  toast.add({ severity: "success", summary: text, life: 3500 });
}
async function load() {
  const current = ++version;
  book.value = null;
  error.value = "";
  loading.value = true;
  editing.value = false;
  dirty.value = false;
  coverFailed.value = false;
  histories.value = {};
  historyOpen.value = null;
  editingCopy.value = null;
  addOpen.value = false;
  deleteOpen.value = false;
  try {
    const [loaded, places, allTags] = await Promise.all([
      api<Book>("/books/" + encodeURIComponent(String(route.params.id))),
      api<Location[]>("/locations"),
      api<Tag[]>("/tags"),
    ]);
    if (current !== version) return;
    book.value = loaded;
    locations.value = places;
    tags.value = allTags;
  } catch (e) {
    if (current === version)
      error.value =
        e instanceof ApiError && [404, 422].includes(e.status || 0)
          ? "Livro não encontrado ou sem acesso nesta biblioteca."
          : (e as Error).message;
  } finally {
    if (current === version) loading.value = false;
  }
}
watch(
  () => route.params.id,
  () => void load(),
  { immediate: true },
);
async function run(fn: () => Promise<void>) {
  if (busy.value) return;
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
function startEdit() {
  if (!book.value) return;
  error.value = "";
  editing.value = true;
  dirty.value = false;
}
function saved(value: Book) {
  book.value = value;
  editing.value = false;
  dirty.value = false;
  busy.value = false;
  coverFailed.value = false;
  success("Dados atualizados.");
}
function cancelEdit() {
  editing.value = false;
  dirty.value = false;
  error.value = "";
}
function canLeave() {
  if (busy.value) {
    toast.add({
      severity: "info",
      summary: "Aguarde a operação em andamento.",
      life: 3500,
    });
    return false;
  }
  return (
    !unsaved.value ||
    window.confirm(
      "Sair sem salvar? As alterações nos dados e na capa serão descartadas.",
    )
  );
}
onBeforeRouteLeave(canLeave);
onBeforeRouteUpdate((to, from) =>
  to.params.id !== from.params.id ? canLeave() : true,
);
function beforeUnload(event: BeforeUnloadEvent) {
  if (unsaved.value || busy.value) {
    event.preventDefault();
    event.returnValue = "";
  }
}
window.addEventListener("beforeunload", beforeUnload);
onUnmounted(() => {
  ++version;
  window.removeEventListener("beforeunload", beforeUnload);
});
async function refreshBook() {
  const id = book.value?.id;
  if (!id) return;
  const value = await api<Book>("/books/" + id);
  if (book.value?.id === id) book.value = value;
}
async function showHistory(copy: Copy) {
  if (historyOpen.value === copy.id) {
    historyOpen.value = null;
    return;
  }
  historyOpen.value = copy.id;
  if (histories.value[copy.id]) return;
  const current = version;
  historyLoading.value = copy.id;
  error.value = "";
  try {
    const items = await api<Loan[]>("/loans?copy_id=" + copy.id);
    if (current === version) histories.value[copy.id] = items;
  } catch (e) {
    if (current === version) error.value = (e as Error).message;
  } finally {
    if (current === version) historyLoading.value = null;
  }
}
function editCopy(copy: Copy) {
  editingCopy.value = copy.id;
  copyLocation.value = copy.location_id;
  copyDate.value = copy.acquired_on;
}
async function saveCopy(copy: Copy) {
  await run(async () => {
    await api("/copies/" + copy.id, {
      method: "PUT",
      body: JSON.stringify({
        location_id: copyLocation.value,
        acquired_on: copyDate.value,
      }),
    });
    await refreshBook();
    editingCopy.value = null;
    success("Exemplar atualizado.");
  });
}
async function retire(copy: Copy, reason: string) {
  if (!reason) return;
  if (
    !window.confirm(
      reason === "active"
        ? "Reativar exemplar?"
        : "Confirmar baixa do exemplar? O histórico será preservado.",
    )
  )
    return;
  await run(async () => {
    await post("/copies/" + copy.id + "/retire", { reason });
    await refreshBook();
    delete histories.value[copy.id];
    success("Situação do exemplar atualizada.");
  });
}
function startCopy() {
  pendingCopy.value = null;
  newLocation.value = null;
  newDate.value = "";
  error.value = "";
  addOpen.value = true;
}
async function addCopy() {
  if (!book.value) return;
  await run(async () => {
    if (!pendingCopy.value)
      pendingCopy.value = {
        key: crypto.randomUUID(),
        target: "collection",
        book: { ...book.value!, tag_ids: book.value!.tags.map((t) => t.id) },
        existing_book_id: book.value!.id,
        location_id: newLocation.value,
        acquired_on: newDate.value || null,
      };
    try {
      await post("/registrations", pendingCopy.value);
    } catch (e) {
      if (e instanceof ApiError && e.status && e.status < 500)
        pendingCopy.value = null;
      throw e;
    }
    pendingCopy.value = null;
    addOpen.value = false;
    await refreshBook();
    success("Exemplar adicionado ao acervo.");
  });
}
async function moveToWishlist() {
  if (
    !book.value ||
    !window.confirm(
      `Mover “${book.value.title}” para desejados? Os ${book.value.copies.filter((c) => c.state === "active").length} exemplares ativos sem histórico serão removidos do acervo. Exemplares baixados e seus históricos serão preservados.`,
    )
  )
    return;
  await run(async () => {
    await post("/books/" + book.value!.id + "/wishlist", {});
    await refreshBook();
    success("Livro movido para desejados.");
  });
}
async function removeBook() {
  if (!book.value || deleteConfirmation.value !== "EXCLUIR") return;
  await run(async () => {
    await api("/books/" + book.value!.id, { method: "DELETE" });
    deleteOpen.value = false;
    dirty.value = false;
    editingCopy.value = null;
    success("Livro excluído definitivamente.");
  });
  if (!deleteOpen.value) {
    busy.value = false;
    await router.push(backUrl.value);
  }
}
const actions = computed(() => [
  ...(book.value?.is_desired
    ? []
    : [
        {
          label: "Mover para desejados",
          icon: "pi pi-heart",
          command: () => void moveToWishlist(),
        },
      ]),
  {
    label: book.value?.can_delete
      ? "Excluir definitivamente"
      : "Exclusão bloqueada: há histórico de empréstimos",
    icon: "pi pi-trash",
    disabled: !book.value?.can_delete,
    command: () => {
      deleteConfirmation.value = "";
      error.value = "";
      deleteOpen.value = true;
    },
  },
]);
const facts = computed(() =>
  book.value
    ? [
        ["ISBN", book.value.isbn],
        ["Editora", book.value.publisher],
        ["Edição", book.value.edition],
        ["Ano de publicação", book.value.year],
        ["Idioma", book.value.language],
        ["Páginas", book.value.page_count ? String(book.value.page_count) : ""],
      ]
    : [],
);
</script>
<template>
  <div class="book-detail-page">
    <div class="book-detail-topline">
      <RouterLink :to="backUrl" class="book-back"
        ><i class="pi pi-arrow-left" aria-hidden="true" />Voltar ao
        catálogo</RouterLink
      >
      <div v-if="book && !loading" class="actions">
        <BookEditActions
          v-if="editing"
          :busy="busy"
          form-id="book-edit-form"
          @cancel="cancelEdit"
        />
        <template v-else
          ><Button
            label="Editar livro"
            icon="pi pi-pencil"
            class="primary"
            :disabled="busy"
            @click="startEdit" /><Button
            icon="pi pi-ellipsis-v"
            text
            aria-label="Mais ações do livro"
            aria-haspopup="menu"
            :disabled="busy"
            @click="menu?.toggle($event)" /><Menu
            ref="menu"
            :model="actions"
            popup
        /></template>
      </div>
    </div>
    <p v-if="loading" role="status" class="muted">Carregando livro…</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <BookEditor
      v-if="book && editing"
      :key="book.id"
      :book="book"
      :tags="tags"
      @tag-created="tags.push($event)"
      @saved="saved"
      @cancel="cancelEdit"
      @dirty="dirty = $event"
      @busy="busy = $event"
    />
    <template v-else-if="book">
      <div class="book-detail-summary book-read-summary">
        <figure class="book-detail-figure">
          <button
            type="button"
            class="book-cover-edit-trigger"
            title="Editar livro"
            :aria-label="
              book.cover_url && !coverFailed
                ? 'Editar livro pela capa'
                : 'Editar livro sem capa'
            "
            @click="startEdit"
          >
            <img
              v-if="book.cover_url && !coverFailed"
              class="book-detail-cover"
              :src="book.cover_url"
              alt="Capa do livro"
              referrerpolicy="no-referrer"
              @error="coverFailed = true"
            />
            <div v-else class="book-detail-cover book-detail-placeholder">
              <i class="pi pi-book" aria-hidden="true" /><span>Sem capa</span>
            </div>
            <span class="book-cover-pencil" aria-hidden="true">
              <i class="pi pi-pencil" />
            </span>
          </button>
          <figcaption
            v-if="book.attribution_url !== book.metadata_attribution_url"
          >
            <SourceAttribution
              :name="book.attribution_name"
              :url="book.attribution_url"
            />
          </figcaption>
        </figure>
        <div class="book-detail-overview">
          <h1>{{ book.title }}</h1>
          <p class="book-detail-authors">{{ book.authors.join(", ") }}</p>
          <span class="tag-pill"
            ><i
              :class="book.is_desired ? 'pi pi-heart' : 'pi pi-book'"
              aria-hidden="true"
            />{{ book.is_desired ? "Desejado" : collectionLabel }}</span
          >
          <div v-if="book.tags.length" class="tag-list">
            <span v-for="tag in book.tags" :key="tag.id" class="tag-pill">{{
              tag.name
            }}</span>
          </div>
        </div>
        <section class="book-detail-facts">
          <h2>Ficha do livro</h2>
          <dl>
            <div v-for="[label, value] in facts" :key="label">
              <dt>{{ label }}</dt>
              <dd>{{ value || "Não informado" }}</dd>
            </div>
          </dl>
          <SourceAttribution
            :name="book.metadata_attribution_name"
            :url="book.metadata_attribution_url"
            kind="metadata"
          />
        </section>
      </div>
      <BookSources :book="book" />
      <section v-if="book.is_desired" class="book-detail-section">
        <div class="book-wish-notice">
          <div>
            <h2>Nos seus desejados</h2>
            <p class="muted">
              Este livro está nos seus desejados. Ele não conta como exemplar do
              acervo.
            </p>
          </div>
          <Button
            label="Adicionar ao acervo"
            icon="pi pi-plus"
            class="primary"
            :disabled="busy"
            @click="startCopy"
          />
        </div>
      </section>
      <section
        v-if="!book.is_desired || book.copies.length"
        class="book-detail-section"
      >
        <div class="book-detail-section-heading">
          <h2>
            {{ book.is_desired ? "Exemplares anteriores" : "Exemplares" }}
            <span class="catalog-count">{{ book.copies.length }}</span>
          </h2>
          <Button
            v-if="!book.is_desired"
            label="Adicionar exemplar"
            icon="pi pi-plus"
            text
            :disabled="busy"
            @click="startCopy"
          />
        </div>
        <p v-if="!book.copies.length" class="muted">
          Nenhum exemplar cadastrado para esta edição.
        </p>
        <div class="book-copy-grid">
          <article
            v-for="copy in book.copies"
            :key="copy.id"
            class="book-copy-card"
          >
            <div class="book-copy-heading">
              <h3>Exemplar #{{ copy.number }}</h3>
              <span
                class="tag-pill"
                :class="{ 'book-copy-loaned': copy.on_loan }"
                ><i
                  v-if="copy.on_loan"
                  class="pi pi-arrow-up-right"
                  aria-hidden="true"
                />{{ status(copy) }}</span
              >
            </div>
            <dl class="book-copy-info">
              <div>
                <dt>
                  <i class="pi pi-map-marker" aria-hidden="true" />Localização
                </dt>
                <dd>{{ locationLabel(locations, copy.location_id) }}</dd>
              </div>
              <div>
                <dt>
                  <i class="pi pi-calendar" aria-hidden="true" />Data de
                  aquisição
                </dt>
                <dd>{{ date(copy.acquired_on) }}</dd>
              </div>
            </dl>
            <div class="book-copy-actions">
              <Button
                label="Editar exemplar"
                icon="pi pi-pencil"
                text
                size="small"
                :disabled="busy"
                @click="editCopy(copy)"
              /><Button
                label="Histórico"
                icon="pi pi-history"
                text
                size="small"
                :aria-expanded="historyOpen === copy.id"
                :disabled="busy"
                @click="showHistory(copy)"
              />
            </div>
            <form
              v-if="editingCopy === copy.id"
              class="book-copy-editor fields"
              @submit.prevent="saveCopy(copy)"
            >
              <label
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
                  show-clear
                  :disabled="busy" /></label
              ><label
                >Data de aquisição<InputText
                  type="date"
                  v-model="copyDate"
                  required
                  :disabled="busy"
              /></label>
              <div class="actions">
                <Button
                  label="Cancelar"
                  type="button"
                  text
                  :disabled="busy"
                  @click="editingCopy = null"
                /><Button
                  label="Salvar exemplar"
                  type="submit"
                  :disabled="busy"
                  :loading="busy"
                />
              </div>
              <label v-if="copy.state === 'active'"
                >Dar baixa<select
                  aria-label="Dar baixa"
                  :disabled="busy"
                  @change="
                    retire(copy, ($event.target as HTMLSelectElement).value);
                    ($event.target as HTMLSelectElement).value = '';
                  "
                >
                  <option value="">Selecione o motivo…</option>
                  <option value="sold">Venda</option>
                  <option value="donated">Doação</option>
                  <option value="lost">Perda</option>
                </select></label
              ><Button
                v-else-if="!book.is_desired"
                label="Reativar exemplar"
                text
                :disabled="busy"
                @click="retire(copy, 'active')"
              />
            </form>
            <div v-if="historyOpen === copy.id" class="book-copy-history">
              <h4>Histórico do exemplar #{{ copy.number }}</h4>
              <p v-if="historyLoading === copy.id" role="status">
                Carregando histórico…
              </p>
              <p v-else-if="histories[copy.id]?.length === 0" class="muted">
                Nenhum empréstimo registrado para este exemplar.
              </p>
              <div
                v-for="loan in histories[copy.id] || []"
                :key="loan.id"
                class="book-loan-record"
              >
                <strong>{{ loan.person_name }}</strong>
                <dl>
                  <div>
                    <dt>Empréstimo</dt>
                    <dd>{{ date(loan.started_on) }}</dd>
                  </div>
                  <div>
                    <dt>Devolução prevista</dt>
                    <dd>{{ date(loan.due_on) }}</dd>
                  </div>
                  <div>
                    <dt>Devolução efetiva</dt>
                    <dd>
                      {{
                        loan.returned_on
                          ? date(loan.returned_on)
                          : loan.state === "lost"
                            ? "Encerrado por perda"
                            : "Ainda não devolvido"
                      }}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          </article>
        </div>
      </section>
    </template>
    <Dialog
      v-model:visible="addOpen"
      modal
      :header="book?.is_desired ? 'Adicionar ao acervo' : 'Adicionar exemplar'"
      :style="{ width: '480px' }"
      :closable="!busy"
      ><p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="pendingCopy" class="notice">
        Há uma tentativa aguardando confirmação. Repita para confirmar a mesma
        aquisição com segurança.
      </p>
      <form class="fields" @submit.prevent="addCopy">
        <label
          >Localização<Select
            v-model="newLocation"
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
            :disabled="busy || !!pendingCopy" /></label
        ><label
          >Data de aquisição<InputText
            type="date"
            v-model="newDate"
            :disabled="busy || !!pendingCopy"
          /><small class="muted"
            >Em branco, usamos a data do cadastro.</small
          ></label
        ><Button
          label="Confirmar aquisição"
          type="submit"
          class="primary"
          :disabled="busy"
          :loading="busy"
        /></form
    ></Dialog>
    <Dialog
      v-model:visible="deleteOpen"
      modal
      header="Excluir livro definitivamente"
      :style="{ width: '480px' }"
      :closable="!busy"
      ><p v-if="error" class="error" role="alert">{{ error }}</p>
      <p>
        Excluir “{{ book?.title }}” e seus
        {{ book?.copies.length || 0 }} exemplares? Esta ação não pode ser
        desfeita.
      </p>
      <p class="muted">
        Livros com qualquer histórico de empréstimo não podem ser excluídos.
      </p>
      <form class="fields" @submit.prevent="removeBook">
        <label
          >Digite EXCLUIR para confirmar<InputText
            v-model="deleteConfirmation"
            autocomplete="off"
            :disabled="busy" /></label
        ><Button
          label="Confirmar exclusão definitiva"
          type="submit"
          severity="danger"
          :disabled="busy || deleteConfirmation !== 'EXCLUIR'"
          :loading="busy"
        /></form
    ></Dialog>
  </div>
</template>
