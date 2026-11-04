<script setup lang="ts">
import { ref, onMounted } from "vue";
import Button from "primevue/button";
import Dialog from "primevue/dialog";
import Select from "primevue/select";
import InputText from "primevue/inputtext";
import { api, post, today, type Loan, type Person, type Book } from "../api";
const loans = ref<Loan[]>([]),
  people = ref<Person[]>([]),
  books = ref<Book[]>([]),
  personId = ref<number | null>(null),
  copyId = ref<number | null>(null),
  state = ref("open"),
  filterPerson = ref<number | null>(null),
  error = ref(""),
  busy = ref(false),
  loanOpen = ref(false),
  personOpen = ref(false),
  editingPerson = ref<number | null>(null);
const start = ref(today()),
  due = ref(""),
  returnDate = ref(today()),
  returning = ref<Loan | null>(null),
  bookQuery = ref("");
const person = ref({ name: "", phone: "", email: "", archived: false });
async function run(fn: () => Promise<void>) {
  error.value = "";
  busy.value = true;
  try {
    await fn();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function load() {
  const params = new URLSearchParams();
  if (state.value) params.set("state", state.value);
  if (filterPerson.value) params.set("person_id", String(filterPerson.value));
  loans.value = await api<Loan[]>("/loans?" + params);
  people.value = await api<Person[]>("/people");
}
async function searchCopies() {
  const data = await api<{ items: Book[] }>(
    "/books?available=true&q=" + encodeURIComponent(bookQuery.value),
  );
  books.value = data.items;
}
async function openLoan() {
  await run(async () => {
    loanOpen.value = true;
    await searchCopies();
  });
}
async function saveLoan() {
  await run(async () => {
    await post("/loans", {
      copy_id: copyId.value,
      person_id: personId.value,
      started_on: start.value,
      due_on: due.value || null,
    });
    loanOpen.value = false;
    copyId.value = null;
    await load();
  });
}
async function savePerson() {
  await run(async () => {
    const response = await api<{ id: number }>(
      editingPerson.value ? "/people/" + editingPerson.value : "/people",
      {
        method: editingPerson.value ? "PUT" : "POST",
        body: JSON.stringify(person.value),
      },
    );
    personId.value = response.id;
    personOpen.value = false;
    await load();
  });
}
function editPerson(p?: Person) {
  editingPerson.value = p?.id || null;
  person.value = p
    ? { name: p.name, phone: p.phone, email: p.email, archived: p.archived }
    : { name: "", phone: "", email: "", archived: false };
  personOpen.value = true;
}
async function finish() {
  if (!returning.value) return;
  await run(async () => {
    await post("/loans/" + returning.value!.id + "/return", {
      returned_on: returnDate.value,
    });
    returning.value = null;
    await load();
  });
}
async function loss(loan: Loan) {
  if (
    !confirm(
      "Encerrar por perda e dar baixa no exemplar? Não será registrada devolução.",
    )
  )
    return;
  await run(async () => {
    await post("/copies/" + loan.copy_id + "/retire", { reason: "lost" });
    await load();
  });
}
onMounted(() => run(load));
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">HISTÓRIAS COMPARTILHADAS</div>
      <h1>Empréstimos</h1>
      <p class="muted">Saiba com quem está cada exemplar.</p>
    </div>
    <Button
      label="Novo empréstimo"
      icon="pi pi-plus"
      class="primary"
      @click="openLoan"
    />
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div class="toolbar">
    <Select
      v-model="state"
      :options="[
        { label: 'Em aberto', value: 'open' },
        { label: 'Devolvidos', value: 'returned' },
        { label: 'Perdidos', value: 'lost' },
        { label: 'Todo o histórico', value: '' },
      ]"
      option-label="label"
      option-value="value"
      aria-label="Situação dos empréstimos"
      @change="run(load)"
    /><Select
      v-model="filterPerson"
      :options="people"
      option-label="name"
      option-value="id"
      show-clear
      placeholder="Todas as pessoas"
      aria-label="Filtrar por pessoa"
      @change="run(load)"
    /><Button label="Cadastrar pessoa" text @click="editPerson()" /><Button
      v-if="filterPerson"
      label="Editar pessoa"
      text
      @click="editPerson(people.find((p) => p.id === filterPerson))"
    />
  </div>
  <div v-if="!loans.length" class="empty">
    <i class="pi pi-arrow-up-right" />Nenhum empréstimo nesta consulta.
  </div>
  <div v-else class="panel">
    <div v-for="loan in loans" :key="loan.id" class="loan-row">
      <div>
        <b>{{ loan.title }}</b>
        <div class="muted">
          #{{ loan.copy_number }} · {{ loan.person_name }}
        </div>
        <div class="muted">
          Emprestado: {{ loan.started_on }} · Previsão: {{ loan.due_on }}
        </div>
        <span v-if="loan.overdue" class="status warn">Em atraso</span
        ><span v-if="loan.returned_on" class="status"
          >Devolvido: {{ loan.returned_on }}</span
        ><span v-if="loan.state === 'lost'" class="status warn"
          >Encerrado por perda</span
        >
      </div>
      <div v-if="loan.state === 'open'" class="actions">
        <Button
          label="Devolver"
          size="small"
          @click="
            returning = loan;
            returnDate = today();
          "
        /><Button label="Perda" size="small" text @click="loss(loan)" />
      </div>
    </div>
  </div>
  <Dialog
    v-model:visible="loanOpen"
    modal
    header="Novo empréstimo"
    :style="{ width: '560px' }"
    ><p v-if="error" class="error">{{ error }}</p>
    <form class="fields" @submit.prevent="saveLoan">
      <label
        >Pessoa *<Select
          v-model="personId"
          :options="people.filter((p) => !p.archived)"
          option-label="name"
          option-value="id"
          filter
          placeholder="Selecione"
          required /></label
      ><Button
        label="Cadastrar outra pessoa"
        text
        @click="editPerson()"
      /><label
        >Buscar livro<InputText
          v-model="bookQuery"
          @input="run(searchCopies)" /></label
      ><label
        >Exemplar disponível *<Select
          v-model="copyId"
          :options="
            books.flatMap((b) =>
              (b.copies || [])
                .filter((c) => c.state === 'active' && !c.on_loan)
                .map((c) => ({ id: c.id, name: b.title + ' · #' + c.number })),
            )
          "
          option-label="name"
          option-value="id"
          placeholder="Selecione"
          required /></label
      ><label
        >Data do empréstimo *<InputText
          type="date"
          v-model="start"
          required /></label
      ><label
        >Devolução prevista<InputText type="date" v-model="due" /><small
          class="muted"
          >Em branco, usamos um mês após o empréstimo.</small
        ></label
      ><Button
        type="submit"
        label="Registrar empréstimo"
        class="primary"
        :disabled="!personId || !copyId"
        :loading="busy"
      /></form
  ></Dialog>
  <Dialog
    v-model:visible="personOpen"
    modal
    :header="editingPerson ? 'Editar pessoa' : 'Cadastrar pessoa'"
    :style="{ width: '480px' }"
    ><p v-if="error" class="error">{{ error }}</p>
    <form class="fields" @submit.prevent="savePerson">
      <label>Nome *<InputText v-model="person.name" required /></label
      ><label
        >Telefone *<InputText
          v-model="person.phone"
          type="tel"
          required /></label
      ><label>E-mail<InputText v-model="person.email" type="email" /></label
      ><label v-if="editingPerson"
        ><span
          ><input type="checkbox" v-model="person.archived" /> Arquivada</span
        ></label
      ><Button type="submit" label="Salvar pessoa" :loading="busy" /></form
  ></Dialog>
  <Dialog
    :visible="!!returning"
    modal
    header="Registrar devolução"
    @update:visible="returning = null"
    ><form class="fields" @submit.prevent="finish">
      <p v-if="error" class="error">{{ error }}</p>
      <label
        >Data efetiva da devolução<InputText
          type="date"
          v-model="returnDate"
          required /></label
      ><Button
        type="submit"
        label="Confirmar devolução"
        :loading="busy"
      /></form
  ></Dialog>
</template>
