# Running Locally

To run the step functions tests locally you need to setup the step-functions-local container.<br>
For that you have the docker-compose.yml file.<br>
Run this command:

```shell
cd tests/integration/step_functions
docker-compose up -d
cd ../../../ # go back to the root of the project
export ENV_NAME=local
export STAGE=local
sls --stage local deploy
```

This will also mount the Mock file (`StepFunctionsMock.json`) onto the container so we could mock the state machine
flow.

# Setting up mock flows

All mocks are configured in `StepFunctionsMock.json`.<br>
Follow this to learn more about it: https://docs.aws.amazon.com/step-functions/latest/dg/sfn-local.html
