import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, nextTick } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LibraryMembers from "../src/pages/LibraryMembers.vue";
import { api } from "../src/api";

vi.mock("vue-router", () => ({ useRoute: () => ({ params: { libraryId: "7" } }) }));
vi.mock("../src/api", () => ({ api: vi.fn() }));

const ButtonStub = defineComponent({
  props: ["label", "disabled", "loading"],
  emits: ["click"],
  template:
    '<button :disabled="disabled || loading" @click="$emit(\'click\')">{{ label }}</button>',
});

const InputTextStub = defineComponent({
  props: ["id", "modelValue", "readonly"],
  template: '<input :id="id" :value="modelValue" :readonly="readonly" />',
});

function mountPage() {
  return mount(LibraryMembers, { global: { stubs: { Button: ButtonStub, InputText: InputTextStub } } });
}

const directory = {
  can_manage: true,
  current_membership: {
    user_id: 1,
    name: "Admin",
    email: "admin@example.com",
    role: "admin",
    joined_at: null,
    is_current_user: true,
    can_change_role: false,
    can_remove: false,
    can_leave: false,
  },
  members: [
    {
      user_id: 2,
      name: "Outro admin",
      email: "other@example.com",
      role: "admin",
      joined_at: null,
      is_current_user: false,
      can_change_role: true,
      can_remove: true,
      can_leave: false,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "/members") return directory as never;
    if (path === "/invites") return [] as never;
    return {} as never;
  });
});

describe("LibraryMembers", () => {
  it("keeps a shared participation invite available for viewing and manual copy", async () => {
    const inviteUrl = "https://julib.example/convites/aceitar#secret-token";
    const share = vi.fn().mockResolvedValue(undefined);
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { share, clipboard: { writeText } });
    vi.mocked(api).mockImplementation(async (path, options) => {
      if (path === "/members") return directory as never;
      if (path === "/invites" && options?.method === "POST")
        return { invite_url: inviteUrl } as never;
      if (path === "/invites") return [] as never;
      return {} as never;
    });
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.findAll("button").find((button) => button.text() === "Criar link de convite")!.trigger("click");
    await flushPromises();

    expect(share).toHaveBeenCalledWith({ title: "Convite para biblioteca", url: inviteUrl });
    expect(wrapper.get("#invite-link").element.getAttribute("value")).toBe(inviteUrl);
    await wrapper.findAll("button").find((button) => button.text() === "Copiar link")!.trigger("click");
    expect(writeText).toHaveBeenCalledWith(inviteUrl);
    expect(wrapper.get('[role="status"]').text()).toContain("Link copiado");
    await wrapper.findAll("button").find((button) => button.text() === "Fechar")!.trigger("click");
    expect(wrapper.find("#invite-link").exists()).toBe(false);
  });

  it("confirms before demoting an administrator", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.findAll("button").find((button) => button.text() === "Tornar membro")!.trigger("click");

    expect(window.confirm).toHaveBeenCalledWith(
      "Confirma rebaixar Outro admin de administrador para membro?",
    );
    expect(api).not.toHaveBeenCalledWith(
      "/members/2/role",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("disables the member actions while the request is pending and reports success", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let resolveChange!: (value: unknown) => void;
    vi.mocked(api).mockImplementation((path) => {
      if (path === "/members") return Promise.resolve(directory) as never;
      if (path === "/invites") return Promise.resolve([]) as never;
      if (path === "/members/2/role")
        return new Promise((resolve) => (resolveChange = resolve)) as never;
      return Promise.resolve({}) as never;
    });
    const wrapper = mountPage();
    await flushPromises();
    const roleButton = wrapper.findAll("button").find((button) => button.text() === "Tornar membro");
    const pending = roleButton!.trigger("click");
    await nextTick();

    expect(roleButton!.element.disabled).toBe(true);

    resolveChange({});
    await pending;
    await flushPromises();
    expect(wrapper.get('[role="status"]').text()).toContain("Papel de Outro admin atualizado.");
  });

  it("reports action errors clearly", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(api).mockImplementation(async (path) => {
      if (path === "/members") return directory as never;
      if (path === "/invites") return [] as never;
      throw new Error("A biblioteca precisa manter pelo menos um administrador.");
    });
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.findAll("button").find((button) => button.text() === "Tornar membro")!.trigger("click");
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain("A biblioteca precisa manter pelo menos um administrador.");
  });
});
