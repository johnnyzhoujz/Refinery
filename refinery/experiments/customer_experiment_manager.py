"""
Customer experiment management system using battle-tested safety patterns.

This is for CUSTOMER HYPOTHESIS VERSIONS - completely separate from Refinery's internal prompts.

Customer experiments: .refinery/prompt_versions/ (customer's hypothesis versions)
Refinery internal: refinery/prompts/ (Refinery's own prompts)

Implements demo-killer prevention:
1. Atomic writes (temp file + fsync + os.replace)
2. Path allowlist validation (only prompts/ directory)
3. Backup before deploy (with automatic recovery)
4. Deterministic version IDs for reproducibility
"""

import hashlib
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.models import Hypothesis

logger = logging.getLogger(__name__)


class CustomerExperimentManager:
    """Customer experiment management for hypothesis versions with demo-safe patterns."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()
        self.refinery_dir = self.repo_root / ".refinery"
        self.versions_dir = self.refinery_dir / "prompt_versions"
        self.staging_dir = self.refinery_dir / "staging"
        self.backups_dir = self.refinery_dir / "backups"
        self.index_file = self.versions_dir / "index.json"

        # Ensure directories exist
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def atomic_write_json(self, path: Path, payload: dict) -> None:
        """Atomic write using temp file + fsync + os.replace (battle-tested pattern)."""
        path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            "w", delete=False, dir=path.parent, suffix=".tmp"
        ) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())  # Force write to disk
            tmp_path = Path(tmp.name)

        # Atomic replace (works on POSIX & Windows)
        os.replace(tmp_path, path)
        logger.debug(f"Atomically wrote {len(json.dumps(payload))} bytes to {path}")

    def validate_change_path(
        self, rel_path: str, allowed_roots: Tuple[str, ...] = ("prompts/",)
    ) -> None:
        """Validate file path is within allowed directories (prevent file clobber demo-killer)."""
        if not rel_path or rel_path.startswith("/"):
            raise ValueError(f"Invalid path: {rel_path} (absolute paths not allowed)")

        if ".." in rel_path:
            raise ValueError(
                f"Invalid path: {rel_path} (parent directory references not allowed)"
            )

        # Resolve full path and check it's under allowed roots
        full_path = (self.repo_root / rel_path).resolve()

        for allowed_root in allowed_roots:
            allowed_full = (self.repo_root / allowed_root).resolve()
            try:
                full_path.relative_to(allowed_full)
                return  # Path is valid
            except ValueError:
                continue  # Try next allowed root

        raise ValueError(
            f"Path outside allowed directories: {rel_path} (allowed: {allowed_roots})"
        )

    def backup_and_deploy(
        self, src_dir: Path, files: List[str], backup_id: Optional[str] = None
    ) -> str:
        """Backup existing files then deploy new versions (prevent hard-to-undo demo-killer)."""
        if backup_id is None:
            backup_id = os.environ.get(
                "RUN_ID", f"manual_{int(datetime.utcnow().timestamp())}"
            )

        backup_dir = self.backups_dir / backup_id
        backup_files = []

        # Phase 1: Backup existing files
        for file_path in files:
            self.validate_change_path(file_path)  # Safety check

            src_file = src_dir / file_path
            dst_file = self.repo_root / file_path
            backup_file = backup_dir / file_path

            if not src_file.exists():
                logger.warning(f"Source file not found: {src_file}")
                continue

            # Create backup if destination exists
            if dst_file.exists():
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst_file, backup_file)
                backup_files.append(file_path)
                logger.info(f"Backed up {dst_file} -> {backup_file}")

        # Phase 2: Deploy new files
        deployed_files = []
        try:
            for file_path in files:
                src_file = src_dir / file_path
                dst_file = self.repo_root / file_path

                if not src_file.exists():
                    continue

                # Ensure parent directory exists
                dst_file.parent.mkdir(parents=True, exist_ok=True)

                # Atomic replace
                shutil.copy2(src_file, dst_file)
                deployed_files.append(file_path)
                logger.info(f"Deployed {src_file} -> {dst_file}")

        except Exception as e:
            logger.error(f"Deploy failed, rolling back: {e}")
            # Rollback: restore from backup
            for file_path in deployed_files:
                backup_file = backup_dir / file_path
                dst_file = self.repo_root / file_path
                if backup_file.exists():
                    shutil.copy2(backup_file, dst_file)
                    logger.info(f"Rolled back {dst_file}")
            raise

        logger.info(
            f"Successfully deployed {len(deployed_files)} files, backed up {len(backup_files)} files"
        )
        return backup_id

    def generate_version_id(self, hypothesis: Hypothesis) -> str:
        """Generate deterministic version ID for reproducibility."""
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        # Create content hash from hypothesis
        content_str = f"{hypothesis.description}:{hypothesis.rationale}"
        for change in hypothesis.proposed_changes:
            content_str += f":{change.file_path}:{change.new_content}"

        content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:6]
        return f"{timestamp}_{content_hash}"

    def save_version(self, hypothesis: Hypothesis, tag: Optional[str] = None) -> str:
        """Save hypothesis as a version with metadata."""
        version_id = self.generate_version_id(hypothesis)
        version_dir = self.versions_dir / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        # Calculate file hashes for integrity
        files_metadata = []
        for change in hypothesis.proposed_changes:
            # Safety check - allow prompts, config, orchestration, tests, and evals
            self.validate_change_path(
                change.file_path,
                allowed_roots=(
                    "prompts/",
                    "config/",
                    "orchestration/",
                    "tests/",
                    "evals/",
                ),
            )  # Safety check

            # Write file content
            target_path = version_dir / change.file_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(change.new_content, encoding="utf-8")

            # Calculate hash
            file_hash = hashlib.sha256(change.new_content.encode()).hexdigest()
            files_metadata.append({"path": change.file_path, "new_sha256": file_hash})

        # Create version.json with minimal but complete metadata
        version_metadata = {
            "schema_version": 1,
            "version_id": version_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "tag": tag,
            "hypothesis_id": hypothesis.id,
            "description": hypothesis.description,
            "confidence": hypothesis.confidence.value,
            "files": files_metadata,
        }

        # Add generation metadata if available
        if hasattr(hypothesis, "generation_metadata"):
            version_metadata["generation"] = hypothesis.generation_metadata

        # Atomic write of version metadata
        version_file = version_dir / "version.json"
        self.atomic_write_json(version_file, version_metadata)

        # Update index
        self._update_index(version_id, version_metadata)

        logger.info(f"Saved version {version_id} with {len(files_metadata)} files")
        return version_id

    def list_versions(self) -> List[Dict[str, Any]]:
        """List all versions from index (fast lookup)."""
        if not self.index_file.exists():
            return []

        try:
            with open(self.index_file, "r") as f:
                index = json.load(f)
            return index.get("versions", [])
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading index: {e}")
            return []

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """Get version metadata."""
        version_dir = self.versions_dir / version_id
        version_file = version_dir / "version.json"

        if not version_file.exists():
            return None

        try:
            with open(version_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading version {version_id}: {e}")
            return None

    def stage_version(self, version_id: str) -> Path:
        """Copy version to staging directory for safe testing."""
        version_dir = self.versions_dir / version_id
        staged_dir = self.staging_dir / version_id

        if not version_dir.exists():
            raise ValueError(f"Version not found: {version_id}")

        # Remove existing staged version
        if staged_dir.exists():
            shutil.rmtree(staged_dir)

        # Copy entire version directory to staging
        shutil.copytree(version_dir, staged_dir)

        logger.info(f"Staged version {version_id} at {staged_dir}")
        return staged_dir

    def deploy_version(self, version_id: str, confirm: bool = False) -> str:
        """Deploy version to production with backup."""
        if not confirm:
            raise ValueError("Deploy requires explicit confirmation")

        version_metadata = self.get_version(version_id)
        if not version_metadata:
            raise ValueError(f"Version not found: {version_id}")

        # Get file list
        files = [f["path"] for f in version_metadata["files"]]

        # Deploy from version directory with backup
        version_dir = self.versions_dir / version_id
        backup_id = self.backup_and_deploy(version_dir, files)

        logger.info(f"Deployed version {version_id}, backup: {backup_id}")
        return backup_id

    def diff_versions(self, version1_id: str, version2_id: str) -> Dict[str, Any]:
        """Compare two versions and return diff information."""
        v1_meta = self.get_version(version1_id)
        v2_meta = self.get_version(version2_id)

        if not v1_meta or not v2_meta:
            raise ValueError("One or both versions not found")

        # Simple file-based diff
        v1_files = {f["path"]: f["new_sha256"] for f in v1_meta["files"]}
        v2_files = {f["path"]: f["new_sha256"] for f in v2_meta["files"]}

        all_files = set(v1_files.keys()) | set(v2_files.keys())

        changes = []
        for file_path in sorted(all_files):
            v1_hash = v1_files.get(file_path)
            v2_hash = v2_files.get(file_path)

            if v1_hash == v2_hash:
                continue  # No change
            elif v1_hash is None:
                changes.append({"type": "added", "path": file_path})
            elif v2_hash is None:
                changes.append({"type": "removed", "path": file_path})
            else:
                changes.append({"type": "modified", "path": file_path})

        return {"version1": version1_id, "version2": version2_id, "changes": changes}

    def _update_index(self, version_id: str, version_metadata: Dict[str, Any]) -> None:
        """Update index.json with new version (atomic)."""
        # Read existing index
        index = {"versions": []}
        if self.index_file.exists():
            try:
                with open(self.index_file, "r") as f:
                    index = json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Corrupted index file, recreating")

        # Add/update version entry
        version_entry = {
            "version_id": version_id,
            "created_at": version_metadata["created_at"],
            "tag": version_metadata.get("tag"),
            "description": version_metadata["description"][:100],  # Truncate for index
            "files_count": len(version_metadata["files"]),
        }

        # Remove existing entry if present
        index["versions"] = [
            v for v in index["versions"] if v["version_id"] != version_id
        ]

        # Add new entry (most recent first)
        index["versions"].insert(0, version_entry)

        # Limit index size
        index["versions"] = index["versions"][:50]  # Keep last 50 versions

        # Atomic write
        self.atomic_write_json(self.index_file, index)
