import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, ref } from "vue";
import { beforeEach, expect, it, vi } from "vitest";
import LibraryCreationAccept from "../src/pages/LibraryCreationAccept.vue";
import { api } from "../src/api";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("vue-router", () => ({ useRouter: () => ({ replace }) }));
vi.mock("../src/api", () => ({ api: vi.fn(), setCsrf: vi.fn() }));

const user = {
  user_id: 7,
  name: "Convidada",
  email: "fora@example.com",
  avatar_url: "",
  technical: false,
  can_create_libraries: false,
  libraries: [],
  library: null,
  csrf: "csrf",
  catalog_view: "covers",
  cover_columns: 7,
};

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState({}, "", "/convites/criar");
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === "/library-creation-invites/pending")
      return { pending: true, email: "", expires_at: "2026-11-24T12:00:00Z" } as never;
    if (path === "/libraries/from-invite" && options?.method === "POST")
      return { id: 31, name: "Biblioteca nova", role: "admin" } as never;
    return {} as never;
  });
});

it("creates the invited library and sends the user to its catalog", async () => {
  const session = ref({ ...user });
  const wrapper = mount(LibraryCreationAccept, {
    global: {
      provide: { session },
      stubs: {
        Button: defineComponent({
          props: ["label", "disabled", "loading"],
          emits: ["click"],
          template:
            '<button :disabled="disabled || loading" @click="$emit(\'click\')">{{ label }}</button>',
        }),
        InputText: defineComponent({
          props: ["modelValue", "id"],
          emits: ["update:modelValue"],
          template:
            '<input :id="id" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        }),
      },
    },
  });
  await flushPromises();
  await wrapper.get("input").setValue("Biblioteca nova");
  await wrapper.get("form").trigger("submit");
  await flushPromises();

  expect(api).toHaveBeenCalledWith(
    "/libraries/from-invite",
    expect.objectContaining({ method: "POST", body: JSON.stringify({ name: "Biblioteca nova" }) }),
  );
  expect(session.value.libraries).toEqual([{ id: 31, name: "Biblioteca nova", role: "admin" }]);
  expect(replace).toHaveBeenCalledWith("/bibliotecas/31/livros");
});
