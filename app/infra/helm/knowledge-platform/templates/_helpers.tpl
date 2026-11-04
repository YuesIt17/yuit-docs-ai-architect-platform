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
