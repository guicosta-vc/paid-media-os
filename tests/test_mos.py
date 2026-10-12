import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mos", ROOT / "scripts" / "mos.py")
mos = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mos)
CHECK_SPEC = importlib.util.spec_from_file_location("check_release", ROOT / "scripts" / "check_release.py")
assert CHECK_SPEC is not None and CHECK_SPEC.loader is not None
check_release = importlib.util.module_from_spec(CHECK_SPEC)
CHECK_SPEC.loader.exec_module(check_release)


class FakeMetaClient:
    def __init__(self, account_id: str, fail_after_posts: int | None = None, wrong_readback_account: bool = False):
        self.account_id = account_id
        self.fail_after_posts = fail_after_posts
        self.wrong_readback_account = wrong_readback_account
        self.posts = 0

    def request(self, method, endpoint, params=None):
        if method == "POST":
            self.posts += 1
            if self.fail_after_posts is not None and self.posts > self.fail_after_posts:
                raise ValueError("simulated uncertain POST failure")
            return {"id": f"created-{self.posts}"}
        object_id = endpoint
        return {
            "id": object_id,
            "account_id": "act_" + ("1" * 15) if self.wrong_readback_account else self.account_id,
            "status": "PAUSED",
            "effective_status": "PAUSED",
            "configured_status": "PAUSED",
        }

    def readback(self, object_id):
        return self.request("GET", object_id)


class MarketingOSTest(unittest.TestCase):
    @staticmethod
    def synthetic_account_id() -> str:
        return "act_" + ("0" * 15)

    @staticmethod
    def manifest_digest(manifest: dict) -> str:
        payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data), encoding="utf-8")

    def make_workspace(self) -> Path:
        temp = Path(tempfile.mkdtemp())
        workspace = temp / "workspace"
        mos.init_workspace(workspace)
        config = json.loads((workspace / "workspace.json").read_text())
        manifest = json.loads((workspace / "campaign-manifest.json").read_text())
        catalog = json.loads((workspace / "creative-catalog.json").read_text())
        account_id = self.synthetic_account_id()
        tenant_id = "tenant-test"
        config.update({
            "account_id": account_id,
            "tenant_id": tenant_id,
            "strategy_lock_version": "strategy-v1",
        })
        manifest.update({"account_id": account_id, "tenant_id": tenant_id})
        manifest["creative_asset_ids"] = [
            "EXAMPLE-TOF-PAIN-01-V01", "EXAMPLE-TOF-PAIN-02-V01", "EXAMPLE-TOF-PAIN-03-V01",
        ]
        endpoint_suffixes = {"campaign": "campaigns", "adset": "adsets", "creative": "adcreatives", "ad": "ads"}
        for obj in manifest["objects"]:
            obj["endpoint"] = f"{account_id}/{endpoint_suffixes[obj['kind']]}"
        manifest["objects"][2]["creative_asset_id"] = "EXAMPLE-TOF-PAIN-01-V01"
        manifest["objects"][2]["payload"]["object_story_spec"]["page_id"] = "TEST_PAGE_ID"
        manifest["objects"][2]["payload"]["object_story_spec"]["link_data"]["image_hash"] = "image-hash-example-01"
        for index in range(2, 4):
            manifest["objects"].insert(-1, {
                "kind": "creative",
                "name": f"Example | Asset {index} | Paused",
                "creative_asset_id": f"EXAMPLE-TOF-PAIN-0{index}-V01",
                "endpoint": f"{account_id}/adcreatives",
                "payload": {
                    "name": f"Example | Asset {index} | Paused",
                    "object_story_spec": {
                        "page_id": "TEST_PAGE_ID",
                        "link_data": {
                            "link": "https://example.com/book",
                            "message": "Approved test copy.",
                            "name": "Approved test headline.",
                            "image_hash": f"image-hash-example-0{index}",
                        },
                    },
                },
            })
        catalog["assets"] = [
            {
                "asset_id": f"EXAMPLE-TOF-PAIN-0{index}-V01",
                "creative_concept_id": f"PAIN-0{index}",
                "media_kind": "static",
                "format": "1080x1350",
                "copy_version": "v1",
                "asset_sha256": chr(96 + index) * 64,
                "rights_status": "approved",
                "approval_status": "approved",
                "meta_asset_ids": [f"image-hash-example-0{index}"],
                "source_path_or_url": "private-approved-storage-reference",
            }
            for index in range(1, 4)
        ]
        self.write_json(workspace / "workspace.json", config)
        self.write_json(workspace / "campaign-manifest.json", manifest)
        self.write_json(workspace / "creative-catalog.json", catalog)
        self.write_json(workspace / "lifecycle-state.json", {
            "schema_version": "1.0",
            "tenant_id": tenant_id,
            "account_id": account_id,
            "state": "ready-for-paused-build",
            "tenant_intake_status": "APPROVED",
            "accountable_owner": "named-owner",
            "tracking_evidence_ref": "private-tracking-evidence",
            "required_evidence": ["private-tracking-evidence"],
            "blockers": [],
            "next_permitted_action": "create-paused",
            "updated_at": "2026-01-01T00:00:00Z",
        })
        self.write_json(workspace / "strategy-approval.json", {
            "schema_version": "1.0",
            "tenant_id": tenant_id,
            "strategy_lock_path": "strategy-lock.md",
            "strategy_lock_version": "strategy-v1",
            "status": "APPROVED",
            "approved_by": "named-owner",
            "approved_at": "2026-01-01T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
        })
        concept_ids = ["PAIN-01", "PAIN-02", "PAIN-03"] + [f"CONCEPT-{index:02d}" for index in range(4, 51)]
        self.write_json(workspace / "creative-bank-register.json", {
            "schema_version": "1.0",
            "tenant_id": tenant_id,
            "strategy_lock_version": "strategy-v1",
            "concepts": [
                {"concept_id": concept_id, "eligibility": "eligible" if concept_id.startswith("PAIN-") else "rejected"}
                for concept_id in concept_ids
            ],
            "reviewed_by": "named-owner",
            "reviewed_at": "2026-01-01T00:00:00Z",
        })
        self.write_json(workspace / "test-selection.json", {
            "schema_version": "1.0",
            "tenant_id": tenant_id,
            "strategy_lock_version": "strategy-v1",
            "selected_concept_ids": ["PAIN-01", "PAIN-02", "PAIN-03"],
            "selection_reason": "Materially distinct hypotheses.",
            "rejected_near_misses": [],
            "approved_by": "named-owner",
            "approved_at": "2026-01-01T00:00:00Z",
        })
        self.write_json(workspace / "production-register.json", {
            "schema_version": "1.0",
            "tenant_id": tenant_id,
            "strategy_lock_version": "strategy-v1",
            "handoffs": [
                {"concept_id": f"PAIN-0{index}", "asset_id": f"EXAMPLE-TOF-PAIN-0{index}-V01", "status": "APPROVED"}
                for index in range(1, 4)
            ],
            "approved_by": "named-owner",
            "approved_at": "2026-01-01T00:00:00Z",
        })
        self.addCleanup(shutil.rmtree, temp)
        return workspace

    def create_approval(self, workspace: Path) -> Path:
        manifest = json.loads((workspace / "campaign-manifest.json").read_text())
        approval = {
            "approval_id": "approved-manifest",
            "action": "CREATE_PAUSED",
            "status": "APPROVED",
            "tenant_id": "tenant-test",
            "account_id": self.synthetic_account_id(),
            "manifest_path": "campaign-manifest.json",
            "manifest_sha256": self.manifest_digest(manifest),
            "expires_at": "2099-01-01T00:00:00Z",
        }
        path = workspace / "approvals" / "approved.json"
        self.write_json(path, approval)
        return path

    def test_initialized_workspace_fails_until_catalog_is_real(self):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        workspace = temp / "workspace"
        mos.init_workspace(workspace)
        self.assertTrue((workspace / "approvals" / "create-paused.json").is_file())
        self.assertTrue((workspace / "approvals" / "activate.json").is_file())
        errors = mos.validate_workspace(workspace)
        self.assertTrue(errors)
        self.assertIn("needs a real asset_sha256", "\n".join(errors))

    def test_valid_workspace_passes(self):
        self.assertEqual(mos.validate_workspace(self.make_workspace()), [])

    def test_active_status_is_rejected(self):
        workspace = self.make_workspace()
        manifest_path = workspace / "campaign-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["objects"][0]["payload"]["status"] = "ACTIVE"
        self.write_json(manifest_path, manifest)
        self.assertIn("must explicitly request PAUSED", "\n".join(mos.validate_workspace(workspace)))

    def test_delivery_object_requires_explicit_paused_status(self):
        workspace = self.make_workspace()
        manifest_path = workspace / "campaign-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["objects"][0]["payload"].pop("status")
        self.write_json(manifest_path, manifest)
        self.assertIn("must explicitly request PAUSED", "\n".join(mos.validate_workspace(workspace)))

    def test_cross_kind_endpoint_is_rejected(self):
        workspace = self.make_workspace()
        manifest_path = workspace / "campaign-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["objects"][0]["endpoint"] = f"{self.synthetic_account_id()}/ads"
        self.write_json(manifest_path, manifest)
        self.assertIn("endpoint must equal", "\n".join(mos.validate_workspace(workspace)))

    def test_cross_tenant_manifest_is_rejected(self):
        workspace = self.make_workspace()
        config_path = workspace / "workspace.json"
        manifest_path = workspace / "campaign-manifest.json"
        config = json.loads(config_path.read_text())
        manifest = json.loads(manifest_path.read_text())
        config["tenant_id"] = "tenant-a"
        manifest["tenant_id"] = "tenant-b"
        self.write_json(config_path, config)
        self.write_json(manifest_path, manifest)
        self.assertIn("tenant_id must match", "\n".join(mos.validate_workspace(workspace)))

    def test_creative_payload_must_bind_catalog_meta_asset(self):
        workspace = self.make_workspace()
        manifest_path = workspace / "campaign-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["objects"][2]["payload"]["object_story_spec"]["link_data"]["image_hash"] = "unapproved-image-hash"
        self.write_json(manifest_path, manifest)
        self.assertIn("must reference exactly the catalog Meta asset IDs", "\n".join(mos.validate_workspace(workspace)))

    def test_creative_payload_rejects_unapproved_cross_media_reference(self):
        workspace = self.make_workspace()
        manifest_path = workspace / "campaign-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["objects"][2]["payload"]["object_story_spec"]["link_data"]["video_id"] = "unapproved-video-id"
        self.write_json(manifest_path, manifest)
        self.assertIn("must reference exactly the catalog Meta asset IDs", "\n".join(mos.validate_workspace(workspace)))

    def test_manifest_assets_must_match_selected_production_assets(self):
        workspace = self.make_workspace()
        manifest_path = workspace / "campaign-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["creative_asset_ids"] = ["EXAMPLE-TOF-PAIN-01-V01"]
        manifest["objects"] = [obj for obj in manifest["objects"] if obj.get("creative_asset_id") != "EXAMPLE-TOF-PAIN-02-V01" and obj.get("creative_asset_id") != "EXAMPLE-TOF-PAIN-03-V01"]
        self.write_json(manifest_path, manifest)
        self.assertIn("must exactly match selected production assets", "\n".join(mos.validate_workspace(workspace)))

    def test_missing_required_gate_is_rejected(self):
        workspace = self.make_workspace()
        (workspace / "strategy-approval.json").unlink()
        self.assertIn("Missing file", "\n".join(mos.validate_workspace(workspace)))

    def test_lifecycle_requires_exact_next_action_and_empty_blockers_list(self):
        workspace = self.make_workspace()
        path = workspace / "lifecycle-state.json"
        lifecycle = json.loads(path.read_text())
        lifecycle["next_permitted_action"] = "collect-report"
        lifecycle["blockers"] = None
        self.write_json(path, lifecycle)
        errors = "\n".join(mos.validate_workspace(workspace))
        self.assertIn("next_permitted_action must be create-paused", errors)
        self.assertIn("blockers must be a present empty list", errors)

    def test_test_cell_must_have_three_to_five_eligible_concepts(self):
        workspace = self.make_workspace()
        path = workspace / "test-selection.json"
        selection = json.loads(path.read_text())
        selection["selected_concept_ids"] = ["PAIN-01", "CONCEPT-04"]
        self.write_json(path, selection)
        self.assertIn("exactly 3 to 5", "\n".join(mos.validate_workspace(workspace)))

    def test_placeholder_resolution_requires_dependency(self):
        with self.assertRaisesRegex(ValueError, "Unresolved dependency"):
            mos.resolve_placeholders({"campaign_id": "$CAMPAIGN_ID"}, {})

    def test_approval_rejects_manifest_mutation_after_approval(self):
        workspace = self.make_workspace()
        approval_path = self.create_approval(workspace)
        manifest_path = workspace / "campaign-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["daily_budget_minor_units"] = 999999
        self.write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "manifest_sha256"):
            mos.load_approval(workspace, str(approval_path.relative_to(workspace)), "CREATE_PAUSED", self.synthetic_account_id(), "campaign-manifest.json", "tenant-test")

    def test_activation_target_requires_approval_bound_object_and_account(self):
        approval = {"object_id": "campaign-test", "object_kind": "campaign"}
        with self.assertRaisesRegex(ValueError, "account"):
            mos.validate_activation_target(approval, "campaign-test", {"id": "campaign-test", "account_id": "act_" + ("1" * 15)}, self.synthetic_account_id())

    def test_activation_rejects_placeholder_tenant_before_any_api_client(self):
        workspace = self.make_workspace()
        config_path = workspace / "workspace.json"
        manifest_path = workspace / "campaign-manifest.json"
        config = json.loads(config_path.read_text())
        manifest = json.loads(manifest_path.read_text())
        config["tenant_id"] = "REPLACE_WITH_TENANT_ID"
        manifest["tenant_id"] = "REPLACE_WITH_TENANT_ID"
        self.write_json(config_path, config)
        self.write_json(manifest_path, manifest)
        approval = {
            "approval_id": "placeholder-tenant", "action": "ACTIVATE", "status": "APPROVED",
            "tenant_id": "REPLACE_WITH_TENANT_ID", "account_id": self.synthetic_account_id(),
            "object_id": "campaign-test", "object_kind": "campaign", "expires_at": "2099-01-01T00:00:00Z",
        }
        self.write_json(workspace / "approvals" / "activate.json", approval)
        args = SimpleNamespace(workspace=str(workspace), approval="approvals/activate.json", object_id="campaign-test", execute=True, acknowledge=mos.ACK_ACTIVATE)
        with self.assertRaisesRegex(ValueError, "tenant"):
            mos.activate(args)

    def test_activation_requires_lifecycle_action_before_any_api_client(self):
        workspace = self.make_workspace()
        approval = {
            "approval_id": "activation-lifecycle", "action": "ACTIVATE", "status": "APPROVED",
            "tenant_id": "tenant-test", "account_id": self.synthetic_account_id(),
            "object_id": "campaign-test", "object_kind": "campaign", "expires_at": "2099-01-01T00:00:00Z",
        }
        self.write_json(workspace / "approvals" / "activate.json", approval)
        original_client = mos.MetaClient
        class MustNotInstantiate:
            def __init__(self):
                raise AssertionError("MetaClient must not be instantiated")
        mos.MetaClient = MustNotInstantiate
        self.addCleanup(setattr, mos, "MetaClient", original_client)
        args = SimpleNamespace(workspace=str(workspace), approval="approvals/activate.json", object_id="campaign-test", execute=True, acknowledge=mos.ACK_ACTIVATE)
        with self.assertRaisesRegex(ValueError, "next_permitted_action must be activate"):
            mos.activate(args)

    def test_create_paused_persists_partial_receipt_after_later_write_failure(self):
        workspace = self.make_workspace()
        self.create_approval(workspace)
        original_client = mos.MetaClient
        mos.MetaClient = lambda: FakeMetaClient(self.synthetic_account_id(), fail_after_posts=1)
        self.addCleanup(setattr, mos, "MetaClient", original_client)
        args = SimpleNamespace(workspace=str(workspace), approval="approvals/approved.json", dry_run=False, execute=True, acknowledge=mos.ACK_CREATE)
        with self.assertRaisesRegex(ValueError, "simulated uncertain POST failure"):
            mos.create_paused(args)
        receipts = list((workspace / "receipts").glob("create-paused-*.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text())
        self.assertEqual(receipt["objects"][0]["state"], "readback-verified")
        self.assertEqual(receipt["objects"][1]["state"], "attempted")

    def test_create_paused_stops_on_readback_scope_mismatch(self):
        workspace = self.make_workspace()
        self.create_approval(workspace)
        original_client = mos.MetaClient
        mos.MetaClient = lambda: FakeMetaClient(self.synthetic_account_id(), wrong_readback_account=True)
        self.addCleanup(setattr, mos, "MetaClient", original_client)
        args = SimpleNamespace(workspace=str(workspace), approval="approvals/approved.json", dry_run=False, execute=True, acknowledge=mos.ACK_CREATE)
        with self.assertRaisesRegex(ValueError, "readback account"):
            mos.create_paused(args)
        receipt = json.loads(next((workspace / "receipts").glob("create-paused-*.json")).read_text())
        self.assertEqual(receipt["objects"][0]["state"], "post-returned")
        self.assertIn("readback", receipt["objects"][0])

    def test_reconciliation_allows_decision_without_mutating_raw_report(self):
        workspace = self.make_workspace()
        report_path = workspace / "reports" / "insights.json"
        report = {
            "report_kind": "meta-insights", "tenant_id": "tenant-test", "account_id": self.synthetic_account_id(),
            "data": [{"spend": "10", "impressions": "100", "clicks": "5"}], "coverage_status": "unknown",
        }
        self.write_json(report_path, report)
        reconciliation = {
            "schema_version": "1.0", "tenant_id": "tenant-test", "account_id": self.synthetic_account_id(),
            "source_report": "reports/insights.json", "source_report_sha256": mos.json_sha256(report),
            "coverage_status": "complete", "method": "Paging and time-window reconciliation completed.",
            "evidence_refs": ["private-reconciliation-record"], "reviewed_by": "named-owner", "reviewed_at": "2026-01-01T00:00:00Z",
        }
        self.write_json(workspace / "reports" / "reconciliation.json", reconciliation)
        self.assertEqual(mos.validate_reconciliation(workspace, "reports/insights.json", "reports/reconciliation.json")["coverage_status"], "complete")
        self.assertEqual(json.loads(report_path.read_text())["coverage_status"], "unknown")

    def test_reconciliation_rejects_foreign_source_report_scope(self):
        workspace = self.make_workspace()
        report = {"report_kind": "meta-insights", "tenant_id": "tenant-other", "account_id": self.synthetic_account_id(), "data": []}
        self.write_json(workspace / "reports" / "insights.json", report)
        reconciliation = {
            "tenant_id": "tenant-test", "account_id": self.synthetic_account_id(), "source_report": "reports/insights.json",
            "source_report_sha256": mos.json_sha256(report), "coverage_status": "complete", "method": "reviewed",
            "evidence_refs": ["private-record"], "reviewed_by": "named-owner", "reviewed_at": "2026-01-01T00:00:00Z",
        }
        self.write_json(workspace / "reports" / "reconciliation.json", reconciliation)
        with self.assertRaisesRegex(ValueError, "source report tenant_id and account_id"):
            mos.validate_reconciliation(workspace, "reports/insights.json", "reports/reconciliation.json")

    def test_release_scanner_reads_staged_blob_not_clean_worktree(self):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        subprocess.run(["git", "init", "-q", str(temp)], check=True)
        tracked = temp / "tracked.txt"
        tracked.write_text("act_" + ("7" * 12), encoding="utf-8")
        subprocess.run(["git", "-C", str(temp), "add", "tracked.txt"], check=True)
        tracked.write_text("clean working tree", encoding="utf-8")
        problems = check_release.scan(temp)
        self.assertTrue(any("tracked.txt" in problem for problem in problems))

    def test_release_contract_reads_staged_documents_not_clean_worktree(self):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        subprocess.run(["git", "init", "-q", str(temp)], check=True)
        (temp / "LICENSE").write_text("not a BUSL license\n", encoding="utf-8")
        (temp / "NOTICE").write_text("\n".join(check_release.REQUIRED_NOTICE_PREFIXES), encoding="utf-8")
        (temp / "README.md").write_text("source-available\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(temp), "add", "LICENSE", "NOTICE", "README.md"], check=True)
        (temp / "LICENSE").write_text("Business Source License 1.1\n", encoding="utf-8")
        self.assertTrue(any("LICENSE must" in problem for problem in check_release.release_contract_problems(temp)))

    def test_release_scanner_includes_untracked_file_planned_for_public_push(self):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        subprocess.run(["git", "init", "-q", str(temp)], check=True)
        (temp / "untracked.txt").write_text("act_" + ("9" * 12), encoding="utf-8")
        self.assertTrue(any("untracked.txt" in problem for problem in check_release.scan(temp)))

    def test_portable_bundle_contains_complete_operating_contract(self):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        destination = temp / "bundle"
        mos.install_bundle(destination)
        for relative in ["AGENT_GUIDE.md", "README.md", "SECURITY.md", "COMMERCIAL-LICENSE.md", "scripts/mos.py", "templates/workspace.example.json", "skills/marketing-os/SKILL.md", "tests/test_mos.py"]:
            self.assertTrue((destination / relative).is_file(), relative)
        release_scan = subprocess.run(["python3", "scripts/check_release.py", "--release"], cwd=destination, capture_output=True, text=True)
        self.assertEqual(release_scan.returncode, 0, release_scan.stderr + release_scan.stdout)
        with self.assertRaisesRegex(ValueError, "already exists"):
            mos.install_bundle(destination)

    def test_release_contract_uses_business_source_license(self):
        self.assertEqual(check_release.LICENSE_TITLE, "Business Source License 1.1")
        self.assertTrue((ROOT / "LICENSE").read_text(encoding="utf-8").startswith("Business Source License 1.1"))

    def test_private_path_rejects_escape(self):
        workspace = self.make_workspace()
        with self.assertRaisesRegex(ValueError, "inside the workspace"):
            mos.private_path(workspace, "../outside.json")


if __name__ == "__main__":
    unittest.main()
