<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, provide, watch } from "vue";
import { useRoute } from "vue-router";
import Button from "primevue/button";
import Drawer from "primevue/drawer";
import Toast from "primevue/toast";
import { api, post, setCsrf, type Session } from "./api";
import { applyTheme, initialTheme, type ThemePreference } from "./theme";
const appVersion = __APP_VERSION__;
const session = ref<Session | null>(null),
  avatarFailed = ref(false),
  navigationOpen = ref(false),
  loading = ref(true),
  error = ref(""),
  online = ref(navigator.onLine);
const theme = ref<ThemePreference>(initialTheme()),
  route = useRoute();
provide("session", session);
const publicLibrary = ref<string | null>(null);
provide("public-library", publicLibrary);
const publicCollection = computed(() => route.path.startsWith("/colecao/"));
const libraryName = computed(() => {
  const current = publicCollection.value
    ? publicLibrary.value
    : session.value?.library;
  return current?.trim() || (loading.value ? "" : "Julib");
});
watch(
  () => route.params.token,
  () => {
    publicLibrary.value = null;
  },
);
watch(
  () => route.path,
  () => {
    navigationOpen.value = false;
  },
);
watch(theme, applyTheme, { immediate: true });
const pageTitle = computed(() => {
  if (route.path.startsWith("/livros")) return "Livros";
  if (route.path.startsWith("/emprestimos")) return "Empréstimos";
  if (route.path.startsWith("/locais")) return "Locais";
  if (route.path.startsWith("/importar")) return "Importar livros";
  if (route.path.startsWith("/configuracoes")) return "Configurações";
  if (route.path.startsWith("/colecao/")) return "Coleção";
  return "Sobre";
});
watch(
  [pageTitle, libraryName, loading],
  ([page, name, isLoading]) => {
    if (!isLoading) document.title = `${page} | ${name || "Julib"}`;
  },
  { immediate: true },
);
const syncOnline = () => (online.value = navigator.onLine);
async function signOut() {
  try {
    await post("/logout");
    session.value = null;
    location.href = "/";
  } catch (e) {
    error.value = (e as Error).message;
  }
}
onMounted(async () => {
  window.addEventListener("online", syncOnline);
  window.addEventListener("offline", syncOnline);
  try {
    const s = await api<Session>("/session");
    session.value = s;
    setCsrf(s.csrf);
  } catch (e) {
    if (!(e as Error).message.includes("Entre com"))
      error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
});
onUnmounted(() => {
  window.removeEventListener("online", syncOnline);
  window.removeEventListener("offline", syncOnline);
});
</script>
<template>
  <header class="app-header">
    <div class="header-inner">
      <Button
        v-if="session"
        class="mobile-nav-trigger"
        aria-label="Abrir navegação"
        icon="pi pi-bars"
        text
        @click="navigationOpen = true"
      />
      <RouterLink
        class="brand"
        :to="publicCollection ? route.path : '/livros'"
        :aria-label="(libraryName || 'Biblioteca') + ' — início'"
        :title="libraryName"
        ><i class="pi pi-book" aria-hidden="true" /><span
          class="brand-name"
          :class="{ 'brand-loading': loading && !libraryName }"
          >{{ libraryName }}</span
        ></RouterLink
      >
      <nav v-if="session" class="desktop-nav" aria-label="Navegação principal">
        <RouterLink
          to="/livros"
          :class="{ 'section-active': route.path.startsWith('/livros/') }"
          >Livros</RouterLink
        ><RouterLink to="/emprestimos">Empréstimos</RouterLink
        ><RouterLink to="/locais">Locais</RouterLink>
      </nav>
      <div class="header-actions">
        <details v-if="session" class="account">
          <summary :aria-label="'Conta de ' + session.name">
            <img
              v-if="session.avatar_url && !avatarFailed"
              class="avatar avatar-photo"
              :src="session.avatar_url"
              alt=""
              referrerpolicy="no-referrer"
              @error="avatarFailed = true"
            />
            <span v-else class="avatar">{{
              session.name.slice(0, 2).toUpperCase()
            }}</span>
          </summary>
          <div class="account-menu">
            <b>{{ session.name }}</b
            ><small>{{ session.email }}</small>
            <fieldset class="theme-options">
              <legend>Tema</legend>
              <label
                ><input
                  v-model="theme"
                  type="radio"
                  name="theme"
                  value="light"
                />Claro</label
              >
              <label
                ><input
                  v-model="theme"
                  type="radio"
                  name="theme"
                  value="dark"
                />Escuro</label
              >
            </fieldset>
            <RouterLink v-if="session.technical" to="/configuracoes"
              >Configurações</RouterLink
            ><RouterLink to="/sobre">Sobre</RouterLink
            ><a v-if="session.technical" href="/admin/">Admin</a
            ><a v-if="session.technical" href="/api/v1/docs">Swagger</a
            ><button @click="signOut">Sair</button>
            <small class="app-version">Julib v{{ appVersion }}</small>
          </div>
        </details>
      </div>
    </div>
  </header>
  <Drawer
    v-model:visible="navigationOpen"
    :header="libraryName"
    position="left"
    class="app-navigation-drawer"
  >
    <nav class="drawer-navigation" aria-label="Navegação principal">
      <RouterLink
        to="/livros"
        :class="{ 'section-active': route.path.startsWith('/livros/') }"
        @click="navigationOpen = false"
        ><i class="pi pi-book" aria-hidden="true" />Livros</RouterLink
      >
      <RouterLink to="/emprestimos" @click="navigationOpen = false"
        ><i
          class="pi pi-arrow-up-right"
          aria-hidden="true"
        />Empréstimos</RouterLink
      >
      <RouterLink to="/locais" @click="navigationOpen = false"
        ><i class="pi pi-map-marker" aria-hidden="true" />Locais</RouterLink
      >
      <RouterLink
        v-if="session?.technical"
        to="/configuracoes"
        @click="navigationOpen = false"
        ><i class="pi pi-cog" aria-hidden="true" />Configurações</RouterLink
      >
    </nav>
  </Drawer>
  <Toast position="top-right" class="app-feedback-toast" />
  <div v-if="!online" class="offline" role="status">
    Sem conexão. Conecte-se à internet para consultar ou salvar.
  </div>
  <main
    class="container"
    :class="{
      'catalog-main': route.path === '/livros',
      'book-detail-main': /^\/livros\/[^/]+$/.test(route.path),
    }"
  >
    <p v-if="loading" role="status" class="muted">Carregando sua biblioteca…</p>
    <template v-else
      ><RouterView
        v-if="
          session ||
          route.path === '/sobre' ||
          route.path.startsWith('/colecao/')
        "
      />
      <section v-else class="welcome">
        <div class="eyebrow">SEU ACERVO, PERTO DE VOCÊ</div>
        <h1>Uma casa para<br />os seus livros.</h1>
        <p>
          Encontre cada exemplar, organize suas estantes<br />e acompanhe os
          livros que estão com amigos.
        </p>
        <Button
          as="a"
          :href="
            '/accounts/google/login/?next=' + encodeURIComponent(route.fullPath)
          "
          label="Entrar com Google"
          icon="pi pi-google"
          class="primary"
        />
        <p class="muted">
          Acesso reservado às contas autorizadas da biblioteca.
        </p>
      </section>
      <p v-if="error" class="error" role="alert">{{ error }}</p></template
    >
  </main>
  <footer class="app-footer">
    <div class="container footer-inner">
      <p class="footer-powered">
        Powered by <RouterLink to="/sobre">Julib</RouterLink>
      </p>
      <div class="footer-links">
        <RouterLink to="/sobre">Sobre</RouterLink
        ><a
          href="https://github.com/marrcandre/julib"
          target="_blank"
          rel="noopener"
          >GitHub</a
        ><a href="mailto:marcoandre@gmail.com">Contato</a
        ><RouterLink to="/sobre#apoie">Apoie este projeto</RouterLink>
      </div>
      <div class="copyright">Marco André Mendes</div>
    </div>
  </footer>
</template>
