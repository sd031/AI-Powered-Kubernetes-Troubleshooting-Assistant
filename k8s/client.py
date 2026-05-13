from __future__ import annotations

from typing import Optional

from kubernetes import client, config
from kubernetes.client import (
    AppsV1Api,
    CoreV1Api,
    BatchV1Api,
    NetworkingV1Api,
    StorageV1Api,
    ApiClient,
)


class K8sClient:
    """Thin wrapper around the Kubernetes Python client."""

    def __init__(self, kubeconfig: Optional[str] = None, context: Optional[str] = None) -> None:
        if kubeconfig:
            config.load_kube_config(config_file=kubeconfig, context=context)
        else:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config(context=context)

        self._api_client = ApiClient()
        self.core = CoreV1Api(self._api_client)
        self.apps = AppsV1Api(self._api_client)
        self.batch = BatchV1Api(self._api_client)
        self.networking = NetworkingV1Api(self._api_client)
        self.storage = StorageV1Api(self._api_client)

    def current_context(self) -> str:
        contexts, active = config.list_kube_config_contexts()
        return active["name"] if active else "unknown"

    def server_version(self) -> str:
        try:
            ver = client.VersionApi(self._api_client).get_code()
            return f"{ver.git_version}"
        except Exception:
            return "unknown"
