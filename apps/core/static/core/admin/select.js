"use strict";

(() => {
  const $ = django.jQuery;
  const language = {
    noResults: () => "Nenhum resultado encontrado",
    searching: () => "Buscando…",
    errorLoading: () => "Não foi possível carregar as opções.",
    loadingMore: () => "Carregando mais opções…",
    inputTooShort: ({ minimum, input }) =>
      `Digite mais ${minimum - input.length} caracteres para buscar.`,
  };
  $.fn.select2.defaults.set("language", language);

  function enhance(root) {
    root.querySelectorAll("select").forEach((select) => {
      // Remote autocompletes and permission lists keep their Django adapters.
      if (
        select.multiple ||
        select.name.includes("__prefix__") ||
        select.matches(
          ".admin-autocomplete, .unfold-admin-autocomplete, .select2-hidden-accessible",
        ) ||
        select.hidden ||
        select.style.display === "none"
      )
        return;

      const parent = select.parentElement;
      parent.classList.add("npca-select-host");
      const field = document.createElement("span");
      field.className = "npca-select-field";
      select.before(field);
      field.append(select);
      const picker = select.closest(".npca-picker");
      $(select).select2({
        theme: "admin-autocomplete",
        width: "100%",
        minimumResultsForSearch: picker
          ? select.getAttribute("aria-label") === "Ano"
            ? 0
            : Infinity
          : 10,
        language,
        dropdownAutoWidth: false,
        dropdownCssClass: picker ? "npca-picker-dropdown" : "",
      });
      if (picker) {
        $(select).on("select2:select.npcaPicker", () => {
          select.dispatchEvent(new Event("change", { bubbles: true }));
        });
        const selection = $(select).data("select2").$selection[0];
        selection.removeAttribute("aria-labelledby");
        selection.setAttribute("aria-label", select.getAttribute("aria-label"));
      }
    });
  }

  window.npcaAdminSelect = {
    enhance,
    focus(select) {
      const instance = $(select).data("select2");
      (instance ? instance.$selection[0] : select).focus();
    },
    sync(select) {
      $(select).trigger("change.select2");
    },
    closeWithin(root) {
      const select = [...root.querySelectorAll("select")].find((item) =>
        $(item).data("select2")?.isOpen(),
      );
      if (!select) return false;
      $(select).select2("close");
      this.focus(select);
      return true;
    },
    destroy(root) {
      root
        .querySelectorAll("select.select2-hidden-accessible")
        .forEach((select) => {
          $(select).off(".npcaPicker").select2("destroy");
        });
    },
  };

  $(() => {
    document.body.classList.add("npca-admin-selects");
    document.querySelectorAll("form").forEach(enhance);
    document.addEventListener("formset:added", (event) => {
      // The added row is inside a form; include its selects without reinitializing others.
      enhance(event.target.closest("form") || document);
    });
    $(document).on("select2:open", () => {
      const search = document.querySelector(
        ".select2-container--open .select2-search__field",
      );
      if (search) {
        search.placeholder = "Buscar opção…";
        search.setAttribute("aria-label", "Buscar opção");
        search.focus();
      }
    });
    $(document).on(
      "select2:select select2:unselect select2:clear",
      "select",
      (event) => {
        // Keep the admin's unsaved-changes warning working with Select2.
        event.target.dispatchEvent(new Event("input", { bubbles: true }));
      },
    );
    $(document).on("reset", "form", (event) => {
      // Wait for the browser to restore the select's original value.
      setTimeout(
        () =>
          $(event.target)
            .find("select.select2-hidden-accessible")
            .trigger("change.select2"),
        0,
      );
    });
  });
})();
