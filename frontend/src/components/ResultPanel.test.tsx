import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ResultPanel } from "./ResultPanel";
import { errorMessage } from "../api/submissions";
import { FilingDetailsForm } from "./FilingDetailsForm";
import type { SubmissionResult } from "../types/tax";

const result = {
  submission_id: "test", status: "completed", original_filename: "sample.pdf", audit_trail: [],
  verification: { valid: true, confidence_score: 0.96, checks: [] },
  receipt: { filing_status: "advisory_only", instructions: "Missing filing fields: date_of_birth" },
  report_url: "/report.pdf",
} as unknown as SubmissionResult;

describe("filing readiness", () => {
  it("does not offer a JSON download for advisory-only receipts", () => {
    const html = renderToStaticMarkup(<ResultPanel result={result} />);
    expect(html).not.toContain("Download ITR JSON");
    expect(html).toContain("Missing filing fields: date_of_birth");
  });
  it("uses backend report eligibility instead of a second hardcoded threshold", () => {
    const html = renderToStaticMarkup(<ResultPanel result={result} />);
    expect(html).toContain('href="/report.pdf"');
  });
  it("shows the sequential submission number", () => {
    const html = renderToStaticMarkup(<ResultPanel result={{ ...result, serial_no: 7 }} />);
    expect(html).toContain("#7");
  });
});

describe("failed runs", () => {
  it("shows the backend failure reason", () => {
    const failed = { submission_id: "f", status: "failed", audit_trail: [], error: "PAN mismatch" } as unknown as SubmissionResult;
    expect(renderToStaticMarkup(<ResultPanel result={failed} />)).toContain("PAN mismatch");
  });
});

describe("errorMessage", () => {
  it("unwraps FastAPI detail strings and validation lists", async () => {
    expect(await errorMessage(new Response('{"detail":"Too many documents"}'), "x")).toBe("Too many documents");
    expect(await errorMessage(new Response('{"detail":[{"msg":"Field required"}]}'), "x")).toBe("Field required");
    expect(await errorMessage(new Response("Bad Gateway"), "x")).toBe("Bad Gateway");
    expect(await errorMessage(new Response(""), "fallback")).toBe("fallback");
  });
});

describe("missing filing details", () => {
  const base = {
    submission_id: "m", status: "completed", audit_trail: [],
    verification: { valid: true, confidence_score: 1, checks: [] },
    receipt: { filing_status: "advisory_only", itr_form: "ITR-1", export_supported: true,
               instructions: "ITR export blocked: PersonalInfo.DOB" },
  };

  it("lists missing details in plain words with a fill option", () => {
    const html = renderToStaticMarkup(
      <ResultPanel result={{ ...base, missing_filing_fields: ["date_of_birth", "bank_ifsc"] } as unknown as SubmissionResult} />,
    );
    expect(html).toContain("Your ITR-1 file needs a few more details");
    expect(html).toContain("Date of birth");
    expect(html).toContain("Bank IFSC");
    expect(html).toContain("Fill details");
    expect(html).not.toContain("PersonalInfo");
  });

  it("asks only for bank details when a refund needs them", () => {
    const html = renderToStaticMarkup(
      <ResultPanel result={{ ...base, status: "manual_review", receipt: undefined,
        missing_filing_fields: ["bank_ifsc", "bank_name", "bank_account_number"] } as unknown as SubmissionResult} />,
    );
    expect(html).toContain("Add your bank account to receive the refund");
  });

  it("explains unsupported forms plainly", () => {
    const html = renderToStaticMarkup(
      <ResultPanel result={{ ...base, receipt: { ...base.receipt, itr_form: "ITR-2", export_supported: false,
        instructions: "ITR-2 file export isn't supported for this return yet." } } as unknown as SubmissionResult} />,
    );
    expect(html).toContain("isn&#x27;t supported");
    expect(html).not.toContain("Fill details");
  });
});

describe("FilingDetailsForm", () => {
  it("renders only the missing fields with dropdowns for coded values", () => {
    const html = renderToStaticMarkup(
      <FilingDetailsForm submissionId="m" missing={["employer_category", "state_code", "pin_code"]} onSaved={() => {}} />,
    );
    expect(html).toContain("Private sector / Others");
    expect(html).toContain("Karnataka");
    expect(html).toContain("PIN code");
    expect(html).not.toContain("Date of birth");
  });
});
