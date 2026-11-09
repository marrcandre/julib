<script setup lang="ts">
import SourceAttribution from "./SourceAttribution.vue";
defineProps<{
  compact?: boolean;
  item: {
    attribution_name?: string;
    attribution_url?: string;
    metadata_attribution_name?: string;
    metadata_attribution_url?: string;
  };
}>();
const links = (item: {
  metadata_attribution_url?: string;
  attribution_url?: string;
}) => [
  ...new Set(
    [item.metadata_attribution_url, item.attribution_url].filter(
      (url): url is string =>
        !!url && url.startsWith("https://books.google.com/books?id="),
    ),
  ),
];
</script>
<template>
  <div v-if="compact" class="book-credit-compact">
    <a
      v-for="url in links(item)"
      :key="url"
      :href="url"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Ver fonte no Google Books"
      title="Ver fonte no Google Books"
      @click.stop
      >↗</a
    >
  </div>
  <template v-else>
    <SourceAttribution
      v-if="item.metadata_attribution_name"
      :name="item.metadata_attribution_name"
      :url="item.metadata_attribution_url"
      kind="metadata"
    />
    <SourceAttribution
      v-if="item.attribution_url !== item.metadata_attribution_url"
      :name="item.attribution_name"
      :url="item.attribution_url"
      kind="cover"
    />
  </template>
</template>

<style scoped>
.book-credit-compact {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
  font-size: 11px;
}
.book-credit-compact a {
  color: var(--green);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  min-height: 24px;
  border-radius: 5px;
  background: var(--soft);
  font-size: 14px;
}
.book-credit-compact a:hover {
  text-decoration: underline;
}
</style>
