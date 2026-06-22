const revealElements = document.querySelectorAll("[data-reveal]");

if ("IntersectionObserver" in window) {
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.18, rootMargin: "0px 0px -60px 0px" },
  );

  revealElements.forEach((element) => revealObserver.observe(element));
} else {
  revealElements.forEach((element) => element.classList.add("is-visible"));
}

const tiltElements = document.querySelectorAll("[data-tilt]");

tiltElements.forEach((element) => {
  element.addEventListener("pointermove", (event) => {
    const bounds = element.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width - 0.5;
    const y = (event.clientY - bounds.top) / bounds.height - 0.5;
    element.style.setProperty("--tilt-x", `${(-y * 5).toFixed(2)}deg`);
    element.style.setProperty("--tilt-y", `${(x * 6).toFixed(2)}deg`);
  });

  element.addEventListener("pointerleave", () => {
    element.style.setProperty("--tilt-x", "0deg");
    element.style.setProperty("--tilt-y", "0deg");
  });
});

const formatMegabytes = (bytes) =>
  `${(bytes / 1000000).toLocaleString("pt-BR", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  })} MB`;

const setDownloadText = (key, value) => {
  document.querySelectorAll(`[data-download-value="${key}"]`).forEach((element) => {
    element.textContent = value;
  });
};

const updateDownloadLinks = (kind, artifact) => {
  if (!artifact?.file) return;
  const cacheKey =
    kind === "mobile" && artifact.build
      ? `${artifact.version}-${artifact.build}`
      : artifact.version || "latest";

  document.querySelectorAll(`[data-download-link="${kind}"]`).forEach((link) => {
    link.href = `./downloads/${artifact.file}?v=${cacheKey}`;
    link.setAttribute("download", artifact.file);
  });
};

if (typeof fetch === "function") {
  fetch("./downloads/manifest.json")
    .then((response) => {
      if (!response.ok) throw new Error("manifest unavailable");
      return response.json();
    })
    .then((manifest) => {
      const { mobile, desktop } = manifest;
      document.documentElement.dataset.manifest = "loaded";

      if (mobile) {
        setDownloadText("mobile.version", mobile.version);
        setDownloadText("mobile.versionLabel", `App ${mobile.version}`);
        setDownloadText("mobile.size", formatMegabytes(mobile.size_bytes));
        setDownloadText("mobile.file", mobile.file);
        setDownloadText("mobile.sha256", mobile.sha256);
        updateDownloadLinks("mobile", mobile);
      }

      if (desktop) {
        setDownloadText("desktop.version", desktop.version);
        setDownloadText("desktop.versionLabel", `Companion ${desktop.version}`);
        setDownloadText("desktop.size", formatMegabytes(desktop.size_bytes));
        setDownloadText("desktop.file", desktop.file);
        setDownloadText("desktop.sha256", desktop.sha256);
        updateDownloadLinks("desktop", desktop);
      }
    })
    .catch(() => {
      document.documentElement.dataset.manifest = "static";
    });
} else {
  document.documentElement.dataset.manifest = "static";
}

document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
  anchor.addEventListener("click", (event) => {
    const target = document.querySelector(anchor.getAttribute("href"));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});
