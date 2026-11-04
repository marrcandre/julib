<script setup lang="ts">
import { ref, onMounted } from "vue";
import Button from "primevue/button";
import Dialog from "primevue/dialog";
import InputText from "primevue/inputtext";
import Select from "primevue/select";
import { api, locationLabel, type Location } from "../api";
const locations = ref<Location[]>([]),
  error = ref(""),
  opened = ref(false),
  busy = ref(false),
  editing = ref<number | null>(null),
  name = ref(""),
  parent = ref<number | null>(null);
async function load() {
  locations.value = await api<Location[]>("/locations");
}
function edit(loc?: Location) {
  editing.value = loc?.id || null;
  name.value = loc?.name || "";
  parent.value = loc?.parent_id || null;
  opened.value = true;
}
async function save() {
  busy.value = true;
  error.value = "";
  try {
    await api(editing.value ? "/locations/" + editing.value : "/locations", {
      method: editing.value ? "PUT" : "POST",
      body: JSON.stringify({ name: name.value, parent_id: parent.value }),
    });
    await load();
    opened.value = false;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
  }
}
async function remove(loc: Location) {
  if (
    !confirm(
      "Excluir este local? Ele precisa estar sem exemplares e sublocais.",
    )
  )
    return;
  try {
    await api("/locations/" + loc.id, { method: "DELETE" });
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
}
onMounted(async () => {
  try {
    await load();
  } catch (e) {
    error.value = (e as Error).message;
  }
});
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">UM LUGAR PARA CADA LIVRO</div>
      <h1>Localizações</h1>
      <p class="muted">Da casa à prateleira, organize do seu jeito.</p>
    </div>
    <Button
      label="Novo local"
      icon="pi pi-plus"
      class="primary"
      @click="edit()"
    />
  </div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div v-if="!locations.length" class="empty">
    <i class="pi pi-map-marker" />Comece criando Casa ou Trabalho. Depois
    acrescente cômodos, estantes e prateleiras.
  </div>
  <div v-else class="panel">
    <div
      v-for="loc in [...locations].sort((a, b) =>
        locationLabel(locations, a.id).localeCompare(
          locationLabel(locations, b.id),
        ),
      )"
      :key="loc.id"
      class="loan-row"
    >
      <span
        ><i class="pi pi-map-marker" />
        {{ locationLabel(locations, loc.id) }}</span
      >
      <div class="actions">
        <Button label="Editar" text size="small" @click="edit(loc)" /><Button
          label="Excluir"
          text
          size="small"
          severity="danger"
          @click="remove(loc)"
        />
      </div>
    </div>
  </div>
  <Dialog
    v-model:visible="opened"
    modal
    :header="editing ? 'Editar local' : 'Novo local'"
    :style="{ width: '480px' }"
    ><p v-if="error" class="error">{{ error }}</p>
    <form class="fields" @submit.prevent="save">
      <label>Nome *<InputText v-model="name" required /></label
      ><label
        >Dentro de<Select
          v-model="parent"
          :options="
            locations
              .filter((l) => l.id !== editing)
              .map((l) => ({ id: l.id, name: locationLabel(locations, l.id) }))
          "
          option-label="name"
          option-value="id"
          placeholder="Local principal"
          show-clear /></label
      ><Button type="submit" label="Salvar local" :loading="busy" /></form
  ></Dialog>
</template>
