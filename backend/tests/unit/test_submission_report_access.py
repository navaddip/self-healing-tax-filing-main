from app.api.routes.submissions import _report_download_eligible


def _state(confidence: float, *, valid: bool = True, status: str = "completed"):
    return {
        "status": status,
        "verification": {
            "valid": valid,
            "confidence_score": confidence,
        },
    }


def test_report_download_requires_97_percent_confidence():
    assert not _report_download_eligible(_state(0.9699))
    assert _report_download_eligible(_state(0.97))
    assert _report_download_eligible(_state(0.99))


def test_report_download_requires_valid_completed_submission():
    assert not _report_download_eligible(_state(0.99, valid=False))
    assert not _report_download_eligible(_state(0.99, status="verifying"))
    assert not _report_download_eligible({"status": "completed"})
