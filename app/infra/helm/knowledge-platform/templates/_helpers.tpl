{{- define "kp.name" -}}
knowledge-platform
{{- end -}}

{{- define "kp.labels" -}}
app.kubernetes.io/name: {{ include "kp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: retailpartnerx-kp
{{- end -}}
