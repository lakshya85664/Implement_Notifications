
import time
import pytest

from notifications import (
    FakeDeliveryAdapter,
    NotificationMetrics,
    ObservedDeliveryAdapter,
    DeliveryFailure,
    get_integration_status,
    redact_secrets,
)


def test_successful_delivery_is_observable():

    metrics = NotificationMetrics()
    traces = []

    fake = FakeDeliveryAdapter()

    adapter = ObservedDeliveryAdapter(
        adapter=fake,
        metrics=metrics,
        traces=traces,
    )

    result = adapter.send(
        recipient="customer@example.com",
        subject="Order update",
        body="Order completed",
        idempotency_key="KEY-OBS-1",
    )

    assert result["status"] == "delivered"

    assert metrics.total_attempts == 1
    assert metrics.successful_deliveries == 1
    assert metrics.failed_deliveries == 0

    assert len(traces) == 1
    assert traces[0]["event"] == "adapter.delivery_succeeded"


def test_failed_dependency_is_recorded():

    class FailingAdapter:

        def send(self, **kwargs):
            raise DeliveryFailure(
                "Temporary failure",
                retryable=True,
                error_type="temporary_failure",
            )

    metrics = NotificationMetrics()
    traces = []

    adapter = ObservedDeliveryAdapter(
        adapter=FailingAdapter(),
        metrics=metrics,
        traces=traces,
    )

    with pytest.raises(DeliveryFailure):

        adapter.send(
            recipient="customer@example.com",
            subject="Update",
            body="Message",
            idempotency_key="KEY-OBS-2",
        )

    assert metrics.failed_deliveries == 1
    assert metrics.total_attempts == 1

    assert traces[0]["status"] == "failed"
    assert traces[0]["error_type"] == "temporary_failure"


def test_timeout_is_enforced_and_recorded():

    class SlowAdapter:

        def send(self, **kwargs):
            time.sleep(0.2)

            return {
                "message_id": "SLOW-1",
                "status": "delivered",
            }

    metrics = NotificationMetrics()
    traces = []

    adapter = ObservedDeliveryAdapter(
        adapter=SlowAdapter(),
        metrics=metrics,
        traces=traces,
        timeout_seconds=0.05,
    )

    with pytest.raises(DeliveryFailure) as error:

        adapter.send(
            recipient="customer@example.com",
            subject="Update",
            body="Message",
            idempotency_key="KEY-OBS-3",
        )

    assert error.value.error_type == "timeout"
    assert metrics.timeout_count == 1
    assert metrics.failed_deliveries == 1


def test_secret_redaction():

    data = {
        "api_key": "SECRET-123",
        "password": "PASSWORD-123",
        "details": {
            "access_token": "TOKEN-123",
            "environment": "test",
        },
    }

    sanitized = redact_secrets(data)

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["password"] == "[REDACTED]"

    assert (
        sanitized["details"]["access_token"]
        == "[REDACTED]"
    )

    assert sanitized["details"]["environment"] == "test"


def test_integration_status():

    metrics = NotificationMetrics()
    traces = []

    adapter = ObservedDeliveryAdapter(
        adapter=FakeDeliveryAdapter(),
        metrics=metrics,
        traces=traces,
    )

    adapter.send(
        recipient="customer@example.com",
        subject="Update",
        body="Message",
        idempotency_key="KEY-OBS-4",
    )

    status = get_integration_status(
        metrics,
        traces,
    )

    assert status["component"] == "notification_delivery"
    assert status["status"] == "healthy"
    assert status["metrics"]["successful_deliveries"] == 1
    assert status["trace_count"] == 1


def test_invalid_timeout_configuration():

    with pytest.raises(ValueError):

        ObservedDeliveryAdapter(
            adapter=FakeDeliveryAdapter(),
            metrics=NotificationMetrics(),
            traces=[],
            timeout_seconds=0,
        )
