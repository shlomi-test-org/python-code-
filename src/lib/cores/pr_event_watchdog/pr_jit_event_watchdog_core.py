import dataclasses
import json
import os
import urllib.parse
from datetime import datetime
from functools import lru_cache
from typing import List, Tuple, Optional, Dict

from jit_utils.aws_clients.events import EventBridgeClient
from jit_utils.event_models import CodeRelatedJitEvent
from jit_utils.jit_clients.execution_service.client import ExecutionService
from jit_utils.jit_clients.github_service.client import GithubService
from jit_utils.logger import logger
from jit_utils.models.execution import Execution, ExecutionStatus
from jit_utils.models.slack.entities import InternalSlackMessageBody
from requests import HTTPError
from jit_utils.jit_clients.github_service.exceptions import ResourceNotFoundException

from src.lib.clients import AuthenticationService
from src.lib.constants import SLACK_CHANNEL_NAME_PR_WATCHDOG, ENV_NAME, SEND_INTERNAL_NOTIFICATION_QUEUE_NAME, \
    TRIGGER_SERVICE, JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME, PR_WATCHDOG_DETAIL_TYPE
from src.lib.cores.pr_event_watchdog.github_api_utils import (list_checks_for_suite, list_check_suites,
                                                              get_pr_details)
from src.lib.data.jit_event_life_cycle_table import JitEventLifeCycleManager
from src.lib.exceptions import FailedPRJitEventWatchdogException
from src.lib.models.jit_event_life_cycle import JitEventDBEntity
from jit_utils.aws_clients.sqs import SQSClient
from src.lib.models.models import PrJitEventWatchdogEvent
from jit_utils.models.oauth.entities import VendorEnum


def run_pr_watchdog_process(event: PrJitEventWatchdogEvent) -> None:
    """
    Logic:
    1. Get all JIT events for a specific bucket that are pr-related and created in the near 15 min to 1 hour duration.
    2. For each JIT event:
        2.1. Identify if it's failed or stuck.
        2.2. If failed or stuck, send a slack notification to a specific channel.
    """
    logger.info(f"Starting PR JIT Event Watchdog, getting events for bucket index: {event.gsi_bucket_index}")
    has_any_failure = False
    jit_events_manager = JitEventLifeCycleManager()
    jit_lifecycle_events = jit_events_manager.get_ttl_jit_events(event.gsi_bucket_index)
    for jit_life_cycle_event in jit_lifecycle_events:
        try:
            has_error = _identify_stuck_or_failed_pr(jit_events_manager, jit_life_cycle_event)
            has_any_failure = has_any_failure or has_error
        except Exception as e:
            logger.exception(f"Failed to process JIT event {jit_life_cycle_event.jit_event_id}. {e=}")
            has_any_failure = True

    if has_any_failure:
        raise FailedPRJitEventWatchdogException("Failed to process some PR JIT events - check logs for more details")


def _identify_stuck_or_failed_pr(  # noqa: C901
        jit_events_manager: JitEventLifeCycleManager,
        jit_life_cycle_event: JitEventDBEntity,
) -> bool:
    """
    Identify if the JIT event is failed or stuck. returns boolean that indicates 'has_error'

    Conditions:
    1. If the JIT event is missing, remove it from the table. (shouldn't happen, but just in case)
    2. If the JIT event is not a code related event, remove it from the table. (shouldn't happen, but just in case)
    3. If the JIT event is non GitHub vendor event, skip it and remove it from the table
    4. If the JIT event has running executions, skip it and keep it in the table.
    5. If the GitHub Installation is missing, remove the event from the table.
    6. If the JIT event is not the last commit, skip it and remove it from the table.
    7. If the JIT event has failed executions, send a slack notification and remove it from the table.
    8. If the Jit Security check is stuck or never opened, send a slack notification and remove it from the table.
    9. If none of the above - The PR has completed successfully and remove it from the table.

    """
    jit_event = jit_life_cycle_event.jit_event
    tenant_id = jit_life_cycle_event.tenant_id
    logger.info(f"Processing JIT event {jit_life_cycle_event.jit_event_id} for tenant {tenant_id}")

    if not jit_event:
        logger.warning(f"Jit event {jit_life_cycle_event.jit_event_id} is missing - skipping")
        jit_events_manager.remove_gsi2_from_record(jit_life_cycle_event)
        return True

    if not isinstance(jit_event, CodeRelatedJitEvent):
        logger.warning(f"Jit event {jit_life_cycle_event.jit_event_id} is not a code related event - skipping")
        jit_events_manager.remove_gsi2_from_record(jit_life_cycle_event)
        return True

    if jit_event.vendor != VendorEnum.GITHUB.value:
        logger.info(f"Jit event {jit_life_cycle_event.jit_event_id} is non github event - skipping")
        jit_events_manager.remove_gsi2_from_record(jit_life_cycle_event)
        return False

    executions = _get_executions(jit_event.jit_event_id, tenant_id)
    has_running_executions = _has_running_executions(executions)
    if has_running_executions:
        logger.info(f"Jit event {jit_event.jit_event_id} has running executions - skipping")
        return False

    org: str = jit_event.owner  # type: ignore
    repo: str = jit_event.original_repository
    pr_number: str = jit_event.pull_request_number  # type: ignore
    jit_event_commit_sha: str = jit_event.commits.head_sha  # type: ignore

    try:
        github_token = _get_github_token(installation_id=jit_event.installation_id, app_id=jit_event.app_id)
        logger.info(f"Got GitHub token for Jit Event {jit_life_cycle_event.jit_event_id}")
        pr_details = get_pr_details(github_token, org, repo, pr_number)
    except ResourceNotFoundException:
        logger.warning(f"Installation not found for Jit Event {jit_life_cycle_event.jit_event_id}. Skipping...")
        jit_events_manager.remove_gsi2_from_record(jit_life_cycle_event)
        return False
    except HTTPError:
        logger.warning(f"Couldn't find PR: {org}/{repo}#{pr_number} - Skipping.")
        return False

    last_pr_commit_sha = pr_details.head.sha

    is_last_commit = _is_latest_commit(
        last_pr_commit_sha=last_pr_commit_sha,
        jit_event_commit_sha=jit_event_commit_sha,
    )
    if not is_last_commit:
        logger.info(f"Jit event {jit_event.jit_event_id} is not the last commit - skipping")
        jit_events_manager.remove_gsi2_from_record(jit_life_cycle_event)
        return False

    has_failed_executions, reason = _has_failed_executions(executions)
    if has_failed_executions:
        logger.info(f"Jit event {jit_event.jit_event_id} has failed executions - alerting")
        send_pr_failed_slack_notification(
            tenant_id=tenant_id, org=org, repo=repo,
            pr_number=pr_number, reason=reason, jit_event_id=jit_event.jit_event_id,
            jit_event_created_at=jit_life_cycle_event.created_at
        )
        jit_events_manager.remove_gsi2_from_record(jit_life_cycle_event)
        return False

    is_stuck, reason = _calc_is_stuck_or_never_opened(
        github_token=github_token,
        org=org,
        repo_name=repo,
        last_pr_commit_sha=last_pr_commit_sha,
    )
    if is_stuck:
        logger.info(f"Jit event {jit_event.jit_event_id} is stuck or never opened - alerting")
        send_pr_failed_slack_notification(
            tenant_id=tenant_id, org=org, repo=repo, pr_number=pr_number, reason=reason,
            jit_event_id=jit_event.jit_event_id, jit_event_created_at=jit_life_cycle_event.created_at
        )
        jit_events_manager.remove_gsi2_from_record(jit_life_cycle_event)
        return False

    logger.info(f"Jit event {jit_event.jit_event_id} has completed successfully - Can be removed from the index")
    jit_events_manager.remove_gsi2_from_record(jit_life_cycle_event)
    return False


def _get_executions(jit_event_id: str, tenant_id: str) -> List[Execution]:
    api_token = _get_tenant_api_token(tenant_id)
    executions = []
    start_key = None
    while True:
        response = ExecutionService().get_executions_by_filters(
            api_token=api_token,
            jit_event_id=jit_event_id,
            start_key=start_key,
            limit=100,
        )
        executions.extend(response.data)
        start_key = response.metadata.last_key
        if not start_key:
            break

    return executions


def _has_running_executions(executions: List[Execution]) -> bool:
    has_running_executions = False
    for execution in executions:
        if not execution.status:
            has_running_executions = True
            break
        execution_status = ExecutionStatus(execution.status)
        if not execution_status.is_complete_status() and not execution_status.is_failed_status():
            has_running_executions = True
            break

    return has_running_executions


def _has_failed_executions(executions: List[Execution]) -> Tuple[bool, str]:
    has_failed_executions = False
    failed_executions: List[str] = []
    for execution in executions:
        execution_status: ExecutionStatus = ExecutionStatus(execution.status)  # type: ignore
        has_failed_without_findings = execution_status.is_failed_status() and not execution.has_findings
        if has_failed_without_findings:
            has_failed_executions = True
            execution_dynamo_link = _build_link_to_dynamo(
                table='Executions',
                pk=f'TENANT#{execution.tenant_id}#JIT_EVENT#{execution.jit_event_id}',
                sk=f'EXECUTION#{execution.execution_id}',
            )
            failed_executions.append(
                f'{str(execution.control_name)}'
                f'(<{execution_dynamo_link}|{execution.execution_id}>)'
            )

    failure_reason = 'The following Executions has failed without findings:\n' + '\n'.join(failed_executions)
    return has_failed_executions, failure_reason


@lru_cache()
def _get_tenant_api_token(tenant_id: str) -> str:
    return AuthenticationService().get_api_token(tenant_id)


@lru_cache()
def _get_github_token(installation_id: Optional[str], app_id: Optional[str]) -> str:
    if not installation_id or not app_id:  # This should never happen
        raise ValueError(f"installation_id or app_id is missing for jit_event. {installation_id=} {app_id=}")
    try:
        github_token = GithubService().get_token(
            installation_id=installation_id,
            app_id=app_id,
        )
    except ResourceNotFoundException:
        raise

    return github_token


def _is_latest_commit(last_pr_commit_sha: str, jit_event_commit_sha: str) -> bool:
    return last_pr_commit_sha == jit_event_commit_sha


def _calc_is_stuck_or_never_opened(
        org: str, repo_name: str, github_token: str, last_pr_commit_sha: str
) -> Tuple[bool, str]:
    # Get the check suites and make sure we have one for Jit
    check_suites = list_check_suites(github_token, org, repo_name, last_pr_commit_sha)
    jit_check_suite = next((suite for suite in check_suites if 'Jit' in suite.app.name), None)
    if not jit_check_suite:
        return True, 'Jit check suite not found'

    jit_check_runs = list_checks_for_suite(github_token, org, repo_name, jit_check_suite.id)
    jitsecurity_check_run = next((run for run in jit_check_runs if run.name == 'Jit Security'), None)
    if not jitsecurity_check_run:
        return True, 'Jit Security check not found'

    # Make sure the Jit Security check is not stuck
    is_jitsecurity_check_stuck = jitsecurity_check_run.status == 'in_progress'
    if is_jitsecurity_check_stuck:
        return True, 'Jit Security check is stuck'

    return False, ''


def alert_pr_failed(
        tenant_id: str, org: str, repo: str, pr_number: str, reason: str, jit_event_id: str, jit_event_created_at: str
) -> None:
    send_pr_failed_slack_notification(
        tenant_id=tenant_id, org=org, repo=repo, pr_number=pr_number, reason=reason, jit_event_id=jit_event_id,
        jit_event_created_at=jit_event_created_at,
    )
    send_pr_failed_metric(
        tenant_id=tenant_id, org=org, repo=repo, pr_number=pr_number, reason=reason, jit_event_id=jit_event_id
    )


def send_pr_failed_metric(
        tenant_id: str, org: str, repo: str, pr_number: str, reason: str, jit_event_id: str,
) -> None:
    EventBridgeClient().put_event(
        source=TRIGGER_SERVICE,
        bus_name=JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME,
        detail_type=PR_WATCHDOG_DETAIL_TYPE,
        detail=json.dumps({
            'tenant_id': tenant_id,
            'org': org,
            'repo': repo,
            'pr_number': pr_number,
            'reason': reason,
            'jit_event_id': jit_event_id,
            'created_at': datetime.now().isoformat(),
        }),
    )


def send_pr_failed_slack_notification(
        tenant_id: str, org: str, repo: str, pr_number: str, reason: str, jit_event_id: str,
        jit_event_created_at: str
) -> None:
    logger.info("Sending a PR failed/stuck slack notification")
    channel_id = SLACK_CHANNEL_NAME_PR_WATCHDOG.format(env_name=os.environ[ENV_NAME])
    blocks = _build_slack_message_blocks(tenant_id, org, repo, pr_number, reason, jit_event_id, jit_event_created_at)
    slack_message = InternalSlackMessageBody(channel_id=channel_id, blocks=blocks, text="")

    logger.info("Sending the message to the internal notification queue")
    SQSClient().send_message(
        SEND_INTERNAL_NOTIFICATION_QUEUE_NAME,
        json.dumps(dataclasses.asdict(slack_message)),
    )


def _build_slack_message_blocks(
        tenant_id: str, org: str, repo: str, pr_number: str, reason: str, jit_event_id: str, jit_event_created_at: str
) -> List[Dict]:
    rerun_data_script_url = 'https://github.com/jitsecurity/jit-ops/actions/workflows/run-data-script.yml'

    tenant_pk = f'TENANT#{tenant_id}'
    tenant_dynamo_link = _build_link_to_dynamo(
        table='Tenants',
        pk=tenant_pk,
        sk=''
    )
    jit_event_dynamo_link = _build_link_to_dynamo(
        table='JitEventLifeCycle',
        pk=tenant_pk,
        sk=f'JIT_EVENT#{jit_event_id}',
    )
    pr_dynamo_link = _build_link_to_dynamo(
        table='PrEvent',
        pk=tenant_pk,
        sk=f'VENDOR#github#OWNER#{org}#REPOSITORY#{repo}#PULL_REQUEST_NUMBER#{pr_number}',
    )
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "PR Watchdog",
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*tenant_id:* <{tenant_dynamo_link}|{tenant_id}>\n"
                    f"*jit_event_id:* <{jit_event_dynamo_link}|{jit_event_id}>\n"
                    f"*created_at:* {jit_event_created_at}\n"
                    f"*org:* {org}\n"
                    f"*repo:* {repo}\n"
                    f"*pull_request_number:* <{pr_dynamo_link}|{pr_number}>\n"
                )
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Reason:* {reason}\n"
                )
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Link for Rerun:* {rerun_data_script_url}\n"
                    f"*Script path:* `trigger_rerun/trigger_rerun.py`\n"
                    f"*args:* `--tenant_id={tenant_id} --repo_name={repo} --pull_request_number={pr_number}`\n"
                )
            }
        },
    ]


def _build_link_to_dynamo(table: str, pk: str, sk: str) -> str:
    base_dynamo_url = ('https://us-east-1.console.aws.amazon.com/dynamodbv2/home?region=us-east-1#item-explorer'
                       '?operation=QUERY&pk={pk}&sk={sk}&table={table}')
    return base_dynamo_url.format(table=table, pk=urllib.parse.quote(pk), sk=urllib.parse.quote(sk))
