{{- define "ppe-compliance-monitor.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "ppe-compliance-monitor.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "ppe-compliance-monitor.labels" -}}
app.kubernetes.io/name: {{ include "ppe-compliance-monitor.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{/*
Parent copies of the aws-compatible-storage helpers.

Subchart defines are not callable with the parent root context. These resolve
both contexts: subchart values (fullnameOverride / s3.existingSecret) and parent
values (aws-compatible-storage.*). fullnameOverride is aws-compatible-storage.
*/}}
{{- define "aws-compatible-storage.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $storage := index .Values "aws-compatible-storage" | default dict -}}
{{- if $storage.fullnameOverride -}}
{{- $storage.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
aws-compatible-storage
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "aws-compatible-storage.secretName" -}}
{{- if and .Values.s3 .Values.s3.existingSecret -}}
{{- .Values.s3.existingSecret -}}
{{- else -}}
{{- $storage := index .Values "aws-compatible-storage" | default dict -}}
{{- $s3 := $storage.s3 | default dict -}}
{{- if $s3.existingSecret -}}
{{- $s3.existingSecret -}}
{{- else -}}
{{- printf "%s-credentials" (include "aws-compatible-storage.fullname" .) -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "aws-compatible-storage.apiPort" -}}
7480
{{- end -}}

{{- define "aws-compatible-storage.uiPort" -}}
5000
{{- end -}}

{{- define "ppe-compliance-monitor.s3Env" -}}
{{- $storage := index .Values "aws-compatible-storage" | default dict -}}
{{- $s3 := $storage.s3 | default dict -}}
- name: AWS_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "aws-compatible-storage.secretName" . }}
      key: AWS_ACCESS_KEY_ID
- name: AWS_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "aws-compatible-storage.secretName" . }}
      key: AWS_SECRET_ACCESS_KEY
- name: AWS_ENDPOINT_URL
  value: {{ printf "http://%s:%s" (include "aws-compatible-storage.fullname" .) (include "aws-compatible-storage.apiPort" .) | quote }}
- name: AWS_DEFAULT_REGION
  value: {{ $s3.region | default "us-east-1" | quote }}
{{- end -}}
