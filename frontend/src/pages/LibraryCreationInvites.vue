<script setup lang="ts">
import { computed, inject, onMounted, ref } from "vue";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import { api, type Session } from "../api";

type CreationInvite = {
  id: number;
  email: string;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  status: "pending" | "accepted" | "expired" | "revoked";
  created_library: { id: number; name: string; role: "admin" } | null;
};

const session = inject<import("vue").Ref<Session | null>>("session");
const isOwner = computed(() => session?.value?.technical === true);
const invites = ref<CreationInvite[]>([]);
const email = ref("");
const newInviteUrl = ref("");
const loading = ref(false);
const busy = ref(false);
const revokingId = ref<number | null>(null);
const error = ref("");
const notice = ref("");

function statusLabel(status: CreationInvite["status"]) {
  return {
    pending: "Pendente",
    accepted: "Utilizado",
    expired: "Expirado",
    revoked: "Revogado",
  }[status];
}

function localDate(value: string) {
  return new Date(value).toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
}

async function load() {
  if (!isOwner.value) return;
  loading.value = true;
  error.value = "";
  try {
    invites.value = await api<CreationInvite[]>("/library-creation-invites");
  } catch (cause) {
    error.value = (cause as Error).message;
  } finally {
    loading.value = false;
  }
}

async function createInvite() {
  if (!isOwner.value || busy.value) return;
  busy.value = true;
  error.value = "";
  notice.value = "";
  try {
    const result = await api<{ invite_url: string }>("/library-creation-invites", {
      method: "POST",
      body: JSON.stringify({ email: email.value.trim() }),
    });
    newInviteUrl.value = result.invite_url;
    email.value = "";
    notice.value = "Link criado. Copie e encaminhe ao convidado; ele expira em sete dias e só pode ser usado uma vez.";
    await load();
  } catch (cause) {
    error.value = (cause as Error).message;
  } finally {
    busy.value = false;
  }
}

async function copyInvite() {
  if (!newInviteUrl.value) return;
  try {
    await navigator.clipboard.writeText(newInviteUrl.value);
    newInviteUrl.value = "";
    notice.value = "Link copiado. Ele não será exibido novamente.";
  } catch (cause) {
    error.value = (cause as Error).message || "Não foi possível copiar o link.";
  }
}

async function revoke(invite: CreationInvite) {
  if (!window.confirm("Confirma revogar este convite?")) return;
  revokingId.value = invite.id;
  error.value = "";
  notice.value = "";
  try {
    await api(`/library-creation-invites/${invite.id}`, { method: "DELETE" });
    notice.value = "Convite revogado.";
    await load();
  } catch (cause) {
    error.value = (cause as Error).message;
  } finally {
    revokingId.value = null;
  }
}

onMounted(load);
</script>

<template>
  <section class="readable creation-invites-page">
    <div class="eyebrow">ADMINISTRAÇÃO DA APLICAÇÃO</div>
    <h1>Convites para criar bibliotecas</h1>
    <template v-if="!session">
      <p>Entre com a conta Google do proprietário para administrar estes convites.</p>
      <Button
        as="a"
        :href="'/accounts/google/login/?next=' + encodeURIComponent('/administracao/convites')"
        label="Entrar com Google"
        icon="pi pi-google"
        class="primary"
      />
    </template>
    <template v-else-if="!isOwner">
      <p class="muted">Somente o proprietário da aplicação pode consultar e administrar estes convites.</p>
    </template>
    <template v-else>
      <p class="muted">
        Convites são de uso único e expiram em sete dias. O link pode ser livre ou vinculado a um e-mail Google verificado.
      </p>
      <form class="creation-invite-form" @submit.prevent="createInvite">
        <label for="creation-invite-email">E-mail do convidado (opcional)</label>
        <InputText
          id="creation-invite-email"
          v-model="email"
          type="email"
          maxlength="254"
          autocomplete="email"
          placeholder="Qualquer conta com o link"
        />
        <small class="muted">Sem e-mail, qualquer pessoa com o link e uma conta Google verificada pode criar a biblioteca.</small>
        <Button type="submit" label="Gerar convite" icon="pi pi-link" class="primary" :loading="busy" :disabled="loading || busy" />
      </form>

      <div v-if="newInviteUrl" class="creation-invite-link">
        <label for="new-creation-invite-link">Link (exibido uma vez)</label>
        <InputText id="new-creation-invite-link" :model-value="newInviteUrl" readonly @focus="($event.target as HTMLInputElement).select()" />
        <Button label="Copiar link e ocultar" icon="pi pi-copy" text @click="copyInvite" />
      </div>

      <p v-if="loading" class="muted" role="status">Carregando convites…</p>
      <p v-if="notice" class="notice" role="status">{{ notice }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <h2>Convites emitidos</h2>
      <p v-if="!loading && invites.length === 0" class="muted">Nenhum convite emitido.</p>
      <ul v-else class="creation-invite-list">
        <li v-for="invite in invites" :key="invite.id">
          <div>
            <strong>{{ statusLabel(invite.status) }}</strong>
            <small>{{ invite.email || "Link livre" }} · expira {{ localDate(invite.expires_at) }}</small>
            <small v-if="invite.created_library">Biblioteca criada: {{ invite.created_library.name }} ({{ invite.created_library.id }})</small>
          </div>
          <Button
            v-if="invite.status === 'pending'"
            label="Revogar"
            text
            :loading="revokingId === invite.id"
            :disabled="loading || revokingId !== null"
            @click="revoke(invite)"
          />
        </li>
      </ul>
    </template>
  </section>
</template>
