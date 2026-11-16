<script setup lang="ts">
import { computed, inject, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import Button from "primevue/button";
import { useToast } from "primevue/usetoast";
import { api, post, setCsrf, type Session } from "../api";

const session = inject<import("vue").Ref<Session | null>>("session");
const router = useRouter();
const toast = useToast();
const busy = ref(true);
const error = ref("");
const libraryName = ref("");
const ready = ref(false);
const needsLogin = computed(() => !session?.value);

onMounted(async () => {
  const token = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : "";
  if (token) history.replaceState(history.state, "", window.location.pathname + window.location.search);
  try {
    if (token) {
      const csrf = await api<{ csrf: string }>("/csrf");
      setCsrf(csrf.csrf);
      const preview = await post<{ pending: boolean; library_name: string | null }>("/invites/prepare", { token });
      libraryName.value = preview.library_name || "";
    } else {
      const pending = await api<{ pending: boolean; library_name: string | null }>("/invites/pending");
      if (!pending.pending) throw new Error("Este link de convite não é válido, expirou ou já foi utilizado.");
      libraryName.value = pending.library_name || "";
    }
    ready.value = true;
  } catch (cause) {
    error.value = (cause as Error).message;
  } finally {
    busy.value = false;
  }
});

async function accept() {
  busy.value = true;
  error.value = "";
  try {
    const result = await post<{ library_id: number; library_name: string; already_member: boolean }>("/invites/accept");
    if (session?.value) {
      const current = session.value.libraries;
      if (!current.some((library) => library.id === result.library_id))
        current.push({ id: result.library_id, name: result.library_name, role: "member" });
      session.value.library = result.library_name;
      try {
        localStorage.setItem(`julib:active-library:${session.value.user_id}`, String(result.library_id));
      } catch {
        // The explicit library URL remains authoritative if storage is unavailable.
      }
    }
    if (result.already_member)
      toast.add({ severity: "info", summary: "Você já faz parte", detail: "Sua participação foi mantida e o convite continua disponível para outra pessoa.", life: 5000 });
    await router.replace(`/bibliotecas/${result.library_id}/livros`);
  } catch (cause) {
    error.value = (cause as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="readable invite-page">
    <div class="eyebrow">CONVITE PARA UMA BIBLIOTECA</div>
    <h1 v-if="busy && !ready">Verificando convite…</h1>
    <template v-else-if="ready">
      <h1>Você foi convidado</h1>
      <p>Convite para participar de <strong>{{ libraryName }}</strong>.</p>
      <Button v-if="needsLogin" as="a" :href="'/accounts/google/login/?next=' + encodeURIComponent('/convites/aceitar')" label="Continuar com Google" icon="pi pi-google" class="primary" />
      <Button v-else label="Aceitar convite" icon="pi pi-check" class="primary" :loading="busy" @click="accept" />
    </template>
    <div v-if="error" class="error" role="alert">{{ error }}</div>
  </section>
</template>
