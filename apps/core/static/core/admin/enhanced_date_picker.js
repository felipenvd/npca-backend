"use strict";

{
  function addYearOption(select, year) {
    if (select.querySelector(`option[value="${year}"]`)) return;

    const option = new Option(String(year), String(year));
    const nextOption = Array.from(select.options).find(
      (item) => Number(item.value) > year,
    );
    select.add(option, nextOption ?? null);
  }

  function formatTypedDate(input) {
    const digits = input.value.replace(/\D/g, "").slice(0, 8);
    if (digits.length <= 2) {
      input.value = digits;
    } else if (digits.length <= 4) {
      input.value = `${digits.slice(0, 2)}/${digits.slice(2)}`;
    } else {
      input.value = `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
    }
  }

  function enhanceCalendar(input, index) {
    const shortcuts = window.DateTimeShortcuts;
    const calendar = shortcuts.calendars[index];
    const calendarBox = document.getElementById(
      `${shortcuts.calendarDivName1}${index}`,
    );
    if (!calendar || !calendarBox || calendarBox.dataset.npcaEnhanced === "true") {
      return;
    }

    calendarBox.dataset.npcaEnhanced = "true";
    calendarBox.classList.add("npca-enhanced-calendar");

    const selectors = document.createElement("div");
    selectors.className = "npca-date-picker__selectors";

    const monthLabel = document.createElement("label");
    monthLabel.className = "npca-date-picker__label";
    monthLabel.htmlFor = `npca-calendar-month-${index}`;
    monthLabel.textContent = gettext("Month");

    const monthSelect = document.createElement("select");
    monthSelect.id = monthLabel.htmlFor;
    monthSelect.className = "npca-date-picker__select";
    monthSelect.setAttribute("aria-label", gettext("Month"));
    window.CalendarNamespace.monthsOfYear.forEach((name, monthIndex) => {
      monthSelect.add(new Option(name, String(monthIndex + 1)));
    });

    const yearLabel = document.createElement("label");
    yearLabel.className = "npca-date-picker__label";
    yearLabel.htmlFor = `npca-calendar-year-${index}`;
    yearLabel.textContent = gettext("Year");

    const yearSelect = document.createElement("select");
    yearSelect.id = yearLabel.htmlFor;
    yearSelect.className = "npca-date-picker__select";
    yearSelect.setAttribute("aria-label", gettext("Year"));
    const currentYear = new Date().getFullYear();
    for (let year = currentYear - 50; year <= currentYear + 30; year += 1) {
      yearSelect.add(new Option(String(year), String(year)));
    }

    selectors.append(monthLabel, monthSelect, yearLabel, yearSelect);
    const calendarBody = calendarBox.querySelector(".calendar");
    calendarBox.insertBefore(selectors, calendarBody);

    const syncSelectors = () => {
      addYearOption(yearSelect, calendar.currentYear);
      monthSelect.value = String(calendar.currentMonth);
      yearSelect.value = String(calendar.currentYear);
    };
    const originalDrawCurrent = calendar.drawCurrent.bind(calendar);
    calendar.drawCurrent = () => {
      originalDrawCurrent();
      syncSelectors();
    };

    const drawSelectedDate = () => {
      calendar.drawDate(Number(monthSelect.value), Number(yearSelect.value));
    };
    monthSelect.addEventListener("change", drawSelectedDate);
    yearSelect.addEventListener("change", drawSelectedDate);
    syncSelectors();

    input.setAttribute("inputmode", "numeric");
    input.addEventListener("input", () => formatTypedDate(input));
  }

  window.addEventListener("load", () => {
    if (!window.DateTimeShortcuts || !window.CalendarNamespace) return;

    window.DateTimeShortcuts.calendarInputs.forEach((input, index) => {
      if (input.classList.contains("npca-enhanced-date-field")) {
        enhanceCalendar(input, index);
      }
    });
  });
}
