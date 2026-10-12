#!/usr/bin/env python3
"""Paid Media OS: local artifacts, safe Meta reads, and gated Meta writes."""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
ACK_CREATE = "I_UNDERSTAND_THIS_CREATES_PAUSED_META_OBJECTS"
ACK_ACTIVATE = "I_UNDERSTAND_THIS_ACTIVATES_A_META_OBJECT"
OBJECT_KINDS = {"campaign", "adset", "creative", "ad"}
ENDPOINT_SUFFIXES = {"campaign": "campaigns", "adset": "adsets", "creative": "adcreatives", "ad": "ads"}
MEDIA_KINDS = {"static", "video", "carousel"}
ASSET_REFERENCE_KEYS = {"image_hash", "video_id"}
BUNDLE_PATHS = (
    "AGENT_GUIDE.md", "README.md", "SECURITY.md", "LICENSE", "NOTICE", "COMMERCIAL-LICENSE.md",
    "TRADEMARKS.md", "CLA.md", "CONTRIBUTING.md", "CHANGELOG.md", ".gitignore", ".env.example", "docs", "templates",
    "scripts", "skills", "tests",
)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fail(message: str) -> None:
    raise ValueError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"Missing file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path}: {exc.msg}")
    if not isinstance(data, dict):
        fail(f"Expected a JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def json_sha256(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def private_path(workspace: Path, relative: str) -> Path:
    candidate = (workspace / relative).resolve()
    root = workspace.resolve()
    if candidate != root and root not in candidate.parents:
        fail("Path must stay inside the workspace")
    return candidate


def completed_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not value.startswith("REPLACE_")


def iso_time(value: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        fail(f"{field} must be ISO 8601")


def is_account_id(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"act_[0-9]+", value) is not None


def load_workspace(workspace: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        read_json(workspace / "workspace.json"),
        read_json(workspace / "campaign-manifest.json"),
        read_json(workspace / "creative-catalog.json"),
    )


def payload_values(payload: Any, keys: set[str]) -> list[str]:
    values: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in keys and isinstance(value, str):
                values.append(value)
            values.extend(payload_values(value, keys))
    elif isinstance(payload, list):
        for value in payload:
            values.extend(payload_values(value, keys))
    return values


def validate_gates(workspace: Path, config: dict[str, Any], manifest: dict[str, Any], catalog: dict[str, Any], required_lifecycle_action: str) -> list[str]:
    errors: list[str] = []
    tenant_id = config.get("tenant_id")
    account_id = config.get("account_id")
    strategy_version = config.get("strategy_lock_version")
    if not completed_text(strategy_version):
        errors.append("workspace.json strategy_lock_version must be completed")
        return errors
    try:
        lifecycle = read_json(workspace / "lifecycle-state.json")
        strategy = read_json(workspace / "strategy-approval.json")
        bank = read_json(workspace / "creative-bank-register.json")
        selection = read_json(workspace / "test-selection.json")
        production = read_json(workspace / "production-register.json")
    except ValueError as exc:
        return [str(exc)]

    if lifecycle.get("tenant_id") != tenant_id or lifecycle.get("account_id") != account_id:
        errors.append("lifecycle state tenant_id and account_id must match workspace scope")
    if lifecycle.get("state") != "ready-for-paused-build":
        errors.append("lifecycle state must be ready-for-paused-build before a Meta write")
    if lifecycle.get("tenant_intake_status") != "APPROVED":
        errors.append("lifecycle state tenant_intake_status must be APPROVED")
    for field in ("accountable_owner", "tracking_evidence_ref", "next_permitted_action"):
        if not completed_text(lifecycle.get(field)):
            errors.append(f"lifecycle state needs a completed {field}")
    if lifecycle.get("next_permitted_action") != required_lifecycle_action:
        errors.append(f"lifecycle state next_permitted_action must be {required_lifecycle_action} before a Meta write")
    if lifecycle.get("blockers") != []:
        errors.append("lifecycle state blockers must be a present empty list before a Meta write")

    if strategy.get("tenant_id") != tenant_id or strategy.get("strategy_lock_version") != strategy_version:
        errors.append("strategy approval must match workspace tenant_id and strategy_lock_version")
    if strategy.get("strategy_lock_path") != "strategy-lock.md" or strategy.get("status") != "APPROVED":
        errors.append("strategy approval must approve strategy-lock.md")
    for field in ("approved_by", "approved_at", "expires_at"):
        if not completed_text(strategy.get(field)):
            errors.append(f"strategy approval needs a completed {field}")
    if completed_text(strategy.get("expires_at")):
        try:
            if iso_time(str(strategy["expires_at"]), "strategy approval expires_at") <= datetime.now(timezone.utc):
                errors.append("strategy approval is expired")
        except ValueError as exc:
            errors.append(str(exc))

    if bank.get("tenant_id") != tenant_id or bank.get("strategy_lock_version") != strategy_version:
        errors.append("creative bank register must match workspace tenant_id and strategy_lock_version")
    concepts = bank.get("concepts")
    if not isinstance(concepts, list) or len(concepts) != 50:
        errors.append("creative bank register must contain exactly 50 concepts")
        concepts = []
    concept_map = {item.get("concept_id"): item for item in concepts if isinstance(item, dict) and completed_text(item.get("concept_id"))}
    if len(concept_map) != 50:
        errors.append("creative bank register concept IDs must be unique and completed")
    if not completed_text(bank.get("reviewed_by")) or not completed_text(bank.get("reviewed_at")):
        errors.append("creative bank register needs reviewed_by and reviewed_at")

    if selection.get("tenant_id") != tenant_id or selection.get("strategy_lock_version") != strategy_version:
        errors.append("test selection must match workspace tenant_id and strategy_lock_version")
    selected = selection.get("selected_concept_ids")
    if not isinstance(selected, list) or not 3 <= len(selected) <= 5 or len(set(selected)) != len(selected):
        errors.append("test selection must contain exactly 3 to 5 unique selected_concept_ids")
        selected = []
    elif any(not isinstance(concept_id, str) or concept_map.get(concept_id, {}).get("eligibility") != "eligible" for concept_id in selected):
        errors.append("every selected concept must be eligible in the creative bank register")
    for field in ("selection_reason", "approved_by", "approved_at"):
        if not completed_text(selection.get(field)):
            errors.append(f"test selection needs a completed {field}")

    if production.get("tenant_id") != tenant_id or production.get("strategy_lock_version") != strategy_version:
        errors.append("production register must match workspace tenant_id and strategy_lock_version")
    handoffs = production.get("handoffs")
    if not isinstance(handoffs, list):
        errors.append("production register handoffs must be a list")
        handoffs = []
    handoff_map = {item.get("concept_id"): item for item in handoffs if isinstance(item, dict) and isinstance(item.get("concept_id"), str)}
    if set(handoff_map) != set(selected):
        errors.append("production register must contain one handoff for every selected concept")
    assets = catalog.get("assets") if isinstance(catalog.get("assets"), list) else []
    assets_by_id = {item.get("asset_id"): item for item in assets if isinstance(item, dict)}
    for concept_id in selected:
        handoff = handoff_map.get(concept_id, {})
        asset = assets_by_id.get(handoff.get("asset_id"))
        if handoff.get("status") != "APPROVED" or not asset or asset.get("creative_concept_id") != concept_id:
            errors.append(f"production handoff for {concept_id!r} must bind an approved matching catalog asset")
    selected_asset_ids = {handoff_map[concept_id].get("asset_id") for concept_id in selected if concept_id in handoff_map}
    manifest_asset_ids = manifest.get("creative_asset_ids")
    if not isinstance(manifest_asset_ids, list) or set(manifest_asset_ids) != selected_asset_ids:
        errors.append("campaign manifest creative_asset_ids must exactly match selected production assets")
    for field in ("approved_by", "approved_at"):
        if not completed_text(production.get(field)):
            errors.append(f"production register needs a completed {field}")
    return errors


def validate_workspace(workspace: Path, required_lifecycle_action: str = "create-paused") -> list[str]:
    errors: list[str] = []
    try:
        config, manifest, catalog = load_workspace(workspace)
    except ValueError as exc:
        return [str(exc)]
    tenant_id = config.get("tenant_id")
    account_id = config.get("account_id")
    if not completed_text(tenant_id):
        errors.append("workspace.json tenant_id must be a completed tenant identifier")
    if manifest.get("tenant_id") != tenant_id:
        errors.append("campaign manifest tenant_id must match workspace tenant_id")
    if not is_account_id(account_id):
        errors.append("workspace.json account_id must use act_<digits>")
    if manifest.get("account_id") != account_id:
        errors.append("campaign manifest account_id must match workspace account_id")
    if manifest.get("target_status") != "PAUSED":
        errors.append("campaign manifest target_status must be PAUSED")
    assets = catalog.get("assets")
    if not isinstance(assets, list):
        errors.append("creative catalog assets must be a list")
        assets = []
    by_id = {item.get("asset_id"): item for item in assets if isinstance(item, dict)}
    asset_ids = manifest.get("creative_asset_ids")
    if not isinstance(asset_ids, list) or not asset_ids or len(set(asset_ids)) != len(asset_ids):
        errors.append("campaign manifest must list unique creative_asset_ids")
        asset_ids = []
    for asset_id in asset_ids:
        asset = by_id.get(asset_id)
        if not asset:
            errors.append(f"manifest asset {asset_id!r} is missing from the catalog")
            continue
        for field in ("asset_sha256", "rights_status", "approval_status"):
            if not completed_text(asset.get(field)):
                errors.append(f"asset {asset_id!r} needs a real {field}")
        meta_asset_ids = asset.get("meta_asset_ids")
        if not isinstance(meta_asset_ids, list) or not meta_asset_ids or any(not completed_text(value) for value in meta_asset_ids):
            errors.append(f"asset {asset_id!r} needs verified meta_asset_ids")
        if asset.get("rights_status") != "approved" or asset.get("approval_status") != "approved":
            errors.append(f"asset {asset_id!r} must have approved rights and approval status")
        if asset.get("media_kind") not in MEDIA_KINDS:
            errors.append(f"asset {asset_id!r} has an unsupported media_kind")

    objects = manifest.get("objects")
    if not isinstance(objects, list) or not objects:
        errors.append("campaign manifest must define at least one object")
        return errors
    seen_kinds: set[str] = set()
    creative_asset_ids: set[str] = set()
    for index, obj in enumerate(objects):
        prefix = f"objects[{index}]"
        if not isinstance(obj, dict):
            errors.append(f"{prefix} must be an object")
            continue
        kind = obj.get("kind")
        suffix = ENDPOINT_SUFFIXES.get(kind) if isinstance(kind, str) else None
        endpoint = obj.get("endpoint")
        payload = obj.get("payload")
        if kind not in OBJECT_KINDS:
            errors.append(f"{prefix} kind must be one of {sorted(OBJECT_KINDS)}")
        else:
            seen_kinds.add(kind)
        expected_endpoint = f"{account_id}/{suffix or ''}"
        if endpoint != expected_endpoint:
            errors.append(f"{prefix} endpoint must equal {expected_endpoint!r}")
        if not isinstance(payload, dict):
            errors.append(f"{prefix} payload must be an object")
            continue
        if kind in {"campaign", "adset", "ad"} and payload.get("status") != "PAUSED":
            errors.append(f"{prefix} delivery payload must explicitly request PAUSED")
        elif kind == "creative" and payload.get("status") not in {None, "PAUSED"}:
            errors.append(f"{prefix} payload cannot request a non-paused status")
        if kind == "creative":
            asset_id = obj.get("creative_asset_id")
            asset = by_id.get(asset_id)
            if asset_id not in asset_ids or not asset:
                errors.append(f"{prefix} creative_asset_id must reference a manifest catalog asset")
                continue
            creative_asset_ids.add(asset_id)
            expected = set(asset.get("meta_asset_ids", []))
            actual = set(payload_values(payload, ASSET_REFERENCE_KEYS))
            if actual != expected:
                errors.append(f"{prefix} must reference exactly the catalog Meta asset IDs for {asset_id!r}")
    if "campaign" not in seen_kinds:
        errors.append("campaign manifest must contain a campaign object")
    if set(asset_ids) != creative_asset_ids:
        errors.append("every manifest creative_asset_id must be bound by one creative object")
    errors.extend(validate_gates(workspace, config, manifest, catalog, required_lifecycle_action))
    return errors


def init_workspace(workspace: Path) -> None:
    if workspace.exists() and any(workspace.iterdir()):
        fail("Workspace already exists and is not empty")
    workspace.mkdir(parents=True, exist_ok=True)
    mapping = {
        "workspace.example.json": "workspace.json",
        "campaign-manifest.example.json": "campaign-manifest.json",
        "creative-catalog.example.json": "creative-catalog.json",
        "strategy-lock.md": "strategy-lock.md",
        "strategy-approval.example.json": "strategy-approval.json",
        "creative-bank.md": "creative-bank.md",
        "creative-bank-register.example.json": "creative-bank-register.json",
        "tenant-intake.md": "tenant-intake.md",
        "lifecycle-state.example.json": "lifecycle-state.json",
        "test-selection.example.json": "test-selection.json",
        "production-handoff.md": "production-handoff.md",
        "production-register.example.json": "production-register.json",
        "decision-record.md": "decision-record.md",
        "report-reconciliation.example.json": "reports/reconciliation.example.json",
        "approval.example.json": "approvals/create-paused.json",
        "activation-approval.example.json": "approvals/activate.json",
    }
    for source, destination in mapping.items():
        target = workspace / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATES / source, target)
    for folder in ("reports", "receipts"):
        (workspace / folder).mkdir(exist_ok=True)
    (workspace / "README.md").write_text(
        "# Private Paid Media OS workspace\n\nDo not commit this directory or store secrets in it. Replace every template placeholder and pass offline validation before any Meta request.\n",
        encoding="utf-8",
    )
    print(f"Initialized private workspace: {workspace}")


def install_bundle(destination: Path) -> None:
    if destination.exists():
        fail("Bundle destination already exists")
    destination.mkdir(parents=True)
    for relative in BUNDLE_PATHS:
        source = ROOT / relative
        target = destination / relative
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(source, target)
    (destination / "INSTALL.md").write_text(
        "# Paid Media OS portable bundle\n\nKeep this bundle intact. Start by reading `AGENT_GUIDE.md`, then run `python3 scripts/mos.py init --workspace <private-path>`. The private workspace must never be committed to this bundle.\n",
        encoding="utf-8",
    )
    print(f"Installed complete Paid Media OS bundle: {destination}")


class MetaClient:
    def __init__(self) -> None:
        self.token = os.environ.get("META_ACCESS_TOKEN")
        if not self.token:
            fail("META_ACCESS_TOKEN is required in the process environment")
        version = os.environ.get("META_GRAPH_VERSION", "v21.0")
        self.base_url = f"https://graph.facebook.com/{version}"

    def request(self, method: str, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{endpoint}"
        params = dict(params or {})
        params["access_token"] = self.token
        headers = {"Accept": "application/json"}
        data = None
        if method.upper() == "GET":
            url = f"{url}?{urlencode(params, doseq=True)}"
        else:
            data = urlencode({key: json.dumps(value) if isinstance(value, (dict, list)) else str(value) for key, value in params.items()}).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            with urlopen(Request(url, data=data, headers=headers, method=method.upper()), timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1500]
            fail(f"Meta HTTP {exc.code}: {body}")
        except URLError as exc:
            fail(f"Meta network error: {exc.reason}")
        if not isinstance(payload, dict):
            fail("Meta returned a non-object response")
        if payload.get("error"):
            fail(f"Meta error: {json.dumps(payload['error'], sort_keys=True)}")
        return payload

    def readback(self, object_id: str) -> dict[str, Any]:
        return self.request("GET", object_id, {"fields": "id,name,status,effective_status,configured_status,account_id"})


def load_approval(workspace: Path, approval_rel: str, action: str, account_id: str, manifest_rel: str | None = None, tenant_id: str | None = None) -> dict[str, Any]:
    approval = read_json(private_path(workspace, approval_rel))
    if approval.get("action") != action or approval.get("status") != "APPROVED":
        fail(f"Approval must be APPROVED for action {action}")
    if approval.get("account_id") != account_id:
        fail("Approval account_id does not match workspace")
    if tenant_id is not None and approval.get("tenant_id") != tenant_id:
        fail("Approval tenant_id does not match workspace")
    if iso_time(str(approval.get("expires_at", "")), "expires_at") <= datetime.now(timezone.utc):
        fail("Approval is expired")
    if manifest_rel and approval.get("manifest_path") != manifest_rel:
        fail("Approval manifest_path does not match the controlled manifest")
    if manifest_rel:
        expected_digest = str(approval.get("manifest_sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            fail("Approval needs a valid manifest_sha256")
        actual_digest = json_sha256(read_json(private_path(workspace, manifest_rel)))
        if not hmac.compare_digest(expected_digest, actual_digest):
            fail("Approval manifest_sha256 does not match the controlled manifest")
    return approval


def validate_activation_target(approval: dict[str, Any], object_id: str, readback: dict[str, Any], account_id: str) -> None:
    if approval.get("object_id") != object_id:
        fail("Approval object_id does not match the requested activation target")
    if approval.get("object_kind") not in OBJECT_KINDS:
        fail("Approval object_kind must be a supported object kind")
    if readback.get("id") != object_id:
        fail("Activation readback object ID does not match the requested target")
    if readback.get("account_id") != account_id:
        fail("Activation readback account does not match the approved account")
    if readback.get("effective_status") not in {"PAUSED", "ACTIVE"}:
        fail("Activation target is not currently eligible for activation")


def validate_paused_readback(kind: str, object_id: str, readback: dict[str, Any], account_id: str) -> None:
    if readback.get("id") != object_id:
        fail("Paused creation readback object ID does not match the POST response")
    if readback.get("account_id") != account_id:
        fail("Paused creation readback account does not match the approved account")
    if kind != "creative" and not any(readback.get(field) == "PAUSED" for field in ("status", "effective_status", "configured_status")):
        fail("Paused creation readback did not confirm a PAUSED delivery status")


def validate_activation_result(object_id: str, readback: dict[str, Any], account_id: str) -> None:
    if readback.get("id") != object_id or readback.get("account_id") != account_id:
        fail("Activation readback does not match the approved object and account")
    if not any(readback.get(field) == "ACTIVE" for field in ("status", "effective_status", "configured_status")):
        fail("Activation readback did not confirm ACTIVE status")


def resolve_placeholders(value: Any, ids: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: resolve_placeholders(item, ids) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_placeholders(item, ids) for item in value]
    if isinstance(value, str):
        for token in re.findall(r"\$[A-Z_]+", value):
            if token not in ids:
                fail(f"Unresolved dependency placeholder: {token}")
            value = value.replace(token, ids[token])
    return value


def create_paused(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    errors = validate_workspace(workspace, "create-paused")
    if errors:
        fail("Validation failed:\n- " + "\n- ".join(errors))
    config, manifest, _ = load_workspace(workspace)
    approval = load_approval(workspace, args.approval, "CREATE_PAUSED", config["account_id"], "campaign-manifest.json", config["tenant_id"])
    planned: list[dict[str, Any]] = []
    ids: dict[str, str] = {}
    for obj in manifest["objects"]:
        payload = resolve_placeholders(copy.deepcopy(obj["payload"]), ids)
        if payload.get("status") not in {None, "PAUSED"}:
            fail("Paused creation rejects non-paused statuses")
        planned.append({"kind": obj["kind"], "name": obj.get("name"), "endpoint": obj["endpoint"], "payload": payload})
        ids[{"campaign": "$CAMPAIGN_ID", "adset": "$ADSET_ID", "creative": "$CREATIVE_ID", "ad": "$AD_ID"}[obj["kind"]]] = f"DRY_RUN_{obj['kind'].upper()}_ID"
    if args.dry_run:
        print(json.dumps({"mode": "dry-run", "approval_id": approval["approval_id"], "objects": planned}, indent=2))
        return
    if not args.execute or args.acknowledge != ACK_CREATE:
        fail("Live creation needs --execute and the exact paused-creation acknowledgement")
    receipt_path = workspace / "receipts" / f"create-paused-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    receipt: dict[str, Any] = {"receipt_kind": "create-paused", "attempted_at": now(), "approval_id": approval["approval_id"], "tenant_id": config["tenant_id"], "account_id": config["account_id"], "manifest_sha256": json_sha256(manifest), "objects": []}
    write_json(receipt_path, receipt)
    client = MetaClient()
    ids = {}
    for obj in manifest["objects"]:
        payload = resolve_placeholders(copy.deepcopy(obj["payload"]), ids)
        entry: dict[str, Any] = {"kind": obj["kind"], "name": obj.get("name"), "endpoint": obj["endpoint"], "resolved_payload_sha256": json_sha256(payload), "state": "attempted", "attempted_at": now()}
        receipt["objects"].append(entry)
        write_json(receipt_path, receipt)
        response = client.request("POST", obj["endpoint"], payload)
        entry["response"] = response
        entry["state"] = "post-returned"
        write_json(receipt_path, receipt)
        object_id = response.get("id")
        if not isinstance(object_id, str):
            fail(f"Meta create response for {obj['kind']} lacked an object ID; do not retry blindly")
        entry["object_id"] = object_id
        write_json(receipt_path, receipt)
        readback = client.readback(object_id)
        entry["readback"] = readback
        write_json(receipt_path, receipt)
        validate_paused_readback(obj["kind"], object_id, readback, config["account_id"])
        entry["state"] = "readback-verified"
        entry["verified_at"] = now()
        write_json(receipt_path, receipt)
        ids[{"campaign": "$CAMPAIGN_ID", "adset": "$ADSET_ID", "creative": "$CREATIVE_ID", "ad": "$AD_ID"}[obj["kind"]]] = object_id
    receipt["completed_at"] = now()
    write_json(receipt_path, receipt)
    print(f"Created and read back {len(receipt['objects'])} paused object(s). Receipt: {receipt_path}")


def account_check(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    config = read_json(workspace / "workspace.json")
    if not is_account_id(config.get("account_id")):
        fail("workspace.json account_id must use act_<digits>")
    client = MetaClient()
    payload = client.request("GET", config["account_id"], {"fields": "id,name,account_status,currency,timezone_name"})
    path = workspace / "receipts" / f"account-check-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    write_json(path, {"receipt_kind": "account-check", "collected_at": now(), "account_id": config["account_id"], "data": payload})
    print(f"Exact-account read succeeded. Receipt: {path}")


def collect(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    config = read_json(workspace / "workspace.json")
    since, until = args.since, args.until
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", since) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", until):
        fail("--since and --until must use YYYY-MM-DD")
    if since > until:
        fail("--since must be on or before --until")
    client = MetaClient()
    fields = "campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,spend,impressions,clicks,ctr,cpc,actions,cost_per_action_type"
    payload = client.request("GET", f"{config['account_id']}/insights", {"level": "ad", "time_range": json.dumps({"since": since, "until": until}), "fields": fields, "limit": 500})
    report = {"report_kind": "meta-insights", "tenant_id": config.get("tenant_id"), "account_id": config["account_id"], "timezone": config.get("timezone"), "currency": config.get("currency"), "window": {"since": since, "until": until}, "collected_at": now(), "data": payload.get("data", []), "paging_present": bool(payload.get("paging")), "coverage_status": "unknown"}
    path = workspace / "reports" / f"insights-{since}_{until}.json"
    write_json(path, report)
    print(f"Collected {len(report['data'])} insight row(s). Report: {path}")


def validate_reconciliation(workspace: Path, report_rel: str, reconciliation_rel: str) -> dict[str, Any]:
    config = read_json(workspace / "workspace.json")
    report = read_json(private_path(workspace, report_rel))
    reconciliation = read_json(private_path(workspace, reconciliation_rel))
    if report.get("tenant_id") != config.get("tenant_id") or report.get("account_id") != config.get("account_id"):
        fail("Reconciliation source report tenant_id and account_id must match workspace scope")
    if reconciliation.get("source_report") != report_rel:
        fail("Reconciliation source_report must match the decision report")
    if reconciliation.get("source_report_sha256") != json_sha256(report):
        fail("Reconciliation source_report_sha256 does not match the immutable report")
    if reconciliation.get("tenant_id") != config.get("tenant_id") or reconciliation.get("account_id") != config.get("account_id"):
        fail("Reconciliation tenant_id and account_id must match workspace scope")
    if reconciliation.get("coverage_status") != "complete":
        fail("Reconciliation coverage_status must be complete before a decision")
    if not completed_text(reconciliation.get("method")) or not completed_text(reconciliation.get("reviewed_by")) or not completed_text(reconciliation.get("reviewed_at")):
        fail("Reconciliation requires method, reviewed_by, and reviewed_at")
    if not isinstance(reconciliation.get("evidence_refs"), list) or not reconciliation["evidence_refs"] or any(not completed_text(ref) for ref in reconciliation["evidence_refs"]):
        fail("Reconciliation requires non-empty evidence_refs")
    return reconciliation


def reconcile(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    reconciliation = validate_reconciliation(workspace, args.report, args.reconciliation)
    print(f"Reconciliation is complete and bound to the immutable report. Reviewed by: {reconciliation['reviewed_by']}")


def decide(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    report = read_json(private_path(workspace, args.report))
    reconciliation = validate_reconciliation(workspace, args.report, args.reconciliation)
    rows = report.get("data")
    if not isinstance(rows, list):
        fail("Report data must be a list")
    def number(row: dict[str, Any], key: str) -> float:
        try:
            return float(row.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    spend = sum(number(row, "spend") for row in rows if isinstance(row, dict))
    impressions = sum(number(row, "impressions") for row in rows if isinstance(row, dict))
    clicks = sum(number(row, "clicks") for row in rows if isinstance(row, dict))
    output = {"decision_kind": "recommendation", "created_at": now(), "source_report": args.report, "source_reconciliation": args.reconciliation, "coverage_status": reconciliation["coverage_status"], "summary": {"spend": round(spend, 2), "impressions": int(impressions), "clicks": int(clicks), "ctr_percent": round((clicks / impressions * 100), 3) if impressions else None, "cpc": round(spend / clicks, 4) if clicks else None}, "decision": "defer", "rationale": "No automatic optimization is performed. Reconcile downstream quality and predeclared thresholds before a keep, kill, or remix decision.", "approval_needed_before_external_action": True}
    path = workspace / "reports" / f"decision-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    write_json(path, output)
    print(f"Wrote {output['decision']} recommendation: {path}")


def activate(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    errors = validate_workspace(workspace, "activate")
    if errors:
        fail("Validation failed:\n- " + "\n- ".join(errors))
    config = read_json(workspace / "workspace.json")
    approval = load_approval(workspace, args.approval, "ACTIVATE", config["account_id"], tenant_id=config["tenant_id"])
    if not args.execute or args.acknowledge != ACK_ACTIVATE:
        fail("Activation needs --execute and the exact activation acknowledgement")
    client = MetaClient()
    before = client.readback(args.object_id)
    validate_activation_target(approval, args.object_id, before, config["account_id"])
    path = workspace / "receipts" / f"activate-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    receipt = {"receipt_kind": "activate", "attempted_at": now(), "approval_id": approval["approval_id"], "tenant_id": config["tenant_id"], "account_id": config["account_id"], "object_id": args.object_id, "before": before, "state": "attempted"}
    write_json(path, receipt)
    response = client.request("POST", args.object_id, {"status": "ACTIVE"})
    receipt.update({"response": response, "state": "post-returned"})
    write_json(path, receipt)
    after = client.readback(args.object_id)
    receipt["after"] = after
    write_json(path, receipt)
    validate_activation_result(args.object_id, after, config["account_id"])
    receipt.update({"state": "readback-verified", "completed_at": now()})
    write_json(path, receipt)
    print(f"Activation request sent and read back. Receipt: {path}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a private local workspace")
    init.add_argument("--workspace", required=True)
    init.set_defaults(func=lambda a: init_workspace(Path(a.workspace)))
    bundle = sub.add_parser("install-bundle", help="Copy the complete portable operating contract")
    bundle.add_argument("--destination", required=True)
    bundle.set_defaults(func=lambda a: install_bundle(Path(a.destination)))
    validate = sub.add_parser("validate", help="Validate workspace artifacts without network access")
    validate.add_argument("--workspace", required=True)
    validate.set_defaults(func=lambda a: print("Validation passed") if not (errors := validate_workspace(Path(a.workspace))) else fail("Validation failed:\n- " + "\n- ".join(errors)))
    account = sub.add_parser("account-check", help="Read the exact configured Meta account")
    account.add_argument("--workspace", required=True)
    account.set_defaults(func=account_check)
    collect_p = sub.add_parser("collect", help="Collect a dated immutable Meta insights report")
    collect_p.add_argument("--workspace", required=True)
    collect_p.add_argument("--since", required=True)
    collect_p.add_argument("--until", required=True)
    collect_p.set_defaults(func=collect)
    reconcile_p = sub.add_parser("reconcile", help="Validate a human-reviewed report reconciliation")
    reconcile_p.add_argument("--workspace", required=True)
    reconcile_p.add_argument("--report", required=True)
    reconcile_p.add_argument("--reconciliation", required=True)
    reconcile_p.set_defaults(func=reconcile)
    decide_p = sub.add_parser("decide", help="Write a bounded decision recommendation")
    decide_p.add_argument("--workspace", required=True)
    decide_p.add_argument("--report", required=True)
    decide_p.add_argument("--reconciliation", required=True)
    decide_p.set_defaults(func=decide)
    create = sub.add_parser("create-paused", help="Dry-run or create approved paused objects")
    create.add_argument("--workspace", required=True)
    create.add_argument("--approval", required=True)
    create.add_argument("--dry-run", action="store_true")
    create.add_argument("--execute", action="store_true")
    create.add_argument("--acknowledge")
    create.set_defaults(func=create_paused)
    activate_p = sub.add_parser("activate", help="Activate one object with separate approval")
    activate_p.add_argument("--workspace", required=True)
    activate_p.add_argument("--approval", required=True)
    activate_p.add_argument("--object-id", required=True)
    activate_p.add_argument("--execute", action="store_true")
    activate_p.add_argument("--acknowledge")
    activate_p.set_defaults(func=activate)
    return p


def main() -> int:
    try:
        args = parser().parse_args()
        args.func(args)
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
