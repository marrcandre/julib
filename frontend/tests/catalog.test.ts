import { it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import BookCard from "../src/components/BookCard.vue";
import { canonicalIsbn } from "../src/isbn";
it("normalizes ISBN-10 to matching ISBN-13 for duplicate confirmation", () => {
  expect(canonicalIsbn("0-261-10221-4")).toBe("9780261102217");
  expect(canonicalIsbn("9780261102217")).toBe("9780261102217");
});
it("shows public tags and availability without copy details", () => {
  const wrapper = mount(BookCard, {
    props: {
      book: {
        id: 1,
        title: "Livro",
        authors: ["Autor"],
        isbn: "",
        publisher: "",
        edition: "",
        year: "",
        language: "",
        cover_url: "",
        tags: [{ id: 1, name: "História" }],
        available: true,
        attribution_name: "",
        attribution_url: "",
      },
    },
  });
  expect(wrapper.text()).toContain("História");
  expect(wrapper.find('[aria-label="Disponível"]').exists()).toBe(false);
  expect(wrapper.find(".status").exists()).toBe(false);
});

it("accepts only valid book ISBN barcodes", async () => {
  const { isbnFromBarcode } = await import("../src/isbn");
  expect(isbnFromBarcode("9780261102217")).toBe("9780261102217");
  expect(isbnFromBarcode("0-261-10221-4")).toBe("9780261102217");
  for (const code of [
    "9780261102218",
    "7891234567895",
    "https://example.com",
    "1234",
  ])
    expect(isbnFromBarcode(code)).toBeNull();
});
