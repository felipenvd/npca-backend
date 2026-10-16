"use strict";

document.addEventListener("formset:added", (event) => {
  if (event.detail?.formsetName !== "author_records") return;

  const row = event.target;
  const field = row.querySelector('[name$="-display_order"]');
  const group = row.closest("#author_records-group");
  if (!field || !group) return;

  let highestOrder = 0;
  group.querySelectorAll('[name$="-display_order"]').forEach((input) => {
    if (input === field || input.name.includes("__prefix__")) return;
    const prefix = input.name.replace(/-display_order$/, "");
    const deleted = group.querySelector(`[name="${prefix}-DELETE"]`);
    if (deleted?.checked) return;
    const order = Number(input.value);
    if (Number.isInteger(order)) highestOrder = Math.max(highestOrder, order);
  });
  field.value = String(highestOrder + 1);
  field.dispatchEvent(new Event("input", { bubbles: true }));
});
