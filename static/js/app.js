// Search events by title
function searchEvent() {
  let input = document.getElementById("searchInput").value.toLowerCase();
  let rows = document.querySelectorAll("#eventTable tbody tr");

  rows.forEach(row => {
    let titleCell = row.querySelector(".event-title");
    if (titleCell) {
      let title = titleCell.innerText.toLowerCase();
      row.style.display = title.includes(input) ? "" : "none";
    }
  });
}

// Update countdown badges dynamically
function updateCountdowns() {
  let elements = document.querySelectorAll(".countdown");
  let today = new Date();
  today.setHours(0, 0, 0, 0); // ✅ normalize to midnight

  elements.forEach(el => {
    let eventDate = new Date(el.dataset.date);
    eventDate.setHours(0, 0, 0, 0); // ✅ normalize to midnight

    let diffDays = Math.ceil((eventDate - today) / (1000 * 60 * 60 * 24));

    if (diffDays > 1) {
      el.innerHTML = `<span class="badge bg-info text-dark">In ${diffDays} days</span>`;
    } else if (diffDays === 1) {
      el.innerHTML = `<span class="badge bg-warning text-dark">Tomorrow</span>`;
    } else if (diffDays === 0) {
      el.innerHTML = `<span class="badge bg-primary">Today</span>`;
    } else {
      el.innerHTML = `<span class="badge bg-secondary">Passed</span>`;
    }
  });
}

// ✅ Run once on page load
document.addEventListener("DOMContentLoaded", updateCountdowns);

// ✅ Update every minute (not every second for performance)
setInterval(updateCountdowns, 60000);
