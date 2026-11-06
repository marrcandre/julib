<script setup lang="ts">
import SourceAttribution from "./SourceAttribution.vue";
defineProps<{
  item: {
    attribution_name?: string;
    attribution_url?: string;
    metadata_attribution_name?: string;
    metadata_attribution_url?: string;
  };
}>();
</script>
<template>
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
