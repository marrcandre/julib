import { it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import SourceAttribution from "../src/components/SourceAttribution.vue";
import BookCredits from "../src/components/BookCredits.vue";
it("omits optional provider branding without changing their stored provenance", () => {
  for (const name of ["Open Library", "BrasilAPI (CBL)"])
    expect(
      mount(SourceAttribution, { props: { name, url: "https://example.com" } })
        .find("a")
        .exists(),
    ).toBe(false);
});
it("labels Google metadata separately and avoids duplicate volume credits", () => {
  const w = mount(BookCredits, {
    props: {
      item: {
        attribution_name: "Google Books",
        attribution_url: "https://books.google.com/books?id=1",
        metadata_attribution_name: "Google Books",
        metadata_attribution_url: "https://books.google.com/books?id=1",
      },
    },
  });
  expect(w.findAll("a")).toHaveLength(1);
  expect(w.text()).toContain("Dados bibliográficos:");
  expect(w.find("a").attributes("aria-label")).toBe(
    "Fonte dos dados: Google Books",
  );
});
it("credits a Google image independently when metadata has another origin", () => {
  const w = mount(BookCredits, {
    props: {
      item: {
        attribution_name: "Google Books",
        attribution_url: "https://books.google.com/books?id=1",
      },
    },
  });
  expect(w.text()).toContain("Capa:");
  expect(w.find("a").attributes("aria-label")).toBe(
    "Fonte da capa: Google Books",
  );
});

it("catalog credits keep only compact deduplicated links without repeated labels", () => {
  const w = mount(BookCredits, {
    props: {
      compact: true,
      item: {
        metadata_attribution_name: "Google Books",
        metadata_attribution_url: "https://books.google.com/books?id=1",
        attribution_url: "https://books.google.com/books?id=1",
      },
    },
  });
  expect(w.findAll("a")).toHaveLength(1);
  expect(w.text()).toBe("↗");
  expect(w.find("img").exists()).toBe(false);
  expect(w.find("a").attributes("aria-label")).toBe(
    "Ver fonte no Google Books",
  );
});
