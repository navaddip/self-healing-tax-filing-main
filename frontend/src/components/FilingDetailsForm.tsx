import { FormEvent, useState } from "react";
import { saveFilingDetails } from "../api/submissions";
import type { SubmissionResult } from "../types/tax";

type Field = {
  label: string;
  type?: "text" | "date" | "email" | "tel";
  options?: [string, string][];
  pattern?: RegExp;
  hint?: string;
  placeholder?: string;
};

const STATES: [string, string][] = [
  ["01", "Andaman and Nicobar Islands"], ["02", "Andhra Pradesh"], ["03", "Arunachal Pradesh"], ["04", "Assam"],
  ["05", "Bihar"], ["06", "Chandigarh"], ["07", "Dadra and Nagar Haveli"], ["08", "Daman and Diu"], ["09", "Delhi"],
  ["10", "Goa"], ["11", "Gujarat"], ["12", "Haryana"], ["13", "Himachal Pradesh"], ["14", "Jammu and Kashmir"],
  ["15", "Karnataka"], ["16", "Kerala"], ["17", "Lakshadweep"], ["18", "Madhya Pradesh"], ["19", "Maharashtra"],
  ["20", "Manipur"], ["21", "Meghalaya"], ["22", "Mizoram"], ["23", "Nagaland"], ["24", "Odisha"],
  ["25", "Puducherry"], ["26", "Punjab"], ["27", "Rajasthan"], ["28", "Sikkim"], ["29", "Tamil Nadu"],
  ["30", "Tripura"], ["31", "Uttar Pradesh"], ["32", "West Bengal"], ["33", "Chhattisgarh"], ["34", "Uttarakhand"],
  ["35", "Jharkhand"], ["36", "Telangana"], ["37", "Ladakh"], ["99", "Outside India"],
];

export const FIELDS: Record<string, Field> = {
  date_of_birth: { label: "Date of birth", type: "date" },
  employer_category: {
    label: "Employer type",
    options: [
      ["OTH", "Private sector / Others"], ["CGOV", "Central Government"], ["SGOV", "State Government"],
      ["PSU", "Public Sector Undertaking"], ["PE", "Pensioner – Central Government"],
      ["PESG", "Pensioner – State Government"], ["PEPS", "Pensioner – Public Sector"],
      ["PEO", "Pensioner – Others"], ["NA", "Not applicable"],
    ],
  },
  address: { label: "Flat / house no. and building", placeholder: "Flat 12B, Lake View Apts" },
  locality_or_area: { label: "Locality / area", placeholder: "HSR Layout" },
  city: { label: "City / town / district" },
  state_code: { label: "State", options: STATES },
  pin_code: { label: "PIN code", pattern: /^[1-9]\d{5}$/, hint: "6 digits" },
  mobile: { label: "Mobile number", type: "tel", pattern: /^[6-9]\d{9}$/, hint: "10 digits, without +91" },
  email: { label: "Email", type: "email", pattern: /^[^@\s]+@[^@\s]+\.[^@\s]+$/, hint: "e.g. name@example.com" },
  bank_ifsc: { label: "Bank IFSC", pattern: /^[A-Za-z]{4}0[A-Za-z0-9]{6}$/, hint: "11 characters, e.g. HDFC0001234" },
  bank_name: { label: "Bank name" },
  bank_account_number: { label: "Bank account number", pattern: /^\d{9,18}$/, hint: "9 to 18 digits" },
  father_name: { label: "Father's name" },
  verification_place: { label: "Place of signing", hint: "Usually your city" },
};

export function labelFor(key: string): string {
  return FIELDS[key]?.label ?? key.replace(/_/g, " ");
}

interface Props {
  submissionId: string;
  missing: string[];
  onSaved: (result: SubmissionResult) => void;
}

export function FilingDetailsForm({ submissionId, missing, onSaved }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [invalid, setInvalid] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const problems: Record<string, string> = {};
    for (const key of missing) {
      const value = (values[key] ?? "").trim();
      const field = FIELDS[key];
      if (!value) problems[key] = "Required";
      else if (field?.pattern && !field.pattern.test(value)) problems[key] = field.hint ?? "Invalid format";
    }
    setInvalid(problems);
    if (Object.keys(problems).length) return;
    setSaving(true);
    setError("");
    try {
      const trimmed = Object.fromEntries(missing.map((key) => [key, values[key].trim()]));
      onSaved(await saveFilingDetails(submissionId, trimmed));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The details could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="filing-details-form" onSubmit={submit} noValidate>
      <div className="filing-details-grid">
        {missing.map((key) => {
          const field = FIELDS[key] ?? { label: labelFor(key) };
          const id = `fd-${key}`;
          return (
            <label key={key} htmlFor={id} className={invalid[key] ? "has-error" : ""}>
              <span>{field.label}</span>
              {field.options ? (
                <select id={id} value={values[key] ?? ""} onChange={(e) => setValues({ ...values, [key]: e.target.value })}>
                  <option value="">Select…</option>
                  {field.options.map(([code, name]) => (
                    <option key={code} value={code}>{name}</option>
                  ))}
                </select>
              ) : (
                <input
                  id={id}
                  type={field.type ?? "text"}
                  placeholder={field.placeholder}
                  value={values[key] ?? ""}
                  onChange={(e) => setValues({ ...values, [key]: e.target.value })}
                />
              )}
              <small>{invalid[key] ?? field.hint ?? ""}</small>
            </label>
          );
        })}
      </div>
      {error && <p className="filing-details-error" role="alert">{error}</p>}
      <button type="submit" disabled={saving}>
        {saving ? "Saving and re-running…" : "Save details and create ITR file"}
      </button>
    </form>
  );
}
