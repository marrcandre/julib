<script setup lang="ts">
import { ref, watch } from "vue";
import type { Loan } from "../api";
import SourceAttribution from "./SourceAttribution.vue";
const props = defineProps<{ loan: Loan }>();
const failed = ref(false);
watch(
  () => props.loan.cover_url,
  () => (failed.value = false),
);
</script>
<template>
  <div class="loan-book">
    <div class="loan-cover">
      <img
        v-if="loan.cover_url && !failed"
        :src="loan.cover_url"
        :alt="'Capa de ' + loan.title"
        loading="lazy"
        referrerpolicy="no-referrer"
        @error="failed = true"
      />
      <i
        v-else
        class="pi pi-book"
        role="img"
        :aria-label="'Sem capa: ' + loan.title"
      />
    </div>
    <div class="loan-book-info">
      <b>{{ loan.title }}</b>
      <slot />
      <SourceAttribution
        :name="loan.attribution_name"
        :url="loan.attribution_url"
      />
    </div>
  </div>
</template>
<style scoped>
.loan-book {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}
.loan-book-info {
  min-width: 0;
  overflow-wrap: anywhere;
}
.loan-cover {
  width: 48px;
  height: 72px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  background: var(--soft);
  border-radius: 4px;
  overflow: hidden;
}
.loan-cover img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.loan-cover i {
  color: var(--muted);
}
</style>
