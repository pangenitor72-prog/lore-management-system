// src/static/entities.js

let allEntities = [];

// ----------- Helpers -----------

function qs(selector) {
    return document.querySelector(selector);
}

function qsa(selector) {
    return Array.from(document.querySelectorAll(selector));
}

function setHidden(el, hidden) {
    if (!el) return;
    el.classList.toggle("hidden", hidden);
}

// ----------- List View -----------

async function loadEntities() {
    const listContainer = qs("#entity-list");
    const loadingEl = qs("#entity-list-loading");
    const errorEl = qs("#entity-list-error");
    const emptyEl = qs("#entity-list-empty");

    if (!listContainer) return;

    setHidden(loadingEl, false);
    setHidden(errorEl, true);
    setHidden(emptyEl, true);

    try {
        const resp = await fetch("/entities");
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
        const data = await resp.json();

        // Expecting an array; if backend returns object, try to adapt.
        allEntities = Array.isArray(data) ? data : (data.items || []);

        renderEntityList(allEntities);
        setHidden(loadingEl, true);

        if (allEntities.length === 0) {
            setHidden(emptyEl, false);
        }
    } catch (err) {
        console.error("Failed to load entities:", err);
        setHidden(loadingEl, true);
        setHidden(errorEl, false);
    }
}

function renderEntityList(entities) {
    const listContainer = qs("#entity-list");
    const emptyEl = qs("#entity-list-empty");
    if (!listContainer) return;

    listContainer.innerHTML = "";

    if (!entities || entities.length === 0) {
        setHidden(emptyEl, false);
        return;
    } else {
        setHidden(emptyEl, true);
    }

    for (const entity of entities) {
        const item = document.createElement("article");
        item.className = "eb-list-item";

        const canonId = entity.canon_id || entity.id || entity.uuid || "UNKNOWN";

        const primaryLabel =
            entity.label ||
            entity.name ||
            entity.title ||
            canonId;

        const typeLabel = entity.entity_type || entity.type || "";

        item.innerHTML = `
            <div class="eb-list-item-main">
                <h2 class="eb-list-item-title">${escapeHtml(primaryLabel)}</h2>
                ${
                    typeLabel
                        ? `<p class="eb-list-item-meta">${escapeHtml(typeLabel)}</p>`
                        : ""
                }
                <p class="eb-list-item-id">${escapeHtml(canonId)}</p>
            </div>
            <div class="eb-list-item-actions">
                <a href="/entities/browser?canon_id=${encodeURIComponent(
                    canonId
                )}" class="eb-list-item-link">
                    View
                </a>
            </div>
        `;

        listContainer.appendChild(item);
    }
}

function attachSearchHandler() {
    const searchInput = qs("#entity-search");
    if (!searchInput) return;

    searchInput.addEventListener("input", () => {
        const query = searchInput.value.toLowerCase().trim();

        if (!query) {
            renderEntityList(allEntities);
            return;
        }

        const filtered = allEntities.filter((entity) => {
            const canonId = (entity.canon_id || entity.id || "").toString();
            const label =
                (entity.label ||
                    entity.name ||
                    entity.title ||
                    "").toString();
            const type = (entity.entity_type || entity.type || "").toString();

            const haystack = [canonId, label, type]
                .join(" ")
                .toLowerCase();

            return haystack.includes(query);
        });

        renderEntityList(filtered);
    });
}

// ----------- Detail View -----------

async function loadEntityDetail() {
    const body = document.body;
    const canonId = body.getAttribute("data-canon-id");
    if (!canonId) return;

    const loadingEl = qs("#entity-detail-loading");
    const errorEl = qs("#entity-detail-error");
    const contentEl = qs("#entity-detail-content");

    setHidden(loadingEl, false);
    setHidden(errorEl, true);
    setHidden(contentEl, true);

    try {
        const resp = await fetch(`/entities/${encodeURIComponent(canonId)}`);
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
        const entity = await resp.json();

        renderEntityDetail(entity);
        setHidden(loadingEl, true);
        setHidden(contentEl, false);
    } catch (err) {
        console.error("Failed to load entity:", err);
        setHidden(loadingEl, true);
        setHidden(errorEl, false);
    }
}

function renderEntityDetail(entity) {
    const contentEl = qs("#entity-detail-content");
    if (!contentEl) return;

    const canonId = entity.canon_id || entity.id || entity.uuid || "UNKNOWN";

    const primaryLabel =
        entity.label ||
        entity.name ||
        entity.title ||
        canonId;

    const typeLabel = entity.entity_type || entity.type || "";

    // Build a generic key-value view to stay schema-agnostic
    const rows = Object.entries(entity).map(([key, value]) => {
        const displayValue =
            typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
        return `
            <div class="eb-detail-row">
                <div class="eb-detail-key">${escapeHtml(key)}</div>
                <div class="eb-detail-value"><pre>${escapeHtml(displayValue)}</pre></div>
            </div>
        `;
    });

    contentEl.innerHTML = `
        <header class="eb-detail-header">
            <h2 class="eb-detail-title">${escapeHtml(primaryLabel)}</h2>
            ${
                typeLabel
                    ? `<p class="eb-detail-type">${escapeHtml(typeLabel)}</p>`
                    : ""
            }
            <p class="eb-detail-id">${escapeHtml(canonId)}</p>
        </header>
        <section class="eb-detail-body">
            ${rows.join("")}
        </section>
    `;
}

// ----------- HTML Escaping -----------

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ----------- Bootstrapping -----------

document.addEventListener("DOMContentLoaded", () => {
    const view = document.body.getAttribute("data-view");

    if (view === "list") {
        loadEntities();
        attachSearchHandler();
    } else if (view === "detail") {
        loadEntityDetail();
    }
});
