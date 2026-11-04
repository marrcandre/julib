<script setup lang="ts">
import type { Book } from "../api";
defineProps<{ book: Omit<Book, "copies" | "source" | "source_id"> }>();
</script>
<template>
  <article class="book-card">
    <div class="cover">
      <img
        v-if="book.cover_url"
        :src="book.cover_url"
        :alt="'Capa de ' + book.title"
        loading="lazy"
        referrerpolicy="no-referrer"
        @error="($event.target as HTMLImageElement).style.display = 'none'"
      /><i v-else class="pi pi-book" aria-hidden="true" />
    </div>
    <h3>{{ book.title }}</h3>
    <p class="muted">{{ book.authors.join(", ") }}</p>
    <div class="tag-list">
      <span v-for="tag in book.tags" :key="tag.id" class="tag-pill">{{
        tag.name
      }}</span>
    </div>
    <span class="status"
      ><i
        class="pi"
        :class="book.available ? 'pi-check-circle' : 'pi-clock'"
      />{{ book.available ? "Disponível" : "Indisponível" }}</span
    >
  </article>
</template>
