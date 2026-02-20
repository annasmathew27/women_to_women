const form = document.getElementById("requestForm");
const msg = document.getElementById("msg");
const feedList = document.getElementById("feedList");
const refreshBtn = document.getElementById("refreshBtn");
const sosBtn = document.getElementById("sosBtn");

async function fetchFeed() {
  feedList.innerHTML = `<div class="meta">Loading…</div>`;
  try {
    const res = await fetch("/api/requests");
    const data = await res.json();

    if (!Array.isArray(data) || data.length === 0) {
      feedList.innerHTML = `<div class="meta">No requests yet.</div>`;
      return;
    }

    feedList.innerHTML = data.map(renderItem).join("");
    wireResolveButtons();
  } catch (e) {
    feedList.innerHTML = `<div class="meta">Failed to load feed.</div>`;
  }
}

function renderItem(r) {
  const created = r.created_at ? new Date(r.created_at).toLocaleString() : "";
  const statusClass = (r.status || "").toLowerCase() === "resolved" ? "resolved" : "open";

  const detailsHtml = r.details ? `<div class="meta" style="margin-top:8px;">${escapeHtml(r.details)}</div>` : "";
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

function wireResolveButtons() {
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

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  msg.textContent = "Submitting…";

  const payload = {
    title: document.getElementById("title").value.trim(),
    category: document.getElementById("category").value.trim(),
    details: document.getElementById("details").value.trim()
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

refreshBtn.addEventListener("click", fetchFeed);

sosBtn.addEventListener("click", () => {
  alert("SOS demo: later this can send location + notify contacts.");
});

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

fetchFeed();
<script>
  const saveBtn = document.getElementById("saveBtn");
  const modal = document.getElementById("resultModal");
  const modalTitle = document.getElementById("modalTitle");
  const modalText = document.getElementById("modalText");
  const modalExtra = document.getElementById("modalExtra");
  const closeModalBtn = document.getElementById("closeModalBtn");

  function openModal(title, text, extra="") {
    modalTitle.textContent = title;
    modalText.textContent = text;
    modalExtra.textContent = extra;
    modal.classList.remove("hidden");
  }
  function closeModal() {
    modal.classList.add("hidden");
  }

  closeModalBtn.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

  saveBtn.addEventListener("click", async () => {
    locStatus.textContent = "Saving…";

    const payload = {
      location_text: document.getElementById("location_text").value.trim(),
      lat: latInput.value ? parseFloat(latInput.value) : null,
      lng: lngInput.value ? parseFloat(lngInput.value) : null
    };

    try {
      const res = await fetch("/api/receiver/location", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });

      const out = await res.json();

      if (!res.ok || !out.ok) {
        locStatus.textContent = "Save failed.";
        openModal("Error", out.error || "Could not save location.");
        return;
      }

      locStatus.textContent = "Saved ✅";

      if (out.can_serve) {
        const extra = `Providers in range: ${out.providers_in_range}`
          + (out.nearest_provider_km != null ? ` • Nearest provider: ${out.nearest_provider_km} km` : "");
        openModal("✅ Service Available", out.reason, extra);
      } else {
        const extra = (out.nearest_provider_km != null)
          ? `Nearest provider: ${out.nearest_provider_km} km`
          : "";
        openModal("❌ Not Available", out.reason, extra);
      }

    } catch (e) {
      locStatus.textContent = "Network error.";
      openModal("Error", "Network error while saving location.");
    }
  });
</script>

