<script setup lang="ts">
import { computed, inject, onMounted, ref } from "vue";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import { useRouter } from "vue-router";
import { api, setCsrf, type Session } from "../api";

const session = inject<import("vue").Ref<Session | null>>("session");
const router = useRouter();
const busy = ref(true);
const creating = ref(false);
const ready = ref(false);
const error = ref("");
const invitedEmail = ref("");
const libraryName = ref("");
const needsLogin = computed(() => !session?.value);

onMounted(async () => {
  const token = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  if (token) history.replaceState(history.state, "", window.location.pathname + window.location.search);
  try {
    if (token) {
      const csrf = await api<{ csrf: string }>("/csrf");
      setCsrf(csrf.csrf);
      const preview = await api<{ pending: boolean; email: string }>(
        "/library-creation-invites/prepare",
        { method: "POST", body: JSON.stringify({ token }) },
      );
      if (!preview.pending) throw new Error("Este convite não está mais disponível.");
      invitedEmail.value = preview.email;
    } else {
      const pending = await api<{ pending: boolean; email: string }>(
        "/library-creation-invites/pending",
      );
      if (!pending.pending) throw new Error("Este link não é válido, expirou, foi revogado ou já foi utilizado.");
      invitedEmail.value = pending.email;
    }
    ready.value = true;
  } catch (cause) {
    error.value = (cause as Error).message;
  } finally {
    busy.value = false;
  }
});

async function createLibrary() {
  if (!session?.value || creating.value || !ready.value) return;
  creating.value = true;
  error.value = "";
  try {
    const created = await api<Session["libraries"][number]>("/libraries/from-invite", {
      method: "POST",
      body: JSON.stringify({ name: libraryName.value.trim() }),
    });
    if (!session.value.libraries.some((library) => library.id === created.id))
      session.value.libraries.push(created);
    session.value.library = created.name;
    try {
      localStorage.setItem(`julib:active-library:${session.value.user_id}`, String(created.id));
    } catch {
      // The explicit library URL remains authoritative if storage is unavailable.
    }
    await router.replace(`/bibliotecas/${created.id}/livros`);
  } catch (cause) {
    error.value = (cause as Error).message;
  } finally {
    creating.value = false;
  }
}
</script>

<template>
  <section class="readable invite-page creation-accept-page">
    <div class="eyebrow">CONVITE PARA CRIAR UMA BIBLIOTECA</div>
    <h1 v-if="busy && !ready">Verificando convite…</h1>
    <template v-else-if="ready">
      <h1>Crie sua biblioteca</h1>
      <p v-if="invitedEmail">Este convite foi emitido para <strong>{{ invitedEmail }}</strong>.</p>
      <p v-else>Você recebeu um link compartilhável para criar uma biblioteca.</p>
      <Button
        v-if="needsLogin"
        as="a"
        :href="'/accounts/google/login/?next=' + encodeURIComponent('/convites/criar')"
        label="Continuar com Google"
        icon="pi pi-google"
        class="primary"
      />
      <form v-else class="library-create-form" @submit.prevent="createLibrary">
        <label for="invited-library-name">Nome da biblioteca</label>
        <InputText
          id="invited-library-name"
          v-model="libraryName"
          maxlength="150"
          required
          autofocus
          autocomplete="off"
        />
        <small class="muted">Você será administrador desta biblioteca.</small>
        <Button
          type="submit"
          :label="creating ? 'Criando…' : 'Criar biblioteca'"
          icon="pi pi-plus"
          class="primary"
          :disabled="creating || !libraryName.trim()"
          :loading="creating"
        />
      </form>
    </template>
    <div v-if="error" class="error" role="alert">{{ error }}</div>
  </section>
</template>
