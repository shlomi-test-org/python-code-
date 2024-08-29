class MockExecutionRunner:
    def __init__(self):
        self.call_count = 0

    def can_terminate(self):
        return True

    def terminate(self):
        self.call_count += 1

    def get_execution_failure_reason(self):
        return None

    @property
    def logs_url(self):
        return "logs_url"
