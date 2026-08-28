from invoice_manager.application.backup_service import BackupService, BackupServiceError


def test_backup_and_restore(tmp_path):
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    (data_dir / "test.txt").write_text("hello")

    service = BackupService(data_dir, backup_dir)
    archive = service.backup()
    assert archive.exists()

    (data_dir / "test.txt").write_text("changed")
    service.restore(archive)
    assert (data_dir / "test.txt").read_text() == "hello"


def test_restore_missing_manifest(tmp_path):
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    service = BackupService(data_dir, backup_dir)

    import zipfile

    bad_zip = backup_dir / "bad.zip"
    bad_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("data/stuff.txt", "x")

    try:
        service.restore(bad_zip)
    except BackupServiceError as exc:
        assert "manifest" in str(exc).lower()
