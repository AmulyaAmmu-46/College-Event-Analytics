(() => {
  const form = document.getElementById("dashboard-filters");
  if (!form) return;

  const colors = [
    "#4f46e5", "#06b6d4", "#f59e0b", "#ec4899", "#8b5cf6",
    "#10b981", "#3b82f6", "#f97316", "#14b8a6", "#64748b"
  ];
  const charts = {};

  function draw(canvasId, labels, sets, type, horizontal = false) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    if (charts[canvasId]) charts[canvasId].destroy();

    charts[canvasId] = new Chart(canvas, {
      type,
      data: {
        labels,
        datasets: sets.map((set, index) => ({
          label: set.label,
          data: set.data,
          backgroundColor: type === "line"
            ? "rgba(79, 70, 229, 0.1)"
            : (type === "doughnut" || type === "pie" ? colors : (set.color || colors[index % colors.length])),
          borderColor: set.color || colors[index % colors.length],
          borderWidth: 2,
          tension: 0.35,
          fill: type === "line",
          borderRadius: type === "bar" ? 6 : undefined
        }))
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: horizontal ? "y" : "x",
        plugins: {
          legend: {
            display: type !== "bar" || sets.length > 1,
            position: "bottom",
            labels: { boxWidth: 12, padding: 10 }
          }
        },
        scales: (type === "bar" || type === "line") ? {
          y: { beginAtZero: true, grid: { color: "#f1f5f9" } },
          x: { grid: { display: false } }
        } : undefined
      }
    });
  }

  function entries(obj) {
    return Object.entries(obj || {});
  }

  async function load() {
    const query = new URLSearchParams(new FormData(form));
    const response = await fetch(`${form.dataset.endpoint}?${query}`);
    if (!response.ok) throw new Error("Analytics could not be loaded. Please try again.");

    const data = await response.json();
    const cards = data.cards || {};

    Object.entries(cards).forEach(([key, value]) => {
      const el = document.getElementById(`card-${key}`);
      if (el) {
        if (key === "average_attendance_rate") {
          el.innerHTML = `${value}<small class="fs-6 text-muted">%</small>`;
        } else if (key === "average_feedback_rating") {
          el.innerHTML = `${value}<small class="fs-6 text-muted"> / 5</small>`;
        } else {
          el.textContent = value;
        }
      }
    });

    // Chart 1: Event-wise Registration (Bar)
    const ev = entries(data.registrations_by_event);
    draw("registrationsChart", ev.map(x => x[0]), [{ label: "Registrations", data: ev.map(x => x[1]), color: "#4f46e5" }], "bar");

    // Chart 5: Category Distribution (Doughnut)
    const cats = entries(data.registrations_by_category);
    draw("categoryChart", cats.map(x => x[0]), [{ label: "Registrations", data: cats.map(x => x[1]) }], "doughnut");

    // Chart 2: Department-wise Participation (Bar across 9 depts)
    const depts = entries(data.department_participation);
    draw("departmentChart", depts.map(x => x[0]), [{ label: "Enrolled Students", data: depts.map(x => x[1]), color: "#06b6d4" }], "bar");

    // Chart 4: Attendance Status (Doughnut: Present, Absent, Excused)
    const statuses = entries(data.attendance_status).filter(x => x[0] !== "Unmarked");
    draw("attendanceChart", statuses.map(x => x[0]), [{ label: "Participants", data: statuses.map(x => x[1]) }], "doughnut");

    // Chart 3: Monthly Registration Trends (Line)
    const months = entries(data.monthly_registrations);
    draw("monthlyChart", months.map(x => x[0]), [{ label: "Registrations", data: months.map(x => x[1]), color: "#8b5cf6" }], "line");

    // Chart 6: Event Feedback Analysis (Bar)
    const ratings = entries(data.ratings_by_event).filter(x => x[1] !== null);
    draw("ratingsChart", ratings.map(x => x[0]), [{ label: "Average Rating (out of 5)", data: ratings.map(x => x[1]), color: "#f59e0b" }], "bar");

    // Chart 7: Top Five Popular Events (Horizontal Bar by popularity score)
    const topEvents = data.top_events || [];
    draw("topChart", topEvents.map(x => x.title), [{ label: "Popularity Score (out of 100)", data: topEvents.map(x => x.popularity_score), color: "#10b981" }], "bar", true);

    // Chart 8: Registration vs Actual Attendance (Grouped Bar)
    const comparisons = entries(data.registered_vs_attended);
    draw("comparisonChart", comparisons.map(x => x[0]), [
      { label: "Registered Students", data: comparisons.map(x => x[1].registered), color: "#4f46e5" },
      { label: "Actual Attendees (Present)", data: comparisons.map(x => x[1].attended), color: "#10b981" }
    ], "bar");

    // Populate Top Events Table (Prompt Section 7)
    const tableBody = document.getElementById("topEventsTableBody");
    if (tableBody) {
      if (topEvents.length > 0) {
        tableBody.innerHTML = topEvents.map((item, idx) => `
          <tr>
            <td><span class="badge ${idx === 0 ? 'bg-warning text-dark' : 'bg-light text-dark border'}">#${idx + 1}</span></td>
            <td><strong>${item.title}</strong></td>
            <td>${item.registrations}</td>
            <td>${item.registration_fill_rate !== null ? item.registration_fill_rate + '%' : 'N/A'}</td>
            <td><span class="badge bg-success-subtle text-success border">${item.attended}</span></td>
            <td><strong>${item.attendance_rate}%</strong></td>
            <td>${item.average_rating !== null ? item.average_rating + ' ★' : 'No ratings'}</td>
            <td><span class="badge bg-primary fs-6">${item.popularity_score} pts</span></td>
          </tr>
        `).join("");
      } else {
        tableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-3">No event ranking data available.</td></tr>`;
      }
    }

    const loader = document.getElementById("chart-loading");
    if (loader) loader.classList.add("d-none");
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    const loader = document.getElementById("chart-loading");
    if (loader) {
      loader.classList.remove("d-none");
      loader.textContent = "Updating charts...";
    }
    load().catch(error => {
      if (loader) {
        loader.textContent = error.message;
        loader.classList.add("text-danger");
      }
    });
  });

  load().catch(error => {
    const loader = document.getElementById("chart-loading");
    if (loader) {
      loader.textContent = error.message;
      loader.classList.add("text-danger");
    }
  });
})();
