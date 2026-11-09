<script setup lang="ts">
withDefaults(
  defineProps<{
    name?: string;
    url?: string;
    kind?: "cover" | "metadata";
    compact?: boolean;
  }>(),
  { kind: "cover" },
);
</script>
<template>
  <p v-if="name === 'Google Books' && url" class="source-attribution">
    <span v-if="!compact">{{
      kind === "metadata" ? "Dados bibliográficos:" : "Capa:"
    }}</span>
    <a
      :href="url"
      :aria-label="
        (kind === 'metadata' ? 'Fonte dos dados: ' : 'Fonte da capa: ') + name
      "
      :title="
        (kind === 'metadata' ? 'Fonte dos dados: ' : 'Fonte da capa: ') + name
      "
      target="_blank"
      rel="noopener noreferrer"
      @click.stop
      ><img
        v-if="name === 'Google Books'"
        src="https://books.google.com/googlebooks/images/poweredby.png"
        alt="Powered by Google"
        referrerpolicy="no-referrer"
      /><span v-if="name !== 'Google Books'">{{ name }} ↗</span></a
    >
  </p>
</template>
<style scoped>
.source-attribution {
  font-size: 11px;
  margin: 10px 0;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.source-attribution a {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.source-attribution img {
  max-width: 80px;
  background: white;
  padding: 3px;
  border-radius: 3px;
}
</style>
