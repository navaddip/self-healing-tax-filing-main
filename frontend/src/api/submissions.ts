import type { SubmissionResult } from "../types/tax";

export async function errorMessage(response: Response, fallback: string): Promise<string> {
  const text = await response.text();
  try {
    const detail = JSON.parse(text).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => item.msg).join("; ");
  } catch {
    // Non-JSON body (e.g. proxy error page); fall through to the raw text.
  }
  return text || fallback;
}

export async function submitDocument(
  files: File | File[],
): Promise<SubmissionResult> {
  const body = new FormData();
  for (const file of Array.isArray(files) ? files : [files]) {
    body.append("documents", file);
  }
  const response = await fetch("/api/v1/submissions", {
    method: "POST",
    body,
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "The submission could not be processed."));
  }
  return response.json();
}

export async function getSubmission(
  submissionId: string,
): Promise<SubmissionResult> {
  const response = await fetch(`/api/v1/submissions/${submissionId}`);
  if (!response.ok) {
    throw new Error("The saved submission could not be loaded.");
  }
  return response.json();
}

export async function saveFilingDetails(
  submissionId: string,
  details: Record<string, string>,
): Promise<SubmissionResult> {
  const response = await fetch(`/api/v1/submissions/${submissionId}/filing-details`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(details),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "The details could not be saved."));
  }
  return response.json();
}

export async function getSensitivity(
  submissionId: string,
  deltas: number[],
): Promise<Array<{ delta: number; old_tax: number; new_tax: number; winner: string }>> {
  const response = await fetch(`/api/v1/submissions/${submissionId}/sensitivity`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ deltas }),
  });
  if (!response.ok) {
    throw new Error("Could not calculate deduction sensitivity");
  }
  const data = await response.json();
  return data.sensitivity;
}
