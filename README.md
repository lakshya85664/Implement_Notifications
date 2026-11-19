
# Topic 12 – Implement Notifications in Code

## Project Overview

This project implements a notification workflow as part of the Workflow Orchestration assessment.

The system simulates order-related notifications for customers and internal teams. It supports notification templates, recipient routing, delivery simulation, duplicate prevention, retry handling, failure classification, integration boundaries, structured tracing and operational reporting.

The implementation uses Python, Pydantic and Pytest.

## Objectives

- Define typed notification and workflow contracts.
- Implement notification templates and delivery.
- Prevent duplicate notification delivery through idempotency.
- Handle timeouts, permanent failures and malformed responses.
- Implement bounded retry and recovery behavior.
- Separate external dependencies through injectable adapters.
- Record structured traces and operational metrics.
- Generate operator runbooks and reproducible evidence.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.13 | Core implementation |
| Pydantic 2.x | Data validation and models |
| Pytest 9.x | Automated testing |
| JSON | Evidence and trace storage |
| ThreadPoolExecutor | Caller-side timeout handling |

## Project Structure

```text
Implement_Notifications/
│
├── notifications.py
├── operator_runbook.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── tests/
│   ├── test_task1_contract.py
│   ├── test_task2_notifications.py
│   ├── test_task3_recovery.py
│   ├── test_task4_observability.py
│   └── test_task5_operator.py
│
├── outputs/
│   ├── task2_notifications.json
│   ├── task3_recovery.json
│   ├── task4_observability.json
│   └── task5_operator_evidence.json
│
├── traces/
│   ├── task4_traces.json
│   └── task5_traces.json
│
└── reports/
    ├── task4_metrics.json
    └── operator_runbook.md
```

## Assessment Tasks

### Task 1 – Workflow Contract and State Model

Implemented typed models for notification input, workflow execution, notification tasks, notification events, delivery results and execution traces.

A workflow state machine enforces legal transitions and rejects invalid state changes.

### Task 2 – Notifications Implementation

Implemented a notification template registry, message rendering, fake delivery adapter and notification service.

Stable idempotency keys prevent repeated delivery of the same notification within the service instance.

### Task 3 – Failure, Retry and Replay Safety

Implemented bounded retries, timeout classification, permanent failure handling and malformed response validation.

The replay test demonstrates that a timeout after remote acceptance does not cause a second side effect when the adapter honors the same idempotency key.

### Task 4 – Integration Boundary and Observability

Implemented injectable delivery adapters, caller-side timeout handling, structured traces, latency measurements, delivery metrics and recursive secret redaction.

An integration status function exposes the current component status and recent traces.

### Task 5 – Operator Runbook and Evidence

Implemented success, failure, replay and recovery scenarios.

Generated JSON evidence, structured traces, an operator runbook and measurement summaries.

## Installation

Clone or download the project.

Open CMD in the project directory:

```cmd
cd /d E:\Tayana_Projects\Workflow_Orchestration\Implement_Notifications
```

Create a virtual environment:

```cmd
python -m venv .venv
```

Activate it:

```cmd
.venv\Scripts\activate
```

Install dependencies:

```cmd
python -m pip install -r requirements.txt
```

## Running the Project

Execute the notification implementation:

```cmd
python notifications.py
```

Execute the operator scenarios:

```cmd
python operator_runbook.py
```

Run the complete test suite:

```cmd
python -m pytest -v
```

## Test Results

| Test Module | Passed |
|---|---:|
| Task 1 | 6 |
| Task 2 | 5 |
| Task 3 | 6 |
| Task 4 | 6 |
| Task 5 | 4 |
| **Total** | **27** |

All 27 automated tests passed during assessment execution.

## Operational Evidence

The project generates evidence under:

- `outputs/` – Notification, recovery, observability and operator evidence.
- `traces/` – Structured execution traces.
- `reports/` – Metrics and operator documentation.

## Known Limitations

1. The delivery adapter is simulated; no real email or messaging provider is connected.
2. Idempotency records are maintained in memory and are not persistent across process restarts.
3. Retry delays are recorded but not actually executed.
4. Caller-side thread timeouts do not forcibly terminate a running Python thread.
5. Production deployment would require durable idempotency storage, provider-level timeouts, a persistent queue and distributed monitoring.

## Reflection

This project helped me understand how notification workflows can be designed as reliable and independently testable components of a larger orchestration system.

One important learning was the separation of notification contracts, templates, recipients and delivery execution. Using Pydantic models made incoming requests predictable, while a template registry ensured consistent message generation. The fake delivery adapter made it possible to test notification behavior without connecting to external services.

Idempotency was another major concept explored during implementation. A timeout does not always mean that an external service rejected a request. The service might have accepted the notification while its acknowledgement was lost. Retrying without an idempotency mechanism could therefore produce duplicate messages. The implementation uses stable keys and tests replay behavior to prevent repeated side effects in the simulated adapter.

The failure-handling task improved my understanding of retry policies, permanent failures, malformed responses and recovery. I also learned how injectable adapters help isolate external dependencies and make testing more deterministic.

The observability implementation introduced structured traces, latency measurements, delivery counters, component status reporting and secret redaction. These capabilities make failures easier to investigate and provide useful operational evidence.

The project also highlighted important production limitations. In-memory deduplication cannot guarantee consistency across process restarts, and a caller-side timeout cannot forcibly stop a running Python thread. A production system would need persistent idempotency storage, a durable notification queue, provider-level timeout controls, secure credential management and distributed monitoring.

Overall, this assessment strengthened my practical understanding of notification orchestration, reliability engineering, failure recovery, idempotency and observability.

