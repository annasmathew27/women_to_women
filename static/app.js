// static/app.js

const form = document.getElementById("requestForm");
const msg = document.getElementById("msg");
const feedList = document.getElementById("feedList");
const refreshBtn = document.getElementById("refreshBtn");
const sosBtn = document.getElementById("sosBtn");

// lock requests until receiver clicks Continue
let requestsUnlocked = false;

// called from receiver_dashboard.html on Continue
window.unlockRequests = function () {
  requestsUnlocked = true;
};

function autoUnlockIfRequestVisible() {
  const requestCard = document.getElementById("requestCard");
  if (!requestCard) return;
  if (requestCard.style.display !== "none") requestsUnlocked = true;
}

function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// Treat both old "Resolved" and new "Serviced" as "done"
function isServicedStatus(status) {
  const s = String(status ?? "").trim().toLowerCase();
  return s === "serviced" || s === "resolved";
}

// Map status to class
function statusToClass(status) {
  return isServicedStatus(status) ? "resolved" : "open";
}

function renderItem(r) {
  const created = r.created_at ? new Date(r.created_at).toLocaleString() : "";
  const statusClass = statusToClass(r.status);

  const detailsHtml = r.details
    ? `<div class="meta" style="margin-top:8px;">${escapeHtml(r.details)}</div>`
    : "";

  // ✅ If already serviced/resolved, show text instead of button
  const actionHtml = isServicedStatus(r.status)
    ? `<span class="meta">Already serviced ✅</span>`
    : `<button class="btn" data-service="${r.id}">Mark Serviced</button>`;

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
      <div style="margin-top:10px; display:flex; gap:10px; align-items:center;">
        ${actionHtml}
      </div>
    </div>
  `;
}

function wireServiceButtons(fetchFeedFn) {
  document.querySelectorAll("[data-service]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-service");
      btn.disabled = true;
      btn.textContent = "Marking…";

      try {
        // ✅ keep using your existing endpoint for now
        const res = await fetch(`/api/requests/${id}/resolve`, {
          method: "POST",
          credentials: "same-origin"
        });

        const out = await res.json().catch(() => ({}));

        if (!res.ok) {
          throw new Error(out.error || `Failed (${res.status})`);
        }

        // if backend says it was already serviced
        if (out.already) {
          // refresh anyway so UI shows "Already serviced ✅"
          await fetchFeedFn();
          return;
        }

        await fetchFeedFn();
      } catch (e) {
        alert(e.message || "Could not mark serviced. Try again.");
        btn.disabled = false;
        btn.textContent = "Mark Serviced";
      }
    });
  });
}

async function fetchFeed() {
  if (!feedList) return;

  feedList.innerHTML = `<div class="meta">Loading…</div>`;
  try {
    const res = await fetch("/api/requests", { credentials: "same-origin" });
    const data = await res.json().catch(() => null);

    if (!res.ok) {
      const err = (data && data.error) ? data.error : `Failed to load (${res.status})`;
      feedList.innerHTML = `<div class="meta">${escapeHtml(err)}</div>`;
      return;
    }

    if (!Array.isArray(data) || data.length === 0) {
      feedList.innerHTML = `<div class="meta">No requests yet.</div>`;
      return;
    }

    feedList.innerHTML = data.map(renderItem).join("");
    wireServiceButtons(fetchFeed);
  } catch (e) {
    feedList.innerHTML = `<div class="meta">Failed to load feed.</div>`;
  }
}

function missingFieldMessage(payload) {
  if (!payload.title) return "Enter a title.";
  if (!payload.category) return "Enter a category.";
  if (!payload.scheduled_date) return "Pick a date.";
  if (!payload.scheduled_time) return "Pick a start time.";
  if (!payload.duration_min) return "Pick a duration.";
  if (!payload.hourly_wage) return "Enter hourly wage.";
  return "";
}

// Attach request submit
if (form && msg) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    autoUnlockIfRequestVisible();

    if (!requestsUnlocked) {
      msg.textContent = "Please confirm your location & availability first (click Continue).";
      return;
    }

    msg.textContent = "Submitting…";

    const hourlyWageVisible = document.getElementById("hourlyWage")?.value;

    const payload = {
      title: document.getElementById("title")?.value.trim() || "",
      category: document.getElementById("category")?.value.trim() || "",
      details: document.getElementById("details")?.value.trim() || "",

      scheduled_date: document.getElementById("scheduled_date")?.value || null,
      scheduled_time: document.getElementById("scheduled_time")?.value || null,
      duration_min: document.getElementById("duration_min")?.value
        ? parseInt(document.getElementById("duration_min").value, 10)
        : null,
      hourly_wage: document.getElementById("hourly_wage")?.value
        ? parseFloat(document.getElementById("hourly_wage").value)
        : (hourlyWageVisible ? parseFloat(hourlyWageVisible) : null)
    };

    const miss = missingFieldMessage(payload);
    if (miss) {
      msg.textContent = miss;
      return;
    }

    try {
      const res = await fetch("/api/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(payload)
      });

      const out = await res.json().catch(() => ({}));

      if (!res.ok) {
        msg.textContent = out.error || `Error submitting request (${res.status}).`;
        return;
      }

      msg.textContent = "Saved ✅";
      form.reset();
      await fetchFeed();
    } catch (e) {
      msg.textContent = "Network error.";
      console.error(e);
    }
  });
}

if (refreshBtn) refreshBtn.addEventListener("click", fetchFeed);

if (sosBtn) {
  sosBtn.addEventListener("click", () => {
    alert("SOS demo: later this can send location + notify contacts.");
  });
}

// Auto-load feed
if (feedList) fetchFeed();