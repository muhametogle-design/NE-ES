"""Multipart upload validation and public static serving, isolated from real uploads."""
import base64
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import media
from app.main import app

UPLOAD_URL = "/api/v1/media/upload"

# Real one-pixel images, generated once for these fixtures. Tests need no image
# library or external binary, and the handler must preserve the original bytes.
IMAGES = [
    ("image/png", ".png", base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQAAAAA3bvkkAAAACklEQVQI12NoAAAAggCB3UNq9AAAAABJRU5ErkJggg=="
    )),
    ("image/jpeg", ".jpg", base64.b64decode(
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8M"
        "CgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQ"
        "AQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q=="
    )),
    ("image/webp", ".webp", base64.b64decode(
        "UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAgA0JaQAA3AA/vuUAAA="
    )),
]
PNG = IMAGES[0][2]


@pytest.fixture(autouse=True)
def photo_dir(tmp_path, monkeypatch):
    # Uploads and the static mount share the backend working directory. Moving
    # both into a per-test cwd avoids ever touching a deployed user's photos.
    monkeypatch.chdir(tmp_path)
    return tmp_path / "uploads" / "photos"


def test_startup_creates_upload_directories_and_preserves_existing_photos(photo_dir):
    assert not photo_dir.parent.exists()
    with TestClient(app):
        assert photo_dir.is_dir()
        (photo_dir / "existing.png").write_bytes(PNG)
    with TestClient(app) as client:
        assert (photo_dir / "existing.png").read_bytes() == PNG
        assert client.get("/static/photos/existing.png").content == PNG


@pytest.mark.parametrize("mime,extension,payload", IMAGES)
def test_valid_image_upload_returns_201_and_public_static_url(
    client, school_manager_headers, photo_dir, mime, extension, payload,
):
    response = client.post(UPLOAD_URL, headers=school_manager_headers, files={
        "file": ("portrait.original", payload, mime),
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"photo_url"}
    photo_url = body["photo_url"]
    assert re.fullmatch(r"/static/photos/[0-9a-f]{32}" + re.escape(extension), photo_url)
    filename = Path(photo_url).name
    assert uuid.UUID(Path(filename).stem).version == 4
    assert (photo_dir / filename).read_bytes() == payload
    assert len(list(photo_dir.iterdir())) == 1

    # Fetch without authorization: the returned URL is publicly served, not a
    # React index.html response or an authenticated profile endpoint.
    static = client.get(photo_url)
    assert static.status_code == 200
    assert static.content == payload
    assert static.headers["content-type"] == mime
    assert static.headers["x-content-type-options"] == "nosniff"
    assert client.head(photo_url).status_code == 200


@pytest.mark.parametrize("mime", [
    "text/plain", "text/html", "application/pdf", "application/octet-stream", "image/gif", "image/svg+xml",
])
def test_unsupported_mime_type_is_rejected_without_saving(client, school_manager_headers, photo_dir, mime):
    response = client.post(UPLOAD_URL, headers=school_manager_headers, files={
        "file": ("pretend-image.png", b"not an allowed image format", mime),
    })
    assert response.status_code == 400
    assert "JPEG, PNG, and WebP" in response.json()["detail"]
    assert list(photo_dir.iterdir()) == []


def test_empty_photo_is_rejected(client, school_manager_headers, photo_dir):
    response = client.post(UPLOAD_URL, headers=school_manager_headers, files={
        "file": ("empty.png", b"", "image/png"),
    })
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]
    assert list(photo_dir.iterdir()) == []


def test_file_at_exact_five_mb_limit_is_accepted(client, school_manager_headers, photo_dir):
    # Payload size, not the larger multipart envelope, is capped at 5 MiB.
    payload = PNG + b"\0" * (media.MAX_PHOTO_SIZE - len(PNG))
    response = client.post(UPLOAD_URL, headers=school_manager_headers, files={
        "file": ("large.png", payload, "image/png"),
    })
    assert response.status_code == 201, response.text
    saved = photo_dir / Path(response.json()["photo_url"]).name
    assert saved.stat().st_size == media.MAX_PHOTO_SIZE
    assert saved.read_bytes() == payload


@pytest.mark.parametrize("part_headers", [{}, {"Content-Length": "1"}])
def test_file_over_five_mb_is_rejected_using_actual_bytes(
    client, school_manager_headers, photo_dir, part_headers,
):
    payload = PNG + b"\0" * (media.MAX_PHOTO_SIZE + 1 - len(PNG))
    response = client.post(UPLOAD_URL, headers=school_manager_headers, files={
        "file": ("oversized.png", payload, "image/png", part_headers),
    })
    assert response.status_code == 400
    assert "5 MB" in response.json()["detail"]
    assert list(photo_dir.iterdir()) == []


def test_client_filename_is_ignored_and_repeated_uploads_get_unique_names(client, school_manager_headers, photo_dir):
    urls = []
    for _ in range(2):
        response = client.post(UPLOAD_URL, headers=school_manager_headers, files={
            "file": ("../../server.py", PNG, "image/png"),
        })
        assert response.status_code == 201
        urls.append(response.json()["photo_url"])
    assert urls[0] != urls[1]
    assert all(re.fullmatch(r"/static/photos/[0-9a-f]{32}\.png", url) for url in urls)
    assert len(list(photo_dir.iterdir())) == 2
    assert not (photo_dir.parent.parent / "server.py").exists()


def test_uuid_collision_never_overwrites_an_existing_photo(client, school_manager_headers, photo_dir, monkeypatch):
    existing_id, new_id = uuid.uuid4(), uuid.uuid4()
    existing = photo_dir / f"{existing_id.hex}.png"
    existing.write_bytes(b"existing photo")
    ids = iter([existing_id, new_id])
    monkeypatch.setattr(media.uuid, "uuid4", lambda: next(ids))
    response = client.post(UPLOAD_URL, headers=school_manager_headers, files={
        "file": ("portrait.png", PNG, "image/png"),
    })
    assert response.status_code == 201, response.text
    assert response.json()["photo_url"] == f"/static/photos/{new_id.hex}.png"
    assert existing.read_bytes() == b"existing photo"
    assert (photo_dir / f"{new_id.hex}.png").read_bytes() == PNG


def test_storage_error_returns_controlled_500(client, school_manager_headers, photo_dir, monkeypatch):
    def fail_write(*_):
        raise OSError("private filesystem path and storage details")

    monkeypatch.setattr(media, "_save_photo", fail_write)
    response = client.post(UPLOAD_URL, headers=school_manager_headers, files={
        "file": ("portrait.png", PNG, "image/png"),
    })
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to save photo"}
    assert list(photo_dir.iterdir()) == []


def test_failed_write_removes_partial_photo(photo_dir, monkeypatch):
    real_open = Path.open

    class FailedWrite:
        def __init__(self, destination):
            self.output = real_open(destination, "xb")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.output.close()

        def write(self, content):
            self.output.write(content[:8])
            raise OSError("disk full")

    monkeypatch.setattr(Path, "open", lambda path, mode: FailedWrite(path))
    with pytest.raises(OSError, match="disk full"):
        media._save_photo(PNG, ".png")
    assert list(photo_dir.iterdir()) == []


def test_static_missing_files_and_path_traversal_return_404(client, photo_dir):
    secret = photo_dir.parent.parent / "private.txt"
    secret.write_text("not in uploads")
    for path in ("/static/photos/missing.png", "/static/photos", "/static/photos/..%2F..%2Fprivate.txt"):
        response = client.get(path)
        assert response.status_code == 404
        assert "not in uploads" not in response.text
        assert "<html" not in response.text.lower()


def test_missing_file_returns_422(client, school_manager_headers, photo_dir):
    response = client.post(UPLOAD_URL, headers=school_manager_headers)
    assert response.status_code == 422
    assert list(photo_dir.iterdir()) == []


def test_upload_requires_school_user_authentication(client, state_admin_headers, photo_dir):
    files = {"file": ("portrait.png", PNG, "image/png")}
    assert client.post(UPLOAD_URL, files=files).status_code == 401
    assert client.post(UPLOAD_URL, headers=state_admin_headers, files=files).status_code == 403
    assert list(photo_dir.iterdir()) == []


def test_teacher_can_upload_photo(client, teacher_headers):
    response = client.post(UPLOAD_URL, headers=teacher_headers, files={
        "file": ("portrait.png", PNG, "image/png"),
    })
    assert response.status_code == 201
    assert client.get(response.json()["photo_url"]).content == PNG
