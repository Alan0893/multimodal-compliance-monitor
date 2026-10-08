{{/* Render once for both the immutable Job template and its name hash. */}}
{{- define "ppe-compliance-monitor.runtimeDeployerPodTemplate" -}}
{{- $saName := printf "%s-runtime-deployer" (include "ppe-compliance-monitor.fullname" .) -}}
metadata:
  labels:
    {{- include "ppe-compliance-monitor.labels" . | nindent 4 }}
    app.kubernetes.io/component: runtime-deployer
spec:
  serviceAccountName: {{ $saName }}
  restartPolicy: OnFailure
  containers:
    - name: runtime-deployer
      image: "{{ .Values.global.imageRegistry }}/{{ .Values.runtimeDeployer.image.repository }}:{{ .Values.runtimeDeployer.image.tag }}"
      imagePullPolicy: {{ .Values.runtimeDeployer.image.pullPolicy }}
      env:
        - name: NAMESPACE
          value: {{ .Release.Namespace }}
        - name: RUNTIME_TYPE
          value: {{ .Values.modelServing.runtimeType | quote }}
        - name: DEPLOY_MODEL
          value: "true"
        - name: S3_BUCKET
          value: {{ .Values.storage.model.bucket | quote }}
        {{- if or (and (eq .Values.modelServing.runtimeType "openvino") .Values.modelServing.openvino.multiModel) (and (eq .Values.modelServing.runtimeType "kserve") .Values.modelServing.kserve.multiModel) }}
        - name: MULTI_MODEL_SERVING
          value: "true"
        - name: INFERENCE_SERVICE_NAME
          value: {{ .Values.runtimeDeployer.inferenceServiceName | quote }}
        {{- end }}
        - name: S3_MODEL_PATH
        {{- if and (eq .Values.modelServing.runtimeType "openvino") .Values.modelServing.openvino.multiModel }}
          value: {{ .Values.modelServing.openvino.multiModelStoragePath | quote }}
        {{- else if and (eq .Values.modelServing.runtimeType "kserve") .Values.modelServing.kserve.multiModel }}
          value: {{ .Values.modelServing.kserve.multiModelStoragePath | quote }}
        {{- else if eq .Values.modelServing.runtimeType "kserve" }}
          value: {{ .Values.modelServing.kserve.modelPath | quote }}
        {{- else }}
          value: {{ .Values.modelServing.openvino.modelPath | quote }}
        {{- end }}
        {{- include "ppe-compliance-monitor.s3Env" . | nindent 8 }}
        - name: MODEL_NAME
          value: {{ .Values.runtimeDeployer.modelName | default "ppe" | quote }}
        - name: MODEL_VERSION
          value: {{ .Values.backend.modelVersion | quote }}
        {{- if eq .Values.modelServing.runtimeType "kserve" }}
        - name: MODEL_FORMAT
          value: {{ .Values.modelServing.kserve.modelFormat.name | quote }}
        - name: MODEL_FORMAT_VERSION
          value: {{ .Values.modelServing.kserve.modelFormat.version | quote }}
        - name: SERVING_RUNTIME_IMAGE
          value: {{ .Values.modelServing.kserve.image | quote }}
        - name: REST_PORT
          value: {{ .Values.modelServing.kserve.restPort | quote }}
        - name: GRPC_PORT
          value: {{ .Values.modelServing.kserve.grpcPort | quote }}
        - name: RUNTIME_ARGS
          value: {{ .Values.modelServing.kserve.args | toJson | quote }}
        - name: RUNTIME_COMMAND
          value: {{ .Values.modelServing.kserve.command | toJson | quote }}
        - name: RUNTIME_ENV
          value: {{ .Values.modelServing.kserve.env | toJson | quote }}
        - name: RUNTIME_TEMPLATE_NAME
          value: {{ .Values.modelServing.kserve.templateName | quote }}
        - name: RUNTIME_TEMPLATE_DISPLAY_NAME
          value: {{ .Values.modelServing.kserve.templateDisplayName | quote }}
        {{- if .Values.modelServing.kserve.gpu.enabled }}
        - name: GPU_ENABLED
          value: "true"
        - name: GPU_COUNT
          value: {{ .Values.modelServing.kserve.gpu.count | quote }}
        - name: GPU_TOLERATIONS
          value: {{ .Values.modelServing.kserve.gpu.tolerations | toJson | quote }}
        {{- end }}
        {{- else }}
        - name: MODEL_FORMAT
          value: {{ .Values.modelServing.openvino.modelFormat.name | quote }}
        - name: MODEL_FORMAT_VERSION
          value: {{ .Values.modelServing.openvino.modelFormat.version | quote }}
        - name: SERVING_RUNTIME_IMAGE
          value: {{ .Values.modelServing.openvino.image | quote }}
        - name: REST_PORT
          value: {{ .Values.modelServing.openvino.restPort | quote }}
        - name: GRPC_PORT
          value: {{ .Values.modelServing.openvino.grpcPort | quote }}
        {{- end }}
        - name: CREATE_SERVING_RUNTIME
          value: "true"
        - name: REPLICAS_MIN
          value: {{ .Values.modelServing.replicas.min | quote }}
        - name: REPLICAS_MAX
          value: {{ .Values.modelServing.replicas.max | quote }}
        - name: RESOURCE_REQ_CPU
          value: {{ .Values.modelServing.resources.requests.cpu | quote }}
        - name: RESOURCE_REQ_MEMORY
          value: {{ .Values.modelServing.resources.requests.memory | quote }}
        - name: RESOURCE_LIM_CPU
          value: {{ .Values.modelServing.resources.limits.cpu | quote }}
        - name: RESOURCE_LIM_MEMORY
          value: {{ .Values.modelServing.resources.limits.memory | quote }}
{{- end -}}
