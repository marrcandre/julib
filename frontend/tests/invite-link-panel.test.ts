import { mount } from "@vue/test-utils";
import { defineComponent } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import InviteLinkPanel from "../src/components/InviteLinkPanel.vue";

const inviteUrl = "https://julib.example/convites/aceitar#private-token";

const ButtonStub = defineComponent({
  props: ["label", "disabled", "loading", "ariaExpanded"],
  emits: ["click"],
  template:
    '<button :disabled="disabled || loading" :aria-expanded="ariaExpanded" @click="$emit(\'click\')">{{ label }}</button>',
});

const InputTextStub = defineComponent({
  props: ["id", "modelValue", "readonly"],
  template: '<input :id="id" :value="modelValue" :readonly="readonly" />',
});

function mountPanel() {
  return mount(InviteLinkPanel, {
    props: { url: inviteUrl },
    global: { stubs: { Button: ButtonStub, InputText: InputTextStub } },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("InviteLinkPanel", () => {
  it("shows the generated URL with its token in the fragment", () => {
    const wrapper = mountPanel();
    const input = wrapper.get("#invite-link");
    const parsed = new URL(input.attributes("value")!);

    expect(input.attributes("readonly")).toBeDefined();
    expect(parsed.hash).toBe("#private-token");
    expect(parsed.search).toBe("");
  });

  it("shows and hides the link without disabling manual copy", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const wrapper = mountPanel();
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "Ocultar link")!
      .trigger("click");

    expect(wrapper.find("#invite-link").exists()).toBe(false);
    expect(wrapper.text()).toContain("Copiar link");
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "Copiar link")!
      .trigger("click");
    expect(writeText).toHaveBeenCalledWith(inviteUrl);
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "Mostrar link")!
      .trigger("click");
    expect(wrapper.find("#invite-link").exists()).toBe(true);
  });

  it("copies manually and reports success without hiding the link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const wrapper = mountPanel();

    await wrapper
      .findAll("button")
      .find((button) => button.text() === "Copiar link")!
      .trigger("click");

    expect(writeText).toHaveBeenCalledWith(inviteUrl);
    expect(wrapper.get('[role="status"]').text()).toContain("Link copiado");
    expect(wrapper.find("#invite-link").exists()).toBe(true);
  });

  it("reports clipboard failures and leaves the URL available for manual selection", async () => {
    vi.stubGlobal("navigator", {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });
    const wrapper = mountPanel();

    await wrapper
      .findAll("button")
      .find((button) => button.text() === "Copiar link")!
      .trigger("click");

    expect(wrapper.get('[role="alert"]').text()).toContain(
      "Selecione o link e copie manualmente",
    );
    expect(wrapper.find("#invite-link").exists()).toBe(true);
  });

  it("keeps the link visible and explains manual copy when Clipboard API is unavailable", async () => {
    vi.stubGlobal("navigator", {});
    const wrapper = mountPanel();

    await wrapper
      .findAll("button")
      .find((button) => button.text() === "Copiar link")!
      .trigger("click");

    expect(wrapper.get('[role="alert"]').text()).toContain(
      "Selecione o link e copie manualmente",
    );
    expect(wrapper.get("#invite-link").attributes("value")).toBe(inviteUrl);
  });

  it("closes and clears only through its close event, without persisting the token", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const wrapper = mountPanel();
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "Fechar")!
      .trigger("click");

    expect(wrapper.emitted("close")).toHaveLength(1);
    expect(setItem).not.toHaveBeenCalled();
  });
});
