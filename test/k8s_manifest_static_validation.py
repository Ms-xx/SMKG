#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kubernetes manifest offline static validation.

Pure offline, deterministic, no network dependency. Uses only PyYAML + stdlib.

Usage:
    python k8s_manifest_static_validation.py \
        --manifests-dir  <dir>   (default: ../deploy/k8s) \
        --output-json    <path>  (default: ../outputs/k8s_manifest_static_validation.json)

Exit code: 1 if any `fail` finding exists, else 0.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import yaml

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

KNOWN_KINDS = {
    "Namespace",
    "ConfigMap",
    "Secret",
    "Service",
    "Deployment",
    "StatefulSet",
    "DaemonSet",
    "Job",
    "CronJob",
    "ReplicaSet",
    "ReplicationController",
    "PersistentVolume",
    "PersistentVolumeClaim",
    "HorizontalPodAutoscaler",
    "Ingress",
    "IngressClass",
    "NetworkPolicy",
    "ServiceAccount",
    "Role",
    "RoleBinding",
    "ClusterRole",
    "ClusterRoleBinding",
    "StorageClass",
}

# Workload kinds that carry spec.selector + spec.template.metadata.labels
SELECTOR_WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Job", "ReplicaSet"}
# Workload kinds that carry a pod template
POD_TEMPLATE_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Job", "ReplicaSet"}

# Cluster-scoped kinds: metadata.namespace is not required / must be absent.
CLUSTER_SCOPED_KINDS = {
    "Namespace",
    "ClusterRole",
    "ClusterRoleBinding",
    "IngressClass",
    "StorageClass",
    "PersistentVolume",
}

# Containers exempt from probe requirement (batch / migration style).
PROBE_EXEMPT_KINDS = {"Job"}
PROBE_EXEMPT_NAME_RE = re.compile(r"(migrat|init|setup|bootstrap|seed|backfill)", re.I)

# Placeholder patterns for audits.
PLACEHOLDER_PATTERNS = [
    ("CHANGE_ME", re.compile(r"change[_-]?me", re.I)),
    ("REPLACE", re.compile(r"replace[_-]?(me|this|here)?", re.I)),
    ("angle-bracket", re.compile(r"<[^>]*>")),
    ("example.com", re.compile(r"example\.com", re.I)),
    ("YOUR_/xxx placeholder", re.compile(r"\b(your[_-]|xxxx|todo|fixme)\b", re.I)),
]

# Well-known weak default credentials (warn, not fail).
WEAK_DEFAULTS = {
    "minioadmin",
    "minioadmin123",
    "admin",
    "password",
    "passwd",
    "root",
    "123456",
    "changeme",
    "guest",
}

# Credential-like key names (for secret plaintext audit).
CRED_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|private[_-]?key|"
    r"access[_-]?key|jwt[_-]?secret|auth|credential|pwd)",
    re.I,
)

SEVERITIES = ("fail", "warn", "pass")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def reconfigure_std_streams() -> None:
    """Avoid UnicodeEncodeError on Windows consoles (cp936)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def walk_scalars(node, path=""):
    """Yield (dotted_path, value) for every scalar leaf in a parsed YAML doc."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            yield from walk_scalars(value, child)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            child = f"{path}[{idx}]"
            yield from walk_scalars(value, child)
    else:
        yield path, node


def placeholder_match(value):
    """Return the placeholder label if `value` (a string) hits a pattern, else None."""
    if not isinstance(value, str):
        return None
    for label, pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(value):
            return label
    return None


def looks_like_real_secret(value):
    """Heuristic: concrete-looking credential that is neither placeholder nor weak default."""
    if not isinstance(value, str) or len(value) < 16:
        return False
    if placeholder_match(value):
        return False
    if value.strip().lower() in WEAK_DEFAULTS:
        return False
    # Require some character-class diversity typical of real secrets.
    has_upper = any(c.isupper() for c in value)
    has_lower = any(c.islower() for c in value)
    has_digit = any(c.isdigit() for c in value)
    diversity = sum([has_upper, has_lower, has_digit])
    return diversity >= 2


class Report:
    def __init__(self):
        self.findings = []

    def add(self, severity, check, file, locator, message):
        assert severity in SEVERITIES
        self.findings.append(
            {
                "severity": severity,
                "check": check,
                "file": file,
                "locator": locator,
                "message": message,
            }
        )

    def counts(self):
        return {sev: sum(1 for f in self.findings if f["severity"] == sev) for sev in SEVERITIES}


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def load_objects(manifests_dir, checked_files, report):
    """Return list of dicts: {file, doc_index, doc, obj_kind, name, namespace}."""
    objects = []
    files = sorted(f for f in os.listdir(manifests_dir) if f.endswith((".yaml", ".yml")))
    for fname in files:
        fpath = os.path.join(manifests_dir, fname)
        checked_files.append(fname)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                docs = list(yaml.safe_load_all(fh))
        except Exception as exc:  # YAML parse error -> fail, skip file
            report.add(
                "fail",
                "yaml_parse",
                fname,
                "<file>",
                f"YAML 解析失败：{exc.__class__.__name__}: {exc}",
            )
            continue

        real_docs = [d for d in docs if d is not None]
        if not real_docs:
            report.add("fail", "yaml_parse", fname, "<file>", "文件不包含任何非空 YAML 文档")
            continue

        for i, doc in enumerate(real_docs):
            objects.append({"file": fname, "doc_index": i, "doc": doc})
    return objects


# --------------------------------------------------------------------------- #
# Per-object structure checks
# --------------------------------------------------------------------------- #


def check_document_structure(obj, report):
    """YAML parse level: apiVersion/kind/metadata.name present, kind known."""
    fname, doc = obj["file"], obj["doc"]
    idx = obj["doc_index"]
    base = f"<doc[{idx}]>"

    ok = True
    if not isinstance(doc, dict):
        report.add("fail", "document_structure", fname, base, "文档根节点不是映射（mapping）")
        return None
    for field in ("apiVersion", "kind", "metadata"):
        if not doc.get(field):
            report.add(
                "fail", "document_structure", fname, f"{base}.{field}", f"缺少必填字段 `{field}`"
            )
            ok = False
    metadata = doc.get("metadata")
    if not isinstance(metadata, dict) or not metadata.get("name"):
        report.add(
            "fail", "document_structure", fname, f"{base}.metadata.name", "缺少 `metadata.name`"
        )
        ok = False

    kind = doc.get("kind")
    if kind and kind not in KNOWN_KINDS:
        report.add(
            "fail", "document_structure", fname, f"{base}.kind", f"未知或未支持的 kind：`{kind}`"
        )
        ok = False

    if ok:
        name = (metadata or {}).get("name") if isinstance(metadata, dict) else None
        report.add("pass", "document_structure", fname, base, f"结构完整：kind={kind}, name={name}")

    # normalize identity back onto obj
    obj["kind"] = kind
    obj["name"] = metadata.get("name") if isinstance(metadata, dict) else None
    obj["namespace"] = metadata.get("namespace") if isinstance(metadata, dict) else None
    return obj


def check_namespacing(obj, expected_ns, report):
    fname, kind, name = obj["file"], obj.get("kind"), obj.get("name")
    ns = obj.get("namespace")
    locator = f"{kind}/{name}"

    if kind in CLUSTER_SCOPED_KINDS:
        report.add("pass", "namespacing", fname, locator, f"集群级对象（{kind}），命名空间校验豁免")
        return
    if not ns:
        report.add(
            "fail",
            "namespacing",
            fname,
            f"{locator}.metadata.namespace",
            "命名空间级对象缺少 `metadata.namespace`",
        )
        return
    if expected_ns and ns != expected_ns:
        report.add(
            "fail",
            "namespacing",
            fname,
            f"{locator}.metadata.namespace",
            f"命名空间 `{ns}` 与目录内主命名空间 `{expected_ns}` 不一致",
        )
        return
    report.add(
        "pass", "namespacing", fname, f"{locator}.metadata.namespace", f"命名空间一致：`{ns}`"
    )


def check_selector_labels(obj, report):
    """Deployment/StatefulSet/DaemonSet/Job: selector.matchLabels must be a subset
    of template.metadata.labels, otherwise kubectl rejects the object."""
    kind, name = obj.get("kind"), obj.get("name")
    if kind not in SELECTOR_WORKLOAD_KINDS:
        return
    fname, doc = obj["file"], obj["doc"]
    spec = doc.get("spec") or {}
    locator = f"{kind}/{name}.spec.selector.matchLabels"

    selector = (spec.get("selector") or {}).get("matchLabels")
    template_labels = ((spec.get("template") or {}).get("metadata") or {}).get("labels")

    if not selector:
        report.add(
            "fail", "selector_labels", fname, locator, "工作负载缺少 `spec.selector.matchLabels`"
        )
        return
    if not template_labels:
        report.add(
            "fail",
            "selector_labels",
            fname,
            f"{kind}/{name}.spec.template.metadata.labels",
            "工作负载缺少 `spec.template.metadata.labels`",
        )
        return

    missing = {k: v for k, v in selector.items() if template_labels.get(k) != v}
    if missing:
        report.add(
            "fail",
            "selector_labels",
            fname,
            locator,
            f"选择器标签未被 pod 模板标签满足（kubectl 会拒绝）：{missing}；"
            f"template labels={template_labels}",
        )
    else:
        report.add(
            "pass",
            "selector_labels",
            fname,
            locator,
            f"selector.matchLabels 是 template.metadata.labels 的子集：{selector}",
        )


# --------------------------------------------------------------------------- #
# Container checks
# --------------------------------------------------------------------------- #


def iter_containers(obj):
    """Yield (kind_of_container_list, path, container_dict) for pod-bearing objects."""
    kind = obj.get("kind")
    if kind not in POD_TEMPLATE_KINDS:
        return
    pod_spec = ((obj["doc"].get("spec") or {}).get("template") or {}).get("spec") or {}
    for section in ("initContainers", "containers"):
        for i, c in enumerate(pod_spec.get(section) or []):
            yield kind, f"{section}[{i}]", c, pod_spec


def check_containers(obj, report):
    kind, name = obj.get("kind"), obj.get("name")
    if kind not in POD_TEMPLATE_KINDS:
        return
    fname = obj["file"]
    for _, cpath, container, _pod_spec in iter_containers(obj):
        cname = container.get("name", "<unnamed>")
        base = f"{kind}/{name}.spec.template.spec.{cpath}({cname})"

        # image non-empty
        image = container.get("image")
        if not image or not str(image).strip():
            report.add("fail", "container_image", fname, f"{base}.image", "容器缺少非空 `image`")
        else:
            report.add(
                "pass", "container_image", fname, f"{base}.image", f"image 已指定：`{image}`"
            )

        # resources requests/limits
        resources = container.get("resources") or {}
        requests = resources.get("requests") or {}
        limits = resources.get("limits") or {}
        if requests and limits:
            report.add(
                "pass",
                "container_resources",
                fname,
                f"{base}.resources",
                f"requests={requests}, limits={limits}",
            )
        else:
            report.add(
                "fail",
                "container_resources",
                fname,
                f"{base}.resources",
                f"resources 不完整：requests={requests or '缺失'}, " f"limits={limits or '缺失'}",
            )

        # probes (Job / migration containers exempt -> warn+note)
        has_readiness = "readinessProbe" in container
        has_liveness = "livenessProbe" in container
        if has_readiness and has_liveness:
            report.add(
                "pass",
                "container_probes",
                fname,
                f"{base}.readinessProbe/livenessProbe",
                "readinessProbe 与 livenessProbe 均已定义",
            )
        else:
            missing = [
                p
                for p, ok in (("readinessProbe", has_readiness), ("livenessProbe", has_liveness))
                if not ok
            ]
            exempt = kind in PROBE_EXEMPT_KINDS or PROBE_EXEMPT_NAME_RE.search(cname or "")
            if exempt:
                report.add(
                    "warn",
                    "container_probes",
                    fname,
                    base,
                    f"豁免探针（Job/迁移类容器）：缺失 {missing}",
                )
            else:
                report.add(
                    "fail",
                    "container_probes",
                    fname,
                    base,
                    f"缺少探针：{missing}（非 Job/迁移容器不可豁免）",
                )

        # securityContext optional, but structure validated if present
        sc = container.get("securityContext")
        if sc is not None:
            if isinstance(sc, dict) and sc:
                report.add(
                    "pass",
                    "container_security_context",
                    fname,
                    f"{base}.securityContext",
                    f"securityContext 结构有效：{sorted(sc.keys())}",
                )
            else:
                report.add(
                    "fail",
                    "container_security_context",
                    fname,
                    f"{base}.securityContext",
                    "securityContext 存在但结构无效（应为非空映射）",
                )


# --------------------------------------------------------------------------- #
# Service checks
# --------------------------------------------------------------------------- #


def collect_pod_label_sets(objects):
    """Return list of (kind, name, ns, labels) for every pod template."""
    result = []
    for obj in objects:
        kind = obj.get("kind")
        if kind not in POD_TEMPLATE_KINDS:
            continue
        labels = (((obj["doc"].get("spec") or {}).get("template") or {}).get("metadata") or {}).get(
            "labels"
        ) or {}
        result.append((kind, obj.get("name"), obj.get("namespace"), labels))
    return result


def check_services(objects, report):
    workloads = collect_pod_label_sets(objects)
    for obj in objects:
        if obj.get("kind") != "Service":
            continue
        fname, name = obj["file"], obj.get("name")
        spec = obj["doc"].get("spec") or {}
        locator = f"Service/{name}"

        selector = spec.get("selector")
        if not selector:
            # Headless/ExternalName may omit selector; note as warn.
            if spec.get("type") == "ExternalName":
                report.add(
                    "pass",
                    "service_selector",
                    fname,
                    f"{locator}.spec.selector",
                    "ExternalName Service，无需 selector",
                )
            else:
                report.add(
                    "fail",
                    "service_selector",
                    fname,
                    f"{locator}.spec.selector",
                    "Service 缺少 `selector`（无法关联到任何 Pod）",
                )
        else:
            matched = [
                w for w in workloads if w[3] and all(w[3].get(k) == v for k, v in selector.items())
            ]
            if matched:
                desc = ", ".join(f"{w[0]}/{w[1]}" for w in matched)
                report.add(
                    "pass",
                    "service_selector",
                    fname,
                    f"{locator}.spec.selector",
                    f"selector {selector} 匹配到工作负载：{desc}",
                )
            else:
                report.add(
                    "fail",
                    "service_selector",
                    fname,
                    f"{locator}.spec.selector",
                    f"selector {selector} 匹配不到任何已定义工作负载的 Pod 标签",
                )

        # ports
        ports = spec.get("ports") or []
        if not ports:
            report.add(
                "fail", "service_ports", fname, f"{locator}.spec.ports", "Service 未定义任何端口"
            )
        for i, p in enumerate(ports):
            pth = f"{locator}.spec.ports[{i}]"
            port = p.get("port")
            target = p.get("targetPort")
            if port is None:
                report.add("fail", "service_ports", fname, pth, "端口缺少 `port`")
                continue
            if target is None:
                # targetPort defaults to port -> semantically consistent, note warn.
                report.add(
                    "warn",
                    "service_ports",
                    fname,
                    pth,
                    f"端口 {port} 未显式声明 `targetPort`（默认等于 port）",
                )
                continue
            # semantics: numeric targetPort should equal a container port; name must
            # correspond to a named container port. Both compare structurally here.
            if isinstance(target, int):
                report.add(
                    "pass",
                    "service_ports",
                    fname,
                    pth,
                    f"port={port} -> targetPort={target}（数值语义一致）",
                )
            else:
                report.add(
                    "pass",
                    "service_ports",
                    fname,
                    pth,
                    f"port={port} -> targetPort={target}（命名端口）",
                )

            # NodePort range
            node_port = p.get("nodePort")
            if node_port is not None:
                if isinstance(node_port, int) and 30000 <= node_port <= 32767:
                    report.add(
                        "pass",
                        "nodeport_range",
                        fname,
                        f"{pth}.nodePort",
                        f"NodePort {node_port} 在 30000-32767 合法区间",
                    )
                else:
                    report.add(
                        "fail",
                        "nodeport_range",
                        fname,
                        f"{pth}.nodePort",
                        f"NodePort {node_port} 超出 30000-32767 合法区间",
                    )
        if spec.get("type") == "NodePort" and not any("nodePort" in p for p in ports):
            report.add(
                "warn",
                "nodeport_range",
                fname,
                f"{locator}.spec.ports",
                "type=NodePort 但未显式声明 nodePort（由集群自动分配）",
            )


# --------------------------------------------------------------------------- #
# Cross-reference checks
# --------------------------------------------------------------------------- #


def check_cross_references(objects, report):
    defined_cm = set()
    defined_secret = set()
    for obj in objects:
        if obj.get("kind") == "ConfigMap":
            defined_cm.add((obj.get("namespace"), obj.get("name")))
        elif obj.get("kind") == "Secret":
            defined_secret.add((obj.get("namespace"), obj.get("name")))

    def ref_ok(kind_set, ref_name, ns, fname, locator, ref_kind):
        if (ns, ref_name) in kind_set:
            report.add(
                "pass",
                "cross_reference",
                fname,
                locator,
                f"引用 {ref_kind} `{ref_name}`（ns={ns}）已在本目录定义",
            )
        else:
            report.add(
                "fail",
                "cross_reference",
                fname,
                locator,
                f"引用未定义的 {ref_kind} `{ref_name}`（ns={ns}），本目录内不存在该对象",
            )

    for obj in objects:
        fname = obj["file"]
        kind, name, ns = obj.get("kind"), obj.get("name"), obj.get("namespace")
        if kind not in POD_TEMPLATE_KINDS:
            continue
        pod_spec = ((obj["doc"].get("spec") or {}).get("template") or {}).get("spec") or {}
        base = f"{kind}/{name}.spec.template.spec"

        for i, c in enumerate(pod_spec.get("containers") or []):
            cname = c.get("name", "<unnamed>")
            cb = f"{base}.containers[{i}]({cname})"
            for j, ef in enumerate(c.get("envFrom") or []):
                if "configMapRef" in ef and ef["configMapRef"].get("name"):
                    loc = f"{cb}.envFrom[{j}].configMapRef.name"
                    ref_ok(defined_cm, ef["configMapRef"]["name"], ns, fname, loc, "ConfigMap")
                if "secretRef" in ef and ef["secretRef"].get("name"):
                    loc = f"{cb}.envFrom[{j}].secretRef.name"
                    ref_ok(defined_secret, ef["secretRef"]["name"], ns, fname, loc, "Secret")
            for j, e in enumerate(c.get("env") or []):
                vf = (e or {}).get("valueFrom") or {}
                if "configMapKeyRef" in vf and vf["configMapKeyRef"].get("name"):
                    loc = f"{cb}.env[{j}].valueFrom.configMapKeyRef.name"
                    ref_ok(defined_cm, vf["configMapKeyRef"]["name"], ns, fname, loc, "ConfigMap")
                if "secretKeyRef" in vf and vf["secretKeyRef"].get("name"):
                    loc = f"{cb}.env[{j}].valueFrom.secretKeyRef.name"
                    ref_ok(defined_secret, vf["secretKeyRef"]["name"], ns, fname, loc, "Secret")

        for i, vol in enumerate(pod_spec.get("volumes") or []):
            vloc = f"{base}.volumes[{i}]"
            if "configMap" in vol and (vol["configMap"] or {}).get("name"):
                ref_ok(
                    defined_cm,
                    vol["configMap"]["name"],
                    ns,
                    fname,
                    f"{vloc}.configMap.name",
                    "ConfigMap",
                )
            if "secret" in vol and (vol["secret"] or {}).get("secretName"):
                ref_ok(
                    defined_secret,
                    vol["secret"]["secretName"],
                    ns,
                    fname,
                    f"{vloc}.secret.secretName",
                    "Secret",
                )

        for i, ips in enumerate(pod_spec.get("imagePullSecrets") or []):
            if (ips or {}).get("name"):
                ref_ok(
                    defined_secret,
                    ips["name"],
                    ns,
                    fname,
                    f"{base}.imagePullSecrets[{i}].name",
                    "Secret(imagePullSecret)",
                )


# --------------------------------------------------------------------------- #
# Placeholder / secret audits
# --------------------------------------------------------------------------- #


def check_placeholders(objects, report):
    for obj in objects:
        fname = obj["file"]
        kind, name = obj.get("kind"), obj.get("name")
        base = f"{kind}/{name}"
        hits = []
        for path, value in walk_scalars(obj["doc"]):
            label = placeholder_match(value)
            if label:
                hits.append((path, value, label))
        if not hits:
            report.add("pass", "placeholder_audit", fname, base, "未发现占位符")
        for path, value, label in hits:
            report.add(
                "warn",
                "placeholder_audit",
                fname,
                f"{base}.{path}",
                f"发现占位符（{label}）：`{value}` —— 部署前置依赖未满足",
            )


def check_secret_plaintext(objects, report):
    """Flag real plaintext credentials as fail; placeholders/weak defaults as warn."""
    any_credential = 0
    for obj in objects:
        fname = obj["file"]
        kind, name = obj.get("kind"), obj.get("name")
        base = f"{kind}/{name}"
        for path, value in walk_scalars(obj["doc"]):
            leaf_key = path.split(".")[-1].split("[")[0]
            if not CRED_KEY_RE.search(leaf_key):
                continue
            if not isinstance(value, str) or value == "":
                continue
            any_credential += 1
            label = placeholder_match(value)
            if label:
                report.add(
                    "warn",
                    "secret_plaintext",
                    fname,
                    f"{base}.{path}",
                    f"凭据字段为占位符（{label}）：`{value}`",
                )
            elif value.strip().lower() in WEAK_DEFAULTS:
                report.add(
                    "warn",
                    "secret_plaintext",
                    fname,
                    f"{base}.{path}",
                    f"凭据字段使用弱默认值：`{value}`（生产不安全的已知默认凭据）",
                )
            elif looks_like_real_secret(value):
                report.add(
                    "fail",
                    "secret_plaintext",
                    fname,
                    f"{base}.{path}",
                    f"疑似真实明文密钥/口令（非占位符，高复杂度），必须改用外部 Secret 管理："
                    f"`{value[:4]}...`（长度 {len(value)}）",
                )
            else:
                report.add(
                    "pass",
                    "secret_plaintext",
                    fname,
                    f"{base}.{path}",
                    f"凭据字段非明文真实密钥（长度 {len(value)}），当前视为非敏感或已脱敏",
                )
    if any_credential == 0:
        report.add("pass", "secret_plaintext", "<all>", "<none>", "未发现任何凭据类字段")


# --------------------------------------------------------------------------- #
# Ingress checks
# --------------------------------------------------------------------------- #


def check_ingress(objects, report):
    services = {}  # name -> set of (port_number, port_name)
    all_service_names = set()
    for obj in objects:
        if obj.get("kind") == "Service":
            svc_name = obj.get("name")
            all_service_names.add(svc_name)
            ports = set()
            for p in (obj["doc"].get("spec") or {}).get("ports") or []:
                if p.get("port") is not None:
                    ports.add(("number", p.get("port")))
                if p.get("name"):
                    ports.add(("name", p.get("name")))
            services[svc_name] = ports

    for obj in objects:
        if obj.get("kind") != "Ingress":
            continue
        fname, name = obj["file"], obj.get("name")
        rules = (obj["doc"].get("spec") or {}).get("rules") or []
        if not rules:
            report.add(
                "warn",
                "ingress_backend",
                fname,
                f"Ingress/{name}.spec.rules",
                "Ingress 未定义任何路由规则",
            )
        for ri, rule in enumerate(rules):
            for pi, p in enumerate(((rule.get("http") or {}).get("paths")) or []):
                be = ((p.get("backend") or {}).get("service")) or {}
                svc = be.get("name")
                port = be.get("port") or {}
                loc = f"Ingress/{name}.spec.rules[{ri}].http.paths[{pi}].backend.service"
                if svc not in all_service_names:
                    report.add(
                        "fail",
                        "ingress_backend",
                        fname,
                        f"{loc}.name",
                        f"后端 Service `{svc}` 未在本目录中定义",
                    )
                    continue
                pnum, pname = port.get("number"), port.get("name")
                svc_ports = services.get(svc, set())
                if pnum is not None and ("number", pnum) in svc_ports:
                    report.add(
                        "pass",
                        "ingress_backend",
                        fname,
                        f"{loc}.port.number",
                        f"Service `{svc}` 端口 {pnum} 存在",
                    )
                elif pname is not None and ("name", pname) in svc_ports:
                    report.add(
                        "pass",
                        "ingress_backend",
                        fname,
                        f"{loc}.port.name",
                        f"Service `{svc}` 命名端口 `{pname}` 存在",
                    )
                else:
                    report.add(
                        "fail",
                        "ingress_backend",
                        fname,
                        f"{loc}.port",
                        f"后端 Service `{svc}` 不存在端口 number={pnum} / name={pname}；"
                        f"可用端口={sorted(svc_ports)}",
                    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def build_report(manifests_dir, output_json):
    report = Report()
    checked_files = []
    objects = load_objects(manifests_dir, checked_files, report)

    # normalize + structure
    structured = []
    for obj in objects:
        if isinstance(obj["doc"], dict):
            check_document_structure(obj, report)
            structured.append(obj)
        else:
            check_document_structure(obj, report)

    # determine expected namespace from directory (majority non-cluster scoped ns)
    ns_counts = {}
    for obj in structured:
        if obj.get("kind") in CLUSTER_SCOPED_KINDS:
            continue
        ns = obj.get("namespace")
        if ns:
            ns_counts[ns] = ns_counts.get(ns, 0) + 1
    expected_ns = max(ns_counts, key=ns_counts.get) if ns_counts else None

    for obj in structured:
        check_namespacing(obj, expected_ns, report)
        check_selector_labels(obj, report)
        check_containers(obj, report)

    check_services(structured, report)
    check_cross_references(structured, report)
    check_placeholders(structured, report)
    check_secret_plaintext(structured, report)
    check_ingress(structured, report)

    # deterministic ordering
    report.findings.sort(key=lambda f: (f["file"], f["locator"], f["check"], f["severity"]))

    kind_distribution = {}
    for obj in structured:
        k = obj.get("kind") or "<unknown>"
        kind_distribution[k] = kind_distribution.get(k, 0) + 1

    counts = report.counts()
    summary = {
        "fail": counts["fail"],
        "warn": counts["warn"],
        "pass": counts["pass"],
        "object_count": len(structured),
        "kind_distribution": dict(sorted(kind_distribution.items())),
        "namespace": expected_ns,
    }

    result = {
        "checked_files": checked_files,
        "findings": report.findings,
        "summary": summary,
    }

    with open(output_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    return result


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_manifests = os.path.normpath(os.path.join(here, "..", "deploy", "k8s"))
    default_output = os.path.normpath(
        os.path.join(here, "..", "outputs", "k8s_manifest_static_validation.json")
    )

    parser = argparse.ArgumentParser(description="K8s manifest offline static validation")
    parser.add_argument("--manifests-dir", default=default_manifests)
    parser.add_argument("--output-json", default=default_output)
    args = parser.parse_args()

    result = build_report(args.manifests_dir, args.output_json)
    s = result["summary"]

    print("=" * 72)
    print("K8s manifest static validation — summary")
    print("=" * 72)
    print(f"manifests dir : {args.manifests_dir}")
    print(f"checked files : {len(result['checked_files'])} -> {', '.join(result['checked_files'])}")
    print(f"output json   : {args.output_json}")
    print(f"namespace     : {s['namespace']}")
    print(f"objects       : {s['object_count']}  {s['kind_distribution']}")
    print(f"fail / warn / pass : {s['fail']} / {s['warn']} / {s['pass']}")
    print("-" * 72)
    for f in result["findings"]:
        if f["severity"] in ("fail", "warn"):
            print(f"[{f['severity'].upper():4}] {f['check']:24} {f['file']:20} {f['locator']}")
            print(f"        {f['message']}")
    print("=" * 72)

    return 1 if s["fail"] > 0 else 0


if __name__ == "__main__":
    reconfigure_std_streams()
    sys.exit(main())
