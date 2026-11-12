import { describe, expect, it } from "vitest";
import { catalogCoverUrl } from "../src/catalog-images";

describe("catalog Cloudinary URLs", () => {
  it("adds bounded automatic transformations before a versioned asset", () => {
    expect(
      catalogCoverUrl(
        "https://res.cloudinary.com/exemplo/image/upload/v123/livros/capa.jpg",
      ),
    ).toBe(
      "https://res.cloudinary.com/exemplo/image/upload/f_auto,q_auto,w_300,c_limit/v123/livros/capa.jpg",
    );
  });

  it("handles unversioned assets and a configurable width", () => {
    expect(
      catalogCoverUrl(
        "https://res.cloudinary.com/exemplo/image/upload/livros/capa.jpg",
        600,
      ),
    ).toBe(
      "https://res.cloudinary.com/exemplo/image/upload/f_auto,q_auto,w_600,c_limit/livros/capa.jpg",
    );
  });

  it("preserves safe query parameters and fragments", () => {
    expect(
      catalogCoverUrl(
        "https://res.cloudinary.com/exemplo/image/upload/v123/capa.jpg?source=catalog#cover",
      ),
    ).toBe(
      "https://res.cloudinary.com/exemplo/image/upload/f_auto,q_auto,w_300,c_limit/v123/capa.jpg?source=catalog#cover",
    );
  });

  it("preserves already transformed, parameterized, signed, and external URLs", () => {
    const urls = [
      "https://res.cloudinary.com/exemplo/image/upload/f_auto,w_200/v123/livros/capa.jpg",
      "https://res.cloudinary.com/exemplo/image/upload/c_fill,w_200/livros/capa.jpg",
      "https://res.cloudinary.com/exemplo/image/upload/v123/livros/capa.jpg?token=abc",
      "https://res.cloudinary.com/exemplo/image/upload/s--signature--/v123/livros/capa.jpg",
      "https://books.google.com/books/content?id=abc",
      "",
      "invalid url",
    ];
    for (const url of urls) expect(catalogCoverUrl(url)).toBe(url);
  });
});
