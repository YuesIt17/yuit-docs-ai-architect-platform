{{- define "kp.name" -}}
knowledge-platform
{{- end -}}

{{- define "kp.labels" -}}
app.kubernetes.io/name: {{ include "kp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: retailpartnerx-kp
{{- end -}}


{{- /* The issuer in tokens: the URL the browser sees. */ -}}
{{- define "kp.oidcIssuer" -}}
{{- if .Values.bff.oidc.issuerUrl -}}
{{- .Values.bff.oidc.issuerUrl -}}
{{- else -}}
{{- printf "%s/idp/realms/%s" (trimSuffix "/" .Values.bff.publicUrl) .Values.keycloak.realm -}}
{{- end -}}
{{- end -}}

{{- /* Where pods reach the IdP. The public host may not resolve inside the cluster. */ -}}
{{- define "kp.oidcInternalUrl" -}}
{{- if .Values.keycloak.enabled -}}
{{- printf "http://keycloak:8080/idp/realms/%s" .Values.keycloak.realm -}}
{{- else -}}
{{- include "kp.oidcIssuer" . -}}
{{- end -}}
{{- end -}}

{{- /* Pod-level Restricted settings. Call with (dict "uid" <numeric user>). */ -}}
{{- define "kp.podSecurity" -}}
automountServiceAccountToken: false
securityContext:
  runAsNonRoot: true
  runAsUser: {{ .uid }}
  runAsGroup: {{ .uid }}
  fsGroup: {{ .uid }}
  seccompProfile:
    type: RuntimeDefault
{{- end -}}

{{- /* Container-level Restricted settings. Call with (dict "readOnly" true|false). */ -}}
{{- define "kp.containerSecurity" -}}
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: {{ .readOnly }}
  capabilities:
    drop: ["ALL"]
{{- end -}}

{{- /* Environment shared by the API and the worker. */ -}}
{{- define "kp.secretEnv" -}}
- name: JWT_SECRET
  valueFrom:
    secretKeyRef: {name: kp-secrets, key: JWT_SECRET}
- name: NEO4J_PASSWORD
  valueFrom:
    secretKeyRef: {name: kp-secrets, key: NEO4J_PASSWORD}
- name: MINIO_ACCESS_KEY
  valueFrom:
    secretKeyRef: {name: kp-secrets, key: MINIO_ROOT_USER}
- name: MINIO_SECRET_KEY
  valueFrom:
    secretKeyRef: {name: kp-secrets, key: MINIO_ROOT_PASSWORD}
{{- end -}}

{{- /* Stops an auth configuration that could not work, or that would mix the two modes. It renders nothing. */ -}}
{{- define "kp.authGuards" -}}
{{- if and .Values.keycloak.enabled (not .Values.bff.enabled) -}}
{{- fail "keycloak.enabled needs bff.enabled: nothing else uses it, and the API would stay in demo mode" -}}
{{- end -}}
{{- if .Values.bff.enabled -}}
{{- if not .Values.bff.publicUrl -}}
{{- fail "bff.enabled needs bff.publicUrl, the origin the browser uses" -}}
{{- end -}}
{{- if and (not .Values.keycloak.enabled) (not .Values.bff.oidc.issuerUrl) -}}
{{- fail "bff.enabled without keycloak.enabled needs bff.oidc.issuerUrl" -}}
{{- end -}}
{{- if and .Values.keycloak.enabled (ne .Values.secrets.provider "helm") -}}
{{- fail "keycloak.enabled is the demo IdP and needs secrets.provider=helm. With Vault, use an external IdP through bff.oidc.issuerUrl" -}}
{{- end -}}
{{- end -}}
{{- end -}}
