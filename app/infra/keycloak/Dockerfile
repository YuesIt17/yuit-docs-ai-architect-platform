# A pre-built Keycloak. `start --optimized` skips the rebuild at startup, which would need a writable root filesystem.
# Build options are fixed here; hostname and credentials stay runtime settings in the chart.
FROM quay.io/keycloak/keycloak:26.4 AS build
ENV KC_DB=dev-file \
    KC_CACHE=local \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true \
    KC_HTTP_RELATIVE_PATH=/idp
RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:26.4
COPY --from=build /opt/keycloak/ /opt/keycloak/
# The image's numeric user lets Kubernetes verify runAsNonRoot.
USER 1000
CMD ["start", "--optimized", "--import-realm"]
