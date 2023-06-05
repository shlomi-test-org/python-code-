FROM bla/blo:0.0.1

RUN addgroup --system trivy-users
RUN adduser --system run-trivy-control --ingroup trivy-users
USER run-trivy-control:trivy-users

COPY --from=entrypoint-tag /entrypoint /opt/entrypoint
COPY ./plugins/mapping.yml /opt/plugins/mapping.yml
ADD --chown=prowler:prowler ./scripts /opt/plugins
COPY scripts/run-trivy.sh /opt/run-trivy.sh
