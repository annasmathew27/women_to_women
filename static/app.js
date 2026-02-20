const form = document.getElementById("requestForm");
const msg = document.getElementById("msg");
const feedList = document.getElementById("feedList");
const refreshBtn = document.getElementById("refreshBtn");
const sosBtn = document.getElementById("sosBtn");

// NEW: lock requests until receiver clicks "Continue"
let requestsUnlocked = false;

// Expose a function receiver_dashboard.html can call
window.unlockRequests = function () {
  requestsUnlocked = true;
};

function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderItem(r) {
  const created = r.created_at ? new Date(r.created_at).toLocaleString() : "";
  const statusClass = (r.status || "").toLowerCase() === "resolved" ? "resolved" : "open";

  const detailsHtml = r.details
    ? `<div class="meta" style="margin-top:8px;">${escapeHtml(r.details)}</div>`
    : "";

  const btnHtml = statusClass === "open"
    ? `<button class="btn" data-resolve="${r.id}">Mark Resolved</button>`
    : "";

  return `
    <div class="item">
      <div class="itemTop">
        <div>
          <div style="font-weight:700;">${escapeHtml(r.title)}</div>
          <div class="meta">${escapeHtml(r.category)} • ${created}</div>
        </div>
        <div class="badge ${statusClass}">${escapeHtml(r.status)}</div>
      </div>
      ${detailsHtml}
      <div style="margin-top:10px; display:flex; gap:10px;">
        ${btnHtml}
      </div>
    </div>
  `;
}

function wireResolveButtons(fetchFeed) {
  document.querySelectorAll("[data-resolve]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-resolve");
      btn.disabled = true;
      try {
        const res = await fetch(`/api/requests/${id}/resolve`, { method: "POST" });
        if (!res.ok) throw new Error("Resolve failed");
        await fetchFeed();
      } catch (e) {
        alert("Could not resolve. Try again.");
        btn.disabled = false;
      }
    });
  });
}

async function fetchFeed() {
  if (!feedList) return;

  feedList.innerHTML = `<div class="meta">Loading…</div>`;
  try {
    const res = await fetch("/api/requests");
    const data = await res.json();

    if (!Array.isArray(data) || data.length === 0) {
      feedList.innerHTML = `<div class="meta">No requests yet.</div>`;
      return;
    }

    feedList.innerHTML = data.map(renderItem).join("");
    wireResolveButtons(fetchFeed);
  } catch (e) {
    feedList.innerHTML = `<div class="meta">Failed to load feed.</div>`;
  }
}

// ✅ Only attach handlers if elements exist on this page
if (form && msg) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    // NEW: block submission unless unlocked
    if (!requestsUnlocked) {
      msg.textContent = "Please confirm your location & availability first.";
      return;
    }

    msg.textContent = "Submitting…";

    const payload = {
      title: document.getElementById("title")?.value.trim() || "",
      category: document.getElementById("category")?.value.trim() || "",
      details: document.getElementById("details")?.value.trim() || ""
    };

    try {
      const res = await fetch("/api/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const out = await res.json().catch(() => ({}));

      if (!res.ok) {
        msg.textContent = out.error || "Error submitting request.";
        return;
      }

      msg.textContent = "Saved ✅";
      form.reset();
      await fetchFeed();
    } catch (e) {
      msg.textContent = "Network error.";
    }
  });
}

if (refreshBtn) refreshBtn.addEventListener("click", fetchFeed);

if (sosBtn) {
  sosBtn.addEventListener("click", () => {
    alert("SOS demo: later this can send location + notify contacts.");
  });
}

// Auto-load feed if feedList exists
if (feedList) fetchFeed();