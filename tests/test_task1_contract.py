
import pytest

from notifications import (
    WorkflowRun,
    WorkflowState,
    NotificationInput,
    NotificationType,
    NotificationTask,
    transition,
)


def test_legal_transition():
    run = WorkflowRun(
        run_id="TEST-1",
        business_key="ORDER-101"
    )

    transition(run, "start")

    assert run.state == WorkflowState.RUNNING


def test_illegal_transition():
    run = WorkflowRun(
        run_id="TEST-2",
        business_key="ORDER-102"
    )

    with pytest.raises(ValueError):
        transition(run, "complete")

    assert run.state == WorkflowState.CREATED


def test_notification_input_validation():
    notification = NotificationInput(
        business_key="ORDER-103",
        notification_type=NotificationType.ORDER_DELAYED,
        recipient="customer@example.com",
        template_id="delay_template",
        payload={"reason": "Weather delay"}
    )

    assert notification.business_key == "ORDER-103"


def test_invalid_notification_type():
    with pytest.raises(ValueError):
        NotificationInput(
            business_key="ORDER-104",
            notification_type="invalid_type",
            recipient="customer@example.com",
            template_id="delay_template"
        )


def test_notification_task_creation():
    task = NotificationTask(
        run_id="RUN-1",
        notification_type=NotificationType.ORDER_APPROVED,
        recipient="customer@example.com",
        template_id="approval_template"
    )

    assert task.status.value == "pending"
    assert task.attempts == 0
    assert task.task_id


def test_workflow_event_recording():
    run = WorkflowRun(
        run_id="RUN-3",
        business_key="ORDER-105"
    )

    transition(run, "start")

    assert len(run.events) == 1
    assert run.events[0]["event"] == "start"
