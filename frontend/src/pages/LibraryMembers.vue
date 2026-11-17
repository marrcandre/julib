<script setup lang="ts">
import { onMounted, ref } from "vue";
import Button from "primevue/button";
import InviteLinkPanel from "../components/InviteLinkPanel.vue";
import { api } from "../api";

type Member = { user_id: number; name: string; email: string; role: "admin" | "member"; joined_at: string | null; is_current_user: boolean; can_change_role: boolean; can_remove: boolean; can_leave: boolean };
type Invite = { id: number; expires_at: string; status: string };
const members = ref<Member[]>([]);
const current = ref<Member | null>(null);
const canManage = ref(false);
const inviteList = ref<Invite[]>([]);
const error = ref("");
const notice = ref("");
const busy = ref(false);
const loading = ref(true);
const pendingActions = ref(new Set<string>());
const newInviteUrl = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const result = await api<{ members: Member[]; current_membership: Member; can_manage: boolean }>("/members");
    members.value = result.members;
    current.value = result.current_membership;
    canManage.value = result.can_manage;
    if (result.can_manage) inviteList.value = await api<Invite[]>("/invites");
  } catch (cause) { error.value = (cause as Error).message; }
  finally { loading.value = false; }
}
async function createInvite() {
  busy.value = true; error.value = "";
  let shareFailure = "";
  try {
    const result = await api<{ invite_url: string }>("/invites", { method: "POST", body: "{}" });
    newInviteUrl.value = result.invite_url;
    notice.value = "Convite criado. O link está disponível para visualização e cópia manual.";
    if (navigator.share) {
      try {
        await navigator.share({ title: "Convite para biblioteca", url: result.invite_url });
        notice.value = "Link compartilhado. Ele vale por 7 dias e só pode ser usado uma vez.";
      } catch (cause) {
        if ((cause as Error).name === "AbortError")
          notice.value = "Compartilhamento cancelado. O link continua disponível nesta tela.";
        else shareFailure = "Não foi possível compartilhar. Você ainda pode copiar o link abaixo.";
      }
    }
    await load();
    if (shareFailure && !error.value) error.value = shareFailure;
  } catch (cause) {
    if ((cause as Error).name !== "AbortError") error.value = (cause as Error).message;
  } finally { busy.value = false; }
}
function isMemberBusy(userId: number) { return pendingActions.value.has(`member:${userId}`); }
function isInviteBusy(inviteId: number) { return pendingActions.value.has(`invite:${inviteId}`); }
function setPending(key: string, pending: boolean) {
  const next = new Set(pendingActions.value);
  if (pending) next.add(key);
  else next.delete(key);
  pendingActions.value = next;
}
async function action(
  path: string,
  method: string,
  body?: unknown,
  successMessage = "Alteração concluída.",
  lockKey = path,
  confirmation?: string,
) {
  error.value = ""; notice.value = "";
  if (confirmation && !window.confirm(confirmation)) return;
  if (pendingActions.value.has(lockKey)) return;
  setPending(lockKey, true);
  try {
    await api(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) });
    notice.value = successMessage;
    await load();
  }
  catch (cause) { error.value = (cause as Error).message; }
  finally { setPending(lockKey, false); }
}
async function changeRole(member: Member) {
  const demoting = member.role === "admin";
  const nextRole = demoting ? "member" : "admin";
  const confirmation = demoting
    ? `Confirma rebaixar ${member.name} de administrador para membro?`
    : undefined;
  await action(
    `/members/${member.user_id}/role`,
    "PATCH",
    { role: nextRole },
    `Papel de ${member.name} atualizado.`,
    `member:${member.user_id}`,
    confirmation,
  );
}
async function removeMember(member: Member) {
  await action(
    `/members/${member.user_id}`,
    "DELETE",
    undefined,
    `${member.name} removido da biblioteca.`,
    `member:${member.user_id}`,
    `Confirma remover ${member.name} desta biblioteca?`,
  );
}
async function revokeInvite(invite: Invite) {
  await action(
    `/invites/${invite.id}`,
    "DELETE",
    undefined,
    "Convite revogado.",
    `invite:${invite.id}`,
    "Confirma revogar este convite?",
  );
}
onMounted(load);
</script>

<template>
  <section class="readable members-page">
    <div class="eyebrow">GESTÃO DA BIBLIOTECA</div>
    <h1>Membros e convites</h1>
    <p v-if="current" class="muted">Seu papel: {{ current.role === 'admin' ? 'administrador' : 'membro' }}.</p>
    <p v-if="loading" class="muted" role="status">Carregando membros e convites…</p>
    <Button v-if="canManage" label="Criar link de convite" icon="pi pi-link" class="primary" :loading="busy" :disabled="loading" @click="createInvite" />
    <InviteLinkPanel
      v-if="newInviteUrl"
      :url="newInviteUrl"
      @close="newInviteUrl = ''"
    />
    <h2 v-if="canManage">Convites ativos e anteriores</h2>
    <ul v-if="canManage" class="invite-list"><li v-for="invite in inviteList" :key="invite.id"><span>{{ invite.status }} · expira {{ new Date(invite.expires_at).toLocaleDateString() }}</span><Button v-if="invite.status === 'pending'" label="Revogar" text :disabled="loading || isInviteBusy(invite.id)" :loading="isInviteBusy(invite.id)" @click="revokeInvite(invite)" /></li></ul>
    <h2 v-if="canManage">Pessoas</h2>
    <ul v-if="canManage" class="member-list"><li v-for="member in members" :key="member.user_id"><span><strong>{{ member.name }}</strong><small>{{ member.email }} · {{ member.role === 'admin' ? 'administrador' : 'membro' }}</small></span><Button v-if="member.can_change_role" :label="member.role === 'admin' ? 'Tornar membro' : 'Tornar admin'" text :disabled="loading || isMemberBusy(member.user_id)" :loading="isMemberBusy(member.user_id)" @click="changeRole(member)" /><Button v-if="member.can_remove" label="Remover" text :disabled="loading || isMemberBusy(member.user_id)" @click="removeMember(member)" /></li></ul>
    <Button v-if="current?.can_leave" label="Sair desta biblioteca" severity="danger" text :disabled="loading || pendingActions.has('leave')" :loading="pendingActions.has('leave')" @click="action('/members/me', 'DELETE', undefined, 'Você saiu da biblioteca.', 'leave', 'Confirma sair desta biblioteca?')" />
    <p v-if="notice" class="success" role="status">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </section>
</template>
