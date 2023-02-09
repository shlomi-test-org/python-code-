# Control Integration Tests Reference

A full integration test for a control includes a tested image and mock services to answer backend requests.
A classic integration tests will execute the image with an event that simulates a real event, and will assert the
following:

- The control execution went as expected
- The findings that were uploaded are as expected
- The logs that were uploaded are as expected
- In the future we will also want to assert that the requests that the control made to the backend are as expected

## Run Locally

To run the integration tests locally, follow these steps:

1. Make sure you have Docker and Python installed
2. Install the dependencies with `pip install -r requirements-test.txt`
3. Set up the mock containers using the `docker-compose.yml` file with the following command:

```
docker-compose -f tests/integration/docker-compose.yml up -d
```

4. Validate all containers are running and are in the same network
5. Run the tests with `python -m pytest -s tests/integration/`
