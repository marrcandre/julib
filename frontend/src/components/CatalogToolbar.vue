<script setup lang="ts">
import { computed, ref, nextTick, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import Button from "primevue/button";
import Dialog from "primevue/dialog";
import Menu from "primevue/menu";
import Select from "primevue/select";
import {
  situationOptions,
  defaultSituations,
  orderOptions,
  type Situation,
  type CatalogOrder,
} from "../catalog-options";
import InputText from "primevue/inputtext";
import { locationLabel, type Tag, type Location } from "../api";

export type CatalogView = "covers" | "cards" | "list";
export type CatalogFilters = {
  tag: number | null;
  location: number | null;
  statuses: Situation[];
  missingLocation: boolean;
};
const props = defineProps<{
  order: CatalogOrder;
  query: string;
  total: number;
  tags: Tag[];
  locations: Location[];
  filters: CatalogFilters;
  view: CatalogView;
  columns: number;
  densitySaved: boolean;
}>();
const emit = defineEmits<{
  "update:order": [value: CatalogOrder];
  "update:query": [value: string];
  "update:view": [value: CatalogView];
  "update:columns": [value: number];
  filters: [value: CatalogFilters];
  add: [method: "camera" | "search" | "manual"];
  bulk: [];
  share: [];
}>();
const router = useRouter();
const viewport = window.matchMedia("(max-width: 800px)");
const mobile = ref(viewport.matches);
const syncViewport = () => {
  mobile.value = viewport.matches;
};
onMounted(() => viewport.addEventListener("change", syncViewport));
onUnmounted(() => viewport.removeEventListener("change", syncViewport));
const addMenu = ref<InstanceType<typeof Menu>>(),
  moreMenu = ref<InstanceType<typeof Menu>>();
const filterOpen = ref(false),
  viewOpen = ref(false),
  orderOpen = ref(false),
  searchContainer = ref<HTMLDivElement>();
const emptyFilters = (): CatalogFilters => ({
  tag: null,
  location: null,
  statuses: [...defaultSituations],
  missingLocation: false,
});
const draft = ref(emptyFilters());
const addItems = [
  {
    label: "Escanear ISBN",
    icon: "pi pi-camera",
    command: () => emit("add", "camera"),
  },
  {
    label: "Buscar livro",
    icon: "pi pi-search",
    command: () => emit("add", "search"),
  },
  {
    label: "Cadastro manual",
    icon: "pi pi-pencil",
    command: () => emit("add", "manual"),
  },
];
const moreItems = [
  {
    label: "Importar do Goodreads",
    icon: "pi pi-upload",
    command: () => router.push("/importar"),
  },
  {
    label: "Organizar exemplares",
    icon: "pi pi-map-marker",
    command: () => emit("bulk"),
  },
  { separator: true },
  {
    label: "Compartilhar coleção",
    icon: "pi pi-share-alt",
    command: () => emit("share"),
  },
];
const chips = computed(() =>
  [
    {
      key: "tag" as const,
      label: props.tags.find((t) => t.id === props.filters.tag)?.name || "",
      active: props.filters.tag !== null,
    },
    {
      key: "location" as const,
      label: props.filters.location
        ? locationLabel(props.locations, props.filters.location)
        : "",
      active: props.filters.location !== null,
    },
    {
      key: "statuses" as const,
      label: props.filters.statuses.length
        ? situationOptions
            .filter((o) => props.filters.statuses.includes(o.value))
            .map((o) => o.label)
            .join(" / ")
        : "Todas as situações",
      active:
        JSON.stringify(props.filters.statuses) !==
        JSON.stringify(defaultSituations),
    },
    {
      key: "missingLocation" as const,
      label: "Sem localização",
      active: props.filters.missingLocation,
    },
  ].filter((item) => item.active),
);
function openFilters() {
  draft.value = { ...props.filters };
  filterOpen.value = true;
}
function applyFilters() {
  emit("filters", { ...draft.value });
  filterOpen.value = false;
}
function removeFilter(key: keyof CatalogFilters) {
  emit("filters", {
    ...props.filters,
    [key]:
      key === "missingLocation"
        ? false
        : key === "statuses"
          ? [...defaultSituations]
          : null,
  });
}
function clearSearch() {
  emit("update:query", "");
  void nextTick(() => searchContainer.value?.querySelector("input")?.focus());
}
function columnsChanged(event: Event) {
  emit("update:columns", Number((event.target as HTMLInputElement).value));
}
</script>
<template>
  <div class="catalog-heading">
    <h1 class="catalog-scope-heading">Livros</h1>
    <span
      class="catalog-count"
      role="status"
      :aria-label="`${total} edições encontradas`"
      :title="`${total} edições encontradas`"
      >{{ total.toLocaleString("pt-BR") }}</span
    >
    <div class="catalog-heading-actions">
      <Button
        aria-label="Adicionar livro"
        title="Adicionar livro"
        icon="pi pi-plus"
        class="primary catalog-add"
        aria-haspopup="menu"
        aria-controls="catalog-add-menu"
        @click="addMenu?.toggle($event)"
      />
      <Button
        aria-label="Mais opções da biblioteca"
        title="Mais opções"
        icon="pi pi-ellipsis-v"
        text
        aria-haspopup="menu"
        aria-controls="catalog-more-menu"
        @click="moreMenu?.toggle($event)"
      />
    </div>
    <Menu ref="addMenu" id="catalog-add-menu" :model="addItems" popup />
    <Menu ref="moreMenu" id="catalog-more-menu" :model="moreItems" popup />
  </div>
  <div class="catalog-search-toolbar">
    <div ref="searchContainer" class="catalog-search">
      <i class="pi pi-search catalog-search-icon" aria-hidden="true" />
      <InputText
        :model-value="query"
        @update:model-value="emit('update:query', $event || '')"
        placeholder="Título, autor ou ISBN"
        aria-label="Buscar livros"
      />
      <button
        v-if="query"
        type="button"
        class="search-clear"
        aria-label="Limpar busca"
        title="Limpar busca"
        @click="clearSearch"
      >
        <i class="pi pi-times" aria-hidden="true" />
      </button>
    </div>
    <Button
      :aria-label="
        chips.length ? `Filtros: ${chips.length} aplicados` : 'Filtros'
      "
      title="Filtros"
      outlined
      class="catalog-tool"
      :class="{ 'has-filters': chips.length }"
      @click="openFilters"
      ><i class="pi pi-filter" aria-hidden="true" /><span
        class="catalog-tool-label"
        >Filtros</span
      ><span v-if="chips.length" class="catalog-filter-count">{{
        chips.length
      }}</span></Button
    >
    <Button
      aria-label="Ordenar livros"
      :title="orderOptions.find((o) => o.value === order)?.label"
      outlined
      class="catalog-tool"
      @click="orderOpen = true"
      ><i class="pi pi-sort-alt" aria-hidden="true" /><span
        class="catalog-tool-label"
        >Ordenar</span
      ></Button
    >
    <Button
      aria-label="Visualização dos livros"
      title="Visualização"
      outlined
      class="catalog-tool"
      @click="viewOpen = true"
      ><i
        :class="
          view === 'covers'
            ? 'pi pi-book'
            : view === 'cards'
              ? 'pi pi-th-large'
              : 'pi pi-list'
        "
        aria-hidden="true"
      /><span class="catalog-tool-label">Visualização</span></Button
    >
  </div>
  <div v-if="chips.length" class="catalog-filter-chips">
    <span v-for="chip in chips" :key="chip.key" class="catalog-chip"
      >{{ chip.label
      }}<button
        :aria-label="'Remover filtro ' + chip.label"
        @click="removeFilter(chip.key)"
      >
        <i class="pi pi-times" aria-hidden="true" /></button
    ></span>
    <Button
      label="Limpar filtros"
      text
      size="small"
      @click="emit('filters', emptyFilters())"
    />
  </div>
  <Dialog
    v-model:visible="filterOpen"
    modal
    header="Filtros"
    :position="mobile ? 'bottom' : 'right'"
    class="catalog-filter-dialog"
    :pt="{ mask: { class: 'catalog-filter-mask' } }"
  >
    <form class="fields" @submit.prevent="applyFilters">
      <label
        >Tags<Select
          v-model="draft.tag"
          :options="tags"
          option-label="name"
          option-value="id"
          placeholder="Todas as tags"
          show-clear
          aria-label="Filtrar por tag"
      /></label>
      <label
        >Localização<Select
          v-model="draft.location"
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
      /></label>
      <fieldset class="catalog-situations">
        <legend>Situação</legend>
        <label
          v-for="option in situationOptions"
          :key="option.value"
          class="catalog-checkbox"
        >
          <input
            type="checkbox"
            v-model="draft.statuses"
            :value="option.value"
          />{{ option.label }}
        </label>
        <small class="muted">Sem seleção, mostrar todas as situações.</small>
      </fieldset>
      <label class="catalog-checkbox"
        ><input type="checkbox" v-model="draft.missingLocation" />Sem
        localização</label
      >
      <div class="catalog-dialog-actions">
        <Button
          label="Limpar filtros"
          text
          @click="draft = emptyFilters()"
        /><Button type="submit" label="Aplicar filtros" class="primary" />
      </div>
    </form>
  </Dialog>
  <Dialog
    v-model:visible="orderOpen"
    modal
    header="Ordenação"
    :position="mobile ? 'bottom' : 'topright'"
    class="catalog-view-dialog"
  >
    <label class="fields"
      >Ordenar livros<Select
        :model-value="order"
        :options="[...orderOptions]"
        option-label="label"
        option-value="value"
        aria-label="Ordenação dos livros"
        @update:model-value="
          emit('update:order', $event);
          orderOpen = false;
        "
    /></label>
    <p class="muted">
      Aquisição considera o exemplar adquirido mais recentemente. Livros sem
      essa informação ficam no final.
    </p>
  </Dialog>
  <Dialog
    v-model:visible="viewOpen"
    modal
    header="Visualização"
    :position="mobile ? 'bottom' : 'topright'"
    class="catalog-view-dialog"
    :pt="{ mask: { class: 'catalog-view-mask' } }"
  >
    <div
      class="catalog-view-options"
      role="group"
      aria-label="Modo de visualização"
    >
      <Button
        v-for="option in [
          {
            value: 'covers' as const,
            label: 'Somente capas',
            icon: 'pi pi-book',
          },
          { value: 'cards' as const, label: 'Cartões', icon: 'pi pi-th-large' },
          { value: 'list' as const, label: 'Lista', icon: 'pi pi-list' },
        ]"
        :key="option.value"
        :label="option.label"
        :icon="option.icon"
        :aria-pressed="view === option.value"
        :outlined="view !== option.value"
        @click="emit('update:view', option.value)"
      />
    </div>
    <div v-if="view === 'covers'" class="catalog-density">
      <div class="catalog-density-heading">
        <label for="cover-density">Livros por linha</label
        ><output for="cover-density">{{ columns }}</output>
      </div>
      <input
        id="cover-density"
        type="range"
        :value="columns"
        min="3"
        max="10"
        step="1"
        @input="columnsChanged"
      />
      <div class="catalog-density-limits" aria-hidden="true">
        <span>3</span><span>10</span>
      </div>
      <p class="muted">
        {{
          densitySaved
            ? "Ajuste independente por conta neste navegador/dispositivo."
            : "O navegador não permitiu salvar; a escolha vale nesta visita."
        }}
      </p>
    </div>
  </Dialog>
</template>
