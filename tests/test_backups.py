import pytest
from app.models.backups import BackupRecord, BackupAuditEvent

def test_encrypted_backup_creation_and_verification(client, school_manager_headers, db_session):
    # 1. Create Backup
    res = client.post("/api/v1/school/backups/create", headers=school_manager_headers)
    assert res.status_code == 201
    backup = res.json()
    assert backup["encryption_algorithm"] == "AES-256-GCM"
    assert "checksum_sha256" in backup
    assert backup["file_size_bytes"] > 0
    backup_id = backup["id"]

    # 2. Verify Integrity
    ver_res = client.post(f"/api/v1/school/backups/{backup_id}/verify", headers=school_manager_headers)
    assert ver_res.status_code == 200
    ver_data = ver_res.json()
    assert ver_data["valid"] is True
    assert ver_data["item_counts"]["schools"] > 0
    assert ver_data["item_counts"]["students"] > 0

    # 3. Download Backup
    down_res = client.get(f"/api/v1/school/backups/{backup_id}/download", headers=school_manager_headers)
    assert down_res.status_code == 200
    assert len(down_res.content) == backup["file_size_bytes"]

    # 4. Check Audit Events
    aud_res = client.get("/api/v1/school/backups/audit-events", headers=school_manager_headers)
    assert aud_res.status_code == 200
    audits = aud_res.json()
    assert len(audits) >= 3

def test_verify_nonexistent_backup_returns_404(client, school_manager_headers):
    response = client.post("/api/v1/school/backups/99999/verify", headers=school_manager_headers)
    assert response.status_code == 404

def test_download_nonexistent_backup_returns_404(client, school_manager_headers):
    response = client.get("/api/v1/school/backups/99999/download", headers=school_manager_headers)
    assert response.status_code == 404

def test_backup_list_ordered_by_creation_desc(client, school_manager_headers):
    response = client.get("/api/v1/school/backups", headers=school_manager_headers)
    assert response.status_code == 200
    backups = response.json()
    assert isinstance(backups, list)
    if len(backups) >= 2:
        assert backups[0]["created_at"] >= backups[1]["created_at"]

