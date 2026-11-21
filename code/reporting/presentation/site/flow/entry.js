// Preserve deep links while giving every chapter the same presentation host.
if (new URLSearchParams(location.search).has("embedded") && parent !== window) {
  document.documentElement.classList.add("flow-embedded", "flow-hold");
} else if (!new URLSearchParams(location.search).has("standalone")) {
  const part = location.pathname.match(/pt([1-4])(?:\.html)?$/)?.[1];
  if (part)
    location.replace(
      `./present.html#pt${part}/${location.hash.slice(1) || (part === "3" ? "gallery/b2" : "01")}`,
    );
}
