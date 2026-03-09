"""
Timer Trigger Simulator for Azure Functions.

Provides classes for simulating Azure Functions timer triggers
with CRON-like scheduling support.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional


@dataclass
class TimerSchedule:
    """
    Represents a CRON schedule for a timer trigger.

    Azure Functions CRON format: {second} {minute} {hour} {day} {month} {day-of-week}
    Example: '0 */5 * * * *' = every 5 minutes
    """

    expression: str
    is_past_due: bool = False
    last_execution: Optional[datetime] = None
    next_execution: Optional[datetime] = None

    def __post_init__(self):
        self._validate_expression()
        if self.last_execution is None:
            self.last_execution = datetime.utcnow()
        if self.next_execution is None:
            self.next_execution = self._calculate_next()

    def _validate_expression(self) -> None:
        """Validate the CRON expression format (6-field Azure format)."""
        parts = self.expression.strip().split()
        if len(parts) != 6:
            raise ValueError(
                f"Invalid CRON expression '{self.expression}'. "
                "Azure timer triggers use 6 fields: "
                "{second} {minute} {hour} {day} {month} {day-of-week}"
            )
        for part in parts:
            if not re.match(r"^[\d\*\/\-\,]+$", part):
                raise ValueError(
                    f"Invalid CRON field '{part}' in expression '{self.expression}'"
                )

    def _calculate_next(self) -> datetime:
        """Calculate the next execution time (simplified)."""
        parts = self.expression.strip().split()
        minute_part = parts[1]
        if "/" in minute_part:
            interval = int(minute_part.split("/")[1])
            return self.last_execution + timedelta(minutes=interval)
        return self.last_execution + timedelta(minutes=1)

    def to_dict(self) -> Dict:
        """Convert schedule to dictionary representation."""
        return {
            "expression": self.expression,
            "is_past_due": self.is_past_due,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
            "next_execution": self.next_execution.isoformat() if self.next_execution else None,
        }


class TimerTrigger:
    """
    Simulates an Azure Functions timer trigger.

    Executes a function on a schedule defined by a CRON expression.
    """

    def __init__(self, schedule: str, name: str = "timer", run_on_startup: bool = False):
        self.schedule_expression = schedule
        self.name = name
        self.run_on_startup = run_on_startup
        self._handler: Optional[Callable] = None
        self._execution_log: List[Dict] = []
        self._schedule = TimerSchedule(expression=schedule)

    def __call__(self, func: Callable) -> Callable:
        """Register a function as the handler for this trigger."""
        self._handler = func
        func._trigger = self
        return func

    def invoke(self, schedule: Optional[TimerSchedule] = None) -> Dict:
        """
        Invoke the timer trigger handler.

        Args:
            schedule: Optional schedule override; defaults to internal schedule.

        Returns:
            Dictionary with execution result and metadata.
        """
        if not self._handler:
            return {"status": "error", "message": "No handler registered"}

        timer_info = schedule or self._schedule
        start_time = datetime.utcnow()

        try:
            result = self._handler(timer_info)
            execution_record = {
                "function": self._handler.__name__,
                "trigger": self.name,
                "schedule": timer_info.expression,
                "started_at": start_time.isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
                "status": "success",
                "result": result,
            }
        except Exception as exc:
            execution_record = {
                "function": self._handler.__name__,
                "trigger": self.name,
                "schedule": timer_info.expression,
                "started_at": start_time.isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
                "status": "error",
                "error": str(exc),
            }

        self._execution_log.append(execution_record)
        self._schedule.last_execution = datetime.utcnow()
        self._schedule.next_execution = self._schedule._calculate_next()

        return execution_record

    def get_execution_log(self) -> List[Dict]:
        """Return the execution history."""
        return list(self._execution_log)
