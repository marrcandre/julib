<script setup lang="ts">
import { computed } from "vue";
import type { Book } from "../api";
const props = defineProps<{ book: Book }>();
const names: Record<string, string> = {
  google: "Google Books",
  openlibrary: "Open Library",
  brasilapi: "BrasilAPI",
  cbl: "CBL via BrasilAPI",
  "mercado-editorial": "Mercado Editorial via BrasilAPI",
  goodreads: "Goodreads",
  manual: "Informado por você",
};
const fields: Record<string, string> = {
  title: "Título",
  authors: "Autores",
  publisher: "Editora",
  year: "Ano da edição",
  language: "Idioma",
  page_count: "Páginas",
  edition: "Edição",
  cover_url: "Capa",
};
const sources = computed(() =>
  Object.entries(props.book.provenance || {})
    .filter(([field]) => fields[field])
    .map(([field, entry]) => ({
      field: fields[field],
      source: names[entry.source] || "Outra fonte",
      alternatives: entry.alternatives || [],
    })),
);
const alternativeLabel = (value: string) => {
  const index = value.indexOf(": ");
  return index < 0
    ? value
    : (names[value.slice(0, index)] || "Outra fonte") + value.slice(index);
};
const storage = computed(() => {
  try {
    return new URL(props.book.cover_url).hostname === "res.cloudinary.com"
      ? "Cloudinary"
      : "Referência externa";
  } catch {
    return "Sem capa";
  }
});
</script>
<template>
  <section class="book-detail-section book-source-details">
    <h2>Fontes dos dados</h2>
    <dl class="book-source-list">
      <div>
        <dt>Origem do cadastro</dt>
        <dd>
          {{
            names[book.source] ||
            (book.source ? "Outra fonte" : "Cadastro manual")
          }}
        </dd>
      </div>
      <div v-for="entry in sources" :key="entry.field">
        <dt>{{ entry.field }}</dt>
        <dd>
          {{ entry.source
          }}<small
            v-for="alternative in entry.alternatives"
            :key="alternative"
            class="source-alternative"
            >Outra fonte informa {{ alternativeLabel(alternative) }}</small
          >
        </dd>
      </div>
      <div>
        <dt>Armazenamento da capa</dt>
        <dd>{{ storage }}</dd>
      </div>
    </dl>
    <p v-if="!sources.length" class="muted">
      Este cadastro não possui origem registrada por campo.
    </p>
  </section>
</template>
<style scoped>
.book-source-list {
  display: grid;
  gap: 10px;
}
.book-source-list div {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) 2fr;
  gap: 12px;
}
.book-source-list dt {
  color: var(--muted);
}
.source-alternative {
  display: block;
  color: var(--muted);
  margin-top: 4px;
}
.book-source-list dd {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
