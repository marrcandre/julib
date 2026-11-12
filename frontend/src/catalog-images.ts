/** Returns a display-only Cloudinary URL, leaving all other image URLs intact. */
export function catalogCoverUrl(value: string, width = 300): string {
  if (!value || !Number.isSafeInteger(width) || width < 1) return value;
  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:" ||
      url.hostname !== "res.cloudinary.com" ||
      url.username ||
      url.password ||
      [...url.searchParams.keys()].some((key) =>
        /token|signature|credential|expires|auth|^sig$|^key$|^policy$/i.test(
          key,
        ),
      )
    )
      return value;
    const parts = url.pathname.split("/");
    const upload = parts.indexOf("upload");
    if (upload < 0 || upload !== 3 || !parts[upload + 1]) return value;
    const delivery = parts.slice(upload + 1);
    // Signed delivery URLs and non-image delivery types must remain untouched.
    if (
      delivery[0].startsWith("s--") ||
      ["private", "authenticated", "raw"].includes(delivery[0])
    )
      return value;
    if (
      /^(?:f|q|w|h|c|g|e|r|dpr|ar|b|l|t|u|so|du|ac|a)_[^/]+/.test(delivery[0])
    )
      return value;
    const assetIndex = delivery.findIndex((part) => /^v\d+$/.test(part));
    const transformEnd = assetIndex >= 0 ? assetIndex : 0;
    const existing = delivery.slice(0, transformEnd);
    const asset = delivery.slice(transformEnd);
    if (!asset.length || !asset[asset.length - 1].includes(".")) return value;
    const requested = `f_auto,q_auto,w_${width},c_limit`;
    const transforms = existing.length ? existing.join("/").split(",") : [];
    // Avoid overriding manually authored/quality transformations or repeating ours.
    if (transforms.some((item) => /^(f_|q_|w_|h_|c_)/.test(item))) return value;
    url.pathname = [...parts.slice(0, upload + 1), requested, ...delivery].join(
      "/",
    );
    return url.toString();
  } catch {
    return value;
  }
}
