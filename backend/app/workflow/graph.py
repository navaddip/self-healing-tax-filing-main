from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.comparison.agent import RegimeComparisonAgent
from app.agents.documentation.agent import DocumentationAgent
from app.agents.income.computation import IncomeComputationService
from app.agents.reading.agent import ReadingAgent
from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator
from app.agents.remediation.agent import RemediationAgent
from app.agents.verification.agent import VerificationAgent
from app.schemas.tax import (
    AuditEntry,
    HeadwiseIncome,
    IndianTaxpayerData,
    Regime,
    RegimeComparison,
    RegimeTaxResult,
    SubmissionResult,
    VerificationResult,
    WorkflowStatus,
    age_band_on,
)
from app.tax_rules.params import get_params
from app.workflow.state import TaxWorkflowState


class TaxWorkflow:
    def __init__(
        self,
        reading: ReadingAgent | None = None,
        income_service: IncomeComputationService | None = None,
        old_calculator: OldRegimeCalculator | None = None,
        new_calculator: NewRegimeCalculator | None = None,
        comparison_agent: RegimeComparisonAgent | None = None,
        verification: VerificationAgent | None = None,
        remediation: RemediationAgent | None = None,
        documentation: DocumentationAgent | None = None,
        max_attempts: int = 2,
        checkpointer: Any | None = None,
        cancellation_check: Any | None = None,
        filing_details_loader: Any | None = None,
        processing: Any | None = None,  # backwards compatibility
    ):
        self.cancellation_check = cancellation_check
        self.filing_details_loader = filing_details_loader
        self.checkpointer = checkpointer
        self.reading = reading
        self.income_service = income_service or IncomeComputationService()
        self.old_calculator = old_calculator or OldRegimeCalculator()
        self.new_calculator = new_calculator or NewRegimeCalculator()
        self.comparison_agent = comparison_agent or RegimeComparisonAgent()
        self.verifier = verification
        self.remediation = remediation
        self.documentation = documentation
        self.max_attempts = max_attempts
        self.graph = self._build()

    def _build(self):
        graph = StateGraph(TaxWorkflowState)
        def guarded(node):
            def run_node(state):
                if self.cancellation_check and self.cancellation_check(state["submission_id"]):
                    raise RuntimeError("Processing cancelled")
                return node(state)
            return run_node
        for name, node in (("parse", self._parse), ("compute_income", self._compute_income),
                           ("tax_old", self._tax_old), ("tax_new", self._tax_new),
                           ("compare", self._compare), ("verify", self._verify),
                           ("remediate", self._remediate), ("document", self._document),
                           ("manual_review", self._manual_review)):
            graph.add_node(name, guarded(node))

        graph.add_edge(START, "parse")
        graph.add_edge("parse", "compute_income")
        graph.add_edge("compute_income", "tax_old")
        graph.add_edge("compute_income", "tax_new")
        graph.add_edge("tax_old", "compare")
        graph.add_edge("tax_new", "compare")
        graph.add_edge("compare", "verify")
        graph.add_conditional_edges(
            "verify",
            self._route_verification,
            {
                "document": "document",
                "remediate": "remediate",
                "manual_review": "manual_review",
            },
        )
        graph.add_conditional_edges(
            "remediate",
            self._route_remediation,
            {"parse": "parse", "compute_income": "compute_income"},
        )
        graph.add_edge("document", END)
        graph.add_edge("manual_review", END)
        return graph.compile(checkpointer=self.checkpointer or MemorySaver())

    def run(self, state: TaxWorkflowState) -> TaxWorkflowState:
        config = {"configurable": {"thread_id": state.get("submission_id", "default")}}
        try:
            snapshot = self.graph.get_state(config)
            return self.graph.invoke(None if snapshot.next else state, config=config)
        except Exception as exc:
            return {**state, "status": "failed", "error": str(exc)}

    def _parse(self, state: TaxWorkflowState):
        if not self.reading:
            # If no reading agent or data already in state, pass through
            return {
                "status": WorkflowStatus.PARSING.value,
                "extracted_data": state.get("extracted_data", {}),
            }
        scale = 2 + state.get("reextraction_passes", 0)
        paths = [
            Path(p)
            for p in state.get("upload_paths") or [state["upload_path"]]
        ]
        data, raw_text, logs = self.reading.run_many(paths, scale=scale)
        params = get_params(state.get("financial_year", data.financial_year))
        data.financial_year = params.financial_year
        data.assessment_year = params.assessment_year
        details = self.filing_details_loader(state["submission_id"]) if self.filing_details_loader else None
        if details:
            data = data.model_copy(update=details.provided())
            if data.bank_account_number:
                data.bank_account_last4 = data.bank_account_number[-4:]
            if data.date_of_birth:
                data.age_band = age_band_on(data.date_of_birth, params.year)
        return {
            "status": WorkflowStatus.PARSING.value,
            "extracted_data": data.model_dump(mode="json"),
            "raw_text": raw_text,
            "audit_trail": state.get("audit_trail", [])
            + [item.model_dump(mode="json") for item in logs],
        }

    def _compute_income(self, state: TaxWorkflowState):
        data = IndianTaxpayerData.model_validate(state["extracted_data"])
        params = get_params(data.financial_year)
        inc_old = self.income_service.compute(data, Regime.OLD, params)
        inc_new = self.income_service.compute(data, Regime.NEW, params)
        log = AuditEntry(
            agent="IncomeComputationService",
            action="compute_income",
            reason="Computed headwise income under both Old and New regimes",
            details={
                "gti_old": str(inc_old.gross_total_income),
                "gti_new": str(inc_new.gross_total_income),
                "total_income_old": str(inc_old.total_income),
                "total_income_new": str(inc_new.total_income),
            },
        )
        return {
            "status": WorkflowStatus.COMPUTING_INCOME.value,
            "computed_income_old": inc_old.model_dump(mode="json"),
            "computed_income_new": inc_new.model_dump(mode="json"),
            "audit_trail": state.get("audit_trail", []) + [log.model_dump(mode="json")],
        }

    def _tax_old(self, state: TaxWorkflowState):
        data = IndianTaxpayerData.model_validate(state["extracted_data"])
        inc_old = HeadwiseIncome.model_validate(state["computed_income_old"])
        params = get_params(data.financial_year)
        result_old = self.old_calculator.calculate(
            data, inc_old, params, filing_date=data.filing_date or params.filing_due_date
        )
        return {
            "result_old": result_old.model_dump(mode="json"),
        }

    def _tax_new(self, state: TaxWorkflowState):
        data = IndianTaxpayerData.model_validate(state["extracted_data"])
        inc_new = HeadwiseIncome.model_validate(state["computed_income_new"])
        params = get_params(data.financial_year)
        result_new = self.new_calculator.calculate(
            data, inc_new, params, filing_date=data.filing_date or params.filing_due_date
        )
        return {
            "result_new": result_new.model_dump(mode="json"),
        }

    def _compare(self, state: TaxWorkflowState):
        data = IndianTaxpayerData.model_validate(state["extracted_data"])
        res_old = RegimeTaxResult.model_validate(state["result_old"])
        res_new = RegimeTaxResult.model_validate(state["result_new"])
        comparison, log_cmp = self.comparison_agent.run(data, res_old, res_new)
        log_old = AuditEntry(
            agent="OldRegimeCalculator",
            action="calculate_tax_old",
            reason="Computed Old Regime tax liability",
            details={"tax_liability": str(res_old.total_tax_liability)},
        )
        log_new = AuditEntry(
            agent="NewRegimeCalculator",
            action="calculate_tax_new",
            reason="Computed New Regime tax liability",
            details={"tax_liability": str(res_new.total_tax_liability)},
        )
        return {
            "status": WorkflowStatus.COMPARING.value,
            "comparison": comparison.model_dump(mode="json"),
            "calculation": comparison.model_dump(mode="json"),
            "audit_trail": state.get("audit_trail", [])
            + [
                log_old.model_dump(mode="json"),
                log_new.model_dump(mode="json"),
                log_cmp.model_dump(mode="json"),
            ],
        }

    def _verify(self, state: TaxWorkflowState):
        if not self.verifier:
            # Stub verification if not configured yet
            ver = VerificationResult(
                valid=True,
                confidence_score=1.0,
                checks=[],
                correctness_ok=True,
                completeness_ok=True,
            )
            return {
                "status": WorkflowStatus.VERIFYING.value,
                "verification": ver.model_dump(mode="json"),
            }
        data = IndianTaxpayerData.model_validate(state["extracted_data"])
        comparison = RegimeComparison.model_validate(state["comparison"])
        result, log = self.verifier.run(
            data,
            comparison,
            transcript=state.get("transcript"),
        )
        return {
            "status": WorkflowStatus.VERIFYING.value,
            "verification": result.model_dump(mode="json"),
            "audit_trail": state.get("audit_trail", [])
            + [log.model_dump(mode="json")],
        }

    def _route_verification(self, state: TaxWorkflowState):
        result = VerificationResult.model_validate(state["verification"])
        if result.valid:
            return "document"
        if state.get("remediation_attempts", 0) < self.max_attempts:
            return "remediate"
        return "manual_review"

    def _route_remediation(self, state: TaxWorkflowState):
        return "parse" if state.get("needs_reextraction") else "compute_income"

    def _remediate(self, state: TaxWorkflowState):
        if not self.remediation:
            return {"status": WorkflowStatus.REMEDIATING.value}
        data, needs_reextraction, log = self.remediation.run(
            IndianTaxpayerData.model_validate(state["extracted_data"]),
            VerificationResult.model_validate(state["verification"]),
        )
        passes = state.get("reextraction_passes", 0) + (
            1 if needs_reextraction else 0
        )
        return {
            "status": WorkflowStatus.REMEDIATING.value,
            "extracted_data": data.model_dump(mode="json"),
            "remediation_attempts": state.get("remediation_attempts", 0) + 1,
            "needs_reextraction": needs_reextraction,
            "reextraction_passes": passes,
            "audit_trail": state.get("audit_trail", [])
            + [log.model_dump(mode="json")],
        }

    def _document(self, state: TaxWorkflowState):
        if not self.documentation:
            return {"status": WorkflowStatus.COMPLETED.value}
        result = SubmissionResult.model_validate(
            {
                "submission_id": state["submission_id"],
                "status": WorkflowStatus.COMPLETED,
                "original_filename": state["original_filename"],
                "extracted_data": state.get("extracted_data"),
                "comparison": state.get("comparison"),
                "verification": state.get("verification"),
                "audit_trail": state.get("audit_trail", []),
            }
        )
        receipt, path, log = self.documentation.run(
            result,
            Path(state["report_path"]),
            [Path(p) for p in state.get("upload_paths") or [state["upload_path"]]],
        )
        return {
            "status": WorkflowStatus.COMPLETED.value,
            "receipt": receipt.model_dump(mode="json"),
            "audit_trail": state.get("audit_trail", [])
            + [log.model_dump(mode="json")],
        }

    @staticmethod
    def _manual_review(state: TaxWorkflowState):
        return {"status": WorkflowStatus.MANUAL_REVIEW.value}
