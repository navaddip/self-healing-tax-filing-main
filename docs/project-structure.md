# Project Structure

```text
tax/
|-- backend/
|   |-- app/
|   |   |-- agents/
|   |   |   |-- reading/
|   |   |   |-- income/
|   |   |   |-- regimes/
|   |   |   |-- comparison/
|   |   |   |-- verification/
|   |   |   |-- remediation/
|   |   |   `-- documentation/
|   |   |-- itr/
|   |   |-- api/
|   |   |   |-- routes/
|   |   |   `-- dependencies/
|   |   |-- core/
|   |   |-- db/
|   |   |-- models/
|   |   |-- prompts/
|   |   |-- repositories/
|   |   |-- schemas/
|   |   |-- services/
|   |   |   |-- chroma/
|   |   |   |-- documents/
|   |   |   |-- ollama/
|   |   |   |-- ocr/
|   |   |   |-- pdf/
|   |   |   `-- storage/
|   |   |-- tax_rules/
|   |   |-- utils/
|   |   `-- workflow/
|   `-- tests/
|       |-- fixtures/
|       |-- integration/
|       `-- unit/
|-- frontend/
|   |-- public/
|   `-- src/
|       |-- api/
|       |-- components/
|       |-- features/
|       |   |-- audit/
|       |   |-- reports/
|       |   |-- submissions/
|       |   |-- upload/
|       |   `-- verification/
|       |-- hooks/
|       |-- pages/
|       |-- styles/
|       `-- types/
|-- infra/
|   |-- chromadb/
|   |-- ollama/
|   `-- postgres/
|-- scripts/
|-- storage/
|   |-- generated/
|   |-- previews/
|   `-- uploads/
|-- docs/
|   |-- architecture.md
|   `-- project-structure.md
`-- README.md
```

## Ownership

- `backend/app/agents`: agent-specific decision logic.
- `backend/app/workflow`: LangGraph state, nodes, edges, and routing.
- `backend/app/tax_rules`: versioned deterministic tax rule data.
- `backend/app/services`: infrastructure adapters with no agent policy.
- `backend/app/schemas`: typed request, response, state, and agent contracts.
- `backend/app/repositories`: PostgreSQL persistence boundaries.
- `frontend/src/features`: user-facing workflows grouped by domain.
- `infra`: local service configuration added during implementation.
- `storage`: development artifacts; contents remain excluded from source control.

Placeholder files exist only to preserve empty directories. They contain no
implementation.
