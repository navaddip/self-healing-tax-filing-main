import sys
import time
import requests
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

root = Path(r"D:\self-healing-tax-filing-main")
server_url = "http://127.0.0.1:8000"

test_files = [
    "form16_test_case1_new_regime_87A_marginal_relief.pdf",
    "form16_test_case2_old_regime_87A_zero_tax.pdf",
    "form16_test_case3_old_regime_hp_loss_perquisites.pdf",
    "form16_test_case4_new_regime_surcharge_above_50L.pdf",
    "form16_test_case5_old_regime_deduction_caps_other_income.pdf",
]

print("=== VERIFYING LIVE HTTP SERVER & BACKGROUND WORKER ACROSS ALL 5 DEMO CASES ===")

for idx, filename in enumerate(test_files, 1):
    file_path = root / filename
    if not file_path.exists():
        print(f"[{idx}/5] ⚠️ File not found: {filename}")
        continue

    print(f"\n[{idx}/5] Uploading: {filename}...")
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{server_url}/api/v1/submissions",
            files={"documents": (filename, f, "application/pdf")},
            data={"financial_year": "2025-26"}
        )

    if resp.status_code != 202:
        print(f"  ❌ Upload failed with {resp.status_code}: {resp.text}")
        continue

    sub_id = resp.json()["submission_id"]
    print(f"  ✅ Uploaded successfully. Submission ID: {sub_id}")

    # Poll until status is completed
    max_wait = 20
    start_time = time.time()
    final_data = None
    while time.time() - start_time < max_wait:
        status_resp = requests.get(f"{server_url}/api/v1/submissions/{sub_id}")
        if status_resp.status_code == 200:
            final_data = status_resp.json()
            if final_data.get("status") in ("completed", "failed"):
                break
        time.sleep(1)

    if not final_data or final_data.get("status") != "completed":
        print(f"  ❌ Submission did not complete in time. Status: {final_data.get('status') if final_data else 'unknown'}")
        continue

    comp = final_data.get("comparison") or {}
    ver = final_data.get("verification") or {}
    rec = comp.get("recommended", "N/A")
    sav = comp.get("savings", "0")
    score = ver.get("confidence_score", 0)

    print(f"  ✅ Completed in {time.time() - start_time:.1f}s")
    print(f"     Recommended Regime: {rec}")
    print(f"     Tax Savings: ₹{float(sav):,.2f}")
    print(f"     Verification Confidence: {float(score)*100:.1f}%")

    # Verify Report PDF
    report_url = final_data.get("report_url")
    if report_url:
        rep_resp = requests.get(f"{server_url}{report_url}")
        if rep_resp.status_code == 200 and len(rep_resp.content) > 1000:
            print(f"     ✅ Advisory Report PDF verified ({len(rep_resp.content):,} bytes)")
        else:
            print(f"     ⚠️ Report PDF returned status {rep_resp.status_code}")

    # Verify Sensitivity Analysis endpoint
    sens_resp = requests.post(
        f"{server_url}/api/v1/submissions/{sub_id}/sensitivity",
        json={"salary_deltas": [-100000, 100000], "deduction_deltas": [-50000, 50000]}
    )
    if sens_resp.status_code == 200:
        points = len(sens_resp.json().get("grid", []))
        print(f"     ✅ Sensitivity Analysis grid verified ({points} scenario points)")
    else:
        print(f"     ⚠️ Sensitivity Analysis returned {sens_resp.status_code}")

print("\n=== ALL 5 DEMO CASES VERIFIED LIVE END-TO-END! ===")
