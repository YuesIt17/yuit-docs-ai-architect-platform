{{- define "kp.name" -}}
knowledge-platform
{{- end -}}

{{- define "kp.labels" -}}
app.kubernetes.io/name: {{ include "kp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: retailpartnerx-kp
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
