<script setup lang="ts">
import SourceAttribution from "../components/SourceAttribution.vue";
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import { api, type Book } from "../api";
import BookCard from "../components/BookCard.vue";
const route = useRoute(),
  books = ref<Book[]>([]),
  name = ref("Coleção"),
  q = ref(""),
  page = ref(1),
  total = ref(0),
  error = ref("");
async function load() {
  error.value = "";
  try {
    const data = await api<{ name: string; items: Book[]; total: number }>(
      "/public/" +
        encodeURIComponent(String(route.params.token)) +
        "/books?q=" +
        encodeURIComponent(q.value) +
        "&page=" +
        page.value,
    );
    name.value = data.name;
    books.value = data.items;
    total.value = data.total;
  } catch (e) {
    books.value = [];
    error.value = (e as Error).message;
  }
}
onMounted(load);
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">COLEÇÃO COMPARTILHADA</div>
      <h1>{{ name }}</h1>
      <p class="muted">
        Um convite para conhecer nossas estantes. Consulta somente leitura.
      </p>
    </div>
  </div>
  <form
    class="toolbar"
    @submit.prevent="
      page = 1;
      load();
    "
  >
    <InputText
      v-model="q"
      placeholder="Buscar título"
      aria-label="Buscar título na coleção"
    /><Button type="submit" label="Buscar" />
  </form>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div v-else-if="!books.length" class="empty">Nenhum livro encontrado.</div>
  <div class="book-grid">
    <div v-for="book in books" :key="book.id">
      <BookCard :book="book" /><SourceAttribution
        :name="book.attribution_name"
        :url="book.attribution_url"
      />
    </div>
  </div>
  <div class="pagination">
    <Button
      label="Anterior"
      text
      :disabled="page === 1"
      @click="
        page--;
        load();
      "
    /><span>{{ page }}</span
    ><Button
      label="Próxima"
      text
      :disabled="page * 24 >= total"
      @click="
        page++;
        load();
      "
    />
  </div>
</template>
