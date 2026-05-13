"""
JSON Schema tool definitions exposed to the LLM.
Each entry maps 1-to-1 with a K8sTools method.
"""

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "list_namespaces",
        "description": "List all Kubernetes namespaces in the cluster with their status.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_pods",
        "description": (
            "List pods in a namespace showing name, ready count, status, restarts, and age. "
            "Use this to spot CrashLoopBackOff, Pending, ImagePullBackOff, OOMKilled pods."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace (default: 'default')",
                },
                "label_selector": {
                    "type": "string",
                    "description": "Optional label selector e.g. 'app=nginx'",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_pod_logs",
        "description": (
            "Fetch recent logs from a pod. Use 'previous=true' to get logs from the "
            "previous (crashed) container instance."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pod_name": {"type": "string", "description": "Name of the pod"},
                "namespace": {"type": "string", "description": "Namespace of the pod"},
                "container": {
                    "type": "string",
                    "description": "Container name (required for multi-container pods)",
                },
                "previous": {
                    "type": "boolean",
                    "description": "Get logs from the previously terminated container",
                },
            },
            "required": ["pod_name"],
        },
    },
    {
        "name": "get_events",
        "description": (
            "List Kubernetes events for a namespace. Warning events appear first. "
            "Useful for diagnosing scheduling failures, image pull errors, OOM kills."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace to list events for"},
                "field_selector": {
                    "type": "string",
                    "description": "e.g. 'involvedObject.name=my-pod' or 'type=Warning'",
                },
            },
            "required": [],
        },
    },
    {
        "name": "describe_pod",
        "description": (
            "Get detailed information about a specific pod including container state, "
            "resource requests/limits, conditions, and node assignment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pod_name": {"type": "string", "description": "Name of the pod"},
                "namespace": {"type": "string", "description": "Namespace of the pod"},
            },
            "required": ["pod_name"],
        },
    },
    {
        "name": "get_nodes",
        "description": "List all cluster nodes with their status, roles, age, and Kubernetes version.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "describe_node",
        "description": "Get detailed information about a node including conditions, capacity, and allocatable resources.",
        "parameters": {
            "type": "object",
            "properties": {
                "node_name": {"type": "string", "description": "Name of the node"},
            },
            "required": ["node_name"],
        },
    },
    {
        "name": "get_deployments",
        "description": "List deployments in a namespace showing replica counts.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace"},
            },
            "required": [],
        },
    },
    {
        "name": "get_services",
        "description": "List services in a namespace showing type, cluster IP, external IP, and ports.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace"},
            },
            "required": [],
        },
    },
    {
        "name": "get_persistent_volumes",
        "description": "List all PersistentVolumes across the cluster.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_pvcs",
        "description": "List PersistentVolumeClaims in a namespace.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace"},
            },
            "required": [],
        },
    },
    {
        "name": "get_configmaps",
        "description": "List ConfigMaps in a namespace.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace"},
            },
            "required": [],
        },
    },
    {
        "name": "get_resource_quotas",
        "description": "Check resource quota usage in a namespace to detect quota exhaustion.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Namespace"},
            },
            "required": [],
        },
    },
    {
        "name": "check_cluster_health",
        "description": (
            "Run an overall cluster health check: node status, problem pods, "
            "pending pods, and recent warning events. Good starting point for any investigation."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "run_kubectl",
        "description": (
            "Run an arbitrary kubectl command and return the output. "
            "Useful for commands not covered by other tools. "
            "Example args: 'top nodes', 'get ingress -A', 'describe svc my-svc -n prod'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "args": {
                    "type": "string",
                    "description": "kubectl arguments (everything after 'kubectl')",
                },
            },
            "required": ["args"],
        },
    },
    {
        "name": "restart_deployment",
        "description": (
            "Perform a rolling restart of a deployment (equivalent to kubectl rollout restart). "
            "Use to recover from transient issues without changing configuration."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Deployment name"},
                "namespace": {"type": "string", "description": "Namespace"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "rollback_deployment",
        "description": "Roll back a deployment to the previous revision or a specific revision.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Deployment name"},
                "namespace": {"type": "string", "description": "Namespace"},
                "revision": {
                    "type": "integer",
                    "description": "Revision number to roll back to (0 = previous)",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "scale_deployment",
        "description": "Scale a deployment to a specific number of replicas.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Deployment name"},
                "replicas": {"type": "integer", "description": "Target replica count"},
                "namespace": {"type": "string", "description": "Namespace"},
            },
            "required": ["name", "replicas"],
        },
    },
    {
        "name": "delete_pod",
        "description": (
            "Delete a specific pod (Kubernetes will recreate it if managed by a controller). "
            "Useful to force a fresh pod start for stuck or wedged pods."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pod_name": {"type": "string", "description": "Pod name"},
                "namespace": {"type": "string", "description": "Namespace"},
            },
            "required": ["pod_name"],
        },
    },
    {
        "name": "apply_manifest",
        "description": (
            "Apply a Kubernetes YAML manifest to the cluster. "
            "Use this to create or update resources as a fix."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "yaml_content": {
                    "type": "string",
                    "description": "Complete YAML manifest to apply",
                },
            },
            "required": ["yaml_content"],
        },
    },
    {
        "name": "patch_resource",
        "description": "Patch an existing Kubernetes resource with a JSON merge patch.",
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "description": "Resource kind e.g. deployment, configmap, service",
                },
                "name": {"type": "string", "description": "Resource name"},
                "namespace": {"type": "string", "description": "Namespace"},
                "patch_json": {
                    "type": "string",
                    "description": "JSON merge patch string e.g. '{\"spec\":{\"replicas\":3}}'",
                },
            },
            "required": ["kind", "name", "namespace", "patch_json"],
        },
    },
]
