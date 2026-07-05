from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FormField:
    ref: str
    type: str
    label: str
    value: str = ""
    required: bool = False
    options: list[str] = field(default_factory=list)
    name: str = ""


@dataclass
class FormButton:
    ref: str
    label: str
    safe: bool


@dataclass
class PageSnapshot:
    url: str
    fields: list[FormField]
    buttons: list[FormButton]
    warnings: list[str] = field(default_factory=list)


SNAPSHOT_JS = """
() => {
  window.__jobAssistantRefs = new Map();
  let counter = 0;
  function assignRef(el) {
    const ref = 'f' + (++counter);
    window.__jobAssistantRefs.set(ref, el);
    return ref;
  }
  function assignBtnRef(el) {
    const ref = 'b' + (++counter);
    window.__jobAssistantRefs.set(ref, el);
    return ref;
  }
  function visible(el) {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    if (el.getAttribute('aria-hidden') === 'true') return false;
    return el.offsetParent !== null || el.type === 'file';
  }
  function labelFor(el) {
    let label = el.getAttribute('aria-label') || el.placeholder || '';
    if (el.labels && el.labels[0]) label = el.labels[0].innerText || label;
    if (!label) {
      const parent = el.closest('fieldset, div, label');
      if (parent) {
        const leg = parent.querySelector('legend, label');
        if (leg) label = leg.innerText;
      }
    }
    return (label || el.name || el.id || '').trim().slice(0, 200);
  }
  const fields = [];
  const buttons = [];
  const seen = new Set();
  const candidates = document.querySelectorAll(
    'input:not([type=hidden]):not([type=submit]):not([type=button]), textarea, select, [role=combobox]'
  );
  for (const el of candidates) {
    if (!visible(el)) continue;
    const type = el.type || el.tagName.toLowerCase();
    if (type === 'password') continue;
    const key = (el.name || el.id || '') + el.tagName;
    if (seen.has(key)) continue;
    seen.add(key);
    const options = [];
    if (el.tagName === 'SELECT') {
      for (const opt of el.options) options.push(opt.text.trim());
    }
    fields.push({
      ref: assignRef(el),
      type: type,
      label: labelFor(el),
      value: el.value || '',
      required: el.required || el.getAttribute('aria-required') === 'true',
      options: options,
      name: el.name || el.id || '',
    });
  }
  for (const el of document.querySelectorAll('button, [role=button], input[type=submit]')) {
    if (!visible(el)) continue;
    const label = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
    if (!label) continue;
    const safe = !/submit|apply now|send application|finish application/i.test(label);
    buttons.push({ ref: assignBtnRef(el), label: label.slice(0, 120), safe });
  }
  return { url: location.href, fields, buttons, warnings: [] };
}
"""


def scrape_page(page) -> PageSnapshot:
    raw: dict[str, Any] = page.evaluate(SNAPSHOT_JS)
    fields = [
        FormField(
            ref=f["ref"],
            type=f.get("type", "text"),
            label=f.get("label", ""),
            value=f.get("value", ""),
            required=bool(f.get("required")),
            options=f.get("options") or [],
            name=f.get("name", ""),
        )
        for f in raw.get("fields", [])
    ]
    buttons = [
        FormButton(ref=b["ref"], label=b["label"], safe=bool(b.get("safe")))
        for b in raw.get("buttons", [])
    ]
    return PageSnapshot(
        url=raw.get("url", page.url),
        fields=fields,
        buttons=buttons,
        warnings=raw.get("warnings") or [],
    )


def normalize_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
