# Topic 12 - Operator Runbook

## 1. Assessment Summary

- Topic: Implement Notifications in Code
- Overall status: Completed
- Scenarios executed: 4
- Successful scenarios: 4
- Actual deliveries: 2
- Duplicate deliveries prevented: 1

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

{
  "scenario": "success",
  "status": "delivered",
  "next_action": "continue_workflow",
  "delivery_count": 1,
  "result": {
    "success": true,
    "recipient": "customer@example.com",
    "notification_type": "order_completed",
    "message_id": "MSG-1",
    "error": null,
    "attempts": 1
  },
  "traces": [
    {
      "run_id": "RUN-OP-SUCCESS",
      "event": "start",
      "state": "running",
      "timestamp": "2026-11-19T12:03:33.419724+00:00",
      "details": {
        "previous_state": "created",
        "next_state": "running"
      }
    },
    {
      "run_id": "RUN-OP-SUCCESS",
      "event": "notification.delivered",
      "state": "running",
      "timestamp": "2026-11-19T12:03:33.419825+00:00",
      "details": {
        "recipient": "customer@example.com",
        "message_id": "MSG-1",
        "business_key": "ORDER-5001"
      }
    }
  ]
}

### Failure

{
  "scenario": "failure",
  "status": "failed",
  "error_type": "permanent_failure",
  "attempts": 1,
  "next_action": "quarantine_and_review",
  "traces": [
    {
      "attempt": 1,
      "status": "failed",
      "error_type": "permanent_failure",
      "error": "Recipient permanently rejected",
      "retryable": false,
      "idempotency_key": "RUN-OP-FAIL|ORDER-5002"
    }
  ]
}

### Replay

{
  "scenario": "replay",
  "status": "duplicate_skipped",
  "first_delivery_success": true,
  "second_delivery_success": true,
  "actual_delivery_count": 1,
  "next_action": "continue_without_resending",
  "traces": [
    {
      "run_id": "RUN-OP-REPLAY",
      "event": "start",
      "state": "running",
      "timestamp": "2026-11-19T12:03:33.419873+00:00",
      "details": {
        "previous_state": "created",
        "next_state": "running"
      }
    },
    {
      "run_id": "RUN-OP-REPLAY",
      "event": "notification.delivered",
      "state": "running",
      "timestamp": "2026-11-19T12:03:33.419902+00:00",
      "details": {
        "recipient": "customer@example.com",
        "message_id": "MSG-1",
        "business_key": "ORDER-5003"
      }
    },
    {
      "run_id": "RUN-OP-REPLAY",
      "event": "notification.duplicate_skipped",
      "state": "running",
      "timestamp": "2026-11-19T12:03:33.419914+00:00",
      "details": {
        "business_key": "ORDER-5003",
        "recipient": "customer@example.com"
      }
    }
  ]
}

### Recovery

{
  "scenario": "recovery",
  "status": "recovered",
  "attempts": 2,
  "response": {
    "message_id": "MSG-RECOVERED-5004",
    "status": "delivered"
  },
  "next_action": "continue_workflow",
  "traces": [
    {
      "attempt": 1,
      "status": "failed",
      "error_type": "timeout",
      "error": "Temporary gateway timeout",
      "retryable": true,
      "idempotency_key": "RUN-OP-RECOVERY|ORDER-5004",
      "next_retry_in_seconds": 1
    },
    {
      "attempt": 2,
      "status": "success",
      "error_type": null,
      "idempotency_key": "RUN-OP-RECOVERY|ORDER-5004"
    }
  ]
}

## 5. Measurements

| Measurement | Result |
|---|---:|
| Scenarios executed | 4 |
| Successful scenarios | 4 |
| Actual deliveries | 2 |
| Duplicate deliveries prevented | 1 |
| Recovery attempts | 2 |
| Permanent failure attempts | 1 |

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
