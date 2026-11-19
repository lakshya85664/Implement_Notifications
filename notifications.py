
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from uuid import uuid4


# -----------------------------
# ENUMERATIONS
# -----------------------------

class WorkflowState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"


class NotificationType(str, Enum):
    ORDER_DELAYED = "order_delayed"
    ORDER_APPROVED = "order_approved"
    ORDER_COMPLETED = "order_completed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DELIVERED = "delivered"
    FAILED = "failed"


# -----------------------------
# INPUT MODEL
# -----------------------------

class NotificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_key: str = Field(min_length=1)
    notification_type: NotificationType
    recipient: str = Field(min_length=3)
    template_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


# -----------------------------
# WORKFLOW RUN MODEL
# -----------------------------

class WorkflowRun(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    business_key: str
    state: WorkflowState = WorkflowState.CREATED
    attempts: int = 0
    context: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)

    def record(self, event: str, **details: Any) -> None:
        self.events.append({
            "run_id": self.run_id,
            "event": event,
            "state": self.state.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details
        })


# -----------------------------
# NOTIFICATION TASK MODEL
# -----------------------------

class NotificationTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    notification_type: NotificationType
    recipient: str
    template_id: str
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0


# -----------------------------
# NOTIFICATION EVENT MODEL
# -----------------------------

class NotificationEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    event_type: NotificationType
    payload: dict[str, Any] = Field(default_factory=dict)


# -----------------------------
# DELIVERY RESULT MODEL
# -----------------------------

class DeliveryResult(BaseModel):
    success: bool
    recipient: str
    notification_type: NotificationType
    message_id: str | None = None
    error: str | None = None
    attempts: int = 0


# -----------------------------
# TRACE MODEL
# -----------------------------

class TraceRecord(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    event: str
    state: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


# -----------------------------
# WORKFLOW TRANSITIONS
# -----------------------------

LEGAL_TRANSITIONS = {
    (WorkflowState.CREATED, "start"): WorkflowState.RUNNING,
    (WorkflowState.RUNNING, "complete"): WorkflowState.COMPLETED,
    (WorkflowState.RUNNING, "pause"): WorkflowState.WAITING,
    (WorkflowState.WAITING, "resume"): WorkflowState.RUNNING,
    (WorkflowState.RUNNING, "fail"): WorkflowState.NEEDS_REVIEW,
}


def transition(run: WorkflowRun, event: str) -> WorkflowRun:
    key = (run.state, event)

    next_state = LEGAL_TRANSITIONS.get(key)

    if next_state is None:
        run.record(
            "invalid_transition",
            attempted_event=event
        )
        raise ValueError(
            f"Illegal transition: {run.state.value} + {event}"
        )

    previous_state = run.state
    run.state = next_state

    run.record(
        event,
        previous_state=previous_state.value,
        next_state=next_state.value
    )

    return run


# -----------------------------
# TOPIC FIXTURE
# -----------------------------

def run_topic_fixture() -> dict[str, Any]:

    run = WorkflowRun(
        run_id="RUN-1",
        business_key="BUSINESS-1"
    )

    transition(run, "start")

    run.record(
        "topic.started",
        topic="Notifications"
    )

    return {
        "status": run.state.value,
        "run_id": run.run_id,
        "events": run.events
    }


if __name__ == "__main__":
    print(run_topic_fixture())


# ============================================================
# TASK 2 - NOTIFICATION IMPLEMENTATION
# ============================================================

import json
from pathlib import Path


# -----------------------------
# TEMPLATE REGISTRY
# -----------------------------

NOTIFICATION_TEMPLATES = {
    "delay_template": {
        "type": NotificationType.ORDER_DELAYED,
        "subject": "Your order has been delayed",
        "body": (
            "Hello {customer_name}, "
            "your order {order_id} has been delayed. "
            "Reason: {reason}."
        ),
    },

    "approval_template": {
        "type": NotificationType.ORDER_APPROVED,
        "subject": "Your order has been approved",
        "body": (
            "Hello {customer_name}, "
            "your order {order_id} has been approved."
        ),
    },

    "completion_template": {
        "type": NotificationType.ORDER_COMPLETED,
        "subject": "Your order is completed",
        "body": (
            "Hello {customer_name}, "
            "your order {order_id} has been completed."
        ),
    },

    "internal_completion_template": {
        "type": NotificationType.ORDER_COMPLETED,
        "subject": "Order completed - Internal update",
        "body": (
            "Order {order_id} for {customer_name} "
            "has been successfully completed."
        ),
    },
}


# -----------------------------
# FAKE DELIVERY ADAPTER
# -----------------------------

class FakeDeliveryAdapter:

    def __init__(self):
        self.delivered_messages = []

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        idempotency_key: str
    ) -> dict:

        message = {
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "idempotency_key": idempotency_key,
            "message_id": f"MSG-{len(self.delivered_messages) + 1}",
            "status": "delivered",
        }

        self.delivered_messages.append(message)

        return message


# -----------------------------
# NOTIFICATION SERVICE
# -----------------------------

class NotificationService:

    def __init__(self, adapter: FakeDeliveryAdapter):

        self.adapter = adapter

        # Stores successful notification deliveries.
        self.delivered_keys = set()

        self.results = []

    def send_notification(
        self,
        run: WorkflowRun,
        notification: NotificationInput
    ) -> DeliveryResult:

        # Validate the template.
        template = NOTIFICATION_TEMPLATES.get(
            notification.template_id
        )

        if template is None:
            raise ValueError("Unknown notification template")

        # Ensure template matches notification event.
        if template["type"] != notification.notification_type:
            raise ValueError(
                "Notification type does not match template"
            )

        # Create a stable idempotency key.
        idempotency_key = "|".join([
            run.run_id,
            notification.business_key,
            notification.notification_type.value,
            notification.recipient,
        ])

        # Prevent duplicate delivery.
        if idempotency_key in self.delivered_keys:

            run.record(
                "notification.duplicate_skipped",
                business_key=notification.business_key,
                recipient=notification.recipient,
            )

            return DeliveryResult(
                success=True,
                recipient=notification.recipient,
                notification_type=notification.notification_type,
                message_id=None,
                attempts=0,
            )

        # Render the template.
        try:
            subject = template["subject"]

            body = template["body"].format(
                **notification.payload
            )

        except (KeyError, ValueError, IndexError) as exc:

            run.record(
                "notification.validation_failed",
                error_type=type(exc).__name__,
            )

            raise ValueError(
                f"Invalid notification payload: {exc}"
            ) from exc

        # Deliver through the adapter.
        message = self.adapter.send(
            recipient=notification.recipient,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
        )

        # Record successful delivery.
        self.delivered_keys.add(idempotency_key)

        result = DeliveryResult(
            success=True,
            recipient=notification.recipient,
            notification_type=notification.notification_type,
            message_id=message["message_id"],
            attempts=1,
        )

        self.results.append(result.model_dump())

        run.record(
            "notification.delivered",
            recipient=notification.recipient,
            message_id=message["message_id"],
            business_key=notification.business_key,
        )

        return result


# -----------------------------
# TASK 2 - HAPPY PATH FIXTURE
# -----------------------------

def run_notification_fixture() -> dict:

    run = WorkflowRun(
        run_id="RUN-NOTIFY-001",
        business_key="ORDER-1001",
    )

    transition(run, "start")

    adapter = FakeDeliveryAdapter()

    service = NotificationService(adapter)

    notification = NotificationInput(
        business_key="ORDER-1001",
        notification_type=NotificationType.ORDER_DELAYED,
        recipient="customer@example.com",
        template_id="delay_template",
        payload={
            "customer_name": "Alex",
            "order_id": "ORDER-1001",
            "reason": "Weather conditions",
        },
    )

    result = service.send_notification(
        run,
        notification
    )

    return {
        "run_id": run.run_id,
        "workflow_state": run.state.value,
        "delivery_result": result.model_dump(mode="json"),
        "messages": adapter.delivered_messages,
        "events": run.events,
    }


# -----------------------------
# SAVE TASK 2 OUTPUT
# -----------------------------

def save_notification_output():

    output = run_notification_fixture()

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "task2_notifications.json"

    output_file.write_text(
        json.dumps(output, indent=4),
        encoding="utf-8"
    )

    print(json.dumps(output, indent=4))

    print(f"\nSaved output: {output_file}")


if __name__ == "__main__":
    save_notification_output()


# ============================================================
# TASK 3 - FAILURE, RETRY AND REPLAY SAFETY
# ============================================================


class DeliveryFailure(Exception):
    """Represents a classified notification delivery failure."""

    def __init__(
        self,
        message: str,
        retryable: bool,
        error_type: str
    ):
        super().__init__(message)
        self.retryable = retryable
        self.error_type = error_type


class RetryingDeliveryAdapter:
    """
    Adds bounded retry, response validation and
    structured attempt tracing around a delivery adapter.
    """

    def __init__(
        self,
        adapter,
        max_attempts: int = 3,
        timeout_seconds: float = 5.0
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.adapter = adapter
        self.max_attempts = max_attempts
        self.timeout_seconds = timeout_seconds
        self.attempt_log = []

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        idempotency_key: str
    ) -> dict:

        for attempt in range(1, self.max_attempts + 1):

            try:
                response = self.adapter.send(
                    recipient=recipient,
                    subject=subject,
                    body=body,
                    idempotency_key=idempotency_key,
                )

                # Validate the external adapter response.
                if not isinstance(response, dict):
                    raise DeliveryFailure(
                        "Adapter returned a non-dictionary response",
                        retryable=False,
                        error_type="malformed_response",
                    )

                if (
                    not response.get("message_id")
                    or response.get("status") != "delivered"
                ):
                    raise DeliveryFailure(
                        "Adapter returned an invalid delivery response",
                        retryable=False,
                        error_type="malformed_response",
                    )

                self.attempt_log.append({
                    "attempt": attempt,
                    "status": "success",
                    "error_type": None,
                    "idempotency_key": idempotency_key,
                })

                return response

            except TimeoutError as exc:

                error_type = "timeout"
                retryable = True
                error_message = str(exc) or "Delivery timed out"

            except DeliveryFailure as exc:

                error_type = exc.error_type
                retryable = exc.retryable
                error_message = str(exc)

            except Exception as exc:

                # Unknown adapter errors are not automatically
                # retried because their side effects are uncertain.
                error_type = "unexpected_error"
                retryable = False
                error_message = str(exc) or type(exc).__name__

            self.attempt_log.append({
                "attempt": attempt,
                "status": "failed",
                "error_type": error_type,
                "error": error_message,
                "retryable": retryable,
                "idempotency_key": idempotency_key,
            })

            if not retryable:

                raise DeliveryFailure(
                    error_message,
                    retryable=False,
                    error_type=error_type,
                )

            if attempt == self.max_attempts:

                raise DeliveryFailure(
                    error_message,
                    retryable=True,
                    error_type=error_type,
                )

            # Deterministic exponential backoff schedule.
            # No real sleeping is required in these tests.
            delay_seconds = min(2 ** (attempt - 1), 30)

            self.attempt_log[-1]["next_retry_in_seconds"] = (
                delay_seconds
            )

        raise RuntimeError("Unexpected retry loop termination")


# -----------------------------
# SCRIPTED FAILURE ADAPTER
# -----------------------------

class ScriptedDeliveryAdapter:

    def __init__(self, outcomes):

        self.outcomes = list(outcomes)
        self.calls = 0

    def send(
        self,
        recipient,
        subject,
        body,
        idempotency_key
    ):

        self.calls += 1

        if not self.outcomes:
            raise RuntimeError("No scripted outcome available")

        outcome = self.outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


# -----------------------------
# IDEMPOTENT TIMEOUT FIXTURE
# -----------------------------

class IdempotentTimeoutAdapter:

    """
    Simulates a timeout after the remote side effect
    has already been accepted.

    Replaying the same idempotency key must not
    repeat the side effect.
    """

    def __init__(self):

        self.accepted = {}
        self.side_effect_count = 0
        self.first_call = True

    def send(
        self,
        recipient,
        subject,
        body,
        idempotency_key
    ):

        if idempotency_key not in self.accepted:

            self.side_effect_count += 1

            self.accepted[idempotency_key] = {
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "message_id": "MSG-IDEMPOTENT-1",
                "status": "delivered",
            }

        response = self.accepted[idempotency_key]

        if self.first_call:
            self.first_call = False

            # Simulate lost acknowledgement after acceptance.
            raise TimeoutError(
                "Acknowledgement timed out after acceptance"
            )

        return response.copy()


# -----------------------------
# FAILURE RECOVERY FIXTURE
# -----------------------------

def run_failure_recovery_fixture():

    adapter = ScriptedDeliveryAdapter([
        TimeoutError("Temporary gateway timeout"),
        {
            "message_id": "MSG-RECOVERY-1",
            "status": "delivered",
        },
    ])

    retry_adapter = RetryingDeliveryAdapter(
        adapter,
        max_attempts=3,
        timeout_seconds=5.0,
    )

    try:

        response = retry_adapter.send(
            recipient="customer@example.com",
            subject="Order update",
            body="Your order has been approved.",
            idempotency_key="RUN-RECOVERY-1|ORDER-3001",
        )

        return {
            "status": "recovered",
            "response": response,
            "attempts": len(retry_adapter.attempt_log),
            "next_action": "continue_workflow",
            "trace": retry_adapter.attempt_log,
        }

    except DeliveryFailure as exc:

        return {
            "status": "failed",
            "error_type": exc.error_type,
            "error": str(exc),
            "attempts": len(retry_adapter.attempt_log),
            "next_action": (
                "escalate_to_operator"
                if exc.retryable
                else "quarantine_and_review"
            ),
            "trace": retry_adapter.attempt_log,
        }


def save_task3_evidence():

    output = run_failure_recovery_fixture()

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "task3_recovery.json"

    output_file.write_text(
        json.dumps(output, indent=4),
        encoding="utf-8",
    )

    print(json.dumps(output, indent=4))

    print(f"\nSaved recovery evidence: {output_file}")


if __name__ == "__main__":
    save_task3_evidence()


# ============================================================
# TASK 4 - INTEGRATION BOUNDARY AND OBSERVABILITY
# ============================================================

import time
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
)


# -----------------------------
# SECRET REDACTION
# -----------------------------

SENSITIVE_KEYWORDS = (
    "password",
    "secret",
    "token",
    "api_key",
    "authorization",
    "credential",
)


def redact_secrets(data):

    if isinstance(data, dict):

        sanitized = {}

        for key, value in data.items():

            normalized_key = str(key).lower()

            if any(
                keyword in normalized_key
                for keyword in SENSITIVE_KEYWORDS
            ):
                sanitized[key] = "[REDACTED]"

            else:
                sanitized[key] = redact_secrets(value)

        return sanitized

    if isinstance(data, list):
        return [redact_secrets(item) for item in data]

    if isinstance(data, tuple):
        return [redact_secrets(item) for item in data]

    return data


# -----------------------------
# OBSERVABILITY METRICS
# -----------------------------

class NotificationMetrics:

    def __init__(self):

        self.total_attempts = 0
        self.successful_deliveries = 0
        self.failed_deliveries = 0
        self.timeout_count = 0
        self.total_latency_ms = 0.0

    def record(
        self,
        success: bool,
        latency_ms: float,
        error_type: str | None = None,
    ):

        self.total_attempts += 1
        self.total_latency_ms += latency_ms

        if success:
            self.successful_deliveries += 1
        else:
            self.failed_deliveries += 1

        if error_type == "timeout":
            self.timeout_count += 1

    def report(self) -> dict:

        average_latency = (
            self.total_latency_ms / self.total_attempts
            if self.total_attempts
            else 0.0
        )

        success_rate = (
            self.successful_deliveries / self.total_attempts
            if self.total_attempts
            else 0.0
        )

        return {
            "total_attempts": self.total_attempts,
            "successful_deliveries": self.successful_deliveries,
            "failed_deliveries": self.failed_deliveries,
            "timeout_count": self.timeout_count,
            "average_latency_ms": round(average_latency, 3),
            "success_rate": round(success_rate, 3),
        }


# -----------------------------
# INJECTABLE OBSERVABILITY
# ADAPTER
# -----------------------------

class ObservedDeliveryAdapter:

    def __init__(
        self,
        adapter,
        metrics: NotificationMetrics,
        traces: list,
        timeout_seconds: float = 5.0,
    ):

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.adapter = adapter
        self.metrics = metrics
        self.traces = traces
        self.timeout_seconds = timeout_seconds

    def send(
        self,
        recipient,
        subject,
        body,
        idempotency_key,
    ):

        start_time = time.perf_counter()

        executor = ThreadPoolExecutor(max_workers=1)

        future = executor.submit(
            self.adapter.send,
            recipient=recipient,
            subject=subject,
            body=body,
            idempotency_key=idempotency_key,
        )

        error_type = None

        try:

            response = future.result(
                timeout=self.timeout_seconds
            )

            latency_ms = (
                time.perf_counter() - start_time
            ) * 1000

            self.metrics.record(
                success=True,
                latency_ms=latency_ms,
            )

            trace = {
                "event": "adapter.delivery_succeeded",
                "recipient": recipient,
                "idempotency_key": idempotency_key,
                "latency_ms": round(latency_ms, 3),
                "status": "success",
            }

            self.traces.append(redact_secrets(trace))

            return response

        except FutureTimeoutError as exc:

            error_type = "timeout"

            latency_ms = (
                time.perf_counter() - start_time
            ) * 1000

            self.metrics.record(
                success=False,
                latency_ms=latency_ms,
                error_type=error_type,
            )

            trace = {
                "event": "adapter.delivery_failed",
                "recipient": recipient,
                "idempotency_key": idempotency_key,
                "error_type": error_type,
                "latency_ms": round(latency_ms, 3),
                "status": "failed",
                "next_action": "retry_or_escalate",
            }

            self.traces.append(redact_secrets(trace))

            future.cancel()

            raise DeliveryFailure(
                "External dependency timed out",
                retryable=True,
                error_type=error_type,
            ) from exc

        except Exception as exc:

            error_type = (
                exc.error_type
                if isinstance(exc, DeliveryFailure)
                else "integration_error"
            )

            latency_ms = (
                time.perf_counter() - start_time
            ) * 1000

            self.metrics.record(
                success=False,
                latency_ms=latency_ms,
                error_type=error_type,
            )

            trace = {
                "event": "adapter.delivery_failed",
                "recipient": recipient,
                "idempotency_key": idempotency_key,
                "error_type": error_type,
                "latency_ms": round(latency_ms, 3),
                "status": "failed",
            }

            self.traces.append(redact_secrets(trace))

            raise

        finally:

            # A running Python thread cannot be forcibly terminated.
            # Real network adapters must also enforce their own
            # connection/read timeout.
            executor.shutdown(
                wait=False,
                cancel_futures=True,
            )


# -----------------------------
# INTEGRATION STATUS FUNCTION
# -----------------------------

def get_integration_status(
    metrics: NotificationMetrics,
    traces: list,
) -> dict:

    report = metrics.report()

    return {
        "component": "notification_delivery",
        "status": (
            "healthy"
            if report["failed_deliveries"] == 0
            else "degraded"
        ),
        "metrics": report,
        "trace_count": len(traces),
        "recent_traces": traces[-10:],
    }


# -----------------------------
# TASK 4 FIXTURE
# -----------------------------

def run_observability_fixture():

    run = WorkflowRun(
        run_id="RUN-OBS-001",
        business_key="ORDER-4001",
    )

    transition(run, "start")

    fake_adapter = FakeDeliveryAdapter()

    metrics = NotificationMetrics()

    traces = []

    observed_adapter = ObservedDeliveryAdapter(
        adapter=fake_adapter,
        metrics=metrics,
        traces=traces,
        timeout_seconds=5.0,
    )

    retry_adapter = RetryingDeliveryAdapter(
        adapter=observed_adapter,
        max_attempts=3,
    )

    response = retry_adapter.send(
        recipient="customer@example.com",
        subject="Order completed",
        body="Your order is completed.",
        idempotency_key="RUN-OBS-001|ORDER-4001",
    )

    # Demonstrate nested secret redaction.
    sample_log = redact_secrets({
        "event": "configuration.checked",
        "api_key": "FAKE-SECRET-VALUE",
        "details": {
            "access_token": "FAKE-TOKEN",
            "mode": "test",
        },
    })

    status = get_integration_status(
        metrics,
        traces,
    )

    return {
        "run_id": run.run_id,
        "response": response,
        "status": status,
        "traces": traces,
        "metrics": metrics.report(),
        "redaction_example": sample_log,
    }


# -----------------------------
# SAVE TASK 4 EVIDENCE
# -----------------------------

def save_task4_evidence():

    output = run_observability_fixture()

    output_dir = Path("outputs")
    trace_dir = Path("traces")
    report_dir = Path("reports")

    output_dir.mkdir(exist_ok=True)
    trace_dir.mkdir(exist_ok=True)
    report_dir.mkdir(exist_ok=True)

    (output_dir / "task4_observability.json").write_text(
        json.dumps(output, indent=4),
        encoding="utf-8",
    )

    (trace_dir / "task4_traces.json").write_text(
        json.dumps(
            output["traces"],
            indent=4
        ),
        encoding="utf-8",
    )

    (report_dir / "task4_metrics.json").write_text(
        json.dumps(
            output["metrics"],
            indent=4
        ),
        encoding="utf-8",
    )

    print(json.dumps(output, indent=4))

    print("\nTask 4 evidence generated successfully.")


if __name__ == "__main__":
    print("\nTASK 4 - OBSERVABILITY EVIDENCE")
    save_task4_evidence()
