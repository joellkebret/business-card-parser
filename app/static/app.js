"use strict";

const $ = (id) => document.getElementById(id);
const pageSize = 20;
const state = { card: null, contacts: [], offset: 0, hasNext: false, persistence: false, busy: false };

function notice(message, error = false) {
  $("notice").textContent = message;
  $("notice").classList.toggle("error", error);
  $("notice").hidden = !message;
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    const detail = data.error;
    if (response.status === 413) throw new Error("This file is too large. Choose a smaller vCard file.");
    const validation = detail?.details?.map((item) => item.message).join(" ");
    throw new Error(validation || detail?.message || `Request failed (${response.status}).`);
  }
  return data;
}

function controls() {
  document.querySelectorAll("button, input").forEach((element) => { element.disabled = state.busy; });
  $("create-button").disabled = state.busy || !state.persistence;
  $("new-name").disabled = state.busy || !state.persistence;
  $("previous-button").disabled = state.busy || !state.persistence || state.offset === 0;
  $("next-button").disabled = state.busy || !state.persistence || !state.hasNext;
  $("parse-button").disabled = state.busy || !$("vcard-file").files.length;
  $("validate-button").disabled = state.busy || !$("vcard-file").files.length;
}

async function perform(action) {
  if (state.busy) return;
  state.busy = true;
  controls();
  document.querySelector("main").setAttribute("aria-busy", "true");
  notice("");
  try { await action(); }
  catch (error) { notice(error instanceof TypeError ? "Could not reach the service. Check your connection and try again." : error.message, true); }
  finally {
    state.busy = false;
    controls();
    document.querySelector("main").setAttribute("aria-busy", "false");
  }
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

function initials(name) {
  return name.trim().split(/\s+/u).slice(0, 2).map((part) => Array.from(part)[0]).join("").toUpperCase();
}

function renderContacts() {
  const list = $("contacts");
  list.replaceChildren();
  if (!state.contacts.length) {
    list.append(element("p", "empty-list", state.persistence ? "No saved contacts." : "Saving is disabled."));
  }
  for (const card of state.contacts) {
    const button = element("button", "contact-row", "");
    button.type = "button";
    button.setAttribute("aria-pressed", String(state.card?.id === card.id));
    const avatar = element("span", "mini-avatar", initials(card.formatted_name));
    avatar.setAttribute("aria-hidden", "true");
    button.append(avatar, element("span", "contact-label", card.formatted_name), element("span", "contact-arrow", "→"));
    button.addEventListener("click", () => perform(async () => {
      showCard(await request(`/api/v1/cards/${card.id}`));
      $("contact-name").focus();
    }));
    list.append(button);
  }
  $("page-label").textContent = `Page ${Math.floor(state.offset / pageSize) + 1}`;
}

async function loadContacts(offset = state.offset) {
  if (!state.persistence) {
    state.contacts = [];
    state.hasNext = false;
    state.offset = 0;
    renderContacts();
    return;
  }
  const cards = await request(`/api/v1/cards?limit=${pageSize + 1}&offset=${offset}`);
  if (!cards.length && offset > 0) return loadContacts(offset - pageSize);
  state.offset = offset;
  state.hasNext = cards.length > pageSize;
  state.contacts = cards.slice(0, pageSize);
  renderContacts();
}

function dateText(date) {
  if (!date) return "Not specified";
  if (date.is_text) return date.text;
  return [date.date, date.time && `${date.time}${date.utc ? " UTC" : ""}`].filter(Boolean).join(" · ");
}

function showCard(card) {
  state.card = card;
  $("empty-detail").hidden = Boolean(card);
  $("card-detail").hidden = !card;
  document.querySelector(".detail-panel").setAttribute("aria-labelledby", card ? "contact-name" : "detail-heading");
  $("detail-kind").hidden = !card;
  $("detail-kind").textContent = card ? (card.id ? "Saved contact" : "File preview") : "";
  if (!card) { renderContacts(); return; }
  $("avatar").textContent = initials(card.formatted_name);
  $("contact-name").textContent = card.formatted_name;
  $("contact-subtitle").textContent = card.id ? `Updated ${new Date(card.updated_at).toLocaleString()}` : "Valid vCard · Preview only · Not saved";
  $("edit-form").hidden = !card.id;
  $("delete-button").hidden = !card.id;
  $("edit-name").value = card.formatted_name;
  $("birthday").textContent = dateText(card.birthday);
  $("anniversary").textContent = dateText(card.anniversary);
  const properties = [card.formatted_name_property, ...card.properties];
  $("property-count").textContent = String(properties.length);
  $("properties").replaceChildren();
  for (const property of properties) {
    const block = element("div", "property", "");
    block.append(element("p", "property-title", [property.group, property.name].filter(Boolean).join(".")),
      element("p", "property-value", property.values.join("; ")));
    if (property.parameters.length) block.append(element("p", "property-parameters", property.parameters.map((parameter) => `${parameter.name}=${parameter.value}`).join(" · ")));
    $("properties").append(block);
  }
  $("vcard-source").textContent = card.vcard;
  renderContacts();
}

async function refresh() {
  const health = await request("/health");
  state.persistence = health.persistence !== "disabled";
  $("connection").textContent = state.persistence ? "Service ready" : "Preview mode";
  $("connection").classList.add("ready");
  $("persistence-note").hidden = state.persistence;
  try { await loadContacts(); }
  catch (error) {
    $("contacts").replaceChildren(element("p", "empty-list", "Contacts could not be loaded. Use Refresh to try again."));
    throw error;
  }
}

async function upload(action) {
  const file = $("vcard-file").files[0];
  if (!file) throw new Error("Choose a .vcf or .vcard file first.");
  if (!/\.(vcf|vcard)$/iu.test(file.name)) throw new Error("Choose a .vcf or .vcard file.");
  const body = new FormData();
  body.append("file", file);
  notice(action === "parse" ? "Parsing your vCard…" : "Validating your vCard…");
  const result = await request(`/api/v1/cards/${action}`, { method: "POST", body });
  if (action === "parse") {
    showCard(result);
    $("contact-name").focus();
  }
  notice(action === "parse" ? "File parsed successfully. This preview has not been saved." : "This file is a valid vCard.");
}

function nameBody(id) {
  const name = $(id).value.trim();
  if (!name) throw new Error("Enter a contact name.");
  return { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ formatted_name: name }) };
}

$("vcard-file").addEventListener("change", controls);
$("upload-form").addEventListener("submit", (event) => { event.preventDefault(); perform(() => upload("parse")); });
$("validate-button").addEventListener("click", () => perform(() => upload("validate")));
$("refresh-button").addEventListener("click", () => perform(async () => { await refresh(); notice("Contact list refreshed."); }));
$("previous-button").addEventListener("click", () => perform(() => loadContacts(state.offset - pageSize)));
$("next-button").addEventListener("click", () => perform(() => loadContacts(state.offset + pageSize)));
$("create-form").addEventListener("submit", (event) => {
  event.preventDefault();
  perform(async () => {
    const card = await request("/api/v1/cards", { method: "POST", ...nameBody("new-name") });
    $("new-name").value = "";
    showCard(card);
    $("contact-name").focus();
    notice("Contact created.");
    await loadContacts(0);
  });
});
$("edit-form").addEventListener("submit", (event) => {
  event.preventDefault();
  perform(async () => {
    showCard(await request(`/api/v1/cards/${state.card.id}`, { method: "PATCH", ...nameBody("edit-name") }));
    notice("Contact name saved.");
    await loadContacts();
  });
});
$("delete-button").addEventListener("click", () => {
  $("delete-description").textContent = state.card.formatted_name;
  $("delete-dialog").showModal();
});
$("cancel-delete").addEventListener("click", () => $("delete-dialog").close());
$("confirm-delete").addEventListener("click", () => {
  $("delete-dialog").close();
  perform(async () => {
    await request(`/api/v1/cards/${state.card.id}`, { method: "DELETE" });
    showCard(null);
    notice("Contact deleted.");
    await loadContacts();
  });
});
$("download-button").addEventListener("click", () => {
  if (!state.card) return;
  const url = URL.createObjectURL(new Blob([state.card.vcard], { type: "text/vcard;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "contact.vcf";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

perform(async () => {
  try { await refresh(); }
  catch (error) {
    $("connection").textContent = "Service needs attention";
    throw error;
  }
});
