<script setup lang="ts">
defineProps<{ name?: string; url?: string }>();
</script>
<template>
  <p v-if="name && url" class="source-attribution">
    <a :href="url" target="_blank" rel="noopener noreferrer" @click.stop
      ><img
        v-if="name === 'Google Books'"
        src="https://books.google.com/googlebooks/images/poweredby.png"
        alt="Powered by Google"
        referrerpolicy="no-referrer"
      /><span>{{ name }} ↗</span></a
    >
  </p>
</template>
<style scoped>
.source-attribution {
  font-size: 11px;
  margin: 10px 0;
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
