<script setup lang="ts">
import { ref, watch } from "vue";
import Button from "primevue/button";
import InputText from "primevue/inputtext";

const props = defineProps<{ url: string }>();
const emit = defineEmits<{ close: [] }>();

const visible = ref(true);
const copied = ref(false);
const error = ref("");

watch(
  () => props.url,
  () => {
    visible.value = true;
    copied.value = false;
    error.value = "";
  },
);

async function copyLink() {
  copied.value = false;
  error.value = "";
  const clipboard =
    typeof navigator === "undefined" ? undefined : navigator.clipboard;
  if (!clipboard?.writeText) {
    visible.value = true;
    error.value =
      "Não foi possível copiar. Selecione o link e copie manualmente.";
    return;
  }

  try {
    await clipboard.writeText(props.url);
    copied.value = true;
  } catch {
    visible.value = true;
    error.value =
      "Não foi possível copiar. Selecione o link e copie manualmente.";
  }
}
</script>

<template>
  <section class="invite-link-panel" aria-label="Link do convite">
    <div class="invite-link-panel__heading">
      <strong>Link do convite</strong>
      <div class="invite-link-panel__actions">
        <Button
          :label="visible ? 'Ocultar link' : 'Mostrar link'"
          text
          :aria-expanded="visible"
          @click="visible = !visible"
        />
        <Button label="Fechar" text @click="emit('close')" />
      </div>
    </div>
    <div v-if="visible" class="invite-link-panel__field">
      <label for="invite-link">Link</label>
      <InputText
        id="invite-link"
        :model-value="url"
        readonly
        autocomplete="off"
        @focus="($event.target as HTMLInputElement).select()"
      />
    </div>
    <Button label="Copiar link" icon="pi pi-copy" text @click="copyLink" />
    <p v-if="copied" class="success" role="status">Link copiado.</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </section>
</template>
