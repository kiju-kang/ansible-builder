FROM quay.io/keycloak/keycloak:23.0
# Simply extending the base image to create a custom artifact as requested.
# Configuration is handled via Environment Variables in Kubernetes.
USER root
# RUN microdnf update -y && microdnf install -y curl && microdnf clean all
LABEL custom-build="v1"
USER keycloak
