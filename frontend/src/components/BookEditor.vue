<script setup lang="ts">
import { ref, computed, onUnmounted, watch } from "vue";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import InputNumber from "primevue/inputnumber";
import MultiSelect from "primevue/multiselect";
import { api, post, type Book, type Tag } from "../api";
import SourceAttribution from "./SourceAttribution.vue";
const props = defineProps<{ book: Book; tags: Tag[] }>();
const emit = defineEmits<{
  saved: [book: Book];
  cancel: [];
  dirty: [value: boolean];
  busy: [value: boolean];
  tagCreated: [tag: Tag];
}>();
const form = ref({
  title: props.book.title,
  authors: props.book.authors.join("; "),
  isbn: props.book.isbn,
  publisher: props.book.publisher,
  edition: props.book.edition,
  year: props.book.year,
  language: props.book.language,
  page_count: props.book.page_count ?? null,
  cover_url: props.book.cover_url,
  source: props.book.source,
  source_id: props.book.source_id,
  tag_ids: props.book.tags.map((t) => t.id),
});
const initial = JSON.stringify(form.value),
  tags = ref([...props.tags]),
  newTag = ref("");
const file = ref<File | null>(null),
  localUrl = ref(""),
  uploadedId = ref<string | null>(null),
  error = ref(""),
  busy = ref(false),
  fileInput = ref<HTMLInputElement>();
const preview = computed(() => localUrl.value || form.value.cover_url);
const dirty = computed(
  () => !!file.value || JSON.stringify(form.value) !== initial,
);
watch(dirty, (value) => emit("dirty", value), { immediate: true });
function clearFile() {
  if (localUrl.value) URL.revokeObjectURL(localUrl.value);
  localUrl.value = "";
  file.value = null;
  uploadedId.value = null;
}
function selectFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const selected = input.files?.[0];
  input.value = "";
  if (!selected) return;
  error.value = "";
  if (
    !["image/jpeg", "image/png", "image/webp"].includes(selected.type) ||
    selected.size > 5 * 1024 * 1024
  ) {
    error.value = "Escolha uma imagem JPG, PNG ou WebP de até 5 MB.";
    return;
  }
  clearFile();
  file.value = selected;
  localUrl.value = URL.createObjectURL(selected);
}
function manualUrl() {
  clearFile();
}
async function addTag() {
  if (!newTag.value.trim()) return;
  busy.value = true;
  emit("busy", true);
  error.value = "";
  try {
    const tag = await post<Tag>("/tags", { name: newTag.value.trim() });
    tags.value.push(tag);
    emit("tagCreated", tag);
    form.value.tag_ids.push(tag.id);
    newTag.value = "";
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
    emit("busy", false);
  }
}
async function save() {
  if (busy.value) return;
  busy.value = true;
  emit("busy", true);
  error.value = "";
  try {
    if (file.value && !uploadedId.value) {
      const signed = await post<Record<string, string>>("/media/sign");
      const body = new FormData();
      for (const [key, value] of Object.entries(signed))
        if (key !== "cloud_name") body.append(key, String(value));
      body.append("file", file.value);
      const response = await fetch(
        `https://api.cloudinary.com/v1_1/${signed.cloud_name}/image/upload`,
        { method: "POST", body },
      );
      if (!response.ok)
        throw new Error(
          "Não foi possível enviar a capa. Seus dados continuam em edição.",
        );
      const data = await response.json();
      if (typeof data.public_id !== "string" || !data.public_id)
        throw new Error("Resposta inválida ao enviar a capa.");
      uploadedId.value = data.public_id;
    }
    const saved = await api<Book>("/books/" + props.book.id, {
      method: "PUT",
      body: JSON.stringify({
        ...form.value,
        authors: form.value.authors
          .split(";")
          .map((a) => a.trim())
          .filter(Boolean),
        cover_public_id: uploadedId.value,
      }),
    });
    emit("saved", saved);
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    busy.value = false;
    emit("busy", false);
  }
}
onUnmounted(clearFile);
</script>
<template>
  <form class="book-editor" @submit.prevent="save">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <fieldset :disabled="busy" class="book-editor-fields">
      <div class="book-detail-summary book-edit-summary">
        <div class="book-cover-editor">
          <img
            v-if="preview"
            class="book-detail-cover"
            :src="preview"
            :alt="file ? 'Prévia da capa selecionada' : 'Capa atual'"
            referrerpolicy="no-referrer"
          />
          <div v-else class="book-detail-cover book-detail-placeholder">
            <i class="pi pi-book" aria-hidden="true" /><span>Sem capa</span>
          </div>
          <div class="book-cover-controls">
            <Button
              type="button"
              label="Trocar capa"
              icon="pi pi-image"
              outlined
              @click="fileInput?.click()"
            />
            <input
              ref="fileInput"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              aria-label="Arquivo da nova capa"
              hidden
              @change="selectFile"
            />
            <Button
              v-if="file"
              type="button"
              label="Desfazer troca da capa"
              text
              size="small"
              @click="clearFile"
            />
            <small class="muted">JPG, PNG ou WebP · até 5 MB</small>
            <details class="book-cover-url">
              <summary>Usar URL de imagem</summary>
              <label
                >URL da capa (HTTPS)<InputText
                  v-model="form.cover_url"
                  @update:model-value="manualUrl"
              /></label>
            </details>
            <SourceAttribution
              v-if="
                !file &&
                form.cover_url === book.cover_url &&
                book.attribution_url !== book.metadata_attribution_url
              "
              :name="book.attribution_name"
              :url="book.attribution_url"
            />
          </div>
        </div>
        <div>
          <h1>Editar livro</h1>
          <p class="muted">
            Dados desta edição. Localização e aquisição pertencem a cada
            exemplar.
          </p>
          <div class="book-edit-grid">
            <label class="book-edit-wide"
              >Título *<InputText v-model="form.title" required maxlength="300"
            /></label>
            <label class="book-edit-wide"
              >Autores *<InputText v-model="form.authors" required /><small
                class="muted"
                >Separe os autores por ponto e vírgula.</small
              ></label
            >
            <label>ISBN<InputText v-model="form.isbn" /></label
            ><label
              >Editora<InputText v-model="form.publisher" maxlength="200"
            /></label>
            <label
              >Edição<InputText v-model="form.edition" maxlength="100" /></label
            ><label
              >Ano de publicação<InputText v-model="form.year" maxlength="20"
            /></label>
            <label
              >Idioma<InputText v-model="form.language" maxlength="50" /></label
            ><label
              >Número de páginas<InputNumber
                v-model="form.page_count"
                :min="1"
                :max="2147483647"
                :use-grouping="false"
                :max-fraction-digits="0"
                input-id="detail-page-count"
            /></label>
            <label class="book-edit-wide"
              >Tags<MultiSelect
                :disabled="busy"
                v-model="form.tag_ids"
                :options="tags"
                option-label="name"
                option-value="id"
                display="chip"
            /></label>
            <div class="book-edit-wide actions">
              <InputText
                v-model="newTag"
                placeholder="Nova tag"
                aria-label="Nova tag"
              /><Button
                type="button"
                label="Criar tag"
                text
                :disabled="!newTag.trim()"
                @click="addTag"
              />
            </div>
          </div>
        </div>
      </div>
    </fieldset>
    <SourceAttribution
      :name="book.metadata_attribution_name"
      :url="book.metadata_attribution_url"
      kind="metadata"
    />
    <div class="book-save-bar">
      <p class="muted">Dados e capa serão salvos juntos.</p>
      <div class="actions">
        <Button
          label="Cancelar"
          type="button"
          outlined
          :disabled="busy"
          @click="emit('cancel')"
        /><Button
          label="Salvar alterações"
          type="submit"
          icon="pi pi-check"
          class="primary"
          :disabled="busy"
          :loading="busy"
        />
      </div>
    </div>
  </form>
</template>
