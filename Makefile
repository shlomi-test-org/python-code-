lint:
	pre-commit run --all-files

unit:
	# `pip install pytest-xdist` for parallel execution
	python -m pytest -v --durations=5 -n=auto tests/unit/ tests/component/

ssh-add:
	@eval $(ssh-agent -s)
	@ssh-add

build-mock:
	make ssh-add
	docker build \
	  --platform linux/amd64 \
	  -f service_mocks/dockerfile-test \
	  --ssh default \
	  -t ghcr.io/jitsecurity/execution-service-mock:local \
	  .

integration-mock:
	make build-mock
	docker run -d -p 8000:80 ghcr.io/jitsecurity/execution-service-mock:local
	python -m pytest -v -s --durations=0 --log-cli-level INFO service_mocks/tests/

integration:
	ENV_NAME=local LOCALSTACK_HOSTNAME=localhost python -m pytest -v --durations=0 tests/integration/

deploy-local:
	ENV_NAME=local sls deploy --stage local --param="loglevel=DEBUG"

deploy-dev:
	@if [ -z "${ENV_NAME}" ]; then \
		echo "ENV_NAME is not set"; \
		exit 1; \
	fi

	aws-vault exec jit-${ENV_NAME}-admin -- sls deploy --stage dev --param="loglevel=DEBUG"
