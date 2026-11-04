<script setup lang="ts">
import { ref, onMounted, onUnmounted, provide, watch } from "vue";
import { useRoute } from "vue-router";
import Button from "primevue/button";
import { api, post, setCsrf, type Session } from "./api";
import { applyTheme, initialTheme, type ThemePreference } from "./theme";
const session = ref<Session | null>(null),
  loading = ref(true),
  error = ref(""),
  online = ref(navigator.onLine);
const theme = ref<ThemePreference>(initialTheme()),
  route = useRoute();
provide("session", session);
watch(theme, applyTheme, { immediate: true });
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
      <RouterLink class="brand" to="/" aria-label="Julib início"
        ><i class="pi pi-book" /> Julib</RouterLink
      >
      <nav v-if="session">
        <RouterLink to="/">Painel</RouterLink
        ><RouterLink to="/livros">Livros</RouterLink
        ><RouterLink to="/emprestimos">Empréstimos</RouterLink
        ><RouterLink to="/locais">Locais</RouterLink>
      </nav>
      <div class="header-actions">
        <button
          class="theme-toggle"
          type="button"
          :aria-label="theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'"
          :title="theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'"
          @click="theme = theme === 'dark' ? 'light' : 'dark'"
        ><i :class="theme === 'dark' ? 'pi pi-sun' : 'pi pi-moon'" aria-hidden="true" /></button>
        <details v-if="session" class="account">
          <summary :aria-label="'Conta de ' + session.name">
            <span class="avatar">{{
              session.name.slice(0, 2).toUpperCase()
            }}</span>
          </summary>
          <div class="account-menu">
            <b>{{ session.name }}</b
            ><small>{{ session.email }}</small
            ><RouterLink to="/sobre">Sobre</RouterLink
            ><a v-if="session.technical" href="/admin/">Admin</a
            ><a v-if="session.technical" href="/api/v1/docs">Swagger</a
            ><button @click="signOut">Sair</button>
          </div>
        </details>
      </div>
    </div>
  </header>
  <div v-if="!online" class="offline" role="status">
    Sem conexão. Conecte-se à internet para consultar ou salvar.
  </div>
  <main class="container">
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
          href="/accounts/google/login/"
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
      <div>
        <b
          ><RouterLink to="/sobre#homenagem">Julib</RouterLink> — Sua
          biblioteca, bem organizada</b
        >
        <p class="muted">
          Um lugar para cada livro. Mais histórias para compartilhar.
        </p>
      </div>
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
      <div class="copyright">Marco André Mendes <span>v0.1.0</span></div>
    </div>
  </footer>
</template>
