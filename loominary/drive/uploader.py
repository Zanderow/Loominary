"""Find/create Drive folder hierarchy, upload transcript, return shareable link."""
from pathlib import Path
from typing import Optional, Tuple

from googleapiclient.http import MediaFileUpload

from loominary import config
from loominary.utils.progress import console


def _find_or_create_folder(service, name: str, parent_id: Optional[str] = None) -> str:
    """Find or create a Drive folder by name under parent_id."""
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def upload_transcript(
    service,
    local_path: Path,
    show_name: str,
) -> Tuple[str, str]:
    """
    Upload transcript to Drive under {GOOGLE_DRIVE_FOLDER_NAME}/{show_name}/.
    Returns (file_id, web_view_link).
    """
    root_folder_id = _find_or_create_folder(service, config.GOOGLE_DRIVE_FOLDER_NAME)
    show_folder_id = _find_or_create_folder(service, show_name, parent_id=root_folder_id)

    file_metadata = {
        "name": local_path.name,
        "parents": [show_folder_id],
    }
    media = MediaFileUpload(str(local_path), mimetype="text/plain", resumable=True)

    console.print(f"[cyan]Uploading to Google Drive...[/cyan]")
    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink",
    ).execute()

    file_id = uploaded["id"]
    web_link = uploaded.get("webViewLink", "")

    # Make the file readable by anyone with the link
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    console.print(f"[green]Uploaded:[/green] {web_link}")
    return file_id, web_link
