
import pytest

from notifications import (
    WorkflowRun,
    NotificationInput,
    NotificationType,
    FakeDeliveryAdapter,
    NotificationService,
)


def create_notification():
    return NotificationInput(
        business_key="ORDER-2001",
        notification_type=NotificationType.ORDER_DELAYED,
        recipient="customer@example.com",
        template_id="delay_template",
        payload={
            "customer_name": "Alex",
            "order_id": "ORDER-2001",
            "reason": "Weather conditions",
        },
    )


def test_successful_notification_delivery():

    run = WorkflowRun(
        run_id="RUN-2001",
        business_key="ORDER-2001",
    )

    adapter = FakeDeliveryAdapter()
    service = NotificationService(adapter)

    result = service.send_notification(
        run,
        create_notification()
    )

    assert result.success is True
    assert result.attempts == 1
    assert len(adapter.delivered_messages) == 1

    assert (
        adapter.delivered_messages[0]["recipient"]
        == "customer@example.com"
    )


def test_duplicate_notification_is_not_delivered():

    run = WorkflowRun(
        run_id="RUN-2002",
        business_key="ORDER-2001",
    )

    adapter = FakeDeliveryAdapter()
    service = NotificationService(adapter)

    notification = create_notification()

    first_result = service.send_notification(
        run, notification
    )

    second_result = service.send_notification(
        run, notification
    )

    assert first_result.success is True
    assert second_result.success is True

    assert len(adapter.delivered_messages) == 1

    assert any(
        event["event"] == "notification.duplicate_skipped"
        for event in run.events
    )


def test_unknown_template_validation_failure():

    run = WorkflowRun(
        run_id="RUN-2003",
        business_key="ORDER-2001",
    )

    adapter = FakeDeliveryAdapter()
    service = NotificationService(adapter)

    notification = create_notification()

    notification.template_id = "unknown_template"

    with pytest.raises(ValueError, match="Unknown notification template"):
        service.send_notification(run, notification)

    assert len(adapter.delivered_messages) == 0


def test_invalid_payload_validation_failure():

    run = WorkflowRun(
        run_id="RUN-2004",
        business_key="ORDER-2001",
    )

    adapter = FakeDeliveryAdapter()
    service = NotificationService(adapter)

    notification = create_notification()

    notification.payload = {
        "customer_name": "Alex"
    }

    with pytest.raises(ValueError, match="Invalid notification payload"):
        service.send_notification(run, notification)

    assert len(adapter.delivered_messages) == 0


def test_notification_type_template_mismatch():

    run = WorkflowRun(
        run_id="RUN-2005",
        business_key="ORDER-2001",
    )

    adapter = FakeDeliveryAdapter()
    service = NotificationService(adapter)

    notification = create_notification()

    notification.template_id = "approval_template"

    with pytest.raises(ValueError, match="does not match template"):
        service.send_notification(run, notification)

    assert len(adapter.delivered_messages) == 0
