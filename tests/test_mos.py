import importlib.util
import hashlib
import json
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mos", ROOT / "scripts" / "mos.py")
mos = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mos)
CHECK_SPEC = importlib.util.spec_from_file_location("check_release", ROOT / "scripts" / "check_release.py")
assert CHECK_SPEC is not None and CHECK_SPEC.loader is not None
check_release = importlib.util.module_from_spec(CHECK_SPEC)
CHECK_SPEC.loader.exec_module(check_release)


class MarketingOSTest(unittest.TestCase):
    @staticmethod
    def synthetic_account_id() -> str:
        return "act_" + ("0" * 15)

    @staticmethod
    def manifest_digest(manifest: dict) -> str:
        payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def make_workspace(self) -> Path:
        temp = Path(tempfile.mkdtemp())
        workspace = temp / "workspace"
        mos.init_workspace(workspace)
        config = json.loads((workspace / "workspace.json").read_text())
        manifest = json.loads((workspace / "campaign-manifest.json").read_text())
        catalog = json.loads((workspace / "creative-catalog.json").read_text())
        account_id = self.synthetic_account_id()
        config["account_id"] = account_id
        config["tenant_id"] = "tenant-test"
        manifest["account_id"] = account_id
        manifest["tenant_id"] = "tenant-test"
        endpoint_suffixes = {"campaign": "campaigns", "adset": "adsets", "creative": "adcreatives", "ad": "ads"}
        for obj in manifest["objects"]:
            obj["endpoint"] = f"{account_id}/{endpoint_suffixes[obj['kind']]}"
        catalog["assets"][0].update({
            "asset_sha256": "a" * 64,
            "rights_status": "approved",
            "approval_status": "approved",
            "meta_asset_id": "image-hash-example",
        })
        manifest["objects"][2]["payload"]["object_story_spec"]["page_id"] = "TEST_PAGE_ID"
        manifest["objects"][2]["payload"]["object_story_spec"]["link_data"]["image_hash"] = "image-hash-example"
        (workspace / "workspace.json").write_text(json.dumps(config))
        (workspace / "campaign-manifest.json").write_text(json.dumps(manifest))
        (workspace / "creative-catalog.json").write_text(json.dumps(catalog))
        self.addCleanup(shutil.rmtree, temp)
        return workspace

    def test_initialized_workspace_fails_until_catalog_is_real(self):
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        workspace = temp / "workspace"
        mos.init_workspace(workspace)
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
        manifest_path.write_text(json.dumps(manifest))
        self.assertIn("non-paused status", "\n".join(mos.validate_workspace(workspace)))

    def test_cross_kind_endpoint_is_rejected(self):
        workspace = self.make_workspace()
        manifest_path = workspace / "campaign-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["objects"][0]["endpoint"] = f"{self.synthetic_account_id()}/ads"
        manifest_path.write_text(json.dumps(manifest))
        self.assertIn("endpoint must equal", "\n".join(mos.validate_workspace(workspace)))

    def test_cross_tenant_manifest_is_rejected(self):
        workspace = self.make_workspace()
        config_path = workspace / "workspace.json"
        manifest_path = workspace / "campaign-manifest.json"
        config = json.loads(config_path.read_text())
        manifest = json.loads(manifest_path.read_text())
        config["tenant_id"] = "tenant-a"
        manifest["tenant_id"] = "tenant-b"
        config_path.write_text(json.dumps(config))
        manifest_path.write_text(json.dumps(manifest))
        self.assertIn("tenant_id must match", "\n".join(mos.validate_workspace(workspace)))

    def test_placeholder_resolution_requires_dependency(self):
        with self.assertRaisesRegex(ValueError, "Unresolved dependency"):
            mos.resolve_placeholders({"campaign_id": "$CAMPAIGN_ID"}, {})

    def test_approval_rejects_expiry_and_account_mismatch(self):
        workspace = self.make_workspace()
        approval = {
            "approval_id": "x", "action": "CREATE_PAUSED", "status": "APPROVED",
            "account_id": self.synthetic_account_id(), "manifest_path": "campaign-manifest.json",
            "expires_at": "2000-01-01T00:00:00Z",
        }
        (workspace / "approvals" / "bad.json").write_text(json.dumps(approval))
        with self.assertRaisesRegex(ValueError, "account_id"):
            mos.load_approval(workspace, "approvals/bad.json", "CREATE_PAUSED", "act_" + ("1" * 15), "campaign-manifest.json")

    def test_approval_rejects_manifest_mutation_after_approval(self):
        workspace = self.make_workspace()
        manifest_path = workspace / "campaign-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        approval = {
            "approval_id": "approved-manifest", "action": "CREATE_PAUSED", "status": "APPROVED",
            "account_id": self.synthetic_account_id(), "manifest_path": "campaign-manifest.json",
            "manifest_sha256": self.manifest_digest(manifest),
            "expires_at": "2099-01-01T00:00:00Z",
        }
        (workspace / "approvals" / "approved.json").write_text(json.dumps(approval))
        manifest["daily_budget_minor_units"] = 999999
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "manifest_sha256"):
            mos.load_approval(workspace, "approvals/approved.json", "CREATE_PAUSED", self.synthetic_account_id(), "campaign-manifest.json")

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
        config_path.write_text(json.dumps(config))
        manifest_path.write_text(json.dumps(manifest))
        approval = {
            "approval_id": "placeholder-tenant", "action": "ACTIVATE", "status": "APPROVED",
            "tenant_id": "REPLACE_WITH_TENANT_ID", "account_id": self.synthetic_account_id(),
            "object_id": "campaign-test", "object_kind": "campaign", "expires_at": "2099-01-01T00:00:00Z",
        }
        (workspace / "approvals" / "activate.json").write_text(json.dumps(approval))
        args = SimpleNamespace(workspace=str(workspace), approval="approvals/activate.json", object_id="campaign-test", execute=True, acknowledge=mos.ACK_ACTIVATE)
        with self.assertRaisesRegex(ValueError, "tenant"):
            mos.activate(args)

    def test_release_scanner_includes_untracked_file_planned_for_public_push(self):
        fixture = ROOT / "UNTRACKED_RELEASE_SCANNER_FIXTURE.txt"
        fixture.write_text("act_" + ("9" * 12), encoding="utf-8")
        self.addCleanup(fixture.unlink)
        self.assertTrue(any("UNTRACKED_RELEASE_SCANNER_FIXTURE.txt" in problem for problem in check_release.scan()))

    def test_private_path_rejects_escape(self):
        workspace = self.make_workspace()
        with self.assertRaisesRegex(ValueError, "inside the workspace"):
            mos.private_path(workspace, "../outside.json")


if __name__ == "__main__":
    unittest.main()
