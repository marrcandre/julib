<script setup lang="ts">
import { computed } from "vue";
import { pageTokens } from "../pagination";
const props = defineProps<{
  page: number;
  pageSize: number;
  total: number;
  compact: boolean;
  busy: boolean;
  href: (page: number) => string;
}>();
const emit = defineEmits<{ select: [page: number] }>();
const pages = computed(() =>
  Math.max(1, Math.ceil(props.total / props.pageSize)),
);
const tokens = computed(() =>
  pageTokens(props.page, pages.value, props.compact),
);
function navigate(event: MouseEvent, page: number) {
  if (
    event.button !== 0 ||
    event.ctrlKey ||
    event.metaKey ||
    event.shiftKey ||
    event.altKey
  )
    return;
  event.preventDefault();
  if (!props.busy && page !== props.page) emit("select", page);
}
</script>
<template>
  <div class="catalog-pagination" aria-live="polite">
    <nav
      v-if="pages > 1"
      aria-label="Paginação dos livros"
      class="catalog-page-links"
    >
      <a
        v-if="page > 1"
        :href="href(page - 1)"
        aria-label="Página anterior"
        :aria-disabled="busy"
        @click="navigate($event, page - 1)"
        ><span aria-hidden="true">‹</span
        ><span class="catalog-page-direction"> Anterior</span></a
      >
      <span
        v-else
        class="catalog-page-disabled"
        aria-label="Página anterior"
        aria-disabled="true"
        ><span aria-hidden="true">‹</span
        ><span class="catalog-page-direction"> Anterior</span></span
      >
      <template v-for="token in tokens" :key="token">
        <span
          v-if="typeof token !== 'number'"
          class="catalog-page-ellipsis"
          aria-hidden="true"
          >…</span
        >
        <span
          v-else-if="token === page"
          class="catalog-page-current"
          aria-current="page"
          :aria-label="`Página ${token}, atual`"
          >{{ token }}</span
        >
        <a
          v-else
          :href="href(token)"
          :aria-label="`Ir para página ${token}`"
          :aria-disabled="busy"
          @click="navigate($event, token)"
          >{{ token }}</a
        >
      </template>
      <a
        v-if="page < pages"
        :href="href(page + 1)"
        aria-label="Próxima página"
        :aria-disabled="busy"
        @click="navigate($event, page + 1)"
        ><span class="catalog-page-direction">Próxima </span
        ><span aria-hidden="true">›</span></a
      >
      <span
        v-else
        class="catalog-page-disabled"
        aria-label="Próxima página"
        aria-disabled="true"
        ><span class="catalog-page-direction">Próxima </span
        ><span aria-hidden="true">›</span></span
      >
    </nav>
    <p class="muted catalog-page-range">
      {{
        total
          ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} de ${total} ${total === 1 ? "livro" : "livros"}`
          : "Nenhum livro encontrado"
      }}
    </p>
  </div>
</template>
