from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Optional

import yaml
from kubernetes import client
from kubernetes.client.rest import ApiException

from .client import K8sClient


def _age(timestamp) -> str:
    if timestamp is None:
        return "unknown"
    now = datetime.now(tz=timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    delta = now - timestamp
    s = int(delta.total_seconds())
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


def _safe(val, default="<none>") -> str:
    return str(val) if val is not None else default


class K8sTools:
    """All Kubernetes operations available to the AI agent as callable methods."""

    def __init__(self, k8s: K8sClient, max_log_lines: int = 200, auto_fix: bool = False) -> None:
        self._k8s = k8s
        self._max_log_lines = max_log_lines
        self._auto_fix = auto_fix
        # Confirmation callback — set by agent to ask user before destructive ops
        self.confirm_callback: Optional[Any] = None

    # ──────────────────────────────────────────────────────────────────────────
    # Read-only tools
    # ──────────────────────────────────────────────────────────────────────────

    def list_namespaces(self) -> str:
        namespaces = self._k8s.core.list_namespace()
        lines = []
        for ns in namespaces.items:
            status = ns.status.phase if ns.status else "Unknown"
            age = _age(ns.metadata.creation_timestamp)
            lines.append(f"  {ns.metadata.name:<40} {status:<12} {age}")
        header = f"{'NAME':<40} {'STATUS':<12} {'AGE'}"
        return header + "\n" + "\n".join(lines)

    def get_pods(self, namespace: str = "default", label_selector: str = "") -> str:
        kwargs: dict = {}
        if label_selector:
            kwargs["label_selector"] = label_selector
        pods = self._k8s.core.list_namespaced_pod(namespace=namespace, **kwargs)
        if not pods.items:
            return f"No pods found in namespace '{namespace}'"
        lines = []
        header = f"{'NAME':<55} {'READY':<8} {'STATUS':<25} {'RESTARTS':<10} {'AGE'}"
        lines.append(header)
        for pod in pods.items:
            total = len(pod.spec.containers) if pod.spec.containers else 0
            ready = 0
            restarts = 0
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    if cs.ready:
                        ready += 1
                    restarts += cs.restart_count or 0
            phase = pod.status.phase or "Unknown"
            # Derive more detailed status
            reason = phase
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    if cs.state.waiting and cs.state.waiting.reason:
                        reason = cs.state.waiting.reason
                        break
                    if cs.state.terminated and cs.state.terminated.reason:
                        reason = cs.state.terminated.reason
                        break
            if pod.metadata.deletion_timestamp:
                reason = "Terminating"
            age = _age(pod.metadata.creation_timestamp)
            lines.append(f"  {pod.metadata.name:<55} {ready}/{total:<6} {reason:<25} {restarts:<10} {age}")
        return "\n".join(lines)

    def get_pod_logs(
        self,
        pod_name: str,
        namespace: str = "default",
        container: str = "",
        previous: bool = False,
    ) -> str:
        kwargs: dict[str, Any] = {
            "name": pod_name,
            "namespace": namespace,
            "tail_lines": self._max_log_lines,
            "timestamps": True,
        }
        if container:
            kwargs["container"] = container
        if previous:
            kwargs["previous"] = True
        try:
            logs = self._k8s.core.read_namespaced_pod_log(**kwargs)
            return logs or "(empty log)"
        except ApiException as e:
            if e.status == 400:
                return f"Error: {e.reason}. Try specifying a container name."
            return f"Error reading logs: {e.reason}"

    def get_events(self, namespace: str = "default", field_selector: str = "") -> str:
        kwargs: dict = {"namespace": namespace}
        if field_selector:
            kwargs["field_selector"] = field_selector
        events = self._k8s.core.list_namespaced_event(**kwargs)
        if not events.items:
            return f"No events in namespace '{namespace}'"
        warnings = [e for e in events.items if e.type == "Warning"]
        normals = [e for e in events.items if e.type != "Warning"]
        all_events = warnings + normals
        lines = [f"{'TYPE':<10} {'REASON':<30} {'OBJECT':<50} {'MESSAGE'}"]
        for ev in all_events[:60]:
            obj = f"{ev.involved_object.kind}/{ev.involved_object.name}"
            msg = (ev.message or "").replace("\n", " ")[:120]
            lines.append(f"  {ev.type:<10} {ev.reason:<30} {obj:<50} {msg}")
        return "\n".join(lines)

    def describe_pod(self, pod_name: str, namespace: str = "default") -> str:
        try:
            pod = self._k8s.core.read_namespaced_pod(name=pod_name, namespace=namespace)
        except ApiException as e:
            return f"Error: {e.reason}"
        lines = [
            f"Name:         {pod.metadata.name}",
            f"Namespace:    {pod.metadata.namespace}",
            f"Node:         {_safe(pod.spec.node_name)}",
            f"Start Time:   {_safe(pod.status.start_time)}",
            f"Labels:       {json.dumps(pod.metadata.labels or {})}",
            f"Status:       {_safe(pod.status.phase)}",
            f"IP:           {_safe(pod.status.pod_ip)}",
            "",
            "Containers:",
        ]
        for c in (pod.spec.containers or []):
            lines.append(f"  {c.name}:")
            lines.append(f"    Image: {c.image}")
            if c.resources:
                req = c.resources.requests or {}
                lim = c.resources.limits or {}
                lines.append(f"    Requests: cpu={req.get('cpu','<none>')} memory={req.get('memory','<none>')}")
                lines.append(f"    Limits:   cpu={lim.get('cpu','<none>')} memory={lim.get('memory','<none>')}")
        if pod.status.container_statuses:
            lines.append("")
            lines.append("Container Status:")
            for cs in pod.status.container_statuses:
                lines.append(f"  {cs.name}:")
                lines.append(f"    Ready:    {cs.ready}")
                lines.append(f"    Restarts: {cs.restart_count}")
                state = cs.state
                if state.running:
                    lines.append(f"    State:    Running since {state.running.started_at}")
                elif state.waiting:
                    lines.append(f"    State:    Waiting ({state.waiting.reason}): {state.waiting.message or ''}")
                elif state.terminated:
                    lines.append(
                        f"    State:    Terminated ({state.terminated.reason}) "
                        f"exit={state.terminated.exit_code}"
                    )
        if pod.status.conditions:
            lines.append("")
            lines.append("Conditions:")
            for cond in pod.status.conditions:
                lines.append(f"  {cond.type}: {cond.status} — {cond.message or ''}")
        return "\n".join(lines)

    def get_nodes(self) -> str:
        nodes = self._k8s.core.list_node()
        lines = [f"{'NAME':<45} {'STATUS':<12} {'ROLES':<20} {'AGE':<8} {'VERSION'}"]
        for node in nodes.items:
            roles = ",".join(
                k.replace("node-role.kubernetes.io/", "")
                for k in (node.metadata.labels or {})
                if "node-role.kubernetes.io/" in k
            ) or "worker"
            ready_status = "Unknown"
            if node.status.conditions:
                for cond in node.status.conditions:
                    if cond.type == "Ready":
                        ready_status = "Ready" if cond.status == "True" else "NotReady"
                        break
            version = _safe(node.status.node_info.kubelet_version if node.status.node_info else None)
            age = _age(node.metadata.creation_timestamp)
            lines.append(f"  {node.metadata.name:<45} {ready_status:<12} {roles:<20} {age:<8} {version}")
        return "\n".join(lines)

    def describe_node(self, node_name: str) -> str:
        try:
            node = self._k8s.core.read_node(name=node_name)
        except ApiException as e:
            return f"Error: {e.reason}"
        lines = [
            f"Name: {node.metadata.name}",
            f"Labels: {json.dumps(node.metadata.labels or {})}",
        ]
        if node.status.conditions:
            lines.append("Conditions:")
            for cond in node.status.conditions:
                lines.append(f"  {cond.type}: {cond.status} — {cond.message or ''}")
        if node.status.allocatable:
            lines.append(f"Allocatable: {dict(node.status.allocatable)}")
        if node.status.capacity:
            lines.append(f"Capacity: {dict(node.status.capacity)}")
        return "\n".join(lines)

    def get_deployments(self, namespace: str = "default") -> str:
        deps = self._k8s.apps.list_namespaced_deployment(namespace=namespace)
        if not deps.items:
            return f"No deployments in namespace '{namespace}'"
        lines = [f"{'NAME':<45} {'READY':<8} {'UP-TO-DATE':<12} {'AVAILABLE':<12} {'AGE'}"]
        for d in deps.items:
            s = d.status
            age = _age(d.metadata.creation_timestamp)
            desired = d.spec.replicas or 0
            ready = s.ready_replicas or 0
            up_to_date = s.updated_replicas or 0
            available = s.available_replicas or 0
            lines.append(
                f"  {d.metadata.name:<45} {ready}/{desired:<6} {up_to_date:<12} {available:<12} {age}"
            )
        return "\n".join(lines)

    def get_services(self, namespace: str = "default") -> str:
        svcs = self._k8s.core.list_namespaced_service(namespace=namespace)
        if not svcs.items:
            return f"No services in namespace '{namespace}'"
        lines = [f"{'NAME':<45} {'TYPE':<15} {'CLUSTER-IP':<18} {'EXTERNAL-IP':<20} {'PORT(S)':<25} {'AGE'}"]
        for svc in svcs.items:
            ext_ips = ",".join(
                [i.ip for i in (svc.status.load_balancer.ingress or [])]
                if svc.status.load_balancer and svc.status.load_balancer.ingress
                else []
            ) or "<none>"
            ports = ",".join(
                f"{p.port}/{p.protocol}" for p in (svc.spec.ports or [])
            ) or "<none>"
            age = _age(svc.metadata.creation_timestamp)
            lines.append(
                f"  {svc.metadata.name:<45} {svc.spec.type:<15} "
                f"{_safe(svc.spec.cluster_ip):<18} {ext_ips:<20} {ports:<25} {age}"
            )
        return "\n".join(lines)

    def get_persistent_volumes(self) -> str:
        pvs = self._k8s.core.list_persistent_volume()
        lines = [f"{'NAME':<45} {'CAPACITY':<12} {'ACCESS':<15} {'STATUS':<12} {'CLAIM':<40} {'AGE'}"]
        for pv in pvs.items:
            cap = dict(pv.spec.capacity or {}).get("storage", "?")
            access = ",".join(pv.spec.access_modes or [])
            claim = (
                f"{pv.spec.claim_ref.namespace}/{pv.spec.claim_ref.name}"
                if pv.spec.claim_ref
                else "<none>"
            )
            age = _age(pv.metadata.creation_timestamp)
            status = pv.status.phase or "Unknown"
            lines.append(
                f"  {pv.metadata.name:<45} {cap:<12} {access:<15} {status:<12} {claim:<40} {age}"
            )
        return "\n".join(lines)

    def get_pvcs(self, namespace: str = "default") -> str:
        pvcs = self._k8s.core.list_namespaced_persistent_volume_claim(namespace=namespace)
        if not pvcs.items:
            return f"No PVCs in namespace '{namespace}'"
        lines = [f"{'NAME':<45} {'STATUS':<12} {'VOLUME':<45} {'CAPACITY':<12} {'ACCESS':<15} {'AGE'}"]
        for pvc in pvcs.items:
            cap = dict(pvc.status.capacity or {}).get("storage", "?")
            age = _age(pvc.metadata.creation_timestamp)
            lines.append(
                f"  {pvc.metadata.name:<45} {pvc.status.phase:<12} "
                f"{_safe(pvc.spec.volume_name):<45} {cap:<12} "
                f"{','.join(pvc.spec.access_modes or []):<15} {age}"
            )
        return "\n".join(lines)

    def get_configmaps(self, namespace: str = "default") -> str:
        cms = self._k8s.core.list_namespaced_config_map(namespace=namespace)
        if not cms.items:
            return f"No configmaps in namespace '{namespace}'"
        lines = [f"{'NAME':<50} {'KEYS':<8} {'AGE'}"]
        for cm in cms.items:
            keys = len(cm.data or {})
            age = _age(cm.metadata.creation_timestamp)
            lines.append(f"  {cm.metadata.name:<50} {keys:<8} {age}")
        return "\n".join(lines)

    def get_resource_quotas(self, namespace: str = "default") -> str:
        try:
            rqs = self._k8s.core.list_namespaced_resource_quota(namespace=namespace)
        except ApiException:
            return "Could not fetch resource quotas"
        if not rqs.items:
            return f"No resource quotas in namespace '{namespace}'"
        lines = []
        for rq in rqs.items:
            lines.append(f"ResourceQuota: {rq.metadata.name}")
            hard = rq.status.hard or {}
            used = rq.status.used or {}
            for resource in hard:
                lines.append(f"  {resource}: used={used.get(resource,'?')} / hard={hard[resource]}")
        return "\n".join(lines)

    def check_cluster_health(self) -> str:
        """Quick overall health summary of the cluster."""
        sections: list[str] = []

        # Nodes
        nodes = self._k8s.core.list_node()
        not_ready = [
            n.metadata.name for n in nodes.items
            if not any(
                c.type == "Ready" and c.status == "True"
                for c in (n.status.conditions or [])
            )
        ]
        sections.append(
            f"Nodes: {len(nodes.items)} total, {len(not_ready)} NotReady"
            + (f" [{', '.join(not_ready)}]" if not_ready else "")
        )

        # Pods with issues across all namespaces
        all_pods = self._k8s.core.list_pod_for_all_namespaces()
        problem_pods: list[str] = []
        for pod in all_pods.items:
            phase = pod.status.phase or ""
            if phase in ("Failed", "Unknown"):
                problem_pods.append(
                    f"{pod.metadata.namespace}/{pod.metadata.name} ({phase})"
                )
                continue
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    if cs.state.waiting and cs.state.waiting.reason in (
                        "CrashLoopBackOff",
                        "ImagePullBackOff",
                        "ErrImagePull",
                        "OOMKilled",
                        "Error",
                    ):
                        problem_pods.append(
                            f"{pod.metadata.namespace}/{pod.metadata.name} "
                            f"({cs.state.waiting.reason})"
                        )
                        break
                    if cs.restart_count and cs.restart_count > 5:
                        problem_pods.append(
                            f"{pod.metadata.namespace}/{pod.metadata.name} "
                            f"(restarts={cs.restart_count})"
                        )
                        break

        sections.append(
            f"Problem Pods: {len(problem_pods)}"
            + ("\n  " + "\n  ".join(problem_pods) if problem_pods else "")
        )

        # Pending pods
        pending = [
            f"{p.metadata.namespace}/{p.metadata.name}"
            for p in all_pods.items
            if p.status.phase == "Pending"
        ]
        sections.append(
            f"Pending Pods: {len(pending)}"
            + ("\n  " + "\n  ".join(pending) if pending else "")
        )

        # Warning events across all namespaces
        events = self._k8s.core.list_event_for_all_namespaces(
            field_selector="type=Warning"
        )
        recent_warnings = sorted(
            events.items,
            key=lambda e: e.last_timestamp or e.event_time or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:10]
        warning_lines = [
            f"  {e.involved_object.kind}/{e.involved_object.name}: {e.message or ''}"
            for e in recent_warnings
        ]
        sections.append(
            f"Recent Warning Events: {len(events.items)} total (showing latest 10)"
            + ("\n" + "\n".join(warning_lines) if warning_lines else "")
        )

        return "\n\n".join(sections)

    def get_hpa(self, namespace: str = "default") -> str:
        try:
            hpas = self._k8s.core.api_client.call_api(
                f"/apis/autoscaling/v2/namespaces/{namespace}/horizontalpodautoscalers",
                "GET",
                response_type="object",
            )
            items = hpas[0].get("items", [])
        except Exception:
            return "Could not fetch HPAs (autoscaling/v2 may not be available)"
        if not items:
            return f"No HPAs in namespace '{namespace}'"
        lines = [f"{'NAME':<45} {'MIN':<6} {'MAX':<6} {'CURRENT':<10} {'TARGET'}"]
        for hpa in items:
            meta = hpa.get("metadata", {})
            spec = hpa.get("spec", {})
            status = hpa.get("status", {})
            lines.append(
                f"  {meta.get('name','?'):<45} "
                f"{spec.get('minReplicas','?'):<6} "
                f"{spec.get('maxReplicas','?'):<6} "
                f"{status.get('currentReplicas','?'):<10} "
                f"{spec.get('scaleTargetRef', {}).get('name','?')}"
            )
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────────────────────
    # Destructive / mutating tools — require confirmation unless auto_fix=True
    # ──────────────────────────────────────────────────────────────────────────

    def _confirm(self, action: str) -> bool:
        if self._auto_fix:
            return True
        if self.confirm_callback:
            return self.confirm_callback(action)
        # Default: ask on stdin
        ans = input(f"\n[CONFIRM] {action}\nProceed? (yes/no): ").strip().lower()
        return ans in ("yes", "y")

    def restart_deployment(self, name: str, namespace: str = "default") -> str:
        if not self._confirm(f"Restart deployment '{name}' in namespace '{namespace}'"):
            return "Aborted by user."
        try:
            now = datetime.now(tz=timezone.utc).isoformat()
            patch = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {"kubectl.kubernetes.io/restartedAt": now}
                        }
                    }
                }
            }
            self._k8s.apps.patch_namespaced_deployment(
                name=name, namespace=namespace, body=patch
            )
            return f"Deployment '{name}' in '{namespace}' restarted successfully."
        except ApiException as e:
            return f"Error: {e.reason}"

    def rollback_deployment(self, name: str, namespace: str = "default", revision: int = 0) -> str:
        if not self._confirm(
            f"Rollback deployment '{name}' in namespace '{namespace}' to revision {revision or 'previous'}"
        ):
            return "Aborted by user."
        try:
            cmd = ["kubectl", "rollout", "undo", f"deployment/{name}", "-n", namespace]
            if revision:
                cmd += [f"--to-revision={revision}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return result.stdout.strip()
            return f"Error: {result.stderr.strip()}"
        except Exception as e:
            return f"Error: {e}"

    def scale_deployment(self, name: str, replicas: int, namespace: str = "default") -> str:
        if not self._confirm(
            f"Scale deployment '{name}' in namespace '{namespace}' to {replicas} replica(s)"
        ):
            return "Aborted by user."
        try:
            self._k8s.apps.patch_namespaced_deployment_scale(
                name=name,
                namespace=namespace,
                body={"spec": {"replicas": replicas}},
            )
            return f"Deployment '{name}' scaled to {replicas} replicas."
        except ApiException as e:
            return f"Error: {e.reason}"

    def delete_pod(self, pod_name: str, namespace: str = "default") -> str:
        if not self._confirm(f"Delete pod '{pod_name}' in namespace '{namespace}'"):
            return "Aborted by user."
        try:
            self._k8s.core.delete_namespaced_pod(name=pod_name, namespace=namespace)
            return f"Pod '{pod_name}' deleted."
        except ApiException as e:
            return f"Error: {e.reason}"

    def apply_manifest(self, yaml_content: str) -> str:
        if not self._confirm(f"Apply Kubernetes manifest:\n{yaml_content[:500]}..."):
            return "Aborted by user."
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                f.write(yaml_content)
                fname = f.name
            result = subprocess.run(
                ["kubectl", "apply", "-f", fname],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return f"Error:\n{result.stderr.strip()}"
        except Exception as e:
            return f"Error: {e}"

    def patch_resource(
        self,
        kind: str,
        name: str,
        namespace: str,
        patch_json: str,
    ) -> str:
        if not self._confirm(
            f"Patch {kind} '{name}' in '{namespace}' with: {patch_json}"
        ):
            return "Aborted by user."
        try:
            patch = json.loads(patch_json)
            result = subprocess.run(
                [
                    "kubectl", "patch", kind, name,
                    "-n", namespace,
                    "--type=merge",
                    "--patch", json.dumps(patch),
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return f"Error:\n{result.stderr.strip()}"
        except Exception as e:
            return f"Error: {e}"

    def run_kubectl(self, args: str) -> str:
        """Run an arbitrary read-only kubectl command."""
        parts = args.split()
        # Block destructive verbs without confirmation
        destructive = {"delete", "apply", "patch", "replace", "edit", "scale", "exec"}
        if parts and parts[0] in destructive:
            if not self._confirm(f"kubectl {args}"):
                return "Aborted by user."
        try:
            result = subprocess.run(
                ["kubectl"] + parts,
                capture_output=True, text=True, timeout=60,
            )
            out = result.stdout.strip() or result.stderr.strip()
            return out or "(no output)"
        except Exception as e:
            return f"Error: {e}"
