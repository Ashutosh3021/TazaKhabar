"""One-shot patch: replace the SQLAlchemy Report bookkeeping in the HN scrapers
with the Pyronites-backed run state, and move the Who Is Hiring thread id from
a local file into the shared state table.

Run from the repo root:  python backend/scripts/_patch_scrapers.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRAPERS = ROOT / "backend" / "src" / "scrapers"

CREATE_REPORT = re.compile(
    r"[ \t]*# Create report entry\n"
    r"[ \t]*async with async_session\(\) as session:\n"
    r"[ \t]*report = Report\(\n"
    r"(?:[^\n]*\n)*?"
    r"[ \t]*session\.add\(report\)\n"
    r"[ \t]*await session\.flush\(\)\n"
    r"[ \t]*report_id = report\.id\n"
    r"[ \t]*await session\.commit\(\)[^\n]*\n",
)

CREATE_REPORT_NOOFLUSH = re.compile(
    r"[ \t]*# Create report entry\n"
    r"[ \t]*async with async_session\(\) as session:\n"
    r"[ \t]*report = Report\(\n"
    r"(?:[^\n]*\n)*?"
    r"[ \t]*session\.add\(report\)\n"
    r"[ \t]*await session\.commit\(\)\n"
    r"[ \t]*report_id = report\.id\n",
)

COMPLETED_BLOCK = re.compile(
    r"[ \t]*# Update report\n"
    r"[ \t]*async with async_session\(\) as session:\n"
    r"[ \t]*from sqlalchemy import select\n"
    r"[ \t]*stmt = select\(Report\)\.where\(Report\.id == report_id\)\n"
    r"[ \t]*result = await session\.execute\(stmt\)\n"
    r"[ \t]*report = result\.scalar_one_or_none\(\)\n"
    r"[ \t]*if report:\n"
    r"[ \t]*report\.items_collected = total\n"
    r"[ \t]*report\.new_items = new_count\n"
    r'[ \t]*report\.status = "completed"\n'
    r"[ \t]*await session\.commit\(\)\n"
    r"[ \t]*else:\n"
    r"[ \t]*logger\.warning\(f\"Could not find report \{report_id\} to update\"\)\n",
)

FAILED_BLOCK = re.compile(
    r"[ \t]*async with async_session\(\) as session:\n"
    r"[ \t]*from sqlalchemy import select\n"
    r"[ \t]*stmt = select\(Report\)\.where\(Report\.id == report_id\)\n"
    r"[ \t]*result = await session\.execute\(stmt\)\n"
    r"[ \t]*report = result\.scalar_one_or_none\(\)\n"
    r"[ \t]*if report:\n"
    r'[ \t]*report\.status = "failed"\n'
    r"[ \t]*await session\.commit\(\)\n",
)

WIH_FAILED_INLINE = re.compile(
    r"[ \t]*async with async_session\(\) as session:\n"
    r"[ \t]*from sqlalchemy import select as _select\n"
    r"[ \t]*r = \(await session\.execute\(_select\(Report\)\.where\(Report\.id == report_id\)\)\)\.scalar_one_or_none\(\)\n"
    r"[ \t]*if r:\n"
    r'[ \t]*r\.status = "failed"\n'
    r"[ \t]*await session\.commit\(\)\n",
)

WIH_SKIPPED_INLINE = re.compile(
    r"[ \t]*async with async_session\(\) as session:\n"
    r"[ \t]*from sqlalchemy import select as _select\n"
    r"[ \t]*r = \(await session\.execute\(_select\(Report\)\.where\(Report\.id == report_id\)\)\)\.scalar_one_or_none\(\)\n"
    r"[ \t]*if r:\n"
    r'[ \t]*r\.status = "completed"\n'
    r"[ \t]*r\.items_collected = 0\n"
    r"[ \t]*await session\.commit\(\)\n",
)


def patch_file(path: Path, name: str) -> None:
    text = path.read_text(encoding="utf-8")

    text = text.replace("from ..db.database import async_session\n", "")
    text = text.replace("from ..db.models import Report\n", "")

    text, n1 = CREATE_REPORT.subn(
        f'        await self.record_run("{name}", "running")\n', text
    )
    text, n2 = CREATE_REPORT_NOOFLUSH.subn(
        f'        await self.record_run("{name}", "running")\n', text
    )
    text, n3 = COMPLETED_BLOCK.subn(
        f'            await self.record_run("{name}", "completed", total, new_count)\n',
        text,
    )
    text, n4 = FAILED_BLOCK.subn(
        f'            await self.record_run("{name}", "failed")\n', text
    )
    text, n5 = WIH_FAILED_INLINE.subn(
        f'                await self.record_run("{name}", "failed")\n', text
    )
    text, n6 = WIH_SKIPPED_INLINE.subn(
        f'                await self.record_run("{name}", "completed", 0, 0)\n', text
    )

    path.write_text(text, encoding="utf-8")
    print(
        f"{path.name}: running={n1 + n2} completed={n3} failed={n4 + n5} skipped={n6}"
    )


def patch_wih_state() -> None:
    path = SCRAPERS / "who_is_hiring.py"
    text = path.read_text(encoding="utf-8")

    old_get = """    def _get_last_thread_id(self) -> int | None:
        \"\"\"Get the last processed Who Is Hiring thread ID.\"\"\"
        try:
            return int(self._last_thread_id_file.read_text(encoding=\"utf-8\").strip())
        except (FileNotFoundError, ValueError, IOError):
            return None
    
    def _set_last_thread_id(self, thread_id: int) -> None:
        \"\"\"Store the last processed Who Is Hiring thread ID.\"\"\"
        try:
            self._last_thread_id_file.write_text(str(thread_id), encoding=\"utf-8\")
        except IOError as e:
            logger.warning(f\"Failed to save last thread ID: {e}\")
"""

    new_get = """    async def _get_last_thread_id(self) -> int | None:
        \"\"\"Get the last processed Who Is Hiring thread ID from shared state.\"\"\"
        try:
            value = await repos.get_state(\"last_wih_thread\")
            return int(value) if value else None
        except (TypeError, ValueError):
            return None
        except Exception as e:
            logger.warning(f\"Could not read last thread ID: {e}\")
            return None

    async def _set_last_thread_id(self, thread_id: int) -> None:
        \"\"\"Store the last processed Who Is Hiring thread ID in shared state.\"\"\"
        try:
            await repos.set_state(\"last_wih_thread\", str(thread_id))
        except Exception as e:
            logger.warning(f\"Failed to save last thread ID: {e}\")
"""

    if old_get in text:
        text = text.replace(old_get, new_get)
    else:
        print("WARNING: could not find the thread-id helpers in who_is_hiring.py")

    text = text.replace(
        "from .base_scraper import BaseScraper",
        "from ..db import repos\nfrom .base_scraper import BaseScraper",
    )
    text = text.replace(
        "last_thread_id = self._get_last_thread_id()",
        "last_thread_id = await self._get_last_thread_id()",
    )
    text = text.replace(
        "self._set_last_thread_id(int(thread_id))",
        "await self._set_last_thread_id(int(thread_id))",
    )
    path.write_text(text, encoding="utf-8")
    print("who_is_hiring.py: thread id moved to shared state")


def main() -> None:
    for filename, name in (
        ("ask_hn.py", "ask_hn"),
        ("show_hn.py", "show_hn"),
        ("top_stories.py", "top_stories"),
        ("who_is_hiring.py", "who_is_hiring"),
    ):
        patch_file(SCRAPERS / filename, name)
    patch_wih_state()


if __name__ == "__main__":
    main()
