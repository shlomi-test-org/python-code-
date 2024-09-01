from aws_lambda_typing.context import Context
from aws_lambda_typing.events import CloudWatchEventsMessageEvent

from src.lib.cores.pr_event_watchdog.pr_jit_event_watchdog_core import run_pr_watchdog_process
from src.lib.models.models import PrJitEventWatchdogEvent


def handler(event: CloudWatchEventsMessageEvent, _: Context) -> None:
    event_model = PrJitEventWatchdogEvent(**event)  # type: ignore
    run_pr_watchdog_process(event=event_model)
