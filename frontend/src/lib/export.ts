/**
 * Export utilities for dashboard data.
 */

export function exportAlertsToCSV(alerts: Array<any>, filename = "trainwatch-alerts.csv") {
  const headers = [
    "Train",
    "Sensor",
    "Severity",
    "Detector",
    "Started",
    "Ended",
    "Status",
    "Peak Value",
    "Recommendation",
  ];

  const rows = alerts.map((a) => [
    a.trainId,
    a.sensor,
    a.severity === "crit" ? "Critical" : "Warning",
    a.detector,
    new Date(a.startedTs).toISOString(),
    new Date(a.endTs).toISOString(),
    a.active ? "Active" : "Resolved",
    a.peak.toFixed(2),
    `"${a.recommendation.replace(/"/g, '""')}"`, // escape quotes in CSV
  ]);

  const csv = [
    headers.join(","),
    ...rows.map((r) => r.join(",")),
  ].join("\n");

  downloadFile(csv, filename, "text/csv");
}

export function exportFleetHealthToCSV(
  health: Array<any>,
  filename = "trainwatch-fleet-health.csv"
) {
  const headers = ["Train", "Health Score", "Status", "Active Alerts"];

  const rows = health.map((h) => [h.trainId, h.score, h.status, h.activeAlerts]);

  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");

  downloadFile(csv, filename, "text/csv");
}

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
