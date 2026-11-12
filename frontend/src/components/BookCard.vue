<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { catalogCoverUrl } from "../catalog-images";
import type { Book, Copy } from "../api";
const props = withDefaults(
  defineProps<{
    book: Omit<
      Book,
      | "provenance"
      | "copies"
      | "source"
      | "source_id"
      | "is_desired"
      | "can_delete"
      | "metadata_attribution_name"
      | "metadata_attribution_url"
    > & { copies?: Copy[]; is_desired?: boolean };
    variant?: "cards" | "covers" | "list";
    imagePriority?: "high" | "eager" | "lazy";
  }>(),
  { variant: "cards", imagePriority: "lazy" },
);
const failed = ref(false);
const loaded = ref(false);
const coverImage = ref<HTMLImageElement | null>(null);
const displayCover = computed(() => catalogCoverUrl(props.book.cover_url));
watch(
  () => props.book.cover_url,
  () => {
    failed.value = false;
    loaded.value = false;
  },
);
function markLoaded(event: Event) {
  if (event.currentTarget !== coverImage.value) return;
  loaded.value = true;
}
function markFailed(event: Event) {
  if (event.currentTarget !== coverImage.value) return;
  failed.value = true;
}
const availability = computed(() =>
  props.book.is_desired
    ? "Desejado"
    : props.book.available
      ? "Disponível"
      : props.book.copies?.some((c) => c.on_loan)
        ? "Emprestado"
        : "Indisponível",
);
const statusIcon = computed(() =>
  props.book.is_desired
    ? "pi-heart"
    : props.book.available
      ? "pi-check-circle"
      : availability.value === "Emprestado"
        ? "pi-arrow-up-right"
        : "pi-minus-circle",
);
</script>
<template>
  <article class="book-card" :class="'book-card--' + variant">
    <div
      class="cover"
      :class="{ 'cover--loading': book.cover_url && !loaded && !failed }"
    >
      <div
        v-if="book.cover_url && !loaded && !failed"
        class="cover-placeholder cover-placeholder--loading"
        aria-hidden="true"
      >
        <i class="pi pi-book" />
      </div>
      <img
        v-if="book.cover_url && !failed"
        :key="displayCover"
        ref="coverImage"
        :src="displayCover"
        :alt="'Capa de ' + book.title"
        :loading="imagePriority === 'lazy' ? 'lazy' : 'eager'"
        :fetchpriority="imagePriority === 'high' ? 'high' : 'auto'"
        decoding="async"
        :class="{ 'cover-image--loaded': loaded }"
        referrerpolicy="no-referrer"
        @load="markLoaded"
        @error="markFailed"
      />
      <div v-else class="cover-placeholder">
        <i class="pi pi-book" aria-hidden="true" /><span
          v-if="variant === 'covers'"
          >{{ book.title }}</span
        >
      </div>
      <i
        v-if="variant === 'covers' && !book.available"
        class="pi availability cover-status"
        :class="statusIcon"
        role="img"
        :aria-label="availability"
        :title="availability"
      />
    </div>
    <div class="book-info">
      <h3 class="book-title">
        <span>{{ book.title }}</span
        ><i
          v-if="!book.available"
          class="pi availability"
          :class="statusIcon"
          role="img"
          :aria-label="availability"
          :title="availability"
        />
      </h3>
      <p class="muted book-authors">{{ book.authors.join(", ") }}</p>
      <p v-if="variant === 'list'" class="muted book-meta">
        {{ [book.publisher, book.year, book.isbn].filter(Boolean).join(" · ") }}
      </p>
      <p v-if="variant === 'list' && book.page_count" class="muted book-meta">
        {{ book.page_count }} páginas
      </p>
      <div v-if="book.tags.length" class="tag-list">
        <span v-for="tag in book.tags" :key="tag.id" class="tag-pill">{{
          tag.name
        }}</span>
      </div>
    </div>
  </article>
</template>
<style scoped>
.book-title {
  display: flex;
  align-items: baseline;
  gap: 7px;
  justify-content: flex-start;
}
.book-title span {
  min-width: 0;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}
.availability {
  font-size: 14px;
  color: var(--green);
  flex-shrink: 0;
}
.pi-arrow-up-right,
.pi-minus-circle {
  color: #aa741f;
}
.dark .pi-arrow-up-right,
.dark .pi-minus-circle {
  color: #ffbd59;
}
.book-info {
  min-width: 0;
}
.book-authors {
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.book-meta {
  overflow-wrap: anywhere;
  margin-top: 8px !important;
  line-height: 1.6;
}
.book-card--covers {
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}
.book-card--covers .book-info {
  display: none;
}
.book-card--covers .cover {
  max-height: none;
}
.cover {
  position: relative;
}
.cover img {
  opacity: 0;
  transition: opacity 180ms ease;
}
.cover img.cover-image--loaded {
  opacity: 1;
}
.cover-placeholder--loading {
  position: absolute;
  inset: 0;
  color: var(--muted);
}
.cover--loading img {
  position: relative;
}
@media (prefers-reduced-motion: reduce) {
  .cover img {
    transition: none;
  }
}
.cover-status {
  position: absolute;
  right: 6px;
  top: 6px;
  background: var(--surface);
  padding: 5px;
  border-radius: 50%;
  box-shadow: var(--shadow);
}
.book-card--list {
  display: grid;
  grid-template-columns: 60px minmax(0, 1fr);
  gap: 18px;
  align-items: center;
  padding: 16px;
}
.book-card--list .cover {
  height: 90px;
  width: 60px;
  aspect-ratio: auto;
}
.book-card--list h3 {
  margin-top: 0;
}
.book-card--list .book-title span {
  -webkit-line-clamp: unset;
}
@media (max-width: 800px) {
  .book-card:not(.book-card--list) h3 {
    font-size: 12px;
    gap: 4px;
  }
  .book-card:not(.book-card--list) p {
    font-size: 10px;
  }
  .availability {
    font-size: 12px;
  }
  .book-card--list {
    grid-template-columns: 48px minmax(0, 1fr);
    gap: 12px;
    padding: 12px;
  }
  .book-card--list .cover {
    width: 48px;
    height: 72px;
  }
  .book-card--list h3 {
    font-size: 14px;
  }
}
.cover-placeholder {
  display: grid;
  justify-items: center;
  gap: 12px;
  padding: 10px;
  text-align: center;
  max-width: 100%;
}
.cover-placeholder span {
  font-size: 12px;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
