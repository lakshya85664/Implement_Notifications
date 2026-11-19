
from operator_runbook import (
    success_scenario,
    failure_scenario,
    replay_scenario,
    recovery_scenario,
)


def test_success_scenario():

    result = success_scenario()

    assert result["status"] == "delivered"
    assert result["delivery_count"] == 1
    assert result["next_action"] == "continue_workflow"


def test_failure_scenario():

    result = failure_scenario()

    assert result["status"] == "failed"
    assert result["error_type"] == "permanent_failure"
    assert result["attempts"] == 1
    assert result["next_action"] == "quarantine_and_review"


def test_replay_scenario():

    result = replay_scenario()

    assert result["status"] == "duplicate_skipped"

    assert result["actual_delivery_count"] == 1

    assert result["first_delivery_success"] is True
    assert result["second_delivery_success"] is True


def test_recovery_scenario():

    result = recovery_scenario()

    assert result["status"] == "recovered"
    assert result["attempts"] == 2
    assert result["response"]["status"] == "delivered"
    assert result["next_action"] == "continue_workflow"
