<script setup lang="ts">
import Button from "primevue/button";

defineProps<{ busy: boolean; formId?: string }>();
defineEmits<{ cancel: [] }>();
</script>

<template>
  <div class="actions book-edit-actions">
    <Button
      label="Cancelar"
      aria-label="Cancelar"
      title="Cancelar"
      type="button"
      icon="pi pi-times"
      class="book-edit-cancel"
      outlined
      :disabled="busy"
      @click="$emit('cancel')"
    />
    <Button
      label="Salvar alterações"
      aria-label="Salvar alterações"
      title="Salvar alterações"
      type="submit"
      :form="formId"
      icon="pi pi-check"
      class="primary"
      :disabled="busy"
      :loading="busy"
    />
  </div>
</template>
