"use strict";

(() => {
  const pad = (value) => String(value).padStart(2, "0");
  const dateValue = (date) =>
    `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`;
  const dateKey = (date) =>
    `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  const monthNames = Array.from({ length: 12 }, (_, month) =>
    new Intl.DateTimeFormat("pt-BR", { month: "long" }).format(
      new Date(2024, month, 1),
    ),
  );
  let active = null;
  let sequence = 0;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function button(text, action, className = "npca-picker__button") {
    const node = element("button", className, text);
    node.type = "button";
    node.addEventListener("click", action);
    return node;
  }

  function parseDate(value) {
    const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value);
    if (!match) return null;
    const [, day, month, year] = match.map(Number);
    const date = new Date(year, month - 1, day);
    return date.getFullYear() === year &&
      date.getMonth() === month - 1 &&
      date.getDate() === day
      ? date
      : null;
  }

  function setValue(input, value) {
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    close(input);
  }

  function close(focusTarget) {
    if (!active) return;
    const { panel, trigger, input } = active;
    active = null;
    window.npcaAdminSelect?.destroy(panel);
    panel.remove();
    trigger.setAttribute("aria-expanded", "false");
    trigger.removeAttribute("aria-controls");
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-controls");
    focusTarget?.focus({ preventScroll: true });
  }

  function position() {
    if (!active) return;
    const { panel, input } = active;
    const rect = input.getBoundingClientRect();
    const viewport = window.visualViewport;
    const left = viewport?.offsetLeft || 0;
    const top = viewport?.offsetTop || 0;
    const width = viewport?.width || window.innerWidth;
    const height = viewport?.height || window.innerHeight;
    const bounds = panel.getBoundingClientRect();
    const below = rect.bottom + 8;
    const y =
      below + bounds.height <= top + height - 8
        ? below
        : rect.top - bounds.height - 8;
    panel.style.left = `${Math.max(left + 8, Math.min(rect.left, left + width - bounds.width - 8))}px`;
    panel.style.top = `${Math.max(top + 8, Math.min(y, top + height - bounds.height - 8))}px`;
    panel.style.maxHeight = `${height - 16}px`;
  }

  function makeSelect(label, values, selected) {
    const wrapper = element("label", "npca-picker__control");
    const caption = element("span", "npca-picker__label", label);
    const select = element("select", "npca-picker__select");
    select.id = `npca-picker-select-${++sequence}`;
    wrapper.htmlFor = select.id;
    select.setAttribute("aria-label", label);
    for (const [value, text] of values) select.add(new Option(text, value));
    select.value = String(selected);
    wrapper.append(caption, select);
    return { wrapper, select };
  }

  function buildCalendar(panel, input) {
    const selected = parseDate(input.value);
    const today = new Date();
    let cursor = selected || today;
    let month = cursor.getMonth();
    let year = cursor.getFullYear();
    const title = element("h2", "npca-picker__title", "Escolha a data");
    const header = element("div", "npca-picker__calendar-header");
    const months = makeSelect(
      "Mês",
      monthNames.map((name, index) => [index, name]),
      month,
    );
    const years = makeSelect("Ano", [], year);
    months.wrapper.classList.add("npca-picker__month");
    years.wrapper.classList.add("npca-picker__year");
    const days = element("div", "npca-picker__days");
    days.setAttribute("role", "group");
    days.setAttribute("aria-label", "Dias do mês. Use as setas para navegar.");
    const announcement = element("span", "npca-picker__sr-only");
    announcement.setAttribute("aria-live", "polite");
    const moveMonth = (offset) => {
      const next = new Date(year, month + offset, 1);
      year = next.getFullYear();
      month = next.getMonth();
      cursor = new Date(
        year,
        month,
        Math.min(cursor.getDate(), new Date(year, month + 1, 0).getDate()),
      );
      render();
    };
    const previous = button("‹", () => moveMonth(-1), "npca-picker__nav");
    previous.setAttribute("aria-label", "Mês anterior");
    const next = button("›", () => moveMonth(1), "npca-picker__nav");
    next.setAttribute("aria-label", "Próximo mês");
    header.append(previous, months.wrapper, years.wrapper, next);
    const weekdays = element("div", "npca-picker__weekdays");
    ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"].forEach((day) =>
      weekdays.append(element("span", "", day)),
    );
    const footer = element("div", "npca-picker__footer");
    footer.append(
      button("Limpar", () => setValue(input, ""), "npca-picker__link"),
      button("Hoje", () => setValue(input, dateValue(today))),
    );
    panel.append(title, header, weekdays, days, announcement, footer);

    function render(focusDay = false) {
      months.select.value = String(month);
      const lower = Math.min(today.getFullYear() - 100, year - 10);
      const upper = Math.max(today.getFullYear() + 100, year + 10);
      years.select.replaceChildren();
      for (let value = lower; value <= upper; value++)
        years.select.add(new Option(String(value), String(value)));
      years.select.value = String(year);
      window.npcaAdminSelect?.sync(months.select);
      window.npcaAdminSelect?.sync(years.select);
      announcement.textContent = `${monthNames[month]} de ${year}`;
      days.replaceChildren();
      const start = new Date(year, month, 1);
      start.setDate(1 - start.getDay());
      for (let index = 0; index < 42; index++) {
        const date = new Date(
          start.getFullYear(),
          start.getMonth(),
          start.getDate() + index,
        );
        const day = button(
          String(date.getDate()),
          () => setValue(input, dateValue(date)),
          "npca-picker__day",
        );
        day.dataset.date = dateKey(date);
        day.tabIndex = dateKey(date) === dateKey(cursor) ? 0 : -1;
        day.setAttribute(
          "aria-label",
          new Intl.DateTimeFormat("pt-BR", { dateStyle: "full" }).format(date),
        );
        day.setAttribute(
          "aria-pressed",
          String(Boolean(selected && dateKey(date) === dateKey(selected))),
        );
        if (date.getMonth() !== month)
          day.classList.add("npca-picker__day--outside");
        if (dateKey(date) === dateKey(today))
          day.setAttribute("aria-current", "date");
        day.addEventListener("keydown", (event) => {
          const offsets = {
            ArrowLeft: -1,
            ArrowRight: 1,
            ArrowUp: -7,
            ArrowDown: 7,
            Home: -date.getDay(),
            End: 6 - date.getDay(),
          };
          if (event.key in offsets) {
            event.preventDefault();
            cursor = new Date(
              date.getFullYear(),
              date.getMonth(),
              date.getDate() + offsets[event.key],
            );
            month = cursor.getMonth();
            year = cursor.getFullYear();
            render(true);
          } else if (["PageUp", "PageDown"].includes(event.key)) {
            event.preventDefault();
            moveMonth(event.key === "PageUp" ? -1 : 1);
            days.querySelector('[tabindex="0"]').focus();
          }
        });
        days.append(day);
      }
      if (focusDay) days.querySelector('[tabindex="0"]').focus();
    }
    const changeView = () => {
      month = Number(months.select.value);
      year = Number(years.select.value);
      cursor = new Date(
        year,
        month,
        Math.min(cursor.getDate(), new Date(year, month + 1, 0).getDate()),
      );
      render();
    };
    months.select.addEventListener("change", changeView);
    years.select.addEventListener("change", changeView);
    render();
    return () => days.querySelector('[tabindex="0"]').focus();
  }

  function buildTime(panel, input) {
    const match = /^(\d{1,2}):(\d{2})(?::\d{2})?$/.exec(input.value);
    const title = element("h2", "npca-picker__title", "Escolha o horário");
    const hint = element(
      "p",
      "npca-picker__hint",
      "Formato de 24 horas · 00:00 a 23:59",
    );
    const controls = element("div", "npca-picker__time-controls");
    const hours = makeSelect(
      "Hora",
      Array.from({ length: 24 }, (_, n) => [pad(n), pad(n)]),
      match ? pad(match[1]) : "00",
    );
    const minutes = makeSelect(
      "Minutos",
      Array.from({ length: 60 }, (_, n) => [pad(n), pad(n)]),
      match ? match[2] : "00",
    );
    controls.append(
      hours.wrapper,
      element("span", "npca-picker__separator", ":"),
      minutes.wrapper,
    );
    const footer = element("div", "npca-picker__footer");
    const apply = () =>
      setValue(input, `${hours.select.value}:${minutes.select.value}`);
    footer.append(
      button("Limpar", () => setValue(input, ""), "npca-picker__link"),
      button(
        "Aplicar horário",
        apply,
        "npca-picker__button npca-picker__button--primary",
      ),
    );
    panel.append(title, hint, controls, footer);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && event.target.tagName === "SELECT") {
        event.preventDefault();
        apply();
      }
    });
    return () => {
      if (window.npcaAdminSelect) window.npcaAdminSelect.focus(hours.select);
      else hours.select.focus();
    };
  }

  function initialize(input) {
    if (input.dataset.pickerReady || input.id.includes("__prefix__")) return;
    input.dataset.pickerReady = "true";
    const kind = input.dataset.npcaPicker;
    const trigger = button(
      "",
      () => {
        if (active?.input === input) return close(input);
        close();
        const panel = element("div", `npca-picker npca-picker--${kind}`);
        panel.id = `npca-picker-${++sequence}`;
        panel.setAttribute("role", "dialog");
        panel.setAttribute(
          "aria-label",
          `${kind === "date" ? "Selecionar data" : "Selecionar horário"}: ${input.labels?.[0]?.textContent.trim() || input.name}`,
        );
        const focus =
          kind === "date"
            ? buildCalendar(panel, input)
            : buildTime(panel, input);
        document.body.append(panel);
        active = { panel, input, trigger };
        trigger.setAttribute("aria-controls", panel.id);
        trigger.setAttribute("aria-expanded", "true");
        input.setAttribute("aria-controls", panel.id);
        input.setAttribute("aria-expanded", "true");
        window.npcaAdminSelect?.enhance(panel);
        position();
        focus();
      },
      "npca-picker-trigger",
    );
    const icon = element(
      "span",
      "material-symbols-outlined",
      kind === "date" ? "calendar_month" : "schedule",
    );
    icon.setAttribute("aria-hidden", "true");
    trigger.append(icon);
    const name = input.labels?.[0]?.textContent.trim() || input.name;
    trigger.setAttribute(
      "aria-label",
      `Escolher ${kind === "date" ? "data" : "horário"}: ${name}`,
    );
    trigger.setAttribute("aria-haspopup", "dialog");
    trigger.setAttribute("aria-expanded", "false");
    trigger.tabIndex = -1;
    trigger.setAttribute("aria-hidden", "true");
    input.after(trigger);
    input.addEventListener("click", () => trigger.click());
    input.addEventListener("keydown", (event) => {
      if (["Enter", " ", "ArrowDown"].includes(event.key)) {
        event.preventDefault();
        trigger.click();
      }
    });
    const allDay = input.form?.querySelector('[name="is_all_day"]');
    if (kind === "time" && allDay && !input.disabled) {
      const update = () => {
        input.disabled = trigger.disabled = allDay.checked;
        if (active?.input === input && allDay.checked) close();
      };
      allDay.addEventListener("change", update);
      update();
    } else {
      trigger.disabled = input.disabled;
    }
  }

  document.addEventListener("pointerdown", (event) => {
    if (
      active &&
      !active.panel.contains(event.target) &&
      !event.target.closest(".npca-picker-dropdown") &&
      event.target !== active.input &&
      !active.trigger.contains(event.target)
    )
      close();
  });
  document.addEventListener("focusin", (event) => {
    if (
      active &&
      !active.panel.contains(event.target) &&
      !event.target.closest(".npca-picker-dropdown") &&
      event.target !== active.input &&
      event.target !== active.trigger
    )
      close();
  });
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Escape" && active) {
        event.preventDefault();
        event.stopPropagation();
        if (window.npcaAdminSelect?.closeWithin(active.panel)) return;
        close(active.input);
      }
    },
    true,
  );
  window.addEventListener("resize", position);
  window.addEventListener("scroll", position, true);
  window.visualViewport?.addEventListener("resize", position);
  window.visualViewport?.addEventListener("scroll", position);
  const initializeAll = (root) =>
    root.querySelectorAll("[data-npca-picker]").forEach(initialize);
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", () =>
      initializeAll(document),
    );
  else initializeAll(document);
  document.addEventListener("formset:added", (event) =>
    initializeAll(event.target),
  );
})();
