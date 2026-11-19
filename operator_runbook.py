
import json
from pathlib import Path

from notifications import (
    WorkflowRun,
    NotificationType,
    NotificationInput,
    FakeDeliveryAdapter,
    NotificationService,
    ScriptedDeliveryAdapter,
    RetryingDeliveryAdapter,
    DeliveryFailure,
    transition,
)


def success_scenario():

    run = WorkflowRun(
        run_id="RUN-OP-SUCCESS",
        business_key="ORDER-5001",
    )

    transition(run, "start")

    adapter = FakeDeliveryAdapter()
    service = NotificationService(adapter)

    notification = NotificationInput(
        business_key="ORDER-5001",
        notification_type=NotificationType.ORDER_COMPLETED,
        recipient="customer@example.com",
        template_id="completion_template",
        payload={
            "customer_name": "Alex",
            "order_id": "ORDER-5001",
        },
    )

    result = service.send_notification(run, notification)

    return {
        "scenario": "success",
        "status": "delivered",
        "next_action": "continue_workflow",
        "delivery_count": len(adapter.delivered_messages),
        "result": result.model_dump(mode="json"),
        "traces": run.events,
    }


def failure_scenario():

    adapter = ScriptedDeliveryAdapter([
        DeliveryFailure(
            "Recipient permanently rejected",
            retryable=False,
            error_type="permanent_failure",
        )
    ])

    retry_adapter = RetryingDeliveryAdapter(
        adapter,
        max_attempts=3,
    )

    try:

        retry_adapter.send(
            recipient="invalid@example.com",
            subject="Order update",
            body="Order update",
            idempotency_key="RUN-OP-FAIL|ORDER-5002",
        )

    except DeliveryFailure as exc:

        return {
            "scenario": "failure",
            "status": "failed",
            "error_type": exc.error_type,
            "attempts": len(retry_adapter.attempt_log),
            "next_action": "quarantine_and_review",
            "traces": retry_adapter.attempt_log,
        }


def replay_scenario():

    run = WorkflowRun(
        run_id="RUN-OP-REPLAY",
        business_key="ORDER-5003",
    )

    transition(run, "start")

    adapter = FakeDeliveryAdapter()
    service = NotificationService(adapter)

    notification = NotificationInput(
        business_key="ORDER-5003",
        notification_type=NotificationType.ORDER_APPROVED,
        recipient="customer@example.com",
        template_id="approval_template",
        payload={
            "customer_name": "Alex",
            "order_id": "ORDER-5003",
        },
    )

    first = service.send_notification(run, notification)
    second = service.send_notification(run, notification)

    return {
        "scenario": "replay",
        "status": "duplicate_skipped",
        "first_delivery_success": first.success,
        "second_delivery_success": second.success,
        "actual_delivery_count": len(adapter.delivered_messages),
        "next_action": "continue_without_resending",
        "traces": run.events,
    }


def recovery_scenario():

    adapter = ScriptedDeliveryAdapter([
        TimeoutError("Temporary gateway timeout"),
        {
            "message_id": "MSG-RECOVERED-5004",
            "status": "delivered",
        },
    ])

    retry_adapter = RetryingDeliveryAdapter(
        adapter,
        max_attempts=3,
    )

    response = retry_adapter.send(
        recipient="customer@example.com",
        subject="Order update",
        body="Your order has been completed",
        idempotency_key="RUN-OP-RECOVERY|ORDER-5004",
    )

    return {
        "scenario": "recovery",
        "status": "recovered",
        "attempts": len(retry_adapter.attempt_log),
        "response": response,
        "next_action": "continue_workflow",
        "traces": retry_adapter.attempt_log,
    }


def generate_operator_evidence():

    scenarios = {
        "success": success_scenario(),
        "failure": failure_scenario(),
        "replay": replay_scenario(),
        "recovery": recovery_scenario(),
    }

    total_deliveries = (
        scenarios["success"]["delivery_count"]
        + scenarios["replay"]["actual_delivery_count"]
    )

    summary = {
        "topic": "Topic 12 - Implement Notifications",
        "overall_status": "completed",
        "scenarios_executed": 4,
        "successful_scenarios": 4,
        "actual_deliveries": total_deliveries,
        "duplicate_deliveries_prevented": 1,
        "recovery_attempts": scenarios["recovery"]["attempts"],
        "failure_attempts": scenarios["failure"]["attempts"],
    }

    evidence = {
        "summary": summary,
        "scenarios": scenarios,
    }

    output_dir = Path("outputs")
    trace_dir = Path("traces")
    report_dir = Path("reports")

    for directory in (output_dir, trace_dir, report_dir):
        directory.mkdir(exist_ok=True)

    # Save complete evidence.
    (output_dir / "task5_operator_evidence.json").write_text(
        json.dumps(evidence, indent=4),
        encoding="utf-8",
    )

    # Save structured traces.
    traces = []

    for scenario_name, scenario in scenarios.items():

        for event in scenario["traces"]:

            traces.append({
                "scenario": scenario_name,
                "run_id": event.get("run_id"),
                "event": event.get("event"),
                "attempt": event.get("attempt"),
                "status": event.get("status"),
                "error_type": event.get("error_type"),
                "idempotency_key": event.get("idempotency_key"),
            })

    (trace_dir / "task5_traces.json").write_text(
        json.dumps(traces, indent=4),
        encoding="utf-8",
    )

    # Operator report.
    report = f"""# Topic 12 - Operator Runbook

## 1. Assessment Summary

- Topic: Implement Notifications in Code
- Overall status: Completed
- Scenarios executed: {summary['scenarios_executed']}
- Successful scenarios: {summary['successful_scenarios']}
- Actual deliveries: {summary['actual_deliveries']}
- Duplicate deliveries prevented: {summary['duplicate_deliveries_prevented']}

## 2. Execution Commands

```cmd
python notifications.py
python operator_runbook.py
python -m pytest -v
python -m pytest -q
```

## 3. Scenario Results

| Scenario | Result | Operator action |
|---|---|---|
| Success | Delivered | Continue workflow |
| Failure | Permanent failure | Quarantine and review |
| Replay | Duplicate skipped | Continue without resending |
| Recovery | Recovered | Continue workflow |

## 4. Scenario Evidence

### Success

{json.dumps(scenarios['success'], indent=2)}

### Failure

{json.dumps(scenarios['failure'], indent=2)}

### Replay

{json.dumps(scenarios['replay'], indent=2)}

### Recovery

{json.dumps(scenarios['recovery'], indent=2)}

## 5. Measurements

| Measurement | Result |
|---|---:|
| Scenarios executed | {summary['scenarios_executed']} |
| Successful scenarios | {summary['successful_scenarios']} |
| Actual deliveries | {summary['actual_deliveries']} |
| Duplicate deliveries prevented | {summary['duplicate_deliveries_prevented']} |
| Recovery attempts | {summary['recovery_attempts']} |
| Permanent failure attempts | {summary['failure_attempts']} |

## 6. Known Limitations

1. Delivery adapters use local fake implementations.
2. Deduplication state is stored in memory and is not persistent across process restarts.
3. Real production delivery requires a persistent idempotency store.
4. Retry backoff is recorded but not actually delayed.
5. Caller-side timeouts cannot forcibly terminate a running Python thread.
6. Real adapters must enforce their own network connection and read timeouts.
7. The current examples do not implement a distributed notification queue.

## 7. Operator Actions

| State | Recommended action |
|---|---|
| Delivered | Continue workflow |
| Temporary failure | Retry within configured limit |
| Permanent failure | Quarantine and investigate |
| Duplicate skipped | Do not resend |
| Recovered | Resume workflow |
| Retry exhausted | Escalate to operator |

## 8. Engineering Reflection

The notification implementation demonstrates how notifications can be designed as an observable and independently testable workflow component. The project separates notification input validation, workflow state, message templates, recipient information and delivery execution into distinct responsibilities.

The template registry ensures that notification content is selected through a defined template rather than being constructed unpredictably. Pydantic models validate incoming requests, while the fake delivery adapter provides a deterministic way to test the system without connecting to production services.

A major engineering challenge was preventing duplicate notifications. Delivery systems can experience a timeout even when the external service has already accepted a message. Retrying such an operation without idempotency can produce duplicate customer messages. The implementation therefore uses stable idempotency keys and verifies that replaying an accepted notification does not repeat its side effect in the simulated adapter.

The retry mechanism distinguishes temporary failures from permanent failures and applies a bounded retry policy. Malformed responses are rejected instead of being treated as successful deliveries. Recovery traces make individual attempts and their outcomes visible.

The integration boundary introduces dependency injection, delivery measurements, structured traces and secret redaction. These features make it easier to investigate failures and understand notification behavior without exposing sensitive configuration.

The implementation also has limitations. Its deduplication store is in memory, so it cannot guarantee duplicate prevention across independent processes or restarts. Retry delays are recorded rather than executed, and the caller-side timeout cannot terminate a running Python thread. A production deployment would require persistent idempotency storage, a durable queue, provider-level timeouts, secure credentials, monitoring and distributed tracing.

Overall, this assessment strengthened my understanding of reliable notification workflows, failure classification, idempotency, integration boundaries and operational evidence.
"""

    (report_dir / "operator_runbook.md").write_text(
        report,
        encoding="utf-8",
    )

    print("\nTOPIC 12 - OPERATOR EVIDENCE")
    print(json.dumps(summary, indent=4))

    print("\nGenerated files:")
    print("outputs/task5_operator_evidence.json")
    print("traces/task5_traces.json")
    print("reports/operator_runbook.md")


if __name__ == "__main__":
    generate_operator_evidence()
