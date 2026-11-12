<script setup lang="ts">
import { inject, onMounted, ref, type Ref } from "vue";
import { useRouter } from "vue-router";
import { api, type Session } from "../api";

const session = inject<Ref<Session | null>>("session");
const router = useRouter();
const name = ref(session?.value?.library || "");
const saving = ref(false);
const error = ref("");
const saved = ref(false);

onMounted(() => {
  if (!session?.value?.technical) router.replace("/livros");
});

async function save() {
  if (!session?.value) return;
  saving.value = true;
  error.value = "";
  saved.value = false;
  try {
    const result = await api<{ name: string }>("/library/name", {
      method: "PUT",
      body: JSON.stringify({ name: name.value }),
    });
    name.value = result.name;
    session.value.library = result.name;
    saved.value = true;
  } catch (cause) {
    error.value = (cause as Error).message;
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <section v-if="session?.technical" class="readable settings-page">
    <div class="eyebrow">IDENTIDADE DA BIBLIOTECA</div>
    <h1>Configurações</h1>
    <p class="muted">
      O nome é compartilhado por todas as pessoas desta biblioteca. Deixe em
      branco para usar Julib.
    </p>
    <form @submit.prevent="save">
      <label for="library-name">Nome da biblioteca</label>
      <input
        id="library-name"
        v-model="name"
        type="text"
        maxlength="150"
        autocomplete="off"
        aria-describedby="library-name-help"
      />
      <small id="library-name-help" class="muted">Até 150 caracteres.</small>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="saved" class="success" role="status">Nome atualizado.</p>
      <button type="submit" class="primary" :disabled="saving">
        {{ saving ? "Salvando…" : "Salvar" }}
      </button>
    </form>
  </section>
</template>
