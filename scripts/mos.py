#!/usr/bin/env python3
"""Paid Media OS: local artifacts, safe Meta reads, gated Meta writes."""
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
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_sha256(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def private_path(workspace: Path, relative: str) -> Path:
    candidate = (workspace / relative).resolve()
    root = workspace.resolve()
    if candidate != root and root not in candidate.parents:
        fail("Path must stay inside the workspace")
    return candidate


def load_workspace(workspace: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = read_json(workspace / "workspace.json")
    manifest = read_json(workspace / "campaign-manifest.json")
    catalog = read_json(workspace / "creative-catalog.json")
    return config, manifest, catalog


def iso_time(value: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        fail(f"{field} must be ISO 8601")


def is_account_id(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"act_[0-9]+", value) is not None


def validate_workspace(workspace: Path) -> list[str]:
    errors: list[str] = []
    try:
        config, manifest, catalog = load_workspace(workspace)
    except ValueError as exc:
        return [str(exc)]
    tenant_id = config.get("tenant_id")
    if not isinstance(tenant_id, str) or not tenant_id or tenant_id.startswith("REPLACE_"):
        errors.append("workspace.json tenant_id must be a completed tenant identifier")
    if manifest.get("tenant_id") != tenant_id:
        errors.append("campaign manifest tenant_id must match workspace tenant_id")
    account_id = config.get("account_id")
    if not is_account_id(account_id):
        errors.append("workspace.json account_id must use act_<digits>")
    if manifest.get("account_id") != account_id:
        errors.append("campaign manifest account_id must match workspace account_id")
    if manifest.get("target_status") != "PAUSED":
        errors.append("campaign manifest target_status must be PAUSED")
    asset_ids = manifest.get("creative_asset_ids")
    if not isinstance(asset_ids, list) or not asset_ids:
        errors.append("campaign manifest must list creative_asset_ids")
    assets = catalog.get("assets")
    if not isinstance(assets, list):
        errors.append("creative catalog assets must be a list")
        assets = []
    by_id = {item.get("asset_id"): item for item in assets if isinstance(item, dict)}
    for asset_id in asset_ids or []:
        asset = by_id.get(asset_id)
        if not asset:
            errors.append(f"manifest asset {asset_id!r} is missing from the catalog")
            continue
        for field in ("asset_sha256", "rights_status", "approval_status", "meta_asset_id"):
            if not asset.get(field) or str(asset.get(field)).startswith("REPLACE_"):
                errors.append(f"asset {asset_id!r} needs a real {field}")
        if asset.get("rights_status") != "approved" or asset.get("approval_status") != "approved":
            errors.append(f"asset {asset_id!r} must have approved rights and approval status")
        if asset.get("media_kind") not in {"static", "video", "carousel"}:
            errors.append(f"asset {asset_id!r} has an unsupported media_kind")
    objects = manifest.get("objects")
    if not isinstance(objects, list) or not objects:
        errors.append("campaign manifest must define at least one object")
        return errors
    seen_kinds: set[str] = set()
    for index, obj in enumerate(objects):
        prefix = f"objects[{index}]"
        if not isinstance(obj, dict):
            errors.append(f"{prefix} must be an object")
            continue
        kind = obj.get("kind")
        kind_suffix = ENDPOINT_SUFFIXES.get(kind) if isinstance(kind, str) else None
        endpoint = obj.get("endpoint")
        payload = obj.get("payload")
        if kind not in OBJECT_KINDS:
            errors.append(f"{prefix} kind must be one of {sorted(OBJECT_KINDS)}")
        else:
            seen_kinds.add(kind)
        expected_endpoint = f"{account_id}/{kind_suffix or ''}"
        if not isinstance(endpoint, str) or endpoint != expected_endpoint:
            errors.append(f"{prefix} endpoint must equal {expected_endpoint!r}")
        if not isinstance(payload, dict):
            errors.append(f"{prefix} payload must be an object")
        elif payload.get("status") not in {None, "PAUSED"}:
            errors.append(f"{prefix} payload cannot request a non-paused status")
    if "campaign" not in seen_kinds:
        errors.append("campaign manifest must contain a campaign object")
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
        "creative-bank.md": "creative-bank.md",
        "tenant-intake.md": "tenant-intake.md",
        "lifecycle-state.example.json": "lifecycle-state.json",
        "test-selection.example.json": "test-selection.json",
        "production-handoff.md": "production-handoff.md",
        "decision-record.md": "decision-record.md",
    }
    for source, destination in mapping.items():
        shutil.copyfile(TEMPLATES / source, workspace / destination)
    (workspace / "approvals").mkdir()
    (workspace / "reports").mkdir()
    (workspace / "receipts").mkdir()
    (workspace / "README.md").write_text(
        "# Private Paid Media OS workspace\n\nDo not commit this directory or store secrets in it.\n",
        encoding="utf-8",
    )
    print(f"Initialized private workspace: {workspace}")


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
            data = urlencode({k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in params.items()}).encode()
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


def resolve_placeholders(value: Any, ids: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: resolve_placeholders(item, ids) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_placeholders(item, ids) for item in value]
    if isinstance(value, str):
        unresolved = re.findall(r"\$[A-Z_]+", value)
        for token in unresolved:
            if token not in ids:
                fail(f"Unresolved dependency placeholder: {token}")
            value = value.replace(token, ids[token])
    return value


def create_paused(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    errors = validate_workspace(workspace)
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
        placeholder = {"campaign": "$CAMPAIGN_ID", "adset": "$ADSET_ID", "creative": "$CREATIVE_ID", "ad": "$AD_ID"}[obj["kind"]]
        ids[placeholder] = f"DRY_RUN_{obj['kind'].upper()}_ID"
    if args.dry_run:
        print(json.dumps({"mode": "dry-run", "approval_id": approval["approval_id"], "objects": planned}, indent=2))
        return
    if not args.execute or args.acknowledge != ACK_CREATE:
        fail("Live creation needs --execute and the exact paused-creation acknowledgement")
    client = MetaClient()
    receipt: dict[str, Any] = {"receipt_kind": "create-paused", "attempted_at": now(), "approval_id": approval["approval_id"], "account_id": config["account_id"], "objects": []}
    ids = {}
    for obj in manifest["objects"]:
        payload = resolve_placeholders(copy.deepcopy(obj["payload"]), ids)
        response = client.request("POST", obj["endpoint"], payload)
        object_id = response.get("id")
        if not isinstance(object_id, str):
            fail(f"Meta create response for {obj['kind']} lacked an object ID; do not retry blindly")
        readback = client.readback(object_id)
        receipt["objects"].append({"kind": obj["kind"], "name": obj.get("name"), "object_id": object_id, "readback": readback})
        placeholder = {"campaign": "$CAMPAIGN_ID", "adset": "$ADSET_ID", "creative": "$CREATIVE_ID", "ad": "$AD_ID"}[obj["kind"]]
        ids[placeholder] = object_id
    receipt["completed_at"] = now()
    receipt_path = workspace / "receipts" / f"create-paused-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    write_json(receipt_path, receipt)
    print(f"Created and read back {len(receipt['objects'])} paused object(s). Receipt: {receipt_path}")


def account_check(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    config = read_json(workspace / "workspace.json")
    if not is_account_id(config.get("account_id")):
        fail("workspace.json account_id must use act_<digits>")
    client = MetaClient()
    payload = client.request("GET", config["account_id"], {"fields": "id,name,account_status,currency,timezone_name"})
    receipt = {"receipt_kind": "account-check", "collected_at": now(), "account_id": config["account_id"], "data": payload}
    path = workspace / "receipts" / f"account-check-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    write_json(path, receipt)
    print(f"Exact-account read succeeded. Receipt: {path}")


def collect(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    config = read_json(workspace / "workspace.json")
    since, until = args.since, args.until
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", since) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", until):
        fail("--since and --until must use YYYY-MM-DD")
    client = MetaClient()
    fields = "campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,spend,impressions,clicks,ctr,cpc,actions,cost_per_action_type"
    payload = client.request("GET", f"{config['account_id']}/insights", {"level": "ad", "time_range": json.dumps({"since": since, "until": until}), "fields": fields, "limit": 500})
    report = {"report_kind": "meta-insights", "account_id": config["account_id"], "timezone": config.get("timezone"), "currency": config.get("currency"), "window": {"since": since, "until": until}, "collected_at": now(), "data": payload.get("data", []), "paging_present": bool(payload.get("paging")), "coverage_status": "unknown"}
    path = workspace / "reports" / f"insights-{since}_{until}.json"
    write_json(path, report)
    print(f"Collected {len(report['data'])} insight row(s). Report: {path}")


def decide(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    report = read_json(private_path(workspace, args.report))
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
    decision = "insufficient-data" if report.get("coverage_status") != "complete" else "defer"
    output = {"decision_kind": "recommendation", "created_at": now(), "source_report": args.report, "coverage_status": report.get("coverage_status"), "summary": {"spend": round(spend, 2), "impressions": int(impressions), "clicks": int(clicks), "ctr_percent": round((clicks / impressions * 100), 3) if impressions else None, "cpc": round(spend / clicks, 4) if clicks else None}, "decision": decision, "rationale": "No automatic optimization is performed. Reconcile downstream quality and predeclared thresholds before a keep, kill, or remix decision.", "approval_needed_before_external_action": True}
    path = workspace / "reports" / f"decision-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    write_json(path, output)
    print(f"Wrote {decision} recommendation: {path}")


def activate(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace)
    errors = validate_workspace(workspace)
    if errors:
        fail("Validation failed:\n- " + "\n- ".join(errors))
    config = read_json(workspace / "workspace.json")
    approval = load_approval(workspace, args.approval, "ACTIVATE", config["account_id"], tenant_id=config["tenant_id"])
    if not args.execute or args.acknowledge != ACK_ACTIVATE:
        fail("Activation needs --execute and the exact activation acknowledgement")
    client = MetaClient()
    before = client.readback(args.object_id)
    validate_activation_target(approval, args.object_id, before, config["account_id"])
    response = client.request("POST", args.object_id, {"status": "ACTIVE"})
    after = client.readback(args.object_id)
    receipt = {"receipt_kind": "activate", "attempted_at": now(), "approval_id": approval["approval_id"], "account_id": config["account_id"], "object_id": args.object_id, "before": before, "response": response, "after": after}
    path = workspace / "receipts" / f"activate-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    write_json(path, receipt)
    print(f"Activation request sent and read back. Receipt: {path}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a private local workspace")
    init.add_argument("--workspace", required=True)
    init.set_defaults(func=lambda a: init_workspace(Path(a.workspace)))
    validate = sub.add_parser("validate", help="Validate workspace artifacts without network access")
    validate.add_argument("--workspace", required=True)
    validate.set_defaults(func=lambda a: print("Validation passed") if not (errors := validate_workspace(Path(a.workspace))) else fail("Validation failed:\n- " + "\n- ".join(errors)))
    account = sub.add_parser("account-check", help="Read the exact configured Meta account")
    account.add_argument("--workspace", required=True)
    account.set_defaults(func=account_check)
    collect_p = sub.add_parser("collect", help="Collect a dated Meta insights report")
    collect_p.add_argument("--workspace", required=True)
    collect_p.add_argument("--since", required=True)
    collect_p.add_argument("--until", required=True)
    collect_p.set_defaults(func=collect)
    decide_p = sub.add_parser("decide", help="Write a bounded decision recommendation")
    decide_p.add_argument("--workspace", required=True)
    decide_p.add_argument("--report", required=True)
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
