(() => {
  const defaults = () => ({ x: 50, y: 50, zoom: 1 });
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  function setup(editor) {
    const input = document.getElementById(editor.dataset.inputId);
    const field = document.getElementById(
      input.id.replace(/photo$/, "photo_crop"),
    );
    const clear =
      document.getElementById(`${input.id}_clear`) ||
      editor.querySelector('input[type="checkbox"]');
    const preview = editor.querySelector("[data-preview]");
    const previewCanvas = editor.querySelector("[data-preview-canvas]");
    const canvas = editor.querySelector("[data-crop-canvas]");
    const dialog = editor.querySelector("dialog");
    const controls = [...editor.querySelectorAll("[data-control]")];
    const status = editor.querySelector("[data-status]");
    let current;
    try {
      current = { ...defaults(), ...JSON.parse(field.value || "{}") };
    } catch {
      current = defaults();
    }
    let draft = { ...current };
    let image = null;
    let objectUrl = null;
    let loadId = 0;
    let drag = null;

    function draw(target, crop) {
      const ctx = target.getContext("2d");
      ctx.clearRect(0, 0, target.width, target.height);
      if (!image) return;
      const side =
        Math.min(image.naturalWidth, image.naturalHeight) / crop.zoom;
      const left = ((image.naturalWidth - side) * crop.x) / 100;
      const top = ((image.naturalHeight - side) * crop.y) / 100;
      ctx.drawImage(
        image,
        left,
        top,
        side,
        side,
        0,
        0,
        target.width,
        target.height,
      );
    }

    function renderDraft() {
      draw(canvas, draft);
      controls.forEach((control) => {
        control.value = draft[control.dataset.control];
        const key = control.dataset.control;
        const side =
          Math.min(image.naturalWidth, image.naturalHeight) / draft.zoom;
        control.disabled =
          key === "x"
            ? image.naturalWidth <= side
            : key === "y"
              ? image.naturalHeight <= side
              : false;
      });
      editor.querySelector('[data-output="zoom"]').textContent =
        `${draft.zoom.toFixed(2).replace(".", ",")}×`;
    }

    function open() {
      if (!image || clear?.checked) return;
      draft = { ...current };
      renderDraft();
      dialog.showModal();
    }

    async function load(url, openAfter = false) {
      const id = ++loadId;
      image = null;
      preview.hidden = true;
      status.textContent = url
        ? "Carregando prévia…"
        : "Selecione uma foto para ajustar o enquadramento.";
      if (!url) return;
      const next = new Image();
      next.src = url;
      try {
        await next.decode();
        if (id !== loadId) return;
        image = next;
        preview.hidden = Boolean(clear?.checked);
        draw(previewCanvas, current);
        status.textContent = "";
        if (openAfter) open();
      } catch {
        if (id === loadId)
          status.textContent =
            "Não foi possível abrir a foto. Selecione uma imagem JPEG, PNG ou WebP válida.";
      }
    }

    editor.querySelector("[data-edit]").addEventListener("click", open);
    editor.querySelectorAll("[data-cancel]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });
    dialog.addEventListener("click", (event) => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      if (
        event.clientX < rect.left ||
        event.clientX > rect.right ||
        event.clientY < rect.top ||
        event.clientY > rect.bottom
      )
        dialog.close();
    });
    editor.querySelector("[data-reset]").addEventListener("click", () => {
      draft = defaults();
      renderDraft();
    });
    controls.forEach((control) =>
      control.addEventListener("input", () => {
        draft[control.dataset.control] = Number(control.value);
        renderDraft();
      }),
    );
    editor.querySelector("[data-apply]").addEventListener("click", () => {
      current = { ...draft };
      field.value = JSON.stringify(current);
      field.dispatchEvent(new Event("change", { bubbles: true }));
      draw(previewCanvas, current);
      status.textContent =
        "Enquadramento aplicado. Salve o cadastro para publicar o ajuste.";
      dialog.close();
    });
    canvas.addEventListener("pointerdown", (event) => {
      if (!image || !event.isPrimary || event.button !== 0) return;
      canvas.setPointerCapture(event.pointerId);
      drag = {
        id: event.pointerId,
        x: event.clientX,
        y: event.clientY,
        crop: { ...draft },
      };
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      const side =
        Math.min(image.naturalWidth, image.naturalHeight) / draft.zoom;
      const ratio = side / canvas.getBoundingClientRect().width;
      const overflowX = image.naturalWidth - side;
      const overflowY = image.naturalHeight - side;
      draft.x = overflowX
        ? clamp(
            drag.crop.x - ((event.clientX - drag.x) * ratio * 100) / overflowX,
            0,
            100,
          )
        : 50;
      draft.y = overflowY
        ? clamp(
            drag.crop.y - ((event.clientY - drag.y) * ratio * 100) / overflowY,
            0,
            100,
          )
        : 50;
      renderDraft();
    });
    ["pointerup", "pointercancel", "lostpointercapture"].forEach((event) => {
      canvas.addEventListener(event, () => {
        drag = null;
      });
    });
    input.addEventListener("change", () => {
      if (!input.files.length) return;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(input.files[0]);
      if (clear) clear.checked = false;
      current = defaults();
      field.value = JSON.stringify(current);
      load(objectUrl, true);
    });
    clear?.addEventListener("change", () => {
      preview.hidden = clear.checked || !image;
      status.textContent = clear.checked
        ? "A foto será removida ao salvar o cadastro."
        : "";
      if (clear.checked && dialog.open) dialog.close();
    });
    window.addEventListener("pagehide", () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    });
    load(editor.dataset.initialUrl);
  }

  function init() {
    document.querySelectorAll("[data-photo-editor]").forEach(setup);
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
  else init();
})();
