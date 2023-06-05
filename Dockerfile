FROM bla/blo:0.0.1

RUN apk update
RUN apk add jq

RUN apt-get update && apt-get install make

COPY --from=entrypoint-tag /entrypoint /opt/entrypoint
COPY ./plugins/mapping.yml /opt/plugins/mapping.yml
ADD --chown=prowler:prowler ./scripts /opt/plugins
COPY ./scripts/run-trivy.sh /opt/run-trivy.sh
RUN chmod +x /opt/run-trivy.sh
