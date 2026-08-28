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


def test_backup_uses_custom_folder_and_prunes(tmp_path, setting_repo):
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    custom_dir = tmp_path / "custom_backups"
    data_dir.mkdir()
    (data_dir / "test.txt").write_text("hello")

    setting_repo.set("backup_enabled", "1")
    setting_repo.set("backup_frequency_hours", "1")
    setting_repo.set("backup_keep", "2")
    setting_repo.set("backup_folder", str(custom_dir))

    service = BackupService(data_dir, backup_dir, setting_repo=setting_repo)
    for _ in range(3):
        service.backup()
    service.prune()

    archives = sorted(custom_dir.glob("invoice_manager_backup_*.zip"))
    assert len(archives) == 2


def test_backup_on_exit(tmp_path, setting_repo):
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    (data_dir / "test.txt").write_text("hello")

    setting_repo.set("backup_on_exit", "1")
    service = BackupService(data_dir, backup_dir, setting_repo=setting_repo)
    assert service.backup_on_exit() is True
    assert any(backup_dir.glob("invoice_manager_backup_*.zip"))
