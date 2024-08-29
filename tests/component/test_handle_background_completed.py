from test_utils.aws import idempotency

from tests.factories import ExecutionFactory


class TestHandleEnrichmentCompleted:
    def test__missing_token(
            self,
            mocker,
            executions_manager,
    ):
        idempotency.create_idempotency_table()

        # Import the handler inside the moto context, reload as more than one test import this module.
        # It's important to always get a fresh reload to get the idempotency config under current moto context
        from src.handlers import handle_enrichment_completed
        __import__('importlib').reload(handle_enrichment_completed)

        mocked_logger = mocker.patch('src.handlers.handle_enrichment_completed.logger')

        def call_handler():
            return handle_enrichment_completed.handler(
                {
                    'id': 'test-id',
                    'detail': ExecutionFactory().build(
                        context=None,  # Important, otherwise tenant_id has a validation error  of not UUID
                        task_token=None,  # Task token is Optional, but we want to test the error case
                    ).dict(),
                },
                None,
            )

        assert call_handler() is None
        assert mocked_logger.error.call_count == 1

        # Call the handler again (idempotency check)
        assert call_handler() is None

        # Assert that the error was logged only once meaning the handler was not executed again
        assert mocked_logger.error.call_count == 1
