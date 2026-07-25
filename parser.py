import json
from pathlib import Path
from typing import List, Optional
from schemas import Dialog, Message


class DialogParser:
    def __init__(self, dialogs_dir: Path):
        self.dialogs_dir = dialogs_dir

    def get_json_files(self) -> List[Path]:
        return sorted(self.dialogs_dir.glob("*.json"))

    def parse_file(self, file_path: Path) -> Optional[Dialog]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Dialog(**data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error parsing {file_path}: {e}")
            return None

    def parse_all(self) -> List[Dialog]:
        dialogs = []
        for file_path in self.get_json_files():
            dialog = self.parse_file(file_path)
            if dialog:
                dialogs.append(dialog)
        return dialogs

    def get_first_user_message(self, dialog: Dialog) -> str:
        for msg in dialog.messages:
            if msg.role == "user":
                return msg.content
        return ""

    def get_dialog_text(self, dialog: Dialog) -> str:
        parts = []
        for msg in dialog.messages:
            role = msg.role.upper()
            parts.append(f"{role}: {msg.content}")
        return "\n\n".join(parts)
