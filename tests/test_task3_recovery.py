
import pytest

from notifications import (
    DeliveryFailure,
    RetryingDeliveryAdapter,
    ScriptedDeliveryAdapter,
    IdempotentTimeoutAdapter,
)


def test_timeout_then_successful_retry():

    adapter = ScriptedDeliveryAdapter([
        TimeoutError("Temporary timeout"),
        {
            "message_id": "MSG-1",
            "status": "delivered",
        },
    ])

    retry_adapter = RetryingDeliveryAdapter(
        adapter,
        max_attempts=3,
    )

    result = retry_adapter.send(
        recipient="customer@example.com",
        subject="Order update",
        body="Your order is approved",
        idempotency_key="KEY-1",
    )

    assert result["status"] == "delivered"
    assert adapter.calls == 2
    assert len(retry_adapter.attempt_log) == 2

    assert retry_adapter.attempt_log[0]["error_type"] == "timeout"
    assert retry_adapter.attempt_log[1]["status"] == "success"


def test_retry_limit_is_enforced():

    adapter = ScriptedDeliveryAdapter([
        TimeoutError("Timeout 1"),
        TimeoutError("Timeout 2"),
        TimeoutError("Timeout 3"),
    ])

    retry_adapter = RetryingDeliveryAdapter(
        adapter,
        max_attempts=3,
    )

    with pytest.raises(DeliveryFailure) as error:

        retry_adapter.send(
            recipient="customer@example.com",
            subject="Order update",
            body="Update",
            idempotency_key="KEY-2",
        )

    assert error.value.retryable is True
    assert error.value.error_type == "timeout"
    assert adapter.calls == 3
    assert len(retry_adapter.attempt_log) == 3


def test_permanent_failure_is_not_retried():

    adapter = ScriptedDeliveryAdapter([
        DeliveryFailure(
            "Recipient rejected",
            retryable=False,
            error_type="permanent_failure",
        ),
    ])

    retry_adapter = RetryingDeliveryAdapter(
        adapter,
        max_attempts=3,
    )

    with pytest.raises(DeliveryFailure) as error:

        retry_adapter.send(
            recipient="invalid@example.com",
            subject="Order update",
            body="Update",
            idempotency_key="KEY-3",
        )

    assert error.value.retryable is False
    assert error.value.error_type == "permanent_failure"
    assert adapter.calls == 1


def test_malformed_response_is_rejected():

    adapter = ScriptedDeliveryAdapter([
        {
            "status": "unknown",
        },
    ])

    retry_adapter = RetryingDeliveryAdapter(
        adapter,
        max_attempts=3,
    )

    with pytest.raises(DeliveryFailure) as error:

        retry_adapter.send(
            recipient="customer@example.com",
            subject="Order update",
            body="Update",
            idempotency_key="KEY-4",
        )

    assert error.value.error_type == "malformed_response"
    assert error.value.retryable is False
    assert adapter.calls == 1


def test_timeout_replay_does_not_duplicate_side_effect():

    adapter = IdempotentTimeoutAdapter()

    retry_adapter = RetryingDeliveryAdapter(
        adapter,
        max_attempts=3,
    )

    result = retry_adapter.send(
        recipient="customer@example.com",
        subject="Order completed",
        body="Your order is complete",
        idempotency_key="KEY-5",
    )

    assert result["message_id"] == "MSG-IDEMPOTENT-1"

    # Two attempts, but only one accepted side effect.
    assert len(retry_adapter.attempt_log) == 2
    assert adapter.side_effect_count == 1


def test_invalid_retry_configuration():

    adapter = ScriptedDeliveryAdapter([])

    with pytest.raises(ValueError):
        RetryingDeliveryAdapter(
            adapter,
            max_attempts=0,
        )

    with pytest.raises(ValueError):
        RetryingDeliveryAdapter(
            adapter,
            timeout_seconds=0,
        )
