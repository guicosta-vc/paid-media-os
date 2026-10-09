import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mos", ROOT / "scripts" / "mos.py")
mos = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mos)


class MarketingOSTest(unittest.TestCase):
    def make_workspace(self) -> Path:
        temp = Path(tempfile.mkdtemp())
        workspace = temp / "workspace"
        mos.init_workspace(workspace)
        config = json.loads((workspace / "workspace.json").read_text())
        manifest = json.loads((workspace / "campaign-manifest.json").read_text())
        catalog = json.loads((workspace / "creative-catalog.json").read_text())
        catalog["assets"][0].update({
            "asset_sha256": "a" * 64,
            "rights_status": "approved",
            "approval_status": "approved",
            "meta_asset_id": "image-hash-example",
        })
        manifest["objects"][2]["payload"]["object_story_spec"]["page_id"] = "123456789"
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

    def test_placeholder_resolution_requires_dependency(self):
        with self.assertRaisesRegex(ValueError, "Unresolved dependency"):
            mos.resolve_placeholders({"campaign_id": "$CAMPAIGN_ID"}, {})

    def test_approval_rejects_expiry_and_account_mismatch(self):
        workspace = self.make_workspace()
        approval = {
            "approval_id": "x", "action": "CREATE_PAUSED", "status": "APPROVED",
            "account_id": "act_000000000", "manifest_path": "campaign-manifest.json",
            "expires_at": "2000-01-01T00:00:00Z",
        }
        (workspace / "approvals" / "bad.json").write_text(json.dumps(approval))
        with self.assertRaisesRegex(ValueError, "account_id"):
            mos.load_approval(workspace, "approvals/bad.json", "CREATE_PAUSED", "act_123456789", "campaign-manifest.json")

    def test_private_path_rejects_escape(self):
        workspace = self.make_workspace()
        with self.assertRaisesRegex(ValueError, "inside the workspace"):
            mos.private_path(workspace, "../outside.json")


if __name__ == "__main__":
    unittest.main()
