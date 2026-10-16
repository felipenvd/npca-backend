(() => {
  const clamp = (value) => Math.max(0, Math.min(100, Math.round(value)));
  const zoomPercent = (value) =>
    Math.max(100, Math.min(300, Math.round(Number(value))));

  function setup(editor) {
    if (editor.dataset.ready) return;
    editor.dataset.ready = "true";
    const form = editor.closest("form");
    const input = form.elements.namedItem("cover");
    const x = form.elements.namedItem("cover_position_x");
    const y = form.elements.namedItem("cover_position_y");
    const zoom = form.elements.namedItem("cover_zoom");
    const clear = form.elements.namedItem("cover-clear");
    const card = editor.querySelector("[data-cover-card]");
    const image = editor.querySelector("[data-cover-image]");
    const detail = editor.querySelector("[data-cover-detail]");
    const previews = editor.querySelector("[data-cover-previews]");
    const status = editor.querySelector("[data-cover-status]");
    const initialUrl = image.getAttribute("src");
    const outputs = [x, y, zoom].map((field) => {
      const output = document.createElement("output");
      output.className = "event-cover-position-value";
      output.htmlFor = field.id;
      field.after(output);
      return output;
    });
    let objectUrl = null;
    let loadId = 0;
    let loaded = false;
    let drag = null;

    function render() {
      editor.style.setProperty(
        "--cover-position",
        `${clamp(Number(x.value))}% ${clamp(Number(y.value))}%`,
      );
      editor.style.setProperty("--cover-zoom", zoomPercent(zoom.value));
      [x, y, zoom].forEach((field, index) => {
        outputs[index].value =
          `${field === zoom ? zoomPercent(field.value) : clamp(Number(field.value))}%`;
      });
      previews.hidden = !loaded || Boolean(clear?.checked);
    }

    async function load(url) {
      const id = ++loadId;
      loaded = false;
      render();
      if (!url) {
        image.removeAttribute("src");
        detail.removeAttribute("src");
        status.textContent = "Selecione uma imagem para visualizar as prévias.";
        return;
      }
      image.src = detail.src = url;
      status.textContent = "Carregando prévias…";
      try {
        await image.decode();
        if (id !== loadId) return;
        loaded = true;
        status.textContent = "";
        render();
      } catch {
        if (id === loadId)
          status.textContent =
            "Não foi possível abrir a imagem. Selecione um JPEG, PNG ou WebP válido.";
      }
    }

    [x, y, zoom].forEach((field) => field.addEventListener("input", render));
    card.addEventListener("pointerdown", (event) => {
      if (!loaded || !event.isPrimary || event.button !== 0) return;
      card.setPointerCapture(event.pointerId);
      drag = {
        id: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        positionX: Number(x.value),
        positionY: Number(y.value),
      };
    });
    card.addEventListener("pointermove", (event) => {
      if (!drag || drag.id !== event.pointerId) return;
      const rect = card.getBoundingClientRect();
      const scale =
        (zoomPercent(zoom.value) / 100) *
        Math.max(
          card.clientWidth / image.naturalWidth,
          card.clientHeight / image.naturalHeight,
        );
      const overflowX = image.naturalWidth * scale - card.clientWidth;
      const overflowY = image.naturalHeight * scale - card.clientHeight;
      const dx = ((event.clientX - drag.x) * card.clientWidth) / rect.width;
      const dy = ((event.clientY - drag.y) * card.clientHeight) / rect.height;
      x.value =
        overflowX > 0.5 ? clamp(drag.positionX - (dx * 100) / overflowX) : 50;
      y.value =
        overflowY > 0.5 ? clamp(drag.positionY - (dy * 100) / overflowY) : 50;
      [x, y].forEach((field) => {
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.dispatchEvent(new Event("change", { bubbles: true }));
      });
    });
    ["pointerup", "pointercancel", "lostpointercapture"].forEach((name) => {
      card.addEventListener(name, () => {
        drag = null;
      });
    });
    input.addEventListener("change", () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = input.files[0] ? URL.createObjectURL(input.files[0]) : null;
      if (objectUrl) {
        if (clear) clear.checked = false;
        x.value = y.value = 50;
        zoom.value = 100;
      }
      load(objectUrl || initialUrl);
    });
    clear?.addEventListener("change", () => {
      render();
      status.textContent = clear.checked
        ? "A imagem será removida ao salvar o cadastro."
        : "";
    });
    form.addEventListener("reset", () =>
      setTimeout(() => {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = null;
        load(initialUrl);
      }, 0),
    );
    window.addEventListener("pagehide", () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    });
    load(initialUrl);
  }

  function init() {
    document.querySelectorAll("[data-event-cover-editor]").forEach(setup);
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
  else init();
})();
