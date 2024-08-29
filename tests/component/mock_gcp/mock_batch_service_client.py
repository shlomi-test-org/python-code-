import google


def mock_gcp_batch_service_client(mocker):
    class MockBatchServiceClient:
        delete_job_calls = []

        def job_path(self, project: str, location: str, job: str) -> str:
            return f'projects/{project}/locations/{location}/jobs/{job}'

        def get_job(self, name: str) -> google.cloud.batch_v1.types.job.Job:
            return google.cloud.batch_v1.types.job.Job({'name': name})

        def delete_job(self, name: str) -> None:
            self.delete_job_calls.append(name)

    mock_batch_client = MockBatchServiceClient()
    mocker.patch.object(google.cloud.batch_v1, 'BatchServiceClient', return_value=mock_batch_client)

    return mock_batch_client
