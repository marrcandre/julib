import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LibraryCreationInvites from "../src/pages/LibraryCreationInvites.vue";
import { api } from "../src/api";

vi.mock("../src/api", () => ({ api: vi.fn() }));

const owner = {
  user_id: 1,
  name: "Proprietário",
  email: "marco@example.com",
  avatar_url: "",
  technical: true,
  can_create_libraries: true,
  libraries: [],
  library: null,
  csrf: "csrf",
  catalog_view: "covers",
  cover_columns: 7,
};

const pendingInvite = {
  id: 9,
  email: "destino@example.com",
  created_at: "2026-11-17T12:00:00Z",
  expires_at: "2026-11-24T12:00:00Z",
  accepted_at: null,
  revoked_at: null,
  status: "pending",
  created_library: null,
};

const InputTextStub = defineComponent({
  props: ["modelValue", "id", "type", "readonly", "placeholder"],
  emits: ["update:modelValue", "focus"],
  template:
    '<input :id="id" :type="type || \'text\'" :value="modelValue" :readonly="readonly" :placeholder="placeholder" @input="$emit(\'update:modelValue\', $event.target.value)" @focus="$emit(\'focus\', $event)" />',
});

function mountPage(technical = true) {
  return mount(LibraryCreationInvites, {
    global: {
      provide: { session: ref(technical ? owner : { ...owner, technical: false }) },
      stubs: {
        Button: defineComponent({
          props: ["label", "disabled", "loading"],
          emits: ["click"],
          template:
            '<button :disabled="disabled || loading" @click="$emit(\'click\')">{{ label }}</button>',
        }),
        InputText: InputTextStub,
      },
    },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api).mockImplementation(async (path, options) => {
    if (path === "/library-creation-invites" && options?.method === "POST")
      return { invite_url: "https://julib.example/convites/criar#secret-token" } as never;
    if (path === "/library-creation-invites") return [pendingInvite] as never;
    return {} as never;
  });
});

describe("LibraryCreationInvites", () => {
  it("shows invite status and the library created from an accepted invite", async () => {
    vi.mocked(api).mockResolvedValueOnce([
      { ...pendingInvite, status: "accepted", created_library: { id: 23, name: "Minha estante" } },
    ] as never);
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.text()).toContain("Utilizado");
    expect(wrapper.text()).toContain("Minha estante");
  });

  it("creates an optional email-bound invite and displays its link once", async () => {
    vi.mocked(api).mockImplementation(async (path, options) => {
      if (path === "/library-creation-invites" && options?.method === "POST")
        return { invite_url: "https://julib.example/convites/criar#secret-token" } as never;
      return [] as never;
    });
    const wrapper = mountPage();
    await flushPromises();
    await wrapper.get('input[type="email"]').setValue("destino@example.com");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(api).toHaveBeenCalledWith(
      "/library-creation-invites",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ email: "destino@example.com" }) }),
    );
    expect(wrapper.get("#new-creation-invite-link").element.getAttribute("value")).toBe(
      "https://julib.example/convites/criar#secret-token",
    );
  });

  it("does not load invite data for a non-owner", async () => {
    const wrapper = mountPage(false);
    await flushPromises();

    expect(api).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Somente o proprietário");
  });
});
