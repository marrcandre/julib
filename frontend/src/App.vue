<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, provide, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import Button from "primevue/button";
import Drawer from "primevue/drawer";
import Dialog from "primevue/dialog";
import InputText from "primevue/inputtext";
import Toast from "primevue/toast";
import { api, post, setCsrf, type Session } from "./api";
import { applyTheme, initialTheme, type ThemePreference } from "./theme";
const appVersion = __APP_VERSION__;
const session = ref<Session | null>(null),
  avatarFailed = ref(false),
  navigationOpen = ref(false),
  loading = ref(true),
  error = ref(""),
  online = ref(navigator.onLine),
  createOpen = ref(false),
  creating = ref(false),
  createName = ref(""),
  createError = ref(""),
  libraryMenu = ref<HTMLDetailsElement>();
const theme = ref<ThemePreference>(initialTheme()),
  route = useRoute(),
  router = useRouter();
provide("session", session);
const publicLibrary = ref<string | null>(null);
provide("public-library", publicLibrary);
const publicCollection = computed(() => route.path.startsWith("/colecao/"));
const activeLibrary = computed(() => {
  const currentSession = session.value;
  if (!currentSession) return undefined;
  const routeId = Number(route.params.libraryId);
  return (
    currentSession.libraries.find((library) => library.id === routeId) ||
    (!route.params.libraryId
      ? currentSession.libraries.find(
          (library) => library.id === savedLibrary(currentSession.user_id),
        ) ||
        (currentSession.libraries.length === 1 ? currentSession.libraries[0] : undefined)
      : undefined)
  );
});
const libraryBase = computed(() =>
  activeLibrary.value ? `/bibliotecas/${activeLibrary.value.id}` : "/bibliotecas",
);
const libraryName = computed(() => {
  const current = publicCollection.value
    ? publicLibrary.value
    : activeLibrary.value?.name || session.value?.library;
  return current?.trim() || (loading.value ? "" : "Julib");
});
function savedLibrary(userId: number): number | null {
  try {
    const raw = localStorage.getItem(`julib:active-library:${userId}`);
    const id = raw ? Number(raw) : NaN;
    return Number.isInteger(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}
function rememberLibrary(userId: number, libraryId: number) {
  try {
    localStorage.setItem(`julib:active-library:${userId}`, String(libraryId));
  } catch {
    // The URL remains authoritative if browser storage is unavailable.
  }
}
function scopedPath(path: string, libraryId: number): string {
  const base = `/bibliotecas/${libraryId}`;
  if (/^\/bibliotecas\/-?\d+(?:\/|$)/.test(path))
    return path.replace(/^\/bibliotecas\/-?\d+/, base);
  if (path === "/livros") return `${base}/livros`;
  if (path.startsWith("/livros/")) return `${base}${path}`;
  if (path === "/emprestimos") return `${base}/emprestimos`;
  if (path === "/locais") return `${base}/locais`;
  if (path === "/importar") return `${base}/importar`;
  if (path === "/configuracoes") return `${base}/configuracoes`;
  return `${base}/livros`;
}
async function normalizeLibraryRoute() {
  const currentSession = session.value;
  if (
    !currentSession ||
    publicCollection.value ||
    route.path === "/sobre"
  )
    return;
  if (currentSession.libraries.length === 0) {
    if (currentSession.can_create_libraries && route.path !== "/bibliotecas")
      await router.replace("/bibliotecas");
    return;
  }
  const routeId = Number(route.params.libraryId);
  const validRouteLibrary = currentSession.libraries.find((item) => item.id === routeId);
  const remembered = savedLibrary(currentSession.user_id);
  const selected =
    validRouteLibrary ||
    currentSession.libraries.find((item) => item.id === remembered) ||
    currentSession.libraries[0];
  rememberLibrary(currentSession.user_id, selected.id);
  currentSession.library = selected.name;
  const target = scopedPath(route.path, selected.id);
  if (target !== route.path)
    await router.replace({ path: target, query: route.query, hash: route.hash });
}
function switchLibrary(libraryId: number) {
  if (!session.value) return;
  rememberLibrary(session.value.user_id, libraryId);
  if (libraryMenu.value) libraryMenu.value.open = false;
  void router.push(`/bibliotecas/${libraryId}/livros`);
}
async function createLibrary() {
  if (!session.value || !session.value.can_create_libraries || creating.value) return;
  creating.value = true;
  createError.value = "";
  try {
    const created = await api<Session["libraries"][number]>("/libraries", {
      method: "POST",
      body: JSON.stringify({ name: createName.value }),
    });
    session.value.libraries.push(created);
    createName.value = "";
    createOpen.value = false;
    rememberLibrary(session.value.user_id, created.id);
    await router.push(`/bibliotecas/${created.id}/livros`);
  } catch (cause) {
    createError.value = (cause as Error).message;
  } finally {
    creating.value = false;
  }
}
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
  if (route.path.endsWith("/livros") || route.path.includes("/livros/")) return "Livros";
  if (route.path.endsWith("/emprestimos")) return "Empréstimos";
  if (route.path.endsWith("/locais")) return "Locais";
  if (route.path.endsWith("/importar")) return "Importar livros";
  if (route.path.endsWith("/configuracoes")) return "Configurações";
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
  await router.isReady();
  window.addEventListener("online", syncOnline);
  window.addEventListener("offline", syncOnline);
  try {
    const response = await api<
      Omit<Session, "libraries" | "can_create_libraries"> &
        Partial<Pick<Session, "libraries" | "can_create_libraries">>
    >("/session");
    const s: Session = {
      ...response,
      can_create_libraries: response.can_create_libraries ?? false,
      libraries:
        response.libraries ??
        (response.library
          ? [
              {
                id: -1,
                name: response.library,
                role: response.technical ? "admin" : "member",
              },
            ]
          : []),
    };
    session.value = s;
    setCsrf(s.csrf);
  } catch (e) {
    if (!(e as Error).message.includes("Entre com"))
      error.value = (e as Error).message;
  } finally {
    await normalizeLibraryRoute();
    loading.value = false;
  }
});
watch(
  () => route.fullPath,
  () => {
    if (!loading.value) normalizeLibraryRoute();
  },
);
watch(activeLibrary, (library) => {
  if (library && session.value) session.value.library = library.name;
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
      <details
        v-if="session && !publicCollection"
        ref="libraryMenu"
        class="library-switcher"
      >
        <summary
          class="brand"
          :aria-label="(libraryName || 'Bibliotecas') + ' — selecionar biblioteca'"
          :title="libraryName"
        >
          <i class="pi pi-book" aria-hidden="true" />
          <span class="brand-name">{{ libraryName || "Bibliotecas" }}</span>
          <i class="pi pi-chevron-down library-chevron" aria-hidden="true" />
        </summary>
        <div class="library-menu" role="menu" aria-label="Bibliotecas disponíveis">
          <button
            v-for="library in session.libraries"
            :key="library.id"
            type="button"
            role="menuitemradio"
            :aria-checked="activeLibrary?.id === library.id"
            @click="switchLibrary(library.id)"
          >
            <span>{{ library.name || "Julib" }}</span>
            <i v-if="activeLibrary?.id === library.id" class="pi pi-check" aria-hidden="true" />
          </button>
          <button
            v-if="session.can_create_libraries"
            type="button"
            role="menuitem"
            class="new-library-option"
            @click="createOpen = true; libraryMenu && (libraryMenu.open = false)"
          >
            <i class="pi pi-plus" aria-hidden="true" /> Nova biblioteca
          </button>
        </div>
      </details>
      <RouterLink
        v-else
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
          :to="libraryBase + '/livros'"
          :class="{ 'section-active': route.path.endsWith('/livros') || route.path.includes('/livros/') }"
          >Livros</RouterLink
        ><RouterLink :to="libraryBase + '/emprestimos'">Empréstimos</RouterLink
        ><RouterLink :to="libraryBase + '/locais'">Locais</RouterLink>
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
            <RouterLink
              v-if="activeLibrary?.role === 'admin'"
              :to="libraryBase + '/configuracoes'"
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
        :to="libraryBase + '/livros'"
        :class="{ 'section-active': route.path.endsWith('/livros') || route.path.includes('/livros/') }"
        @click="navigationOpen = false"
        ><i class="pi pi-book" aria-hidden="true" />Livros</RouterLink
      >
      <RouterLink :to="libraryBase + '/emprestimos'" @click="navigationOpen = false"
        ><i
          class="pi pi-arrow-up-right"
          aria-hidden="true"
        />Empréstimos</RouterLink
      >
      <RouterLink :to="libraryBase + '/locais'" @click="navigationOpen = false"
        ><i class="pi pi-map-marker" aria-hidden="true" />Locais</RouterLink
      >
      <RouterLink
        v-if="activeLibrary?.role === 'admin'"
        :to="libraryBase + '/configuracoes'"
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
      'catalog-main': pageTitle === 'Livros' && !route.path.includes('/livros/'),
      'book-detail-main': /\/livros\/[^/]+$/.test(route.path),
    }"
  >
    <p v-if="loading" role="status" class="muted">Carregando sua biblioteca…</p>
    <template v-else
      ><RouterView
        v-if="(session && (session.libraries.length > 0 || publicCollection || route.path === '/sobre')) || publicCollection || route.path === '/sobre'"
        :key="String(route.params.libraryId || 'public')"
      />
      <section
        v-else-if="session && session.libraries.length === 0 && !publicCollection && route.path !== '/sobre'"
        class="readable library-empty-state"
      >
        <div class="eyebrow">SUA BIBLIOTECA</div>
        <h1>Nenhuma biblioteca disponível</h1>
        <p v-if="session.can_create_libraries" class="muted">
          Crie sua primeira biblioteca para começar a organizar o acervo.
        </p>
        <p v-else class="muted">
          Sua conta ainda não está associada a uma biblioteca. Solicite acesso ao administrador.
        </p>
        <Button
          v-if="session.can_create_libraries"
          label="Nova biblioteca"
          icon="pi pi-plus"
          class="primary"
          @click="createOpen = true"
        />
      </section>
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
  <Dialog
    v-model:visible="createOpen"
    header="Nova biblioteca"
    modal
    :style="{ width: 'min(28rem, calc(100vw - 2rem))' }"
  >
    <form class="library-create-form" @submit.prevent="createLibrary">
      <label for="new-library-name">Nome da biblioteca</label>
      <InputText
        id="new-library-name"
        v-model="createName"
        maxlength="150"
        required
        autofocus
        autocomplete="off"
        aria-describedby="new-library-help"
      />
      <small id="new-library-help" class="muted">Até 150 caracteres.</small>
      <p v-if="createError" class="error" role="alert">{{ createError }}</p>
      <Button
        type="submit"
        :label="creating ? 'Criando…' : 'Criar biblioteca'"
        icon="pi pi-plus"
        class="primary"
        :disabled="creating || !createName.trim()"
      />
    </form>
  </Dialog>
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
      <div class="copyright">Marco André Mendes <span>v{{ appVersion }}</span></div>
    </div>
  </footer>
</template>
