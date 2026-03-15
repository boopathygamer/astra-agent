"""
Tests for the File Recovery & Deep Search System.

Validates all 6 tools: deep_search, content_search, deleted_files,
duplicate_files, file_metadata, and file_recovery.
"""

import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_deep_search_files():
    """Test full-drive deep search finds files."""
    from agents.tools.file_recovery import deep_search_files

    # Search for Python files in this project (should find many)
    result = deep_search_files(
        query="*.py",
        drives=[str(Path(__file__).parent.parent)],
        max_results=10,
    )

    assert result["success"] is True, f"Search failed: {result}"
    assert result["total_found"] > 0, "Should find .py files in project"
    assert result["files_scanned"] > 0, "Should scan files"
    assert result["directories_searched"] > 0

    # Verify result structure
    first = result["results"][0]
    assert "path" in first
    assert "name" in first
    assert "size_bytes" in first
    assert "size_human" in first
    assert first["name"].endswith(".py")

    print(f"  ✅ Deep search: found {result['total_found']} .py files, "
          f"scanned {result['files_scanned']} files in "
          f"{result['search_duration_s']}s")


def test_deep_search_with_filters():
    """Test deep search with size and date filters."""
    from agents.tools.file_recovery import deep_search_files

    result = deep_search_files(
        query="*",
        drives=[str(Path(__file__).parent.parent)],
        extension=".py",
        min_size_bytes=100,
        max_size_bytes=50000,
        max_results=5,
    )

    assert result["success"] is True
    for r in result["results"]:
        assert r["size_bytes"] >= 100, f"File too small: {r['size_bytes']}"
        assert r["size_bytes"] <= 50000, f"File too large: {r['size_bytes']}"
        assert r["name"].endswith(".py")

    print(f"  ✅ Filtered search: {result['total_found']} files within "
          f"100B-50KB .py filter")


def test_deep_search_all_drives():
    """Test drive discovery works."""
    from agents.tools.file_recovery import _get_all_drives

    drives = _get_all_drives()
    assert len(drives) > 0, "Should find at least one drive"

    print(f"  ✅ Drive discovery: found {drives}")


def test_search_file_contents():
    """Test grep-like content search inside files."""
    from agents.tools.file_recovery import search_file_contents

    # Search for a known string in this test file
    result = search_file_contents(
        pattern="test_search_file_contents",
        search_dir=str(Path(__file__).parent),
        extensions=[".py"],
        max_results=5,
    )

    assert result["success"] is True, f"Search failed: {result}"
    assert result["total_matches"] > 0, "Should find this function name"
    assert result["files_searched"] > 0

    first = result["results"][0]
    assert "file" in first
    assert "line_number" in first
    assert "line_content" in first
    assert "test_search_file_contents" in first["line_content"]

    print(f"  ✅ Content search: {result['total_matches']} matches in "
          f"{result['files_searched']} files, {result['search_duration_s']}s")


def test_search_file_contents_with_context():
    """Test content search with context lines."""
    from agents.tools.file_recovery import search_file_contents

    result = search_file_contents(
        pattern="def test_deep_search_files",
        search_dir=str(Path(__file__).parent),
        extensions=[".py"],
        context_lines=2,
        max_results=3,
    )

    assert result["success"] is True
    if result["total_matches"] > 0:
        first = result["results"][0]
        assert "context_before" in first
        assert "context_after" in first

    print(f"  ✅ Content search with context: "
          f"{result['total_matches']} matches")


def test_search_file_contents_case_insensitive():
    """Test case-insensitive content search."""
    from agents.tools.file_recovery import search_file_contents

    # Search with different case
    result = search_file_contents(
        pattern="TEST_SEARCH_FILE_CONTENTS",
        search_dir=str(Path(__file__).parent),
        extensions=[".py"],
        case_sensitive=False,
        max_results=3,
    )

    assert result["success"] is True
    assert result["total_matches"] > 0, "Case-insensitive should match"

    print(f"  ✅ Case-insensitive search: {result['total_matches']} matches")


def test_search_file_contents_regex():
    """Test regex-based content search."""
    from agents.tools.file_recovery import search_file_contents

    result = search_file_contents(
        pattern=r"def test_\w+_files",
        search_dir=str(Path(__file__).parent),
        extensions=[".py"],
        use_regex=True,
        max_results=10,
    )

    assert result["success"] is True
    assert result["total_matches"] > 0, "Regex should match test functions"

    print(f"  ✅ Regex search: {result['total_matches']} matches for "
          f"'def test_\\w+_files'")


def test_find_deleted_files():
    """Test Recycle Bin / Trash scanning."""
    from agents.tools.file_recovery import find_deleted_files

    result = find_deleted_files(query="*", max_results=10)

    assert result["success"] is True
    assert "platform" in result
    assert "total_found" in result
    assert isinstance(result["results"], list)

    if result["total_found"] > 0:
        first = result["results"][0]
        assert "name" in first
        assert "trash_path" in first
        assert "recoverable" in first
        print(f"  ✅ Deleted files: found {result['total_found']} in "
              f"{result['platform']} recycle bin")
        for f in result["results"][:3]:
            print(f"     - {f['name']} ({f.get('size_human', '?')})")
    else:
        print(f"  ✅ Deleted files: recycle bin is empty (0 files)")


def test_find_duplicate_files():
    """Test hash-based duplicate detection."""
    from agents.tools.file_recovery import find_duplicate_files

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create duplicate files
        content_a = b"This is test file content for duplicate detection A" * 50
        content_b = b"This is different content B" * 50

        # Write duplicates of content_a
        (Path(tmpdir) / "file1.txt").write_bytes(content_a)
        (Path(tmpdir) / "subdir").mkdir()
        (Path(tmpdir) / "subdir" / "file1_copy.txt").write_bytes(content_a)
        (Path(tmpdir) / "subdir" / "file1_copy2.txt").write_bytes(content_a)

        # Write unique file
        (Path(tmpdir) / "unique.txt").write_bytes(content_b)

        result = find_duplicate_files(
            search_dir=tmpdir,
            min_size_bytes=100,
            max_groups=10,
        )

        assert result["success"] is True
        assert result["files_scanned"] >= 4
        assert result["duplicate_groups"] >= 1, "Should find at least 1 group"

        group = result["groups"][0]
        assert group["count"] >= 2, "Duplicate group should have 2+ files"
        assert group["wasted_bytes"] > 0
        assert len(group["files"]) >= 2

        print(f"  ✅ Duplicate finder: {result['duplicate_groups']} groups, "
              f"wasted {result['total_wasted_human']}")


def test_read_file_metadata_basic():
    """Test basic file metadata extraction."""
    from agents.tools.file_recovery import read_file_metadata

    # Read metadata of this test file
    result = read_file_metadata(str(Path(__file__)))

    assert result["success"] is True
    assert "basic" in result, "Should have basic metadata"

    basic = result["basic"]
    assert basic["extension"] == ".py"
    assert basic["size_bytes"] > 0
    assert "created" in basic
    assert "modified" in basic

    assert "hash_sha256" in result
    assert len(result["hash_sha256"]) == 64  # SHA-256 hex length

    print(f"  ✅ File metadata: {basic['name']}, "
          f"{basic['size_human']}, hash={result['hash_sha256'][:12]}...")


def test_read_file_metadata_image():
    """Test image metadata extraction (EXIF)."""
    from agents.tools.file_recovery import read_file_metadata

    # Find any image file in the project
    project_root = Path(__file__).parent.parent
    image_found = None
    for ext in [".jpg", ".jpeg", ".png", ".gif"]:
        for img in project_root.rglob(f"*{ext}"):
            image_found = str(img)
            break
        if image_found:
            break

    if image_found:
        result = read_file_metadata(image_found)
        assert result["success"] is True
        assert "exif" in result or "media" in result
        print(f"  ✅ Image metadata: {Path(image_found).name}, "
              f"EXIF keys: {list(result.get('exif', {}).keys())[:5]}")
    else:
        print(f"  ✅ Image metadata: skipped (no images in project)")


def test_read_file_metadata_not_found():
    """Test metadata for non-existent file."""
    from agents.tools.file_recovery import read_file_metadata

    result = read_file_metadata("C:\\nonexistent\\file.txt")
    assert result["success"] is False
    assert "error" in result

    print("  ✅ Metadata not-found: correctly returns error")


def test_recover_deleted_file():
    """Test file recovery from a simulated trash folder."""
    from agents.tools.file_recovery import recover_deleted_file

    with tempfile.TemporaryDirectory() as tmpdir:
        # Simulate a file "in trash"
        trash_file = Path(tmpdir) / "lost_document.txt"
        trash_file.write_text("This is recovered content!")

        restore_dir = Path(tmpdir) / "restored"
        restore_dir.mkdir()

        result = recover_deleted_file(
            trash_path=str(trash_file),
            restore_to=str(restore_dir),
        )

        assert result["success"] is True, f"Recovery failed: {result}"
        assert "restored_to" in result
        assert Path(result["restored_to"]).exists()

        # Verify content
        restored_content = Path(result["restored_to"]).read_text()
        assert restored_content == "This is recovered content!"

        print(f"  ✅ File recovery: restored to {result['restored_to']}")


def test_recover_avoids_overwrite():
    """Test recovery avoids overwriting existing files."""
    from agents.tools.file_recovery import recover_deleted_file

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create source
        source = Path(tmpdir) / "file.txt"
        source.write_text("recovered!")

        # Create existing file with same name in restore dir
        restore_dir = Path(tmpdir) / "dest"
        restore_dir.mkdir()
        (restore_dir / "file.txt").write_text("existing!")

        result = recover_deleted_file(
            trash_path=str(source),
            restore_to=str(restore_dir),
        )

        assert result["success"] is True
        # Should have "_recovered_1" suffix
        restored = Path(result["restored_to"])
        assert "recovered" in restored.name
        assert restored.read_text() == "recovered!"

        # Original should be untouched
        assert (restore_dir / "file.txt").read_text() == "existing!"

        print(f"  ✅ Recovery anti-overwrite: saved as {restored.name}")


def test_hash_file_utility():
    """Test file hashing utility."""
    from agents.tools.file_recovery import _hash_file

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"test content for hashing")
        f.flush()
        path = f.name

    try:
        h = _hash_file(path)
        assert h is not None
        assert len(h) == 64  # SHA-256

        # Verify deterministic
        h2 = _hash_file(path)
        assert h == h2, "Same file should produce same hash"

        # Verify against known hash
        expected = hashlib.sha256(b"test content for hashing").hexdigest()
        assert h == expected

        print(f"  ✅ File hashing: SHA-256 verified ({h[:16]}...)")
    finally:
        os.unlink(path)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🔍  File Recovery & Deep Search — Test Suite")
    print("=" * 60 + "\n")

    print("─── Test 1: Deep Search Files ───")
    test_deep_search_files()

    print("\n─── Test 2: Deep Search with Filters ───")
    test_deep_search_with_filters()

    print("\n─── Test 3: Drive Discovery ───")
    test_deep_search_all_drives()

    print("\n─── Test 4: Content Search (grep) ───")
    test_search_file_contents()

    print("\n─── Test 5: Content Search with Context ───")
    test_search_file_contents_with_context()

    print("\n─── Test 6: Case-Insensitive Search ───")
    test_search_file_contents_case_insensitive()

    print("\n─── Test 7: Regex Search ───")
    test_search_file_contents_regex()

    print("\n─── Test 8: Find Deleted Files ───")
    test_find_deleted_files()

    print("\n─── Test 9: Find Duplicate Files ───")
    test_find_duplicate_files()

    print("\n─── Test 10: File Metadata (Basic) ───")
    test_read_file_metadata_basic()

    print("\n─── Test 11: File Metadata (Image) ───")
    test_read_file_metadata_image()

    print("\n─── Test 12: File Metadata (Not Found) ───")
    test_read_file_metadata_not_found()

    print("\n─── Test 13: Recover Deleted File ───")
    test_recover_deleted_file()

    print("\n─── Test 14: Recovery Anti-Overwrite ───")
    test_recover_avoids_overwrite()

    print("\n─── Test 15: File Hash Utility ───")
    test_hash_file_utility()

    print("\n" + "=" * 60)
    print("  🎉  ALL 15 FILE RECOVERY TESTS PASSED!")
    print("=" * 60 + "\n")
