<script setup lang="ts">
import LoanBook from "../components/LoanBook.vue";
import BookCredits from "../components/BookCredits.vue";
import { ref, onMounted, inject, type Ref } from "vue";
import Button from "primevue/button";
import BookCard from "../components/BookCard.vue";
import { api, type Book, type Loan, type Session } from "../api";
interface Dashboard {
  books: number;
  copies: number;
  loans: number;
  overdue: number;
  recent: { number: number; acquired_on: string; book: Book }[];
  attention: Loan[];
}
const data = ref<Dashboard | null>(null),
  error = ref(""),
  session = inject<Ref<Session>>("session");
onMounted(async () => {
  try {
    data.value = await api<Dashboard>("/dashboard");
  } catch (e) {
    error.value = (e as Error).message;
  }
});
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">SUA BIBLIOTECA PESSOAL</div>
      <h1>Olá, {{ session?.name.split(" ")[0] }}.</h1>
      <p class="muted">
        Cada livro tem uma história. Vamos cuidar da sua coleção.
      </p>
    </div>
    <Button
      as="router-link"
      to="/livros?novo=1"
      class="primary"
      label="Adicionar livro"
      icon="pi pi-plus"
    />
  </div>
  <p v-if="error" class="error">{{ error }}</p>
  <template v-if="data"
    ><div class="stats">
      <div
        class="stat"
        v-for="item in [
          { label: 'Livros / edições', value: data.books, icon: 'pi-book' },
          {
            label: 'Exemplares no acervo',
            value: data.copies,
            icon: 'pi-objects-column',
          },
          {
            label: 'Emprestados',
            value: data.loans,
            icon: 'pi-arrow-up-right',
          },
          { label: 'Em atraso', value: data.overdue, icon: 'pi-clock' },
        ]"
        :key="item.label"
      >
        <div class="stat-head">
          {{ item.label }}<i class="pi" :class="item.icon" />
        </div>
        <strong>{{ item.value }}</strong>
      </div>
    </div>
    <div class="section-heading">
      <h2>Empréstimos para acompanhar</h2>
      <RouterLink to="/emprestimos">Ver todos →</RouterLink>
    </div>
    <div v-if="!data.attention.length" class="empty">
      <i class="pi pi-check-circle" />Nenhum empréstimo em aberto. Tudo em seu
      lugar.
    </div>
    <div v-else class="panel">
      <div v-for="loan in data.attention" :key="loan.id" class="loan-row">
        <LoanBook :loan="loan">
          <div class="muted">
            {{ loan.person_name }} · Exemplar #{{ loan.copy_number }}
          </div>
        </LoanBook>
        <div>
          <span class="status" :class="{ warn: loan.overdue }"
            >{{ loan.overdue ? "Em atraso" : "Previsto" }} ·
            {{ loan.due_on.split("-").reverse().join("/") }}</span
          >
        </div>
      </div>
    </div>
    <div class="section-heading">
      <h2>Últimas aquisições</h2>
      <RouterLink to="/livros">Explorar acervo →</RouterLink>
    </div>
    <div v-if="!data.recent.length" class="empty">
      <i class="pi pi-book" />Sua biblioteca começa com o primeiro livro.<br /><RouterLink
        to="/importar"
        >Importar do Goodreads</RouterLink
      >
      ou <RouterLink to="/livros?novo=1">cadastrar um livro</RouterLink>.
    </div>
    <div v-else class="book-grid recent-covers">
      <div v-for="item in data.recent" :key="item.number">
        <RouterLink :to="'/livros/' + item.book.id"
          ><BookCard :book="item.book" variant="covers" /></RouterLink
        ><BookCredits :item="item.book" />
      </div></div
  ></template>
</template>

<style scoped>
.recent-covers {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}
</style>
