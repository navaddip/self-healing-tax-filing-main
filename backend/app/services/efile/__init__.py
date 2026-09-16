"""E-file boundary.

The IRS has no open public e-file API: real transmission requires the MeF
system behind an EFIN/ERO that has passed ATS testing. That is out of scope for
this build, so filing sits behind a swappable adapter:

  * ``PdfSelfFileBackend``   -- default; the taxpayer self-files the generated
    return (mail / IRS Free File Fillable Forms / IRS Direct File).
  * ``MockTransmitterBackend`` -- simulates a commercial MeF transmitter,
    returning an Accepted/Rejected acknowledgement, to demonstrate the swap.

Drop in a real ``TransmitterBackend`` the day a transmitter agreement exists,
without touching the rest of the pipeline.
"""

from app.services.efile.backends import (
    EFileBackend,
    JsonSelfFileBackend,
    MockEriBackend,
    MockTransmitterBackend,
    PdfSelfFileBackend,
    SubmissionAck,
    get_backend,
)

__all__ = [
    "EFileBackend",
    "JsonSelfFileBackend",
    "MockEriBackend",
    "MockTransmitterBackend",
    "PdfSelfFileBackend",
    "SubmissionAck",
    "get_backend",
]
