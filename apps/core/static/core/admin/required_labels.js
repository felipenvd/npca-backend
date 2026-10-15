"use strict";

(() => {
  function update(form) {
    form.querySelectorAll("[data-required-controller]").forEach((marker) => {
      const controller = form.elements.namedItem(
        marker.dataset.requiredController,
      );
      if (!controller) return;
      const values = marker.dataset.requiredValues;
      marker.hidden =
        values === "unchecked"
          ? controller.checked
          : !values.split(",").includes(controller.value);
    });
  }

  function initialize() {
    document.querySelectorAll("form").forEach(update);
    document.addEventListener("input", (event) => {
      if (event.target.form) update(event.target.form);
    });
    document.addEventListener("change", (event) => {
      if (event.target.form) update(event.target.form);
    });
    document.addEventListener("formset:added", (event) => {
      const form = event.target.closest("form");
      if (form) update(form);
    });
    document.addEventListener("reset", (event) => {
      if (event.target.tagName === "FORM")
        setTimeout(() => update(event.target), 0);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
})();
