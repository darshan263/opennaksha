import hashlib
from datetime import timedelta

from opennaksha.files import FileState, check_file, needs_download
from opennaksha.http import HeadInfo

from .helpers import T0, T1, FakeFiles, mock_client

URL = "https://example.test/tp57.pdf"


def head(etag=None, lm=None, cl=None):
    return HeadInfo(200, etag, lm, cl)


def test_needs_download_rules():
    prev = FileState(sha256="x", size_bytes=10, etag='"1"', last_hashed=T0)
    assert needs_download(None, head(), T1)
    assert needs_download(FileState(), head('"1"'), T1)  # never hashed
    assert not needs_download(prev, head('"1"', cl=10), T1)
    assert needs_download(prev, head('"2"'), T1)
    assert needs_download(prev, head('"1"', cl=11), T1)
    # no validators: re-hash only after 30 days
    assert not needs_download(prev, head(), T0 + timedelta(days=29))
    assert needs_download(prev, head(), T0 + timedelta(days=30))
    assert not needs_download(prev, None, T0 + timedelta(days=1))


def test_check_file_downloads_new_then_skips_unchanged():
    fake = FakeFiles({URL: b"%PDF-1 hello"})
    with mock_client(fake) as client:
        st = check_file(client, URL, None, T0)
        assert st.sha256 == hashlib.sha256(b"%PDF-1 hello").hexdigest()
        assert st.size_bytes == 12 and st.last_hashed == T0 and st.etag
        st2 = check_file(client, URL, st, T1)
    assert fake.gets == [URL]  # second time: HEAD only
    assert st2.sha256 == st.sha256 and st2.last_hashed == T0


def test_check_file_redownloads_when_etag_changes():
    fake = FakeFiles({URL: b"v1"})
    with mock_client(fake) as client:
        st = check_file(client, URL, None, T0)
        fake.files[URL] = b"version 2"
        st2 = check_file(client, URL, st, T1)
    assert st2.sha256 == hashlib.sha256(b"version 2").hexdigest()
    assert len(fake.gets) == 2


def test_no_download_mode_never_downloads():
    fake = FakeFiles({URL: b"v1"})
    with mock_client(fake) as client:
        st = check_file(client, URL, None, T0, no_download=True)
    assert fake.gets == []
    assert st.sha256 is None and st.size_bytes == 2
