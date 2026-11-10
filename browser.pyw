"""A simple tabbed web browser, file browser, text editor, and terminal built with PySide6."""

from __future__ import annotations

import codecs
import json
import math
import os
import re
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import threading
import unicodedata
from string import Template

try:
    import fcntl
    import termios
except ImportError:  # Windows
    fcntl = termios = None

try:
    from winpty import PtyProcess as WinPtyProcess  # optional, for a full terminal on Windows
except ImportError:
    WinPtyProcess = None

import PySide6
from PySide6.QtCore import (
    QByteArray,
    QDir,
    QElapsedTimer,
    QEvent,
    QFile,
    QFileInfo,
    QLocale,
    QMimeData,
    QModelIndex,
    QObject,
    QPoint,
    QPointF,
    QProcess,
    QProcessEnvironment,
    QRect,
    QRectF,
    QRunnable,
    QSettings,
    QSize,
    QSocketNotifier,
    QStandardPaths,
    QStorageInfo,
    Qt,
    QThread,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
    qVersion,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QClipboard,
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QGuiApplication,
    QIcon,
    QImage,
    QImageReader,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileIconProvider,
    QFileSystemModel,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QTextEdit,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Simple Browser"

SEARCH_ENGINES = {
    "DuckDuckGo": "https://duckduckgo.com/?q={}",
    "Google": "https://www.google.com/search?q={}",
    "Bing": "https://www.bing.com/search?q={}",
    "Brave Search": "https://search.brave.com/search?q={}",
}
THEMES = ["System", "Light", "Dark"]
ZOOM_CHOICES = [50, 67, 75, 80, 90, 100, 110, 125, 150, 175, 200]
ZOOM_STEPS = [0.25, 0.33, 0.5, 0.67, 0.75, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]

# Opening a file: text files go to the editor, these go to a browser tab, and anything else
# uses the system default app.
VIEWABLE_EXTENSIONS = {
    ".html", ".htm", ".xhtml", ".svg", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".bmp", ".ico", ".mp4", ".webm", ".mp3", ".ogg", ".wav",
}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".env", ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".scss",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".java", ".kt", ".go", ".rs", ".rb", ".php", ".swift",
    ".sql", ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1", ".gitignore", ".editorconfig",
}
MAX_EDITOR_BYTES = 50 * 1024 * 1024

DEFAULTS = {
    "home_url": "https://duckduckgo.com",
    "search_engine": "DuckDuckGo",
    "theme": "System",
    "zoom": 100,
    "javascript": True,
    "images": True,
    "force_dark": False,
    "show_hidden": False,
    "files_view": "list",
    "files_preview": True,
    "restore_session": True,
    "download_dir": "",
    "ask_download": False,
    "word_wrap": True,
    "terminal_shell": "",
}

# Qt 6.7+ only.
FORCE_DARK = getattr(QWebEngineSettings.WebAttribute, "ForceDarkMode", None)


# ----- look and feel -----------------------------------------------------

# Lucide-style 24x24 stroke icons.
ICONS = {
    "back": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "forward": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "up": '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
    "reload": '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
    "stop": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "home": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "menu": '<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    "desktop": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
    "documents": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v5h5"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    "downloads": '<path d="M12 15V3"/><path d="m7 10 5 5 5-5"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>',
    "pictures": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
    "music": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "videos": '<rect x="2" y="6" width="14" height="12" rx="2"/><path d="m22 8-6 4 6 4V8Z"/>',
    "drive": '<path d="M22 12H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><path d="M6 16h.01"/><path d="M10 16h.01"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v5h5"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "chevron-up": '<path d="m18 15-6-6-6 6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
    "play": '<path d="m6 3 14 9-14 9V3z"/>',
    "terminal": '<path d="m4 17 6-6-6-6"/><path d="M12 19h8"/>',
    "panel": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M15 3v18"/>',
    "list": '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
}

LIGHT = {
    "frame": "#e9edf3", "surface": "#ffffff", "field": "#eef1f5", "hover": "#dde3ea",
    "pressed": "#cfd6df", "border": "#d5dbe3", "text": "#1f2329", "muted": "#5c6470",
    "icon": "#3c4450", "disabled": "#b6bdc7", "accent": "#2563eb", "accent_text": "#ffffff",
    "selected": "#dbe6fd", "line": "#f3f6fa", "match": "#ffecb3", "term_bg": "#ffffff",
}
DARK = {
    "frame": "#1b1d22", "surface": "#2a2d34", "field": "#1f2227", "hover": "#383c45",
    "pressed": "#444955", "border": "#3a3e47", "text": "#e8eaed", "muted": "#a1a7b3",
    "icon": "#d5d9e0", "disabled": "#5a606b", "accent": "#7aa7ff", "accent_text": "#0d1526",
    "selected": "#2f3d5c", "line": "#30343c", "match": "#5a4a1f", "term_bg": "#17191e",
}

STYLE = Template("""
QMainWindow, #tabRow { background: $frame; }
#navRow { background: $surface; border-bottom: 1px solid $border; }
QStackedWidget { background: $surface; }

QTabBar { background: transparent; }
QTabBar::tab {
    background: transparent; color: $muted; border: none;
    padding: 8px 10px 8px 12px; margin-right: 2px;
    border-top-left-radius: 10px; border-top-right-radius: 10px;
}
QTabBar::tab:selected { background: $surface; color: $text; }
QTabBar::tab:hover:!selected { background: $hover; }

QToolButton { background: transparent; border: none; border-radius: 17px; }
QToolButton:hover { background: $hover; }
QToolButton:pressed { background: $pressed; }
QToolButton::menu-indicator { image: none; width: 0; }
QToolButton#tabClose { border-radius: 9px; }
QToolButton#newTab { border-radius: 14px; }

QLineEdit#address, QLineEdit#search {
    background: $field; color: $text; border: 2px solid transparent;
    border-radius: 18px; padding: 5px 10px; font-size: 14px;
    selection-background-color: $accent; selection-color: $accent_text;
}
QLineEdit#address:hover, QLineEdit#search:hover { background: $hover; }
QLineEdit#address:focus, QLineEdit#search:focus { background: $surface; border-color: $accent; }

QProgressBar#loadBar { background: transparent; border: none; }
QProgressBar#loadBar::chunk { background: $accent; }

QLabel#linkHint {
    background: $surface; color: $muted; border: 1px solid $border;
    border-radius: 6px; padding: 4px 10px;
}

QMenu {
    background: $surface; color: $text; border: 1px solid $border;
    border-radius: 10px; padding: 6px 0;
}
QMenu::item { padding: 7px 32px 7px 18px; border-radius: 6px; margin: 0 6px; }
QMenu::item:selected { background: $hover; }
QMenu::item:disabled { color: $disabled; }
QMenu::separator { height: 1px; background: $border; margin: 6px 12px; }

QDialog { background: $surface; }
QDialog QLineEdit {
    background: $field; color: $text; border: 1px solid $border;
    border-radius: 8px; padding: 6px 10px;
}
QDialog QLineEdit:focus { border-color: $accent; }
QDialog QComboBox { min-height: 26px; padding-left: 8px; }
QDialog QPushButton {
    background: $field; color: $text; border: 1px solid $border;
    border-radius: 8px; padding: 7px 16px;
}
QDialog QPushButton:hover { background: $hover; }
QDialog QPushButton:default { background: $accent; color: $accent_text; border-color: $accent; }
QLabel#sectionNote { color: $muted; }

QListWidget#sidebar { background: $frame; border: none; padding: 10px 8px; outline: 0; }
QListWidget#sidebar::item { color: $text; padding: 7px 10px; border-radius: 8px; margin: 1px 0; }
QListWidget#sidebar::item:disabled { color: $muted; padding: 14px 10px 4px 10px; }
QListWidget#sidebar::item:hover:!disabled { background: $hover; }
QListWidget#sidebar::item:selected { background: $selected; color: $text; }

QLabel#folderTitle { color: $text; font-size: 18px; font-weight: 600; }
QTreeView#files, QListView#files { background: $surface; color: $text; border: none; outline: 0; }
QTreeView#files::item { padding: 5px 4px; border: none; }
QListView#files::item { padding: 6px; border-radius: 10px; }
QTreeView#files::item:hover, QListView#files::item:hover { background: $hover; }
QTreeView#files::item:selected, QListView#files::item:selected { background: $selected; color: $text; }
QTreeView#files QLineEdit, QListView#files QLineEdit {
    background: $surface; color: $text; border: 2px solid $accent; border-radius: 4px; padding: 1px 4px;
}
QHeaderView { background: $surface; }
QHeaderView::section {
    background: $surface; color: $muted; border: none;
    border-bottom: 1px solid $border; padding: 7px 8px;
}
QHeaderView::section:hover { color: $text; }
QLabel#emptyState { color: $muted; font-size: 15px; background: $surface; }
#statusRow { background: $surface; border-top: 1px solid $border; }
QLabel#statusText { color: $muted; }
QSplitter::handle { background: $border; }
#preview { background: $surface; }
#terminal { background: $term_bg; }

#downloadsCard { background: $surface; border: 1px solid $border; border-radius: 12px; }
QLabel#panelTitle { color: $text; font-size: 15px; font-weight: 600; }
QLabel#panelEmpty { color: $muted; padding: 24px; }
QScrollArea#downloadsScroll, QWidget#downloadsList { background: transparent; border: none; }
#downloadItem { background: transparent; border-radius: 8px; }
#downloadItem:hover { background: $hover; }
QLabel#downloadName { color: $text; font-weight: 600; }
QLabel#downloadStatus { color: $muted; }
QProgressBar#downloadBar { background: $field; border: none; border-radius: 2px; }
QProgressBar#downloadBar::chunk { background: $accent; border-radius: 2px; }
QLabel#previewImage { background: $field; border-radius: 12px; }
QLabel#previewName { color: $text; font-size: 15px; font-weight: 600; }
QLabel#previewKey { color: $muted; }
QLabel#previewValue { color: $text; }

QPlainTextEdit#editor {
    background: $surface; color: $text; border: none;
    selection-background-color: $selected; selection-color: $text;
}
#findBar { background: $surface; border-bottom: 1px solid $border; }
QLabel#findCount { color: $muted; min-width: 70px; }
QToolButton#textButton { color: $text; padding: 6px 12px; border-radius: 8px; }

QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle { background: $disabled; border-radius: 4px; }
QScrollBar::handle:vertical { min-height: 32px; margin: 0 2px; }
QScrollBar::handle:horizontal { min-width: 32px; margin: 2px 0; }
QScrollBar::handle:hover { background: $muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
""")


def system_prefers_dark() -> bool:
    hints = QGuiApplication.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    return scheme is not None and scheme() == Qt.ColorScheme.Dark


def make_palette(c: dict) -> QPalette:
    pal = QPalette()
    roles = {
        QPalette.Window: c["surface"], QPalette.WindowText: c["text"],
        QPalette.Base: c["field"], QPalette.AlternateBase: c["frame"],
        QPalette.Text: c["text"], QPalette.Button: c["field"],
        QPalette.ButtonText: c["text"], QPalette.Highlight: c["accent"],
        QPalette.HighlightedText: c["accent_text"], QPalette.ToolTipBase: c["surface"],
        QPalette.ToolTipText: c["text"], QPalette.PlaceholderText: c["muted"],
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(c["disabled"]))
    return pal


_ICON_CACHE: dict = {}


def make_icon(name: str, color: str, disabled_color: str | None = None) -> QIcon:
    key = (name, color, disabled_color)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached
    icon = QIcon()
    states = [(QIcon.Normal, color)]
    if disabled_color:
        states.append((QIcon.Disabled, disabled_color))
    for mode, stroke in states:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{stroke}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round">{ICONS[name]}</svg>'
        )
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        QSvgRenderer(QByteArray(svg.encode())).render(painter)
        painter.end()
        icon.addPixmap(pixmap, mode)
    _ICON_CACHE[key] = icon
    return icon


FILE_KINDS = {
    "pictures": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico", ".heic", ".tiff"},
    "music": {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"},
    "videos": {".mp4", ".webm", ".mov", ".mkv", ".avi"},
    "documents": {".txt", ".md", ".pdf", ".doc", ".docx", ".rtf", ".csv", ".json", ".xml",
                  ".html", ".htm", ".log", ".xlsx", ".pptx"},
}


class FileIcons(QFileIconProvider):
    """Line icons for the file list so it matches the rest of the UI on every platform."""

    def __init__(self, colors: dict):
        super().__init__()
        self._colors = colors
        self._cache: dict = {}

    def _get(self, name: str, color: str) -> QIcon:
        if name not in self._cache:
            self._cache[name] = make_icon(name, color)
        return self._cache[name]

    def icon(self, arg):
        if not isinstance(arg, QFileInfo):
            return super().icon(arg)
        if arg.isRoot():
            return self._get("drive", self._colors["icon"])
        if arg.isDir():
            return self._get("folder", self._colors["accent"])
        ext = "." + arg.suffix().lower()
        kind = next((k for k, exts in FILE_KINDS.items() if ext in exts), "file")
        return self._get(kind, self._colors["muted"])


# ----- helpers -----------------------------------------------------------

class Settings:
    def __init__(self):
        self.store = QSettings("SimpleBrowser", "SimpleBrowser")

    def get(self, key: str):
        default = DEFAULTS[key]
        return self.store.value(key, default, type=type(default))

    def set(self, key: str, value):
        self.store.setValue(key, value)

    def get_session(self) -> dict:
        try:
            session = json.loads(self.store.value("session", "{}", type=str))
        except ValueError:
            return {}
        return session if isinstance(session, dict) else {}

    def set_session(self, session: dict):
        self.store.setValue("session", json.dumps(session))

    def search_template(self) -> str:
        return SEARCH_ENGINES.get(self.get("search_engine"), SEARCH_ENGINES["DuckDuckGo"])


def to_url(text: str, settings: Settings) -> QUrl:
    """Turn address-bar input into a URL: a web address, a local path, or a web search."""
    text = text.strip()
    if not text:
        return QUrl.fromUserInput(settings.get("home_url"))
    if text.startswith("file:"):
        return QUrl(text)
    expanded = os.path.expanduser(text)
    if os.path.isabs(expanded):
        return QUrl.fromLocalFile(os.path.normpath(expanded))
    if "://" in text or text.startswith("about:"):
        return QUrl(text)
    if " " not in text and ("." in text or text.startswith("localhost")):
        return QUrl.fromUserInput(text)
    query = QUrl.toPercentEncoding(text).data().decode()
    return QUrl(settings.search_template().format(query))


def is_viewable(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIEWABLE_EXTENSIONS


def is_text(path: str) -> bool:
    # Files without an extension (README, Makefile, .bashrc…) are usually text.
    ext = os.path.splitext(os.path.basename(path))[1].lower()
    return ext in TEXT_EXTENSIONS or ext == ""


def read_text_file(path: str):
    """Return (text, uses_crlf). Raises ValueError for binary or very large files."""
    if os.path.getsize(path) > MAX_EDITOR_BYTES:
        raise ValueError("too large")
    with open(path, "rb") as f:
        data = f.read()
    if b"\0" in data[:8192]:
        raise ValueError("binary")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return text.replace("\r\n", "\n"), "\r\n" in text


def unique_name(folder: str, name: str) -> str:
    """Return `name`, or "name (2)", "name (3)", … if it already exists in `folder`."""
    base, ext = os.path.splitext(name)
    if os.path.isdir(os.path.join(folder, name)):
        base, ext = name, ""
    candidate, n = name, 2
    while os.path.lexists(os.path.join(folder, candidate)):
        candidate = f"{base} ({n}){ext}"
        n += 1
    return candidate


SYSTEM_FILE_MANAGER = {"win32": "File Explorer", "darwin": "Finder"}.get(
    sys.platform, "System file manager")


def common_extension(paths: list):
    """The shared lowercase extension of `paths` ("" for none), or None if they differ."""
    exts = {os.path.splitext(p)[1].lower() for p in paths}
    return exts.pop() if len(exts) == 1 else None


def _apps_key(ext: str) -> str:
    return "open_with/" + (ext.lstrip(".") or "no_extension")


def remembered_apps(settings: Settings, ext: str) -> list:
    value = settings.store.value(_apps_key(ext), "", type=str)
    return [app for app in value.split("\n") if app and os.path.exists(app)]


def remember_app(settings: Settings, ext: str, app: str):
    apps = [app] + [a for a in remembered_apps(settings, ext) if a != app]
    settings.store.setValue(_apps_key(ext), "\n".join(apps[:5]))


def app_name(app: str) -> str:
    return os.path.splitext(os.path.basename(app.rstrip("/\\")))[0]


def default_download_dir() -> str:
    return (QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
            or os.path.join(QDir.homePath(), "Downloads"))


def plural(count: int, word: str) -> str:
    if count == 1:
        return f"{count} {word}"
    return f"{count} {word}{'es' if word.endswith(('ch', 'sh', 's', 'x')) else 's'}"


# ----- thumbnails & preview ----------------------------------------------

THUMB_SIZE = 128
PREVIEW_SIZE = 520
_thumbnail_extensions: set | None = None


def thumbnail_extensions() -> set:
    """Image extensions Qt can decode. An empty set is a real answer, so it is cached separately."""
    global _thumbnail_extensions
    if _thumbnail_extensions is None:
        found = set()
        for fmt in QImageReader.supportedImageFormats():
            found.add("." + bytes(fmt).decode().lower())
        _thumbnail_extensions = found
    return _thumbnail_extensions


def has_thumbnail(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in thumbnail_extensions()


class ThumbnailJob(QRunnable):
    def __init__(self, owner: Thumbnails, path: str, size: int, stamp: int):
        super().__init__()
        self.owner, self.path, self.size, self.stamp = owner, path, size, stamp

    def run(self):
        reader = QImageReader(self.path)
        reader.setAutoTransform(True)
        full = reader.size()
        if full.isValid() and (full.width() > self.size or full.height() > self.size):
            reader.setScaledSize(full.scaled(self.size, self.size, Qt.KeepAspectRatio))
        image = reader.read()
        try:
            self.owner.loaded.emit(self.path, self.size, self.stamp, image)
        except RuntimeError:
            pass  # The window closed while this was loading.


class Thumbnails(QObject):
    """Loads scaled-down images on worker threads and caches the results."""

    ready = Signal(str)
    loaded = Signal(str, int, "qint64", QImage)
    MAX_ENTRIES = 800

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max(2, min(4, QThread.idealThreadCount())))
        self._cache: dict = {}
        self._pending: set = set()
        self.loaded.connect(self._store)

    def get(self, path: str, size: int, stamp: int):
        """Return a cached QPixmap (or None) and start loading it if it's missing or stale."""
        key = (path, size)
        entry = self._cache.get(key)
        if entry is not None and entry[0] == stamp:
            return entry[1]
        if key not in self._pending:
            self._pending.add(key)
            self._pool.start(ThumbnailJob(self, path, size, stamp))
        return entry[1] if entry is not None else None

    def _store(self, path: str, size: int, stamp: int, image: QImage):
        self._pending.discard((path, size))
        pixmap = None
        if not image.isNull():
            pixmap = self._framed(image, size) if size <= THUMB_SIZE else QPixmap.fromImage(image)
        if len(self._cache) >= self.MAX_ENTRIES:
            self._cache.pop(next(iter(self._cache)))
        self._cache[(path, size)] = (stamp, pixmap)
        self.ready.emit(path)

    @staticmethod
    def _framed(image: QImage, size: int) -> QPixmap:
        """Center the image on a square, transparent canvas with rounded corners."""
        scaled = image.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        canvas = QPixmap(size, size)
        canvas.fill(Qt.transparent)
        x, y = (size - scaled.width()) // 2, (size - scaled.height()) // 2
        clip = QPainterPath()
        clip.addRoundedRect(x, y, scaled.width(), scaled.height(), 8, 8)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setClipPath(clip)
        painter.drawImage(x, y, scaled)
        painter.end()
        return canvas


class FileModel(QFileSystemModel):
    """QFileSystemModel that shows thumbnails for images."""

    def __init__(self, thumbnails: Thumbnails, parent: QObject):
        super().__init__(parent)
        self.thumbnails = thumbnails
        self._thumb_icon: dict = {}
        thumbnails.ready.connect(self._on_ready)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if (role == Qt.DecorationRole and index.column() == 0
                and has_thumbnail(self.fileName(index))):
            info = self.fileInfo(index)
            if info.isFile():
                path = info.absoluteFilePath()
                stamp = info.lastModified().toMSecsSinceEpoch()
                pixmap = self.thumbnails.get(path, THUMB_SIZE, stamp)
                if pixmap is not None:
                    key = (path, stamp)
                    icon = self._thumb_icon.get(key)
                    if icon is None:
                        icon = QIcon(pixmap)
                        icon.addPixmap(pixmap, QIcon.Selected)
                        if len(self._thumb_icon) >= Thumbnails.MAX_ENTRIES:
                            self._thumb_icon.pop(next(iter(self._thumb_icon)))
                        self._thumb_icon[key] = icon
                    return icon
        return super().data(index, role)

    def _on_ready(self, path: str):
        index = self.index(path)
        if index.isValid():
            self.dataChanged.emit(index, index)


class PreviewPane(QWidget):
    """Shows a large preview and details for the selected file, or the folder itself."""

    def __init__(self, tab: FilesTab):
        super().__init__(objectName="preview")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setMinimumWidth(220)
        self.tab = tab
        self.image_path = ""
        self._icon_name = "folder"

        self.image = QLabel(objectName="previewImage", alignment=Qt.AlignCenter)
        self.image.setFixedHeight(220)
        self.name = QLabel(objectName="previewName", wordWrap=True)
        self.name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.details = QGridLayout()
        self.details.setHorizontalSpacing(12)
        self.details.setVerticalSpacing(8)
        self.details.setColumnStretch(1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.addWidget(self.image)
        layout.addWidget(self.name)
        layout.addLayout(self.details)
        layout.addStretch(1)

        tab.model.thumbnails.ready.connect(self._on_thumbnail)

    def show_info(self, title: str, rows: list, icon: str, image_path: str = ""):
        self.name.setText(title)
        while self.details.count():
            widget = self.details.takeAt(0).widget()
            widget.hide()
            widget.deleteLater()
        for row, (key, value) in enumerate(rows):
            self.details.addWidget(QLabel(key, objectName="previewKey"), row, 0, Qt.AlignTop)
            label = QLabel(value, objectName="previewValue", wordWrap=True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.details.addWidget(label, row, 1)
        self.image_path = image_path
        self._icon_name = icon
        self._show_image()

    def _show_image(self):
        pixmap = None
        if self.image_path:
            info = QFileInfo(self.image_path)
            pixmap = self.tab.model.thumbnails.get(
                self.image_path, PREVIEW_SIZE, info.lastModified().toMSecsSinceEpoch())
        if pixmap is not None:
            ratio = self.devicePixelRatioF()
            box = QSize(self.image.width() - 16, self.image.height() - 16) * ratio
            scaled = pixmap.scaled(box, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(ratio)
            self.image.setPixmap(scaled)
        else:
            colors = self.tab._window.colors
            color = colors["accent"] if self._icon_name == "folder" else colors["muted"]
            self.image.setPixmap(make_icon(self._icon_name, color).pixmap(QSize(72, 72)))

    def _on_thumbnail(self, path: str):
        if path == self.image_path:
            self._show_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.image_path:
            self._show_image()


# ----- tabs --------------------------------------------------------------

class BrowserTab(QWebEngineView):
    def __init__(self, window: BrowserWindow):
        super().__init__()
        self._window = window
        self.loading = False
        self.progress = 0

    def createWindow(self, _type: QWebEnginePage.WebWindowType) -> QWebEngineView:
        # Links with target="_blank" and window.open() land in a new tab.
        return self._window.add_tab()

    def location(self) -> str:
        return self.url().toString()

    def address_icon_name(self) -> str:
        return "lock" if self.url().scheme() == "https" else "globe"

    def can_go_back(self) -> bool:
        return self.history().canGoBack()

    def can_go_forward(self) -> bool:
        return self.history().canGoForward()

    def clear_history(self):
        self.history().clear()


class FilesTab(QWidget):
    """A folder view that plugs into the same tab strip and toolbar as web pages."""

    titleChanged = Signal(str)
    urlChanged = Signal(QUrl)
    iconChanged = Signal(QIcon)

    # Shared so "Cut" in one tab and "Paste" in another moves the files.
    cut_paths: set = set()

    def __init__(self, window: BrowserWindow, path: str):
        super().__init__()
        self._window = window
        self.loading = False
        self.progress = 0
        self.path = ""
        self._back: list = []
        self._forward: list = []
        self._zoom = 1.0
        self._loaded = False
        self._readable = True
        self._reveal = ""
        self._preview_again = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(50)
        self._preview_timer.timeout.connect(self._flush_preview)
        self.view_mode = window.settings.get("files_view")

        self.model = FileModel(window.thumbnails, self)
        self.model.setReadOnly(False)
        self.model.setNameFilterDisables(False)
        self.model.directoryLoaded.connect(self._on_directory_loaded)
        self.model.rowsInserted.connect(self.update_status)
        self.model.rowsRemoved.connect(self.update_status)

        self.sidebar = QListWidget(objectName="sidebar")
        self.sidebar.setIconSize(QSize(18, 18))
        self.sidebar.setMinimumWidth(160)
        self.sidebar.itemClicked.connect(self._on_sidebar_clicked)
        self._populate_sidebar()

        self.heading = QLabel(objectName="folderTitle")
        self.search = QLineEdit(objectName="search", placeholderText="Search this folder")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(self.apply_filter)
        self.search_icon = self.search.addAction(QIcon(), QLineEdit.LeadingPosition)
        self.view_button = QToolButton(autoRaise=True)
        self.view_button.setFixedSize(34, 34)
        self.view_button.setIconSize(QSize(18, 18))
        self.view_button.setCursor(Qt.PointingHandCursor)
        self.view_button.clicked.connect(
            lambda: self.set_view_mode("grid" if self.view_mode == "list" else "list"))
        self.preview_button = QToolButton(autoRaise=True)
        self.preview_button.setFixedSize(34, 34)
        self.preview_button.setIconSize(QSize(18, 18))
        self.preview_button.setCursor(Qt.PointingHandCursor)
        self.preview_button.clicked.connect(self.toggle_preview)

        header = QHBoxLayout()
        header.setContentsMargins(20, 12, 12, 10)
        header.setSpacing(8)
        header.addWidget(self.heading, 1)
        header.addWidget(self.search)
        header.addWidget(self.view_button)
        header.addWidget(self.preview_button)

        self.tree = QTreeView(objectName="files")
        self.tree.setModel(self.model)
        self.tree.setRootIsDecorated(False)
        self.tree.setItemsExpandable(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.AscendingOrder)
        self.tree.setAllColumnsShowFocus(True)
        head = self.tree.header()
        head.setStretchLastSection(False)
        head.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        head.setSectionResizeMode(0, QHeaderView.Stretch)
        for column, width in ((1, 100), (2, 140), (3, 170)):
            head.setSectionResizeMode(column, QHeaderView.Interactive)
            head.resizeSection(column, width)

        self.grid = QListView(objectName="files")
        self.grid.setModel(self.model)
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setMovement(QListView.Static)
        self.grid.setWordWrap(True)
        self.grid.setTextElideMode(Qt.ElideMiddle)
        self.grid.setLayoutMode(QListView.Batched)

        self.empty = QLabel(objectName="emptyState", alignment=Qt.AlignCenter, wordWrap=True)
        for view in (self.tree, self.grid, self.empty):
            view.setContextMenuPolicy(Qt.CustomContextMenu)
            view.customContextMenuRequested.connect(
                lambda pos, v=view: self.show_context_menu(v, pos))
        for view in (self.tree, self.grid):
            view.setSelectionMode(QAbstractItemView.ExtendedSelection)
            view.setEditTriggers(QAbstractItemView.NoEditTriggers)
            view.activated.connect(self.open_index)
            view.selectionModel().selectionChanged.connect(self.update_status)

        self.pages = QStackedWidget()
        for page in (self.tree, self.grid, self.empty):
            self.pages.addWidget(page)

        self.status = QLabel(objectName="statusText")
        status_row = QWidget(objectName="statusRow")
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(16, 6, 16, 6)
        status_layout.addWidget(self.status)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addLayout(header)
        right_layout.addWidget(self.pages, 1)
        right_layout.addWidget(status_row)

        splitter = QSplitter()
        self.preview = PreviewPane(self)
        self.preview.setVisible(window.settings.get("files_preview"))
        splitter.addWidget(self.sidebar)
        splitter.addWidget(right)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([210, 700, 280])
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self._build_actions()
        self.apply_filter()
        self.setZoomFactor(1.0)
        self.set_view_mode(self.view_mode)
        self.set_path(path)

    # ----- setup -------------------------------------------------------

    def _action(self, text, slot, shortcut=None) -> QAction:
        act = QAction(text, self)
        if isinstance(shortcut, QKeySequence.StandardKey):
            act.setShortcuts(shortcut)
        elif shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        act.setIconVisibleInMenu(False)
        act.triggered.connect(slot)
        self.addAction(act)
        return act

    def _build_actions(self):
        K = QKeySequence.StandardKey
        self.open_act = self._action("Open", self.open_selected)
        self.open_default_act = self._action("Open with default app", self.open_with_default)
        self.edit_act = self._action("Edit as text", self.edit_selected)
        self.cut_act = self._action("Cut", lambda: self.copy_selected(cut=True), K.Cut)
        self.copy_act = self._action("Copy", self.copy_selected, K.Copy)
        self.paste_act = self._action("Paste", self.paste, K.Paste)
        self.rename_act = self._action("Rename", self.rename_selected, "F2")
        self.trash_act = self._action("Move to Trash", self.trash_selected, K.Delete)
        self.new_folder_act = self._action("New folder", self.new_folder, "Ctrl+Shift+N")
        self.copy_path_act = self._action("Copy path", self.copy_path, "Ctrl+Shift+C")
        self._action("Search", lambda: self.search.setFocus(), K.Find)

    def _populate_sidebar(self):
        places = [
            ("Home", QStandardPaths.HomeLocation, "home"),
            ("Desktop", QStandardPaths.DesktopLocation, "desktop"),
            ("Documents", QStandardPaths.DocumentsLocation, "documents"),
            ("Downloads", QStandardPaths.DownloadLocation, "downloads"),
            ("Pictures", QStandardPaths.PicturesLocation, "pictures"),
            ("Music", QStandardPaths.MusicLocation, "music"),
            ("Videos", QStandardPaths.MoviesLocation, "videos"),
        ]
        home = os.path.normpath(QDir.homePath())
        self._add_heading("Places")
        for label, location, icon in places:
            path = QStandardPaths.writableLocation(location)
            if not path or not os.path.isdir(path):
                continue
            path = os.path.normpath(path)
            if label == "Home" or path != home:
                self._add_place(label, path, icon)

        self._add_heading("Drives")
        for volume in QStorageInfo.mountedVolumes():
            if not (volume.isValid() and volume.isReady()):
                continue
            root = volume.rootPath()
            if sys.platform == "win32":
                label = f"{volume.name() or 'Local Disk'} ({root[:2]})"
            elif root == "/":
                label = "File system"
            elif root.startswith(("/media/", "/mnt/", "/run/media/", "/Volumes/")):
                label = volume.displayName()
            else:
                continue
            self._add_place(label, os.path.normpath(root), "drive")

    def _add_heading(self, text: str):
        item = QListWidgetItem(text.upper())
        item.setFlags(Qt.NoItemFlags)
        font = item.font()
        font.setPointSizeF(font.pointSizeF() * 0.8)
        font.setBold(True)
        item.setFont(font)
        self.sidebar.addItem(item)

    def _add_place(self, label: str, path: str, icon: str):
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, path)
        item.setData(Qt.UserRole + 1, icon)
        item.setToolTip(QDir.toNativeSeparators(path))
        self.sidebar.addItem(item)

    def refresh_icons(self):
        icon = self._window.icon
        # The model doesn't take ownership, so keep the provider alive.
        self._icon_provider = FileIcons(self._window.colors)
        self.model.setIconProvider(self._icon_provider)
        self.view_button.setIcon(icon("grid" if self.view_mode == "list" else "list"))
        self.preview_button.setIcon(icon("panel"))
        self.preview_button.setToolTip(
            "Hide preview" if self.preview.isVisible() else "Show preview")
        self.search_icon.setIcon(icon("search", muted=True))
        for row in range(self.sidebar.count()):
            item = self.sidebar.item(row)
            name = item.data(Qt.UserRole + 1)
            if name:
                item.setIcon(icon(name))
        self.iconChanged.emit(icon("folder"))

    # ----- tab interface shared with BrowserTab --------------------------

    def title(self) -> str:
        return QDir(self.path).dirName() or QDir.toNativeSeparators(self.path)

    def url(self) -> QUrl:
        return QUrl.fromLocalFile(self.path)

    def location(self) -> str:
        return QDir.toNativeSeparators(self.path)

    def address_icon_name(self) -> str:
        return "folder"

    def can_go_back(self) -> bool:
        return bool(self._back)

    def can_go_forward(self) -> bool:
        return bool(self._forward)

    def can_go_up(self) -> bool:
        return os.path.dirname(self.path) != self.path

    def clear_history(self):
        self._back.clear()
        self._forward.clear()

    def back(self):
        if self._back:
            self._forward.append(self.path)
            self._show(self._back.pop())

    def forward(self):
        if self._forward:
            self._back.append(self.path)
            self._show(self._forward.pop())

    def up(self):
        if self.can_go_up():
            self.set_path(os.path.dirname(self.path))

    def reload(self):
        self._show(self.path)

    def stop(self):
        pass

    def zoomFactor(self) -> float:
        return self._zoom

    def setZoomFactor(self, factor: float):
        self._zoom = factor
        small, large = round(20 * factor), round(64 * factor)
        self.tree.setIconSize(QSize(small, small))
        self.grid.setIconSize(QSize(large, large))
        self.grid.setGridSize(QSize(max(large * 2, 112) + 16, large + 56))

    def focus_view(self):
        self.pages.currentWidget().setFocus()

    # ----- navigation ----------------------------------------------------

    def set_path(self, path: str) -> bool:
        path = os.path.normpath(path)
        if not os.path.isdir(path):
            self.flash(f"Folder not found: {QDir.toNativeSeparators(path)}")
            return False
        if self.path and path != self.path:
            self._back.append(self.path)
            self._forward.clear()
        self._show(path)
        return True

    def _show(self, path: str):
        self.path = path
        self._loaded = False
        self._readable = QDir(path).isReadable()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.model.setNameFilters([])
        root = self.model.setRootPath(path)
        self.tree.setRootIndex(root)
        self.grid.setRootIndex(root)
        self.heading.setText(self.title())
        self._sync_sidebar()
        self.titleChanged.emit(self.title())
        self.urlChanged.emit(self.url())
        self.update_status()
        # directoryLoaded isn't re-emitted for folders the model already cached.
        QTimer.singleShot(600, lambda p=path: self._on_directory_loaded(p))

    def _on_directory_loaded(self, path: str):
        if os.path.normpath(path) == self.path:
            self._loaded = True
            self.update_status()
            self._try_reveal()

    def reveal(self, path: str):
        """Select `path` (a file in this folder) as soon as it shows up."""
        self._reveal = os.path.normpath(path)
        self._try_reveal()

    def _try_reveal(self):
        if not self._reveal:
            return
        index = self.model.index(self._reveal)
        if index.isValid():
            view = self.current_view()
            view.setCurrentIndex(index)
            view.scrollTo(index)
            self._reveal = ""

    def _on_sidebar_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            self.set_path(path)

    def _sync_sidebar(self):
        self.sidebar.clearSelection()
        for row in range(self.sidebar.count()):
            item = self.sidebar.item(row)
            if item.data(Qt.UserRole) == self.path:
                item.setSelected(True)
                break

    def set_view_mode(self, mode: str):
        self.view_mode = mode
        self._window.settings.set("files_view", mode)
        self.view_button.setToolTip("Show as grid" if mode == "list" else "Show as list")
        self.refresh_icons()
        self.update_status()

    def apply_filter(self, *_):
        flags = QDir.AllEntries | QDir.NoDotAndDotDot
        if self._window.settings.get("show_hidden"):
            flags |= QDir.Hidden
        self.model.setFilter(flags)
        text = self.search.text().strip()
        self.model.setNameFilters([f"*{text}*"] if text else [])
        self.update_status()

    # ----- status ------------------------------------------------------

    def current_view(self) -> QAbstractItemView:
        return self.tree if self.view_mode == "list" else self.grid

    def update_status(self, *_):
        if not self.path:
            return
        count = self.model.rowCount(self.model.index(self.path))
        query = self.search.text().strip()
        if not self._readable:
            self.empty.setText("You don't have permission to open this folder.")
        elif query:
            self.empty.setText(f"No items match \u201c{query}\u201d")
        else:
            self.empty.setText("This folder is empty")
        show_empty = count == 0 and (self._loaded or not self._readable)
        self.pages.setCurrentWidget(self.empty if show_empty else self.current_view())

        if count == 0 and not self._loaded and self._readable:
            self.status.setText("Loading…")
            return
        text = plural(count, "item")
        selected = self.selected_indexes()
        if selected:
            size = sum(self.model.size(i) for i in selected if not self.model.isDir(i))
            text += f"  ·  {len(selected)} selected"
            if size:
                text += f" ({QLocale().formattedDataSize(size)})"
        self.status.setText(text)
        self.update_preview()

    def toggle_preview(self):
        visible = not self.preview.isVisible()
        self.preview.setVisible(visible)
        self._window.settings.set("files_preview", visible)
        self.refresh_icons()
        self.update_preview()

    def update_preview(self):
        """Paint the preview now, then fold the next burst of updates into one follow-up."""
        if not self.preview.isVisible():
            return
        if self._preview_timer.isActive():
            self._preview_again = True
            return
        self._render_preview()
        self._preview_timer.start()

    def _flush_preview(self):
        if not self._preview_again:
            return
        self._preview_again = False
        if self.preview.isVisible():
            self._render_preview()
        self._preview_timer.start()

    def _render_preview(self):
        locale = QLocale()
        selected = self.selected_indexes()
        if len(selected) > 1:
            size = sum(self.model.size(i) for i in selected if not self.model.isDir(i))
            rows = [("Size", locale.formattedDataSize(size))] if size else []
            self.preview.show_info(f"{len(selected)} items selected", rows, "documents")
            return
        if selected:
            index = selected[0]
            info = self.model.fileInfo(index)
            path = info.absoluteFilePath()
        else:
            index = None
            info = QFileInfo(self.path)
            path = self.path
        rows = [("Kind", self.model.type(index) if index else "Folder")]
        if info.isDir():
            count = len(QDir(path).entryList(QDir.AllEntries | QDir.NoDotAndDotDot))
            rows.append(("Contains", plural(count, "item")))
        else:
            rows.append(("Size", locale.formattedDataSize(info.size())))
        image_path = ""
        if info.isFile() and has_thumbnail(path):
            dimensions = QImageReader(path).size()
            if dimensions.isValid():
                rows.append(("Dimensions", f"{dimensions.width()} × {dimensions.height()}"))
            image_path = path
        rows.append(("Modified", locale.toString(info.lastModified(), QLocale.ShortFormat)))
        rows.append(("Where", QDir.toNativeSeparators(info.absolutePath())))
        if info.isDir():
            icon = "folder"
        else:
            ext = "." + info.suffix().lower()
            icon = next((k for k, exts in FILE_KINDS.items() if ext in exts), "file")
        self.preview.show_info(info.fileName() or self.title(), rows, icon, image_path)

    def flash(self, message: str):
        self.status.setText(message)
        QTimer.singleShot(3000, self.update_status)

    # ----- file actions --------------------------------------------------

    def selected_indexes(self) -> list:
        selection = self.current_view().selectionModel().selectedIndexes()
        return [i for i in selection if i.column() == 0]

    def selected_paths(self) -> list:
        return [self.model.filePath(i) for i in self.selected_indexes()]

    def open_index(self, index: QModelIndex):
        path = self.model.filePath(index)
        if self.model.isDir(index):
            self.set_path(path)
        else:
            self._window.open_file(path)

    def open_selected(self):
        paths = self.selected_paths()
        if len(paths) == 1 and os.path.isdir(paths[0]):
            self.set_path(paths[0])
            return
        for path in paths:
            if os.path.isdir(path):
                self._window.add_tab(QUrl.fromLocalFile(path))
            else:
                self._window.open_file(path)

    def edit_selected(self):
        for path in self.selected_paths():
            if not os.path.isdir(path):
                self._window.open_in_editor(path)

    def open_with_default(self):
        for path in self.selected_paths():
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def copy_selected(self, cut: bool = False):
        paths = self.selected_paths()
        if not paths:
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
        mime.setText("\n".join(QDir.toNativeSeparators(p) for p in paths))
        QGuiApplication.clipboard().setMimeData(mime)
        FilesTab.cut_paths = {os.path.normpath(p) for p in paths} if cut else set()
        self.flash(f"{'Cut' if cut else 'Copied'} {plural(len(paths), 'item')}")

    def copy_path(self):
        paths = self.selected_paths() or [self.path]
        QGuiApplication.clipboard().setText(
            "\n".join(QDir.toNativeSeparators(p) for p in paths))
        self.flash("Path copied")

    def clipboard_paths(self) -> list:
        mime = QGuiApplication.clipboard().mimeData()
        if mime is None or not mime.hasUrls():
            return []
        return [os.path.normpath(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]

    def paste(self):
        sources = self.clipboard_paths()
        if not sources:
            return
        moving = all(src in FilesTab.cut_paths for src in sources)
        done, errors = 0, []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for src in sources:
                name = os.path.basename(src)
                if not os.path.lexists(src):
                    continue
                if moving and os.path.dirname(src) == self.path:
                    continue
                if os.path.isdir(src) and (self.path + os.sep).startswith(src + os.sep):
                    errors.append(f"Can't put \u201c{name}\u201d inside itself.")
                    continue
                dest = os.path.join(self.path, unique_name(self.path, name))
                try:
                    if moving:
                        shutil.move(src, dest)
                    elif os.path.isdir(src) and not os.path.islink(src):
                        shutil.copytree(src, dest, symlinks=True)
                    else:
                        shutil.copy2(src, dest, follow_symlinks=False)
                    done += 1
                except OSError as error:
                    errors.append(f"{name}: {error.strerror or error}")
        finally:
            QApplication.restoreOverrideCursor()
        if moving:
            FilesTab.cut_paths = set()
            QGuiApplication.clipboard().clear()
        if errors:
            QMessageBox.warning(self, "Paste", "\n".join(errors))
        if done:
            self.flash(f"{'Moved' if moving else 'Copied'} {plural(done, 'item')}")

    def rename_selected(self):
        view = self.current_view()
        index = view.currentIndex().siblingAtColumn(0)
        if index.isValid():
            view.edit(index)

    def new_folder(self):
        name = unique_name(self.path, "New folder")
        index = self.model.mkdir(self.model.index(self.path), name)
        if not index.isValid():
            QMessageBox.warning(self, "New folder", "Couldn't create a folder here.")
            return
        view = self.current_view()
        view.setCurrentIndex(index)
        view.scrollTo(index)
        view.edit(index)

    def trash_selected(self):
        paths = self.selected_paths()
        if not paths:
            return
        trashed, failed = 0, []
        for path in paths:
            result = QFile.moveToTrash(path)
            ok = result[0] if isinstance(result, tuple) else result
            if ok:
                trashed += 1
            else:
                failed.append(path)
        if failed:
            answer = QMessageBox.question(
                self, "Delete permanently?",
                f"{plural(len(failed), 'item')} couldn't be moved to the trash.\n"
                "Delete permanently? This can't be undone.")
            if answer == QMessageBox.Yes:
                for path in failed:
                    try:
                        if os.path.isdir(path) and not os.path.islink(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                        trashed += 1
                    except OSError as error:
                        QMessageBox.warning(self, "Delete", f"{os.path.basename(path)}: {error}")
        if trashed:
            self.flash(f"Removed {plural(trashed, 'item')}")

    # ----- open with -----------------------------------------------------

    def open_with_menu(self, paths: list):
        folders = [p for p in paths if os.path.isdir(p)]
        if folders and len(paths) > 1:
            return None
        menu = QMenu("Open with", self)

        def add(text, slot):
            menu.addAction(text).triggered.connect(slot)

        if folders:
            add("New tab", lambda: self._window.add_tab(QUrl.fromLocalFile(folders[0])))
            add(SYSTEM_FILE_MANAGER, self.open_with_default)
            return menu

        if not all(has_thumbnail(p) and not p.lower().endswith(".svg") for p in paths):
            add("Text editor", self.edit_selected)
        add("Browser tab", lambda: self.open_in_browser(paths))
        add("Default app", self.open_with_default)
        ext = common_extension(paths)
        apps = remembered_apps(self._window.settings, ext) if ext is not None else []
        if apps:
            menu.addSeparator()
            for app in apps:
                add(app_name(app), lambda _checked=False, a=app: self.launch_app(a, paths))
        menu.addSeparator()
        if sys.platform == "win32" and len(paths) == 1:
            add("Choose another app…", lambda: QProcess.startDetached(
                "rundll32.exe", ["shell32.dll,OpenAs_RunDLL", QDir.toNativeSeparators(paths[0])]))
        add("Browse for an app…", lambda: self.browse_for_app(paths))
        return menu

    def open_in_browser(self, paths: list):
        for path in paths:
            self._window.add_tab(QUrl.fromLocalFile(path))

    def browse_for_app(self, paths: list):
        if sys.platform == "win32":
            start, filters = os.environ.get("ProgramFiles", "C:\\"), "Programs (*.exe)"
        elif sys.platform == "darwin":
            start, filters = "/Applications", "Applications (*.app)"
        else:
            start, filters = "/usr/bin", "All files (*)"
        app, _filter = QFileDialog.getOpenFileName(self, "Choose an app", start, filters)
        if not app:
            return
        ext = common_extension(paths)
        if ext is not None:
            remember_app(self._window.settings, ext, os.path.normpath(app))
        self.launch_app(os.path.normpath(app), paths)

    def launch_app(self, app: str, paths: list):
        native = [QDir.toNativeSeparators(p) for p in paths]
        if sys.platform == "darwin":
            program, args = "open", ["-a", app, *native]
        else:
            program, args = app, native
        result = QProcess.startDetached(program, args)
        ok = result[0] if isinstance(result, tuple) else result
        if not ok:
            QMessageBox.warning(self, "Open with", f"Couldn't start {app_name(app)}.")

    def show_context_menu(self, source: QWidget, pos: QPoint):
        is_item_view = isinstance(source, QAbstractItemView)
        index = source.indexAt(pos) if is_item_view else QModelIndex()
        menu = QMenu(self)
        self.paste_act.setEnabled(bool(self.clipboard_paths()))
        if index.isValid():
            if not source.selectionModel().isSelected(index):
                source.setCurrentIndex(index)
            paths = self.selected_paths()
            single = len(paths) == 1
            menu.addAction(self.open_act)
            open_with = self.open_with_menu(paths)
            if open_with is not None:
                menu.addMenu(open_with)
            menu.addSeparator()
            menu.addActions([self.cut_act, self.copy_act, self.paste_act])
            menu.addSeparator()
            if single:
                menu.addAction(self.rename_act)
            menu.addAction(self.trash_act)
            if single:
                folder = paths[0] if os.path.isdir(paths[0]) else os.path.dirname(paths[0])
                menu.addSeparator()
                menu.addAction("Open in terminal", lambda p=folder: self._window.new_terminal(p))
            menu.addSeparator()
            menu.addAction(self.copy_path_act)
        else:
            if is_item_view:
                source.clearSelection()
            menu.addAction(self.new_folder_act)
            menu.addAction(self.paste_act)
            menu.addSeparator()
            for mode, label in (("list", "View as list"), ("grid", "View as grid")):
                act = menu.addAction(label)
                act.setCheckable(True)
                act.setChecked(self.view_mode == mode)
                act.triggered.connect(lambda _checked=False, m=mode: self.set_view_mode(m))
            menu.addAction(self._window.hidden_act)
            menu.addSeparator()
            menu.addAction("Open in terminal", lambda: self._window.new_terminal(self.path))
            menu.addAction(self.copy_path_act)
        widget = source.viewport() if is_item_view else source
        menu.exec(widget.mapToGlobal(pos))


class LineNumbers(QWidget):
    def __init__(self, editor: CodeEditor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


class CodeEditor(QPlainTextEdit):
    """Plain-text editor with line numbers, current-line highlight, and auto-indent."""

    def __init__(self):
        super().__init__(objectName="editor")
        self.colors = LIGHT
        self.search_highlights: list = []
        self.gutter = LineNumbers(self)
        self.document().setDocumentMargin(8)
        self.blockCountChanged.connect(self._update_margins)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self.highlight)
        self._update_margins()

    def set_colors(self, colors: dict):
        self.colors = colors
        self.highlight()
        self.gutter.update()

    def gutter_width(self) -> int:
        digits = max(3, len(str(self.blockCount())))
        return 20 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margins(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margins()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor(self.colors["surface"]))
        painter.setFont(self.font())
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        line_height = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                color = self.colors["muted"] if number == current else self.colors["disabled"]
                painter.setPen(QColor(color))
                painter.drawText(0, top, self.gutter.width() - 10, line_height,
                                 Qt.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1
        painter.end()

    def highlight(self):
        line = QTextEdit.ExtraSelection()
        line.format.setBackground(QColor(self.colors["line"]))
        line.format.setProperty(QTextFormat.FullWidthSelection, True)
        line.cursor = self.textCursor()
        line.cursor.clearSelection()
        self.setExtraSelections([line] + self.search_highlights)
        self.gutter.update()

    def keyPressEvent(self, event):
        plain = event.modifiers() in (Qt.NoModifier, Qt.KeypadModifier)
        cursor = self.textCursor()
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and plain:
            text = cursor.block().text()
            indent = text[:len(text) - len(text.lstrip(" \t"))]
            cursor.insertText("\n" + indent[:cursor.positionInBlock()])
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            return
        if event.key() == Qt.Key_Tab and plain and not cursor.hasSelection():
            cursor.insertText("    ")
            return
        super().keyPressEvent(event)


class EditorTab(QWidget):
    """A text file editor that plugs into the same tab strip and toolbar as web pages."""

    titleChanged = Signal(str)
    urlChanged = Signal(QUrl)
    iconChanged = Signal(QIcon)

    def __init__(self, window: BrowserWindow, path: str | None = None,
                 text: str = "", crlf: bool = False):
        super().__init__()
        self._window = window
        self.loading = False
        self.progress = 0
        self.path = path
        self._crlf = crlf
        self._zoom = 1.0
        self._base_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self._base_size = max(11.0, self._base_font.pointSizeF())

        self.editor = CodeEditor()
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self.editor.document().modificationChanged.connect(self._on_modified)
        self.editor.cursorPositionChanged.connect(self.update_status)
        self.editor.textChanged.connect(self.update_status)
        self.set_word_wrap(window.settings.get("word_wrap"))

        self.find_field = QLineEdit(objectName="search", placeholderText="Find")
        self.find_field.setClearButtonEnabled(True)
        self.find_field.setFixedWidth(220)
        self.find_field.textChanged.connect(self._find_as_you_type)
        self.find_field.returnPressed.connect(self.find_next)
        self.find_icon = self.find_field.addAction(QIcon(), QLineEdit.LeadingPosition)
        self.find_count = QLabel(objectName="findCount")
        self.replace_field = QLineEdit(objectName="search", placeholderText="Replace with")
        self.replace_field.setFixedWidth(200)
        self.replace_field.returnPressed.connect(self.replace_one)

        self.prev_button = self._icon_button("Previous match (Shift+F3)", self.find_previous)
        self.next_button = self._icon_button("Next match (F3)", self.find_next)
        self.close_find_button = self._icon_button("Close (Esc)", self.hide_find)
        replace_button = self._text_button("Replace", self.replace_one)
        replace_all_button = self._text_button("Replace all", self.replace_all)

        self.find_bar = QWidget(objectName="findBar")
        find_layout = QHBoxLayout(self.find_bar)
        find_layout.setContentsMargins(12, 6, 8, 6)
        find_layout.setSpacing(4)
        find_layout.addWidget(self.find_field)
        find_layout.addWidget(self.find_count)
        find_layout.addWidget(self.prev_button)
        find_layout.addWidget(self.next_button)
        find_layout.addSpacing(12)
        find_layout.addWidget(self.replace_field)
        find_layout.addWidget(replace_button)
        find_layout.addWidget(replace_all_button)
        find_layout.addStretch(1)
        find_layout.addWidget(self.close_find_button)
        self.find_bar.hide()

        self.state = QLabel(objectName="statusText")
        self.position = QLabel(objectName="statusText")
        status_row = QWidget(objectName="statusRow")
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(16, 6, 16, 6)
        status_layout.addWidget(self.state, 1)
        status_layout.addWidget(self.position)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.find_bar)
        layout.addWidget(self.editor, 1)
        layout.addWidget(status_row)

        K = QKeySequence.StandardKey
        self._shortcut(self, K.Find, self.show_find)
        self._shortcut(self, K.FindNext, self.find_next)
        self._shortcut(self, K.FindPrevious, self.find_previous)
        self._shortcut(self.find_bar, "Escape", self.hide_find)

        self.setZoomFactor(1.0)
        self.update_status()

    def _shortcut(self, widget: QWidget, keys, slot):
        act = QAction(widget)
        if isinstance(keys, QKeySequence.StandardKey):
            act.setShortcuts(keys)
        else:
            act.setShortcut(QKeySequence(keys))
        act.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        act.triggered.connect(slot)
        widget.addAction(act)

    def _icon_button(self, tip: str, slot) -> QToolButton:
        button = QToolButton(autoRaise=True, toolTip=tip)
        button.setFixedSize(30, 30)
        button.setIconSize(QSize(16, 16))
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def _text_button(self, text: str, slot) -> QToolButton:
        button = QToolButton(objectName="textButton", autoRaise=True, text=text)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def refresh_icons(self):
        icon = self._window.icon
        self.find_icon.setIcon(icon("search", muted=True))
        self.prev_button.setIcon(icon("chevron-up"))
        self.next_button.setIcon(icon("chevron-down"))
        self.close_find_button.setIcon(icon("close"))
        self.editor.set_colors(self._window.colors)
        self._highlight_matches()
        self.iconChanged.emit(icon("edit"))

    # ----- tab interface shared with BrowserTab --------------------------

    def file_name(self) -> str:
        return os.path.basename(self.path) if self.path else "Untitled"

    def is_modified(self) -> bool:
        return self.editor.document().isModified()

    def title(self) -> str:
        return ("• " if self.is_modified() else "") + self.file_name()

    def url(self) -> QUrl:
        return QUrl.fromLocalFile(self.path) if self.path else QUrl()

    def location(self) -> str:
        return QDir.toNativeSeparators(self.path) if self.path else "Untitled"

    def address_icon_name(self) -> str:
        return "edit"

    def can_go_back(self) -> bool:
        return False

    def can_go_forward(self) -> bool:
        return False

    def clear_history(self):
        pass

    def back(self):
        pass

    def forward(self):
        pass

    def stop(self):
        pass

    def reload(self):
        if not self.path:
            return
        if self.is_modified():
            answer = QMessageBox.question(
                self, "Reload file", f"Discard your changes to \u201c{self.file_name()}\u201d "
                "and reload it from disk?")
            if answer != QMessageBox.Yes:
                return
        try:
            text, self._crlf = read_text_file(self.path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Reload file", f"Couldn't reload the file: {error}")
            return
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self.flash("Reloaded from disk")

    def zoomFactor(self) -> float:
        return self._zoom

    def setZoomFactor(self, factor: float):
        self._zoom = factor
        font = QFont(self._base_font)
        font.setPointSizeF(self._base_size * factor)
        self.editor.setFont(font)
        self.editor.setTabStopDistance(QFontMetricsF(font).horizontalAdvance(" ") * 4)
        self.editor._update_margins()

    def focus_view(self):
        self.editor.setFocus()

    def set_word_wrap(self, wrap: bool):
        self.editor.setLineWrapMode(
            QPlainTextEdit.WidgetWidth if wrap else QPlainTextEdit.NoWrap)

    # ----- saving --------------------------------------------------------

    def _on_modified(self, _modified: bool):
        self.titleChanged.emit(self.title())
        self.update_status()

    def save(self) -> bool:
        if not self.path:
            return self.save_as()
        text = self.editor.toPlainText()
        if self._crlf:
            text = text.replace("\n", "\r\n")
        try:
            with open(self.path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        except OSError as error:
            QMessageBox.warning(self, "Save", f"Couldn't save \u201c{self.file_name()}\u201d: "
                                f"{error.strerror or error}")
            return False
        self.editor.document().setModified(False)
        self.flash("Saved")
        return True

    def save_as(self) -> bool:
        start = self.path or os.path.join(
            QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or QDir.homePath(),
            "Untitled.txt")
        path, _filter = QFileDialog.getSaveFileName(self, "Save as", start)
        if not path:
            return False
        self.path = os.path.normpath(path)
        saved = self.save()
        self.titleChanged.emit(self.title())
        self.urlChanged.emit(self.url())
        return saved

    def maybe_close(self) -> bool:
        """Ask about unsaved changes; returns False if the user cancels."""
        if not self.is_modified():
            return True
        self._window.show_view(self)
        answer = QMessageBox.question(
            self, "Unsaved changes", f"Save changes to \u201c{self.file_name()}\u201d?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if answer == QMessageBox.Save:
            return self.save()
        return answer == QMessageBox.Discard

    # ----- status ------------------------------------------------------

    def update_status(self, *_):
        cursor = self.editor.textCursor()
        chars = self.editor.document().characterCount() - 1
        self.position.setText(
            f"Ln {cursor.blockNumber() + 1}, Col {cursor.positionInBlock() + 1}  ·  "
            f"{plural(chars, 'character')}  ·  UTF-8")
        if not self.path:
            self.state.setText("Not saved yet")
        elif self.is_modified():
            self.state.setText("Unsaved changes")
        else:
            self.state.setText(self.location())

    def flash(self, message: str):
        self.state.setText(message)
        QTimer.singleShot(2500, self.update_status)

    # ----- find & replace ----------------------------------------------

    def show_find(self):
        self.find_bar.show()
        selected = self.editor.textCursor().selectedText()
        if selected and "\u2029" not in selected:
            self.find_field.setText(selected)
        self.find_field.setFocus()
        self.find_field.selectAll()
        self._highlight_matches()

    def hide_find(self):
        self.find_bar.hide()
        self.editor.search_highlights = []
        self.editor.highlight()
        self.editor.setFocus()

    def _find(self, backward: bool = False) -> bool:
        query = self.find_field.text()
        if not query:
            return False
        flags = QTextDocument.FindBackward if backward else QTextDocument.FindFlag(0)
        if self.editor.find(query, flags):
            return True
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.End if backward else QTextCursor.Start)
        self.editor.setTextCursor(cursor)
        return self.editor.find(query, flags)

    def find_next(self):
        if not self.find_bar.isVisible():
            self.show_find()
            return
        self._find()
        self._highlight_matches()

    def find_previous(self):
        self._find(backward=True)
        self._highlight_matches()

    def _find_as_you_type(self, _text: str):
        cursor = self.editor.textCursor()
        cursor.setPosition(cursor.selectionStart())
        self.editor.setTextCursor(cursor)
        self._find()
        self._highlight_matches()

    def _highlight_matches(self):
        query = self.find_field.text()
        highlights = []
        if query and self.find_bar.isVisible():
            document = self.editor.document()
            cursor = document.find(query)
            while not cursor.isNull() and len(highlights) < 5000:
                match = QTextEdit.ExtraSelection()
                match.format.setBackground(QColor(self.editor.colors["match"]))
                match.cursor = cursor
                highlights.append(match)
                cursor = document.find(query, cursor)
            self.find_count.setText(plural(len(highlights), "match"))
        else:
            self.find_count.setText("")
        self.editor.search_highlights = highlights
        self.editor.highlight()

    def replace_one(self):
        query = self.find_field.text()
        if not query:
            return
        cursor = self.editor.textCursor()
        if cursor.selectedText().lower() == query.lower():
            cursor.insertText(self.replace_field.text())
        self._find()
        self._highlight_matches()

    def replace_all(self):
        query = self.find_field.text()
        if not query:
            return
        document = self.editor.document()
        count = 0
        edit = QTextCursor(document)
        edit.beginEditBlock()
        cursor = document.find(query)
        while not cursor.isNull():
            cursor.insertText(self.replace_field.text())
            count += 1
            cursor = document.find(query, cursor)
        edit.endEditBlock()
        self._highlight_matches()
        self.flash(f"Replaced {plural(count, 'match')}")


# ----- terminal ----------------------------------------------------------
# Qt has no terminal widget, and the usual one (QTermWidget) has no PySide6
# bindings, so this is a small VT100/xterm emulator: a screen that parses the
# program's output, a view that draws it, and a pty the shell runs on.

DEFAULT_ATTR = (None, None, 0)
BLANK = (" ", DEFAULT_ATTR)
BOLD, DIM, ITALIC, UNDERLINE, INVERSE, HIDDEN, STRIKE = 1, 2, 4, 8, 16, 32, 64
TRUECOLOR = 1 << 24
MAX_SCROLLBACK = 5000
DEC_GRAPHICS = str.maketrans("`afgjklmnopqrstuvwxyz{|}~", "◆▒°±┘┐┌└┼⎺⎻─⎼⎽├┤┴┬│≤≥π≠£·")
PRINTABLE_RUN = re.compile(r"[^\x00-\x1f\x7f]+")
STRING_END = re.compile(r"[\x07\x1b]")

ANSI_LIGHT = ["#1f2329", "#c4262e", "#24803a", "#9a6700", "#1f5fd6", "#9333c8", "#0b7f8a", "#a8afb9",
              "#5c6470", "#e5484d", "#2fa45a", "#b88400", "#4c82f7", "#b65ad9", "#13a3b0", "#d5dbe3"]
ANSI_DARK = ["#3a3e47", "#ff6b6b", "#7bd88f", "#f2c55c", "#7aa7ff", "#d38aea", "#5fd7d7", "#d5d9e0",
             "#6c7280", "#ff8f8f", "#9be8aa", "#ffd77a", "#a2c0ff", "#e4abf3", "#8ae8e8", "#ffffff"]


class TermLine(list):
    """One row of (character, attribute) cells. `wrapped` means it continues on the next row."""

    __slots__ = ("wrapped",)

    def __init__(self, cells):
        super().__init__(cells)
        self.wrapped = False


class TermScreen:
    """Parses a program's output into a grid of cells, plus scrollback."""

    def __init__(self, cols: int = 80, rows: int = 24):
        self.cols, self.rows = cols, rows
        self.scrollback: list = []
        self.base = 0  # absolute index of scrollback[0], so a selection survives trimming
        self.title = ""
        self.cwd = ""
        self.reply = lambda text: None
        self.reset()

    def reset(self):
        self.attr = DEFAULT_ATTR
        self.lines = [self.blank_line() for _ in range(self.rows)]
        self.main_lines = None
        self.using_alt = False
        self.x = self.y = 0
        self.wrapnext = False
        self.top, self.bottom = 0, self.rows - 1
        self.saved = None
        self.autowrap = True
        self.cursor_visible = True
        self.app_cursor = False
        self.bracketed_paste = False
        self.insert_mode = False
        self.charsets = ["B", "B"]
        self.shift = 0
        self.last_char = " "
        self.tabs = set(range(8, self.cols, 8))
        self.state = "ground"
        self.buf = ""

    def erase_cell(self):
        return (" ", (None, self.attr[1], 0)) if self.attr[1] is not None else BLANK

    def blank_line(self) -> TermLine:
        return TermLine([self.erase_cell()] * self.cols)

    def push_scrollback(self, line: TermLine):
        self.scrollback.append(line)
        if len(self.scrollback) > MAX_SCROLLBACK + 500:
            del self.scrollback[:500]
            self.base += 500

    def clear_scrollback(self):
        self.base += len(self.scrollback)
        self.scrollback.clear()

    def scroll_up(self, n: int = 1):
        for _ in range(min(n, self.bottom - self.top + 1)):
            line = self.lines.pop(self.top)
            if self.top == 0 and not self.using_alt:
                self.push_scrollback(line)
            self.lines.insert(self.bottom, self.blank_line())

    def scroll_down(self, n: int = 1):
        for _ in range(min(n, self.bottom - self.top + 1)):
            self.lines.pop(self.bottom)
            self.lines.insert(self.top, self.blank_line())

    def linefeed(self):
        self.wrapnext = False
        if self.y == self.bottom:
            self.scroll_up()
        elif self.y < self.rows - 1:
            self.y += 1

    def reverse_index(self):
        self.wrapnext = False
        if self.y == self.top:
            self.scroll_down()
        elif self.y > 0:
            self.y -= 1

    def _wrap(self):
        self.wrapnext = False
        if self.autowrap:
            self.lines[self.y].wrapped = True
            self.x = 0
            self.linefeed()

    def save_cursor(self):
        self.saved = (self.x, self.y, self.attr, self.wrapnext, list(self.charsets), self.shift)

    def restore_cursor(self):
        if self.saved is None:
            self.x = self.y = 0
            self.attr = DEFAULT_ATTR
            return
        self.x, self.y, self.attr, self.wrapnext, charsets, self.shift = self.saved
        self.charsets = list(charsets)
        self.x = min(self.x, self.cols - 1)
        self.y = min(self.y, self.rows - 1)

    def set_alt_screen(self, on: bool, save: bool):
        if on == self.using_alt:
            return
        if on:
            if save:
                self.save_cursor()
            self.main_lines = self.lines
            self.lines = [self.blank_line() for _ in range(self.rows)]
        else:
            self.lines = self.main_lines
            self.main_lines = None
            if save:
                self.restore_cursor()
        self.using_alt = on
        self.wrapnext = False

    def resize(self, cols: int, rows: int):
        if (cols, rows) == (self.cols, self.rows) or cols < 2 or rows < 2:
            return
        old_rows = self.rows
        self.cols, self.rows = cols, rows

        def adjust(lines: list, cursor: int, main: bool) -> int:
            if rows < old_rows:
                extra = old_rows - rows
                while extra and len(lines) - 1 > cursor and not "".join(
                        cell[0] for cell in lines[-1]).strip():
                    lines.pop()
                    extra -= 1
                for _ in range(extra):
                    line = lines.pop(0)
                    if main:
                        self.push_scrollback(line)
                    cursor -= 1
            elif rows > old_rows:
                extra = rows - old_rows
                if main:
                    pulled = min(extra, len(self.scrollback))
                    for _ in range(pulled):
                        lines.insert(0, self.scrollback.pop())
                    cursor += pulled
                    extra -= pulled
                lines.extend(TermLine([BLANK] * cols) for _ in range(extra))
            for line in lines:
                if len(line) < cols:
                    line.extend([BLANK] * (cols - len(line)))
                elif len(line) > cols:
                    del line[cols:]
            return max(0, cursor)

        if self.using_alt:
            self.y = adjust(self.lines, self.y, False)
            adjust(self.main_lines, old_rows - 1, True)
        else:
            self.y = adjust(self.lines, self.y, True)
        self.x = min(self.x, cols - 1)
        self.y = min(self.y, rows - 1)
        self.top, self.bottom = 0, rows - 1
        self.wrapnext = False
        self.tabs = set(range(8, cols, 8))

    def feed(self, data: str):
        i, n = 0, len(data)
        while i < n:
            state = self.state
            if state == "ground":
                match = PRINTABLE_RUN.match(data, i)
                if match:
                    self.write_text(match.group())
                    i = match.end()
                else:
                    self.control(data[i])
                    i += 1
            elif state in ("osc", "string"):
                match = STRING_END.search(data, i)
                end = match.start() if match else n
                if state == "osc" and len(self.buf) < 4096:
                    self.buf += data[i:end]
                i = end
                if match:
                    if data[end] == "\x1b":
                        self.state = state + "_esc"
                    else:
                        self.end_string()
                    i += 1
            elif state in ("osc_esc", "string_esc"):
                self.end_string()
                if data[i] != "\\":
                    self.state = "esc"
                    continue
                i += 1
            else:
                ch = data[i]
                i += 1
                if ch < " " and state != "charset":
                    if ch == "\x1b":
                        self.state = "esc"
                    elif ch in "\x18\x1a":
                        self.state = "ground"
                    else:
                        self.control(ch)
                elif state == "esc":
                    self.escape(ch)
                elif state == "csi":
                    if "@" <= ch <= "~":
                        self.state = "ground"
                        self.csi(self.buf, ch)
                    elif len(self.buf) < 256:
                        self.buf += ch
                elif state == "charset":
                    self.charsets[self.buf_index] = ch
                    self.state = "ground"
                else:  # "skip": the byte after ESC #, ESC % or ESC space
                    self.state = "ground"

    def end_string(self):
        if self.state.startswith("osc"):
            self.osc(self.buf)
        self.state = "ground"

    def write_text(self, text: str):
        if self.charsets[self.shift] == "0":
            text = text.translate(DEC_GRAPHICS)
        if not text.isascii() or self.insert_mode:
            for ch in text:
                self._put(ch)
            return
        attr = self.attr
        chunk = ""
        while text:
            if self.wrapnext:
                self._wrap()
                if self.wrapnext:
                    break
            line = self.lines[self.y]
            room = self.cols - self.x
            chunk, text = text[:room], text[room:]
            line[self.x:self.x + len(chunk)] = [(ch, attr) for ch in chunk]
            self.x += len(chunk)
            if self.x >= self.cols:
                self.x = self.cols - 1
                self.wrapnext = True
                if not self.autowrap:
                    text = ""
        if chunk:
            self.last_char = chunk[-1]

    def _put(self, ch: str):
        if unicodedata.combining(ch):
            line = self.lines[self.y]
            x = self.x if self.wrapnext else self.x - 1
            if x >= 0:
                char, attr = line[x]
                line[x] = (char + ch, attr)
            return
        width = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if self.wrapnext:
            self._wrap()
        if width == 2 and self.x == self.cols - 1:
            self.lines[self.y][self.x] = self.erase_cell()
            self._wrap()
        line = self.lines[self.y]
        if self.insert_mode:
            line[self.x:self.x] = [self.erase_cell()] * width
            del line[self.cols:]
        line[self.x] = (ch, self.attr)
        if width == 2 and self.x + 1 < self.cols:
            line[self.x + 1] = ("", self.attr)
        self.last_char = ch
        if self.x + width >= self.cols:
            self.x = self.cols - 1
            self.wrapnext = True
        else:
            self.x += width

    def control(self, ch: str):
        if ch == "\r":
            self.x = 0
            self.wrapnext = False
        elif ch in "\n\x0b\x0c":
            self.linefeed()
        elif ch == "\x08":
            self.wrapnext = False
            self.x = max(0, self.x - 1)
        elif ch == "\t":
            stops = [tab for tab in self.tabs if tab > self.x]
            self.x = min(stops) if stops else self.cols - 1
        elif ch == "\x0e":
            self.shift = 1
        elif ch == "\x0f":
            self.shift = 0
        elif ch == "\x1b":
            self.state = "esc"

    def escape(self, ch: str):
        self.state = "ground"
        self.buf = ""
        if ch == "[":
            self.state = "csi"
        elif ch == "]":
            self.state = "osc"
        elif ch in "PX^_":
            self.state = "string"
        elif ch in "()*+":
            self.state = "charset"
            self.buf_index = 0 if ch == "(" else 1
        elif ch in "#% ":
            self.state = "skip"
        elif ch == "7":
            self.save_cursor()
        elif ch == "8":
            self.restore_cursor()
        elif ch == "D":
            self.linefeed()
        elif ch == "E":
            self.x = 0
            self.linefeed()
        elif ch == "M":
            self.reverse_index()
        elif ch == "H":
            self.tabs.add(self.x)
        elif ch == "c":
            self.reset()

    def osc(self, text: str):
        code, _sep, value = text.partition(";")
        if code in ("0", "2"):
            self.title = value[:200]
        elif code == "7":
            if value.startswith("file://"):
                value = QUrl(value).toLocalFile()
            if value:
                self.cwd = os.path.normpath(value)

    def csi(self, buf: str, final: str):
        private = ""
        if buf and buf[0] in "?<=>":
            private, buf = buf[0], buf[1:]
        inter = ""
        while buf and not (buf[-1].isdigit() or buf[-1] in ";:"):
            inter, buf = buf[-1] + inter, buf[:-1]
        params = []
        for part in buf.split(";") if buf else []:
            part = part.split(":")[0]
            params.append(int(part) if part.isdigit() else 0)

        def arg(index: int = 0, default: int = 1) -> int:
            value = params[index] if index < len(params) else 0
            return value or default

        line = self.lines[self.y]
        cols, rows = self.cols, self.rows
        if final not in "mhl":
            self.wrapnext = False
        if inter:
            if final == "p" and inter == "!":
                self.attr = DEFAULT_ATTR
                self.insert_mode = self.app_cursor = False
                self.autowrap = self.cursor_visible = True
                self.top, self.bottom = 0, rows - 1
            return
        if final == "m" and not private:
            self.sgr(buf)
        elif final in "Hf":
            self.y = min(rows - 1, arg(0) - 1)
            self.x = min(cols - 1, arg(1) - 1)
        elif final == "A":
            self.y = max(self.top if self.y >= self.top else 0, self.y - arg())
        elif final in "Be":
            self.y = min(self.bottom if self.y <= self.bottom else rows - 1, self.y + arg())
        elif final in "Ca":
            self.x = min(cols - 1, self.x + arg())
        elif final == "D":
            self.x = max(0, self.x - arg())
        elif final == "E":
            self.y = min(rows - 1, self.y + arg())
            self.x = 0
        elif final == "F":
            self.y = max(0, self.y - arg())
            self.x = 0
        elif final in "G`":
            self.x = min(cols - 1, arg() - 1)
        elif final == "d":
            self.y = min(rows - 1, arg() - 1)
        elif final == "J":
            mode = params[0] if params else 0
            if mode == 0:
                line[self.x:] = [self.erase_cell()] * (cols - self.x)
                for row in range(self.y + 1, rows):
                    self.lines[row] = self.blank_line()
            elif mode == 1:
                line[:self.x + 1] = [self.erase_cell()] * (self.x + 1)
                for row in range(self.y):
                    self.lines[row] = self.blank_line()
            elif mode == 2:
                self.lines = [self.blank_line() for _ in range(rows)]
            elif mode == 3:
                self.clear_scrollback()
        elif final == "K":
            mode = params[0] if params else 0
            if mode == 0:
                line[self.x:] = [self.erase_cell()] * (cols - self.x)
                line.wrapped = False
            elif mode == 1:
                line[:self.x + 1] = [self.erase_cell()] * (self.x + 1)
            elif mode == 2:
                self.lines[self.y] = self.blank_line()
        elif final in "LM":
            if self.top <= self.y <= self.bottom:
                for _ in range(min(arg(), self.bottom - self.y + 1)):
                    if final == "L":
                        self.lines.pop(self.bottom)
                        self.lines.insert(self.y, self.blank_line())
                    else:
                        self.lines.pop(self.y)
                        self.lines.insert(self.bottom, self.blank_line())
                self.x = 0
        elif final == "@":
            count = min(arg(), cols - self.x)
            line[self.x:self.x] = [self.erase_cell()] * count
            del line[cols:]
        elif final == "P":
            count = min(arg(), cols - self.x)
            del line[self.x:self.x + count]
            line.extend([self.erase_cell()] * count)
        elif final == "X":
            count = min(arg(), cols - self.x)
            line[self.x:self.x + count] = [self.erase_cell()] * count
        elif final == "S" and not private:
            self.scroll_up(arg())
        elif final == "T" and not private and len(params) <= 1:
            self.scroll_down(arg())
        elif final == "b":
            self.write_text(self.last_char * min(arg(), cols * rows))
        elif final == "I":
            for _ in range(arg()):
                self.control("\t")
        elif final == "Z":
            for _ in range(arg()):
                stops = [tab for tab in self.tabs if tab < self.x]
                self.x = max(stops) if stops else 0
        elif final == "g":
            mode = params[0] if params else 0
            if mode == 0:
                self.tabs.discard(self.x)
            elif mode == 3:
                self.tabs.clear()
        elif final == "c":
            if private == ">":
                self.reply("\x1b[>0;10;1c")
            elif not private:
                self.reply("\x1b[?62;22c")
        elif final == "n":
            if arg(0, 0) == 5:
                self.reply("\x1b[0n")
            elif arg(0, 0) == 6:
                mark = "?" if private == "?" else ""
                self.reply(f"\x1b[{mark}{self.y + 1};{self.x + 1}R")
        elif final == "r" and not private:
            top, bottom = arg(0) - 1, arg(1, rows) - 1
            if 0 <= top < bottom < rows:
                self.top, self.bottom = top, bottom
                self.x = self.y = 0
        elif final == "s" and not private:
            self.save_cursor()
        elif final == "u" and not private:
            self.restore_cursor()
        elif final in "hl":
            on = final == "h"
            for mode in params:
                if private == "?":
                    if mode == 1:
                        self.app_cursor = on
                    elif mode == 7:
                        self.autowrap = on
                    elif mode == 25:
                        self.cursor_visible = on
                    elif mode in (47, 1047):
                        self.set_alt_screen(on, False)
                    elif mode == 1049:
                        self.set_alt_screen(on, True)
                    elif mode == 2004:
                        self.bracketed_paste = on
                elif mode == 4:
                    self.insert_mode = on

    def sgr(self, buf: str):
        fg, bg, flags = self.attr
        parts = buf.split(";") if buf else ["0"]
        i = 0
        while i < len(parts):
            sub = parts[i].split(":")
            code = int(sub[0]) if sub[0].isdigit() else 0
            if code in (38, 48, 58):
                nums = [int(piece) if piece.isdigit() else 0 for piece in sub[1:]]
                if not nums:  # semicolon form: 38;5;n or 38;2;r;g;b
                    rest = [int(piece) if piece.isdigit() else 0 for piece in parts[i + 1:i + 5]]
                    if rest[:1] == [5]:
                        nums = rest[:2]
                    elif rest[:1] == [2]:
                        nums = rest[:4]
                    i += len(nums)
                color = None
                if len(nums) >= 2 and nums[0] == 5:
                    color = nums[1] & 255
                elif len(nums) >= 4 and nums[0] == 2:
                    red, green, blue = (value & 255 for value in nums[-3:])
                    color = TRUECOLOR | (red << 16) | (green << 8) | blue
                if code == 38:
                    fg = color
                elif code == 48:
                    bg = color
            elif code == 0:
                fg, bg, flags = None, None, 0
            elif code == 1:
                flags |= BOLD
            elif code == 2:
                flags |= DIM
            elif code == 3:
                flags |= ITALIC
            elif code == 4:
                flags = flags & ~UNDERLINE if sub[1:2] == ["0"] else flags | UNDERLINE
            elif code == 7:
                flags |= INVERSE
            elif code == 8:
                flags |= HIDDEN
            elif code == 9:
                flags |= STRIKE
            elif code in (21, 22):
                flags &= ~(BOLD | DIM)
            elif code == 23:
                flags &= ~ITALIC
            elif code == 24:
                flags &= ~UNDERLINE
            elif code == 27:
                flags &= ~INVERSE
            elif code == 28:
                flags &= ~HIDDEN
            elif code == 29:
                flags &= ~STRIKE
            elif 30 <= code <= 37:
                fg = code - 30
            elif code == 39:
                fg = None
            elif 40 <= code <= 47:
                bg = code - 40
            elif code == 49:
                bg = None
            elif 90 <= code <= 97:
                fg = code - 90 + 8
            elif 100 <= code <= 107:
                bg = code - 100 + 8
            i += 1
        self.attr = (fg, bg, flags)


class UnixPty(QObject):
    """Runs a program on a real pseudo-terminal (Linux and macOS)."""

    output = Signal(bytes)
    finished = Signal(int)

    # Makes the pty the program's controlling terminal (so Ctrl+C and job control work),
    # then becomes the program. A fresh interpreter is used because forking a Qt process is unsafe.
    HELPER = ("import fcntl, os, sys, termios; fcntl.ioctl(0, termios.TIOCSCTTY, 0); "
              "os.execvp(sys.argv[1], sys.argv[1:])")

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self.fd = -1
        self.proc = None
        self._pending = b""

    def start(self, argv: list, cwd: str, env: dict, cols: int, rows: int):
        master, slave = os.openpty()
        self.fd = master
        self._pending = b""
        try:
            self.resize(cols, rows)
            self.proc = subprocess.Popen(
                [sys.executable, "-c", self.HELPER] + argv, stdin=slave, stdout=slave,
                stderr=slave, cwd=cwd, env=env, start_new_session=True, close_fds=True)
        except Exception:
            os.close(master)
            self.fd = -1
            raise
        finally:
            os.close(slave)
        os.set_blocking(master, False)
        self._reader = QSocketNotifier(master, QSocketNotifier.Read, self)
        self._reader.activated.connect(self._read)
        self._writer = QSocketNotifier(master, QSocketNotifier.Write, self)
        self._writer.setEnabled(False)
        self._writer.activated.connect(self._flush)

    def _read(self, *_args):
        try:
            data = os.read(self.fd, 65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if data:
            self.output.emit(data)
        else:
            self._close()

    def _close(self):
        if self.fd < 0:
            return
        self._reader.setEnabled(False)
        self._writer.setEnabled(False)
        os.close(self.fd)
        self.fd = -1
        try:
            code = self.proc.wait(timeout=1) if self.proc else -1
        except subprocess.TimeoutExpired:
            code = -1
        self.finished.emit(code)

    def write(self, data: bytes):
        self._pending += data
        self._flush()

    def _flush(self, *_args):
        while self._pending and self.fd >= 0:
            try:
                written = os.write(self.fd, self._pending[:4096])
            except BlockingIOError:
                break
            except OSError:
                self._pending = b""
                break
            self._pending = self._pending[written:]
        if self.fd >= 0:
            self._writer.setEnabled(bool(self._pending))

    def resize(self, cols: int, rows: int):
        if self.fd >= 0:
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def busy_name(self) -> str:
        """Name of the foreground program, or "" while the shell is waiting at a prompt."""
        try:
            group = os.tcgetpgrp(self.fd)
        except OSError:
            return ""
        if group <= 0 or self.proc is None or group == self.proc.pid:
            return ""
        try:
            with open(f"/proc/{group}/comm") as comm:
                return comm.read().strip()
        except OSError:
            return "a program"

    def cwd(self) -> str:
        try:
            return os.readlink(f"/proc/{self.proc.pid}/cwd")
        except OSError:
            return ""

    def interrupt(self):
        self.write(b"\x03")

    def terminate(self):
        if self.fd < 0:
            return
        if self.proc is not None:
            try:
                os.killpg(self.proc.pid, signal.SIGHUP)
            except OSError:
                pass
        self._reader.setEnabled(False)
        self._writer.setEnabled(False)
        os.close(self.fd)
        self.fd = -1


class WinPty(QObject):
    """Runs a program on a Windows console through the optional pywinpty package."""

    output = Signal(bytes)
    finished = Signal(int)

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self.proc = None
        self._alive = False

    def start(self, argv: list, cwd: str, env: dict, cols: int, rows: int):
        self.proc = WinPtyProcess.spawn(
            subprocess.list2cmdline(argv), cwd=cwd, env=env, dimensions=(rows, cols))
        self._alive = True
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        while self._alive:
            try:
                data = self.proc.read(65536)
            except Exception:
                break
            if data:
                self.output.emit(data.encode("utf-8", "replace"))
            elif not self.proc.isalive():
                break
        if self._alive:
            self._alive = False
            self.finished.emit(self.proc.exitstatus or 0)

    def write(self, data: bytes):
        if self._alive:
            self.proc.write(data.decode("utf-8", "replace"))

    def resize(self, cols: int, rows: int):
        if self._alive:
            self.proc.setwinsize(rows, cols)

    def busy_name(self) -> str:
        return ""

    def cwd(self) -> str:
        return ""

    def interrupt(self):
        self.write(b"\x03")

    def terminate(self):
        if self._alive:
            self._alive = False
            try:
                self.proc.terminate(force=True)
            except Exception:
                pass


class PipeShell(QObject):
    """Fallback with no pty: output streams back, and input is sent a line at a time."""

    output = Signal(bytes)
    finished = Signal(int)
    line_mode = True

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self.proc = QProcess(self)

    def start(self, argv: list, cwd: str, env: dict, cols: int, rows: int):
        environment = QProcessEnvironment()
        for key, value in env.items():
            environment.insert(key, value)
        self.proc.setProcessEnvironment(environment)
        self.proc.setWorkingDirectory(cwd)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyRead.connect(
            lambda: self.output.emit(bytes(self.proc.readAll()).replace(b"\n", b"\r\n")))
        self.proc.finished.connect(lambda code, _status: self.finished.emit(code))
        self.proc.errorOccurred.connect(self._on_error)
        self.proc.start(argv[0], argv[1:])

    def _on_error(self, error):
        if error == QProcess.FailedToStart:
            self.output.emit(f"Couldn't start {self.proc.program()}\r\n".encode())
            self.finished.emit(-1)

    def write(self, data: bytes):
        self.proc.write(data)

    def resize(self, cols: int, rows: int):
        pass

    def busy_name(self) -> str:
        return ""

    def cwd(self) -> str:
        return ""

    def interrupt(self):
        pid = self.proc.processId()
        if pid:
            try:
                os.kill(pid, signal.SIGINT)
                return
            except OSError:
                pass
        self.proc.terminate()

    def terminate(self):
        self.proc.kill()


def git_bash() -> str:
    roots = [os.environ.get(key, "") for key in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)")]
    roots.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"))
    for root in roots:
        path = os.path.join(root, "Git", "bin", "bash.exe")
        if root and os.path.isfile(path):
            return path
    return ""


def shell_command(custom: str = "") -> list:
    """The command a shell tab runs. Empty means bash, or the best shell available."""
    custom = custom.strip()
    if custom:
        if os.path.exists(custom.strip('"')):
            return [custom.strip('"')]
        return shlex.split(custom, posix=sys.platform != "win32")
    if sys.platform == "win32":
        if git_bash():
            return [git_bash(), "--login", "-i"]
        for name in ("wsl.exe", "powershell.exe", "cmd.exe"):
            if shutil.which(name):
                return [name]
        return ["cmd.exe"]
    shell = shutil.which("bash") or os.environ.get("SHELL") or "/bin/sh"
    return [shell, "-l"] if sys.platform == "darwin" else [shell]


def terminal_font() -> QFont:
    families = set(QFontDatabase.families())
    for name in ("Cascadia Mono", "Consolas", "SF Mono", "Menlo", "JetBrains Mono",
                 "DejaVu Sans Mono", "Ubuntu Mono", "Liberation Mono"):
        if name in families:
            font = QFont(name)
            break
    else:
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    font.setStyleHint(QFont.Monospace)
    font.setFixedPitch(True)
    font.setKerning(False)
    return font


MAC = sys.platform == "darwin"
# On macOS, Qt's ControlModifier is the Command key; the Control key arrives as Meta.
TERM_CTRL = Qt.MetaModifier if MAC else Qt.ControlModifier
# Ctrl chords that keep working while a terminal is focused. Everything else (Ctrl+C,
# Ctrl+R, Ctrl+D, …) goes to the program. Ctrl+Shift+letter stays with the app.
APP_CTRL_KEYS = {Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Plus,
                 Qt.Key_Equal, Qt.Key_Minus, Qt.Key_0, Qt.Key_QuoteLeft, Qt.Key_Q, Qt.Key_Comma,
                 Qt.Key_T, Qt.Key_L, Qt.Key_W}
CURSOR_KEYS = {Qt.Key_Up: "A", Qt.Key_Down: "B", Qt.Key_Right: "C", Qt.Key_Left: "D",
               Qt.Key_Home: "H", Qt.Key_End: "F"}
TILDE_KEYS = {Qt.Key_Insert: 2, Qt.Key_Delete: 3, Qt.Key_PageUp: 5, Qt.Key_PageDown: 6,
              Qt.Key_F5: 15, Qt.Key_F6: 17, Qt.Key_F7: 18, Qt.Key_F8: 19, Qt.Key_F9: 20,
              Qt.Key_F10: 21, Qt.Key_F11: 23, Qt.Key_F12: 24}
SS3_KEYS = {Qt.Key_F1: "P", Qt.Key_F2: "Q", Qt.Key_F3: "R", Qt.Key_F4: "S"}
CTRL_SYMBOLS = {Qt.Key_Space: "\x00", Qt.Key_At: "\x00", Qt.Key_BracketLeft: "\x1b",
                Qt.Key_Backslash: "\x1c", Qt.Key_BracketRight: "\x1d",
                Qt.Key_AsciiCircum: "\x1e", Qt.Key_Underscore: "\x1f", Qt.Key_Slash: "\x1f"}
WORD_DELIMITERS = set(" \t\"'`()[]{}<>|;,")


class TerminalView(QAbstractScrollArea):
    """Draws a TermScreen and turns the keyboard, mouse, and clipboard into input."""

    PAD = 10

    def __init__(self, tab: TerminalTab):
        super().__init__()
        self.tab = tab
        self.screen = tab.screen
        # Paint and mouse handling go through an event filter. A custom viewport widget
        # never gets a usable paint engine here, so the default viewport is drawn instead.
        viewport = self.viewport()
        viewport.setCursor(Qt.IBeamCursor)
        viewport.setMouseTracking(True)
        viewport.setAutoFillBackground(False)
        viewport.installEventFilter(self)
        self.setFrameShape(QFrame.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_InputMethodEnabled)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.verticalScrollBar().valueChanged.connect(self.viewport().update)
        self._anchor = None
        self.sel_start = self.sel_end = None
        self._selecting = False
        self._base = 0
        self._blink = True
        self.fonts = {}
        self.colors = {}
        self._truecolor = {}
        self._blink_timer = QTimer(self, interval=530)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_timer.start()
        self.set_font(terminal_font())

    def _toggle_blink(self):
        self._blink = not self._blink
        if self.hasFocus() and self.screen.cursor_visible:
            self.viewport().update()

    def set_font(self, font: QFont):
        self.fonts = {}
        for flags in range(16):
            variant = QFont(font)
            variant.setBold(bool(flags & 1))
            variant.setItalic(bool(flags & 2))
            variant.setUnderline(bool(flags & 4))
            variant.setStrikeOut(bool(flags & 8))
            self.fonts[flags] = variant
        metrics = QFontMetricsF(font)
        self.cell_w = max(1.0, metrics.horizontalAdvance("M"))
        self.cell_h = float(max(1, math.ceil(metrics.lineSpacing())))
        self.ascent = metrics.ascent()
        self.fit()
        self.viewport().update()

    def set_theme(self, colors: dict):
        dark = colors is DARK
        self.ansi = [QColor(color) for color in (ANSI_DARK if dark else ANSI_LIGHT)]
        steps = (0, 95, 135, 175, 215, 255)
        for index in range(216):
            self.ansi.append(QColor(steps[index // 36], steps[index // 6 % 6], steps[index % 6]))
        for level in range(24):
            shade = 8 + level * 10
            self.ansi.append(QColor(shade, shade, shade))
        self.colors = {
            "bg": QColor(colors["term_bg"]), "fg": QColor(colors["text"]),
            "selection": QColor(colors["selected"]), "cursor": QColor(colors["accent"]),
            "cursor_text": QColor(colors["accent_text"]),
        }
        self._truecolor = {}
        self.viewport().update()

    def color(self, value, default: QColor) -> QColor:
        if value is None:
            return default
        if value & TRUECOLOR:
            color = self._truecolor.get(value)
            if color is None:
                color = QColor((value >> 16) & 255, (value >> 8) & 255, value & 255)
                self._truecolor[value] = color
            return color
        return self.ansi[value]

    def fit(self):
        if not self.fonts:
            return
        area = self.viewport().size()
        cols = max(10, int((area.width() - 2 * self.PAD) / self.cell_w))
        rows = max(3, int((area.height() - 2 * self.PAD) / self.cell_h))
        if (cols, rows) != (self.screen.cols, self.screen.rows):
            self.screen.resize(cols, rows)
            self.tab.resize_pty(cols, rows)
            self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def scrollContentsBy(self, dx, dy):
        self.viewport().update()

    def history(self) -> list:
        return [] if self.screen.using_alt else self.screen.scrollback

    def refresh(self):
        screen = self.screen
        bar = self.verticalScrollBar()
        total = len(self.history())
        follow = bar.value() >= bar.maximum()
        shift = screen.base - self._base
        self._base = screen.base
        bar.blockSignals(True)
        bar.setRange(0, total)
        bar.setPageStep(screen.rows)
        bar.setSingleStep(3)
        bar.setValue(total if follow else max(0, bar.value() - shift))
        bar.blockSignals(False)
        self.viewport().update()

    def scroll_to_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def line(self, index: int):
        """Row `index`, counting from the top of the scrollback."""
        history = self.history()
        if index < 0:
            return None
        if index < len(history):
            return history[index]
        index -= len(history)
        return self.screen.lines[index] if index < len(self.screen.lines) else None

    def offset(self) -> int:
        return 0 if self.screen.using_alt else self.screen.base

    def paint_viewport(self):
        if not self.colors:
            return
        painter = QPainter(self.viewport())
        colors = self.colors
        painter.fillRect(self.viewport().rect(), colors["bg"])
        screen = self.screen
        first = self.verticalScrollBar().value()
        selection = self.selection()
        for row in range(screen.rows):
            line = self.line(first + row)
            if line is None:
                break
            self.paint_line(painter, line, self.PAD + row * self.cell_h,
                            first + row + self.offset(), selection)
        cursor_row = len(self.history()) + screen.y - first
        if screen.cursor_visible and 0 <= cursor_row < screen.rows and (self._blink or not self.hasFocus()):
            x = self.PAD + screen.x * self.cell_w
            y = self.PAD + cursor_row * self.cell_h
            rect = QRectF(x, y, self.cell_w, self.cell_h)
            if self.hasFocus():
                painter.fillRect(rect, colors["cursor"])
                char, attr = screen.lines[screen.y][min(screen.x, screen.cols - 1)]
                if char.strip():
                    painter.setFont(self.fonts[self._font_key(attr[2])])
                    painter.setPen(colors["cursor_text"])
                    painter.drawText(QPointF(x, y + self.ascent), char)
            else:
                painter.setPen(colors["cursor"])
                painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))

    @staticmethod
    def _font_key(flags: int) -> int:
        return (bool(flags & BOLD) | bool(flags & ITALIC) << 1 | bool(flags & UNDERLINE) << 2
                | bool(flags & STRIKE) << 3)

    def paint_line(self, painter: QPainter, line: list, y: float, row: int, selection):
        colors = self.colors
        cols = min(len(line), self.screen.cols)
        sel_from = sel_to = -1
        if selection is not None:
            (row1, col1), (row2, col2) = selection
            if row1 <= row <= row2:
                sel_from = col1 if row == row1 else 0
                sel_to = col2 if row == row2 else cols
        x0 = 0
        while x0 < cols:
            attr = line[x0][1]
            selected = sel_from <= x0 < sel_to
            x1 = x0 + 1
            while x1 < cols and line[x1][1] == attr and (sel_from <= x1 < sel_to) == selected:
                x1 += 1
            fg_value, bg_value, flags = attr
            if flags & BOLD and fg_value is not None and fg_value < 8:
                fg_value += 8
            fg = self.color(fg_value, colors["fg"])
            bg = self.color(bg_value, colors["bg"]) if bg_value is not None else None
            if flags & INVERSE:
                fg, bg = (bg or colors["bg"]), fg
            if selected:
                bg = colors["selection"]
            if flags & DIM:
                base = bg or colors["bg"]
                fg = QColor((fg.red() + base.red()) // 2, (fg.green() + base.green()) // 2,
                            (fg.blue() + base.blue()) // 2)
            left = self.PAD + x0 * self.cell_w
            if bg is not None:
                painter.fillRect(QRectF(left, y, (x1 - x0) * self.cell_w, self.cell_h), bg)
            text = "".join(cell[0] for cell in line[x0:x1])
            if not flags & HIDDEN and (text.strip() or flags & (UNDERLINE | STRIKE)):
                painter.setFont(self.fonts[self._font_key(flags)])
                painter.setPen(fg)
                if text.isascii():
                    painter.drawText(QPointF(left, y + self.ascent), text)
                else:
                    for column in range(x0, x1):
                        char = line[column][0]
                        if char:
                            painter.drawText(
                                QPointF(self.PAD + column * self.cell_w, y + self.ascent), char)
            x0 = x1

    def _point(self, event) -> QPoint:
        return event.position().toPoint()

    def cell_at(self, pos: QPoint) -> tuple:
        column = int((pos.x() - self.PAD) / self.cell_w)
        row = int((pos.y() - self.PAD) / self.cell_h)
        row = max(0, min(self.screen.rows - 1, row))
        column = max(0, min(self.screen.cols - 1, column))
        return self.verticalScrollBar().value() + row + self.offset(), column

    def selection(self):
        """The selected span as ((row, start column), (row, end column)), end exclusive."""
        if self.sel_start is None or self.sel_end is None or self.sel_start == self.sel_end:
            return None
        (row1, col1), (row2, col2) = sorted((self.sel_start, self.sel_end))
        return (row1, col1), (row2, col2 + 1)

    def selected_text(self) -> str:
        span = self.selection()
        if span is None:
            return ""
        (row1, col1), (row2, col2) = span
        parts = []
        for row in range(row1, row2 + 1):
            line = self.line(row - self.offset())
            if line is None:
                continue
            start = col1 if row == row1 else 0
            end = col2 if row == row2 else len(line)
            text = "".join(cell[0] for cell in line[start:end])
            if row == row2 or not line.wrapped:
                text = text.rstrip()
                if row != row2:
                    text += "\n"
            parts.append(text)
        return "".join(parts)

    def clear_selection(self):
        self.sel_start = self.sel_end = None
        self.viewport().update()

    def copy(self) -> bool:
        text = self.selected_text()
        if text:
            QGuiApplication.clipboard().setText(text)
        return bool(text)

    def paste(self, mode=QClipboard.Clipboard):
        text = QGuiApplication.clipboard().text(mode)
        if not text:
            return
        text = text.replace("\r\n", "\r").replace("\n", "\r")
        if self.screen.bracketed_paste:
            text = f"\x1b[200~{text}\x1b[201~"
        self.scroll_to_bottom()
        self.tab.send_input(text.encode("utf-8"))

    def select_all(self):
        last = len(self.history()) + self.screen.rows - 1
        self.sel_start = (self.offset(), 0)
        self.sel_end = (last + self.offset(), self.screen.cols - 1)
        self.viewport().update()

    def on_mouse_press(self, event):
        self.setFocus()
        if event.button() == Qt.LeftButton:
            self._anchor = self.cell_at(self._point(event))
            self.sel_start = self.sel_end = None
            self._selecting = True
            self.viewport().update()
        elif event.button() == Qt.MiddleButton and QGuiApplication.clipboard().supportsSelection():
            self.paste(QClipboard.Selection)
        else:
            event.ignore()

    def on_mouse_move(self, event):
        if not self._selecting or self._anchor is None:
            return
        pos = self._point(event)
        bar = self.verticalScrollBar()
        if pos.y() < 0:
            bar.setValue(bar.value() - 1)
        elif pos.y() > self.viewport().height():
            bar.setValue(bar.value() + 1)
        current = self.cell_at(pos)
        if current == self._anchor:
            self.sel_start = self.sel_end = None
        else:
            self.sel_start, self.sel_end = self._anchor, current
        self.viewport().update()

    def on_mouse_release(self, event):
        if event.button() == Qt.LeftButton and self._selecting:
            self._selecting = False
            text = self.selected_text()
            if text and QGuiApplication.clipboard().supportsSelection():
                QGuiApplication.clipboard().setText(text, QClipboard.Selection)

    def on_double_click(self, event):
        if event.button() != Qt.LeftButton:
            return
        row, column = self.cell_at(self._point(event))
        line = self.line(row - self.offset())
        if line is None or line[column][0] in WORD_DELIMITERS:
            return
        start = end = column
        while start > 0 and line[start - 1][0] not in WORD_DELIMITERS:
            start -= 1
        while end < len(line) - 1 and line[end + 1][0] not in WORD_DELIMITERS:
            end += 1
        self.sel_start, self.sel_end = (row, start), (row, end)
        self._selecting = False
        self.viewport().update()

    def on_context_menu(self, event):
        menu = QMenu(self)
        copy = menu.addAction("Copy", self.copy)
        copy.setEnabled(self.selection() is not None)
        menu.addAction("Paste", self.paste).setEnabled(bool(QGuiApplication.clipboard().text()))
        menu.addAction("Select all", self.select_all)
        menu.addSeparator()
        menu.addAction("Clear scrollback", self.tab.clear_scrollback)
        menu.addAction("Open folder in files tab", self.tab.open_folder)
        menu.exec(event.globalPos())

    def eventFilter(self, watched, event):
        if watched is self.viewport():
            kind = event.type()
            if kind == QEvent.Paint:
                self.paint_viewport()
                return True
            if kind == QEvent.MouseButtonPress:
                self.on_mouse_press(event)
                return True
            if kind == QEvent.MouseMove:
                self.on_mouse_move(event)
                return True
            if kind == QEvent.MouseButtonRelease:
                self.on_mouse_release(event)
                return True
            if kind == QEvent.MouseButtonDblClick:
                self.on_double_click(event)
                return True
            if kind == QEvent.ContextMenu:
                self.on_context_menu(event)
                return True
            if kind == QEvent.Wheel and self.screen.using_alt and self.tab.process is not None:
                steps = event.angleDelta().y() // 40
                if steps:
                    key = ("\x1bO" if self.screen.app_cursor else "\x1b[") + ("A" if steps > 0 else "B")
                    self.tab.send_input((key * abs(steps)).encode())
                return True
        return super().eventFilter(watched, event)

    def focusNextPrevChild(self, _next: bool) -> bool:
        return False

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._blink = True
        self.viewport().update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.viewport().update()

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride and self.wants_key(event):
            event.accept()
            return True
        return super().event(event)

    @staticmethod
    def wants_key(event) -> bool:
        mods, key = event.modifiers(), event.key()
        if MAC and mods & Qt.ControlModifier:
            return False  # Command stays with the app
        if mods & Qt.ControlModifier:
            if mods & Qt.ShiftModifier and key not in CURSOR_KEYS:
                return False
            if key in APP_CTRL_KEYS:
                return False
        return True

    def keyPressEvent(self, event):
        mods, key = event.modifiers(), event.key()
        ctrl = bool(mods & TERM_CTRL)
        shift = bool(mods & Qt.ShiftModifier)
        bar = self.verticalScrollBar()
        if shift and not ctrl and not self.screen.using_alt:
            if key == Qt.Key_PageUp:
                bar.setValue(bar.value() - self.screen.rows + 1)
                return
            if key == Qt.Key_PageDown:
                bar.setValue(bar.value() + self.screen.rows - 1)
                return
        if shift and key == Qt.Key_Insert:
            self.paste()
            return
        if ctrl and not shift and key == Qt.Key_V and sys.platform == "win32":
            self.paste()
            return
        data = self.key_bytes(event)
        if data:
            self.clear_selection()
            self.scroll_to_bottom()
            self.tab.send_input(data)

    def key_bytes(self, event) -> bytes:
        mods, key, text = event.modifiers(), event.key(), event.text()
        ctrl = bool(mods & TERM_CTRL)
        alt = bool(mods & Qt.AltModifier)
        shift = bool(mods & Qt.ShiftModifier)
        modifier = 1 + shift + 2 * alt + 4 * ctrl
        if key in CURSOR_KEYS:
            final = CURSOR_KEYS[key]
            if modifier > 1:
                return f"\x1b[1;{modifier}{final}".encode()
            return (("\x1bO" if self.screen.app_cursor else "\x1b[") + final).encode()
        if key in TILDE_KEYS:
            number = TILDE_KEYS[key]
            return (f"\x1b[{number};{modifier}~" if modifier > 1 else f"\x1b[{number}~").encode()
        if key in SS3_KEYS:
            final = SS3_KEYS[key]
            return (f"\x1b[1;{modifier}{final}" if modifier > 1 else "\x1bO" + final).encode()
        if ctrl and alt and text and text.isprintable():
            return text.encode()  # AltGr on Windows arrives as Ctrl+Alt
        if key in (Qt.Key_Return, Qt.Key_Enter):
            out = "\r"
        elif key == Qt.Key_Backspace:
            out = "\x08" if ctrl else "\x7f"
        elif key == Qt.Key_Backtab:
            out = "\x1b[Z"
        elif key == Qt.Key_Tab:
            out = "\t"
        elif key == Qt.Key_Escape:
            out = "\x1b"
        elif ctrl and Qt.Key_A <= key <= Qt.Key_Z:
            out = chr(key - Qt.Key_A + 1)
        elif ctrl and key in CTRL_SYMBOLS:
            out = CTRL_SYMBOLS[key]
        else:
            out = text
        if not out:
            return b""
        if alt:
            out = "\x1b" + out
        return out.encode("utf-8", "replace")

    def inputMethodEvent(self, event):
        if event.commitString():
            self.scroll_to_bottom()
            self.tab.send_input(event.commitString().encode("utf-8"))
        event.accept()


class TerminalTab(QWidget):
    """A shell in the same tab strip and toolbar as the other tabs."""

    titleChanged = Signal(str)
    urlChanged = Signal(QUrl)
    iconChanged = Signal(QIcon)

    def __init__(self, window: BrowserWindow, cwd: str | None = None):
        super().__init__(objectName="terminal")
        self.setAttribute(Qt.WA_StyledBackground)
        self._window = window
        self.loading = False
        self.progress = 0
        self.cwd = os.path.normpath(cwd) if cwd and os.path.isdir(cwd) else QDir.homePath()
        self.process = None
        self.exited = False
        self._started = False
        self._line = ""
        self._title = ""
        self._zoom = 1.0
        self.argv: list = []
        self._base_font = terminal_font()
        self._base_size = max(11.0, self._base_font.pointSizeF())

        self.screen = TermScreen()
        self.screen.reply = self._reply
        self.view = TerminalView(self)
        self.view.set_theme(window.colors)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        self._render_timer = QTimer(self, singleShot=True, interval=10)
        self._render_timer.timeout.connect(self._render)
        for keys, slot in (("Ctrl+Shift+C", self.view.copy), ("Ctrl+Shift+V", self.view.paste),
                           ("Ctrl+Shift+T", lambda: window.new_terminal(self.cwd)),
                           ("Ctrl+Shift+W", lambda: window.close_tab(window._index(self)))):
            act = QAction(self)
            act.setShortcut(QKeySequence(keys))
            act.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            act.triggered.connect(slot)
            self.addAction(act)
        self.setZoomFactor(window.settings.get("zoom") / 100)
        QTimer.singleShot(0, self._start_when_ready)

    def _reply(self, text: str):
        if self.process is not None:
            self.process.write(text.encode())

    def _start_when_ready(self, tries: int = 0):
        if self._started or self.exited:
            return
        self.view.fit()
        if self.view.viewport().width() < 80 and tries < 40:
            QTimer.singleShot(30, lambda: self._start_when_ready(tries + 1))
            return
        self.start()

    def shell_name(self) -> str:
        if not self.argv:
            return "Terminal"
        return os.path.splitext(os.path.basename(self.argv[0]))[0] or "Terminal"

    def start(self):
        self._started = True
        argv = shell_command(self._window.settings.get("terminal_shell"))
        self.argv = argv
        env = dict(os.environ)
        env.update(TERM="xterm-256color", COLORTERM="truecolor", TERM_PROGRAM=APP_NAME)
        env.setdefault("LANG", env.get("LC_ALL") or "C.UTF-8")
        if os.path.basename(argv[0]).lower() in ("bash", "bash.exe"):
            # Tell us the working directory after every prompt, so the address bar follows `cd`.
            # Git Bash's `pwd -W` gives a Windows path.
            report = ("printf '\\033]7;%s\\007' \"$(pwd -W 2>/dev/null || pwd)\""
                      if sys.platform == "win32" else "printf '\\033]7;%s\\007' \"$PWD\"")
            existing = env.get("PROMPT_COMMAND", "")
            env["PROMPT_COMMAND"] = f"{report}; {existing}" if existing else report
            if sys.platform == "win32":
                env.setdefault("CHERE_INVOKING", "1")
                env.setdefault("MSYSTEM", "MINGW64")
        if fcntl is not None:
            backend = UnixPty(self)
        elif WinPtyProcess is not None:
            backend = WinPty(self)
        else:
            backend = PipeShell(self)
            self.screen.feed("\x1b[2mBasic mode: full-screen programs and Ctrl+C need a terminal. "
                             "On Windows, install one with: pip install pywinpty\x1b[0m\r\n")
        backend.output.connect(self._on_output)
        backend.finished.connect(self._on_finished)
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        try:
            backend.start(argv, self.cwd, env, self.screen.cols, self.screen.rows)
        except Exception as error:
            self.screen.feed(f"\x1b[31mCouldn't start {argv[0]}: {error}\x1b[0m\r\n")
            self.view.refresh()
            self._finish(-1)
            return
        self.process = backend
        self.exited = False
        self.view.refresh()

    def _on_output(self, data: bytes):
        self.screen.feed(self._decoder.decode(data))
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _render(self):
        self.view.refresh()
        cwd = ""
        if self.process is not None:
            cwd = self.process.cwd()
        cwd = cwd or self.screen.cwd
        if cwd and os.path.isdir(cwd) and os.path.normpath(cwd) != self.cwd:
            self.cwd = os.path.normpath(cwd)
            self.urlChanged.emit(self.url())
            self.titleChanged.emit(self.title())
        if self.screen.title != self._title:
            self._title = self.screen.title
            self.titleChanged.emit(self.title())

    def _on_finished(self, code: int):
        self._render()
        self._finish(code)

    def _finish(self, code: int):
        self.process = None
        self.exited = True
        window = self._window
        if code == 0 and len(window._views) > 1 and self in window._views:
            QTimer.singleShot(0, lambda: self in window._views
                              and window.close_tab(window._index(self)))
            return
        self.screen.feed(f"\r\n\x1b[2m[Process exited with code {code}. "
                         "Press Enter to start again.]\x1b[0m\r\n")
        self.titleChanged.emit(self.title())
        self.view.refresh()

    def send_input(self, data: bytes):
        if self.exited:
            if data == b"\r":
                self.screen.feed("\r\n")
                self.exited = False
                self.start()
            return
        if self.process is None:
            return
        if getattr(self.process, "line_mode", False):
            self._line_input(data)
        else:
            self.process.write(data)

    def _line_input(self, data: bytes):
        text = data.decode("utf-8", "replace")
        if text.startswith("\x1b[200~") and text.endswith("\x1b[201~"):
            text = text[6:-6]
        for ch in text:
            if ch == "\r":
                self.screen.feed("\r\n")
                self.process.write((self._line + "\n").encode("utf-8"))
                self._line = ""
            elif ch == "\x7f":
                if self._line:
                    self._line = self._line[:-1]
                    self.screen.feed("\b \b")
            elif ch == "\x03":
                self.screen.feed("^C\r\n")
                self._line = ""
                self.process.interrupt()
            elif ch >= " ":
                self._line += ch
                self.screen.feed(ch)
            elif ch == "\x1b":
                break
        self._render_timer.start()

    def resize_pty(self, cols: int, rows: int):
        if self.process is not None:
            self.process.resize(cols, rows)

    def shutdown(self):
        process = self.process
        if process is None:
            return
        self.process = None
        try:
            process.output.disconnect(self._on_output)
            process.finished.disconnect(self._on_finished)
        except (RuntimeError, TypeError):
            pass
        process.terminate()

    def maybe_close(self) -> bool:
        name = self.process.busy_name() if self.process is not None else ""
        if not name:
            return True
        self._window.show_view(self)
        answer = QMessageBox.question(
            self, "Close terminal", f"\u201c{name}\u201d is still running in this terminal. "
            "Close it anyway?")
        return answer == QMessageBox.Yes

    def change_directory(self, path: str) -> bool:
        """Move this terminal into `path` if it is sitting at a prompt."""
        if self.process is None or self.exited or self.process.busy_name():
            return False
        shell = os.path.basename(self.argv[0]).lower().split(".")[0] if self.argv else ""
        if shell not in ("bash", "sh", "zsh", "dash", "ksh"):
            return False
        quoted = path.replace("\\", "/") if sys.platform == "win32" else os.path.normpath(path)
        # Ctrl+E Ctrl+U clears anything half-typed at the prompt first.
        self.send_input(f"\x05\x15cd -- {shlex.quote(quoted)}\r".encode("utf-8"))
        self.view.setFocus()
        return True

    def clear_scrollback(self):
        self.screen.clear_scrollback()
        self.view.clear_selection()
        self.view.refresh()

    def open_folder(self):
        self._window.add_tab(QUrl.fromLocalFile(self.cwd))

    def refresh_icons(self):
        self.view.set_theme(self._window.colors)
        self.iconChanged.emit(self._window.icon("terminal"))

    def title(self) -> str:
        name = self.shell_name()
        if self.exited:
            return f"{name} (exited)"
        if self.screen.title:
            return self.screen.title
        folder = os.path.basename(self.cwd) or self.cwd
        return f"{name} \u2014 {folder}"

    def url(self) -> QUrl:
        return QUrl.fromLocalFile(self.cwd)

    def location(self) -> str:
        return QDir.toNativeSeparators(self.cwd)

    def address_icon_name(self) -> str:
        return "terminal"

    def can_go_back(self) -> bool:
        return False

    def can_go_forward(self) -> bool:
        return False

    def clear_history(self):
        pass

    def back(self):
        pass

    def forward(self):
        pass

    def stop(self):
        if self.process is not None:
            self.process.interrupt()

    def reload(self):
        if self.exited:
            self.screen.feed("\r\n")
            self.exited = False
            self.start()

    def zoomFactor(self) -> float:
        return self._zoom

    def setZoomFactor(self, factor: float):
        self._zoom = factor
        font = QFont(self._base_font)
        font.setPointSizeF(self._base_size * factor)
        self.view.set_font(font)

    def focus_view(self):
        self.view.setFocus()


# ----- downloads ---------------------------------------------------------

DownloadState = QWebEngineDownloadRequest.DownloadState


class DownloadItem(QWidget):
    """One row in the downloads panel, kept in sync with a QWebEngineDownloadRequest."""

    def __init__(self, window: BrowserWindow, download: QWebEngineDownloadRequest):
        super().__init__(objectName="downloadItem")
        self.setAttribute(Qt.WA_StyledBackground)
        self._window = window
        self.download = download
        self._clock = QElapsedTimer()
        self._clock.start()
        self._last_bytes = 0
        self._speed = 0.0
        self._icon_key = None
        self._progress_timer = QTimer(self)
        self._progress_timer.setSingleShot(True)
        self._progress_timer.setInterval(100)
        self._progress_timer.timeout.connect(self.refresh)

        self.icon = QLabel()
        self.icon.setFixedSize(32, 32)
        self.name = QLabel(objectName="downloadName")
        self.status = QLabel(objectName="downloadStatus")
        self.bar = QProgressBar(objectName="downloadBar", textVisible=False)
        self.bar.setFixedHeight(4)
        self.pause_button = self._button(self.toggle_pause)
        self.folder_button = self._button(self.show_in_folder)
        self.folder_button.setToolTip("Show in folder")
        self.close_button = self._button(self.cancel_or_remove)

        text = QVBoxLayout()
        text.setSpacing(4)
        text.addWidget(self.name)
        text.addWidget(self.bar)
        text.addWidget(self.status)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 6, 8)
        layout.setSpacing(10)
        layout.addWidget(self.icon, 0, Qt.AlignTop)
        layout.addLayout(text, 1)
        for button in (self.pause_button, self.folder_button, self.close_button):
            layout.addWidget(button, 0, Qt.AlignVCenter)

        for changed in (download.receivedBytesChanged, download.totalBytesChanged):
            changed.connect(self._schedule_refresh)
        for changed in (download.stateChanged, download.isPausedChanged):
            changed.connect(self.refresh)
        self.refresh()

    def _schedule_refresh(self, *_):
        if not self._progress_timer.isActive():
            self._progress_timer.start()

    def _button(self, slot) -> QToolButton:
        button = QToolButton(autoRaise=True)
        button.setFixedSize(30, 30)
        button.setIconSize(QSize(16, 16))
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def path(self) -> str:
        return os.path.join(self.download.downloadDirectory(), self.download.downloadFileName())

    def is_active(self) -> bool:
        return self.download.state() in (DownloadState.DownloadRequested,
                                          DownloadState.DownloadInProgress)

    def refresh(self, *_):
        download = self.download
        state = download.state()
        received, total = download.receivedBytes(), download.totalBytes()
        size = QLocale().formattedDataSize
        name = download.downloadFileName()
        self.name.setText(self.name.fontMetrics().elidedText(name, Qt.ElideMiddle, 230))
        self.name.setToolTip(QDir.toNativeSeparators(self.path()))

        elapsed = self._clock.elapsed()
        if elapsed >= 700:
            current = (received - self._last_bytes) * 1000 / elapsed
            self._speed = current if not self._speed else 0.6 * self._speed + 0.4 * current
            self._last_bytes = received
            self._clock.restart()

        active = self.is_active()
        self.bar.setVisible(active)
        if total > 0:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(received * 1000 / total))
        else:
            self.bar.setRange(0, 0)
        progress = f"{size(received)} of {size(total)}" if total > 0 else size(received)

        if state == DownloadState.DownloadCompleted:
            status = f"{size(received or total)}  ·  Done"
        elif state == DownloadState.DownloadCancelled:
            status = "Canceled"
        elif state == DownloadState.DownloadInterrupted:
            status = f"Failed — {download.interruptReasonString()}"
        elif download.isPaused():
            status = f"Paused  ·  {progress}"
        elif self._speed > 0:
            status = f"{progress}  ·  {size(int(self._speed))}/s"
        else:
            status = progress
        self.status.setText(status)

        done = state == DownloadState.DownloadCompleted
        self.pause_button.setVisible(active)
        self.folder_button.setVisible(done)
        self.setCursor(Qt.PointingHandCursor if done else Qt.ArrowCursor)
        self.setToolTip("Click to open" if done else "")
        self.refresh_icons()
        self._window.update_downloads_button()

    def refresh_icons(self):
        icon = self._window.icon
        colors = self._window.colors
        ext = os.path.splitext(self.download.downloadFileName())[1].lower()
        paused = self.download.isPaused()
        key = (self.download.state(), paused, ext)
        if key == self._icon_key:
            return
        self._icon_key = key
        kind = next((k for k, exts in FILE_KINDS.items() if ext in exts), "file")
        color = colors["accent"] if self.is_active() else colors["muted"]
        self.icon.setPixmap(make_icon(kind, color).pixmap(QSize(28, 28)))
        self.pause_button.setIcon(icon("play" if paused else "pause"))
        self.pause_button.setToolTip("Resume" if paused else "Pause")
        self.folder_button.setIcon(icon("folder"))
        self.close_button.setIcon(icon("close"))
        self.close_button.setToolTip("Cancel" if self.is_active() else "Remove from list")

    def toggle_pause(self):
        if self.download.isPaused():
            self.download.resume()
        else:
            self.download.pause()

    def cancel_or_remove(self):
        if self.is_active():
            self.download.cancel()
        else:
            self._window.downloads_panel.remove(self)

    def show_in_folder(self):
        self._window.downloads_panel.hide()
        self._window.reveal_in_files(self.path())

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if (event.button() == Qt.LeftButton
                and self.download.state() == DownloadState.DownloadCompleted):
            if os.path.exists(self.path()):
                self._window.downloads_panel.hide()
                self._window.open_file(self.path())
            else:
                self.status.setText("File was moved or deleted")


class DownloadsPanel(QFrame):
    """Popup listing this session's downloads, newest first."""

    def __init__(self, window: BrowserWindow):
        super().__init__(window, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._window = window
        self.items: list = []

        card = QFrame(objectName="downloadsCard")
        title = QLabel("Downloads", objectName="panelTitle")
        open_folder = QToolButton(objectName="textButton", autoRaise=True, text="Open folder")
        open_folder.setCursor(Qt.PointingHandCursor)
        open_folder.clicked.connect(self.open_folder)
        clear = QToolButton(objectName="textButton", autoRaise=True, text="Clear")
        clear.setCursor(Qt.PointingHandCursor)
        clear.setToolTip("Remove finished downloads from the list")
        clear.clicked.connect(self.clear_finished)
        header = QHBoxLayout()
        header.setContentsMargins(16, 12, 8, 4)
        header.addWidget(title, 1)
        header.addWidget(open_folder)
        header.addWidget(clear)

        self.empty = QLabel("Files you download will show up here.",
                            objectName="panelEmpty", alignment=Qt.AlignCenter)
        self.list = QWidget(objectName="downloadsList")
        self.list_layout = QVBoxLayout(self.list)
        self.list_layout.setContentsMargins(6, 0, 6, 6)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch(1)
        self.scroll = QScrollArea(objectName="downloadsScroll", widgetResizable=True)
        self.scroll.setWidget(self.list)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 6)
        card_layout.setSpacing(0)
        card_layout.addLayout(header)
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.scroll, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)
        self.setFixedWidth(400)
        self._sync()

    def add(self, item: DownloadItem):
        self.items.insert(0, item)
        self.list_layout.insertWidget(0, item)
        self._sync()

    def remove(self, item: DownloadItem):
        self.items.remove(item)
        item.hide()
        item.deleteLater()
        self._sync()
        self._window.update_downloads_button()

    def clear_finished(self):
        for item in [i for i in self.items if not i.is_active()]:
            self.remove(item)

    def open_folder(self):
        self.hide()
        self._window.add_tab(QUrl.fromLocalFile(self._window.download_folder()))

    def refresh_icons(self):
        for item in self.items:
            item.refresh_icons()

    def _sync(self):
        self.empty.setVisible(not self.items)
        self.scroll.setVisible(bool(self.items))
        rows = min(len(self.items), 5)
        self.setFixedHeight(56 + (rows * 74 if rows else 70))

    def show_below(self, button: QWidget):
        self._sync()
        pos = button.mapToGlobal(QPoint(button.width() - self.width(), button.height() + 4))
        self.move(pos)
        self.show()


# ----- window chrome -----------------------------------------------------

class TabBar(QTabBar):
    middle_clicked = Signal(int)

    def tabSizeHint(self, index: int) -> QSize:
        size = super().tabSizeHint(index)
        parent = self.parentWidget()
        # Leave room for the new-tab, files, editor, and terminal buttons.
        available = (parent.width() if parent else 1200) - 160
        size.setWidth(max(72, min(230, available // max(1, self.count()))))
        return size

    def minimumTabSizeHint(self, index: int) -> QSize:
        return self.tabSizeHint(index)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            index = self.tabAt(event.position().toPoint())
            if index >= 0:
                self.middle_clicked.emit(index)
                return
        super().mouseReleaseEvent(event)


class AddressBar(QLineEdit):
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(460)

        self.home = QLineEdit(placeholderText="https://example.com")
        self.engine = QComboBox()
        self.engine.addItems(list(SEARCH_ENGINES))
        self.theme = QComboBox()
        self.theme.addItems(THEMES)
        self.zoom = QComboBox()
        for z in ZOOM_CHOICES:
            self.zoom.addItem(f"{z}%", z)

        self.javascript = QCheckBox("Allow JavaScript")
        self.images = QCheckBox("Load images")
        self.force_dark = QCheckBox("Force dark mode on websites")
        self.force_dark.setVisible(FORCE_DARK is not None)
        content = QVBoxLayout()
        content.setSpacing(8)
        for box in (self.javascript, self.images, self.force_dark):
            content.addWidget(box)
        note = QLabel("Content changes apply after a page reloads.", objectName="sectionNote")
        content.addWidget(note)

        self.show_hidden = QCheckBox("Show hidden files")
        self.word_wrap = QCheckBox("Wrap long lines")
        self.download_dir = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_download_dir)
        download_row = QHBoxLayout()
        download_row.setSpacing(8)
        download_row.addWidget(self.download_dir, 1)
        download_row.addWidget(browse)
        self.ask_download = QCheckBox("Ask where to save each file")
        downloads = QVBoxLayout()
        downloads.setSpacing(8)
        downloads.addLayout(download_row)
        downloads.addWidget(self.ask_download)
        self.shell = QLineEdit()
        self.shell.setPlaceholderText("Automatic (" + os.path.basename(shell_command()[0]) + ")")
        self.shell.setToolTip("Command new shell tabs run. Leave empty for bash "
                              "(Git Bash on Windows, when it's installed).")
        self.startup = QComboBox()
        self.startup.addItem("Reopen the tabs from last time", True)
        self.startup.addItem("Open the home page", False)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.addRow("On startup", self.startup)
        form.addRow("Home page", self.home)
        form.addRow("Search engine", self.engine)
        form.addRow("Theme", self.theme)
        form.addRow("Default zoom", self.zoom)
        form.addRow("Websites", content)
        form.addRow("Downloads", downloads)
        form.addRow("Files", self.show_hidden)
        form.addRow("Text editor", self.word_wrap)
        form.addRow("Shell", self.shell)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(
            lambda: self._load(DEFAULTS.get))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(22)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._load(settings.get)

    def _load(self, get):
        self.home.setText(get("home_url"))
        self.engine.setCurrentText(get("search_engine"))
        self.theme.setCurrentText(get("theme"))
        self.zoom.setCurrentIndex(max(0, self.zoom.findData(get("zoom"))))
        self.javascript.setChecked(get("javascript"))
        self.images.setChecked(get("images"))
        self.force_dark.setChecked(get("force_dark"))
        self.show_hidden.setChecked(get("show_hidden"))
        self.word_wrap.setChecked(get("word_wrap"))
        self.startup.setCurrentIndex(0 if get("restore_session") else 1)
        self.download_dir.setText(QDir.toNativeSeparators(get("download_dir") or default_download_dir()))
        self.ask_download.setChecked(get("ask_download"))
        self.shell.setText(get("terminal_shell"))

    def _browse_download_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Download folder", self.download_dir.text())
        if folder:
            self.download_dir.setText(QDir.toNativeSeparators(folder))

    def accept(self):
        home = self.home.text().strip() or DEFAULTS["home_url"]
        self.settings.set("home_url", QUrl.fromUserInput(home).toString())
        self.settings.set("search_engine", self.engine.currentText())
        self.settings.set("theme", self.theme.currentText())
        self.settings.set("zoom", self.zoom.currentData())
        self.settings.set("javascript", self.javascript.isChecked())
        self.settings.set("images", self.images.isChecked())
        self.settings.set("force_dark", self.force_dark.isChecked())
        self.settings.set("show_hidden", self.show_hidden.isChecked())
        self.settings.set("word_wrap", self.word_wrap.isChecked())
        self.settings.set("restore_session", self.startup.currentData())
        folder = os.path.normpath(os.path.expanduser(self.download_dir.text().strip()))
        default = os.path.normpath(default_download_dir())
        self.settings.set("download_dir", "" if not self.download_dir.text().strip()
                          or folder == default else folder)
        self.settings.set("ask_download", self.ask_download.isChecked())
        self.settings.set("terminal_shell", self.shell.text().strip())
        super().accept()


class BrowserWindow(QMainWindow):
    def __init__(self, settings: Settings, start: QUrl | None = None):
        super().__init__()
        self.settings = settings
        self.colors = LIGHT
        self._views: list = []
        self._iconed: list = []
        self.thumbnails = Thumbnails(self)

        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)
        geometry = settings.store.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        self._build_actions()
        self._build_ui()
        self._build_menu()

        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda _scheme: self.apply_theme())

        self._session_timer = QTimer(self, singleShot=True, interval=1000)
        self._session_timer.timeout.connect(self.save_session)

        self.apply_settings()
        if settings.get("restore_session"):
            self.restore_session()
        if start is not None:
            path = start.toLocalFile() if start.isLocalFile() else ""
            if os.path.isfile(path) and not is_viewable(path):
                self.open_file(path)
            else:
                self.add_tab(start)
        if not self._views:
            self.add_tab(self.home_url(), focus_address=True)

    # ----- setup -------------------------------------------------------

    def _action(self, text, slot, shortcut=None, icon=None) -> QAction:
        act = QAction(text, self)
        if isinstance(shortcut, QKeySequence.StandardKey):
            act.setShortcuts(shortcut)
        elif shortcut:
            act.setShortcut(QKeySequence(shortcut))
        keys = act.shortcut().toString(QKeySequence.NativeText)
        act.setToolTip(f"{text} ({keys})" if keys else text)
        act.triggered.connect(slot)
        self.addAction(act)
        if icon:
            self._iconed.append((act, icon))
        return act

    def _build_actions(self):
        K = QKeySequence.StandardKey
        self.back_act = self._action("Back", lambda: self.current().back(), K.Back, "back")
        self.forward_act = self._action(
            "Forward", lambda: self.current().forward(), K.Forward, "forward")
        self.up_act = self._action("Up one folder", self.go_up, "Alt+Up", "up")
        self.reload_act = self._action("Reload", self.reload_or_stop, K.Refresh)
        self.home_act = self._action("Home", self.go_home, "Alt+Home", "home")
        self.new_tab_act = self._action(
            "New tab", lambda: self.add_tab(self.home_url(), focus_address=True), "Ctrl+T", "plus")
        self.new_files_act = self._action(
            "New files tab", lambda: self.add_tab(QUrl.fromLocalFile(QDir.homePath())),
            "Ctrl+E", "folder")
        self.new_text_act = self._action(
            "New text file", lambda: self.add_tab(view=EditorTab(self)), "Ctrl+N", "edit")
        self.new_terminal_act = self._action(
            "New terminal", lambda: self.new_terminal(), "Ctrl+`", "terminal")
        self.open_file_act = self._action("Open file…", self.open_file_dialog, "Ctrl+O")
        self.save_act = self._action("Save", self.save_current, "Ctrl+S")
        self.save_as_act = self._action("Save as…", self.save_current_as, "Ctrl+Shift+S")
        self._action("Close tab", lambda: self.close_tab(self.tabbar.currentIndex()), "Ctrl+W")
        self._action("Next tab", lambda: self.cycle_tab(1), "Ctrl+Tab")
        self._action("Previous tab", lambda: self.cycle_tab(-1), "Ctrl+Shift+Tab")
        self._action("Focus address bar", self.focus_address, "Ctrl+L")
        self.zoom_in_act = self._action("Zoom in", lambda: self.step_zoom(1), K.ZoomIn)
        self.zoom_out_act = self._action("Zoom out", lambda: self.step_zoom(-1), K.ZoomOut)
        self.zoom_reset_act = self._action("Reset zoom", self.reset_zoom, "Ctrl+0")
        self.hidden_act = self._action("Show hidden files", self.toggle_hidden, "Ctrl+H")
        self.hidden_act.setCheckable(True)
        self.wrap_act = self._action("Word wrap", self.toggle_word_wrap, "Alt+Z")
        self.wrap_act.setCheckable(True)
        self.settings_act = self._action("Settings…", self.open_settings, "Ctrl+,")
        self.clear_act = self._action(
            "Clear browsing data…", self.clear_browsing_data, "Ctrl+Shift+Delete")
        self.about_act = self._action(f"About {APP_NAME}", self.show_about)
        self.quit_act = self._action("Quit", self.close, "Ctrl+Q")
        self.downloads_act = self._action("Downloads", self.show_downloads, "Ctrl+J")

    def _tool_button(self, action: QAction, size: int = 34, icon: int = 18) -> QToolButton:
        button = QToolButton()
        button.setDefaultAction(action)
        button.setAutoRaise(True)
        button.setFixedSize(size, size)
        button.setIconSize(QSize(icon, icon))
        button.setCursor(Qt.PointingHandCursor)
        return button

    def _build_ui(self):
        self.tabbar = TabBar()
        self.tabbar.setDocumentMode(True)
        self.tabbar.setDrawBase(False)
        self.tabbar.setExpanding(False)
        self.tabbar.setMovable(True)
        self.tabbar.setUsesScrollButtons(False)
        self.tabbar.setElideMode(Qt.ElideRight)
        self.tabbar.setIconSize(QSize(16, 16))
        self.tabbar.currentChanged.connect(self.on_tab_changed)
        self.tabbar.tabMoved.connect(self._on_tab_moved)
        self.tabbar.middle_clicked.connect(self.close_tab)

        tab_row = QWidget(objectName="tabRow")
        tab_layout = QHBoxLayout(tab_row)
        tab_layout.setContentsMargins(8, 8, 8, 0)
        tab_layout.setSpacing(2)
        tab_layout.addWidget(self.tabbar, 0, Qt.AlignBottom)
        tab_layout.addSpacing(2)
        for act in (self.new_tab_act, self.new_files_act, self.new_text_act,
                    self.new_terminal_act):
            button = self._tool_button(act, size=28, icon=16)
            button.setObjectName("newTab")
            tab_layout.addWidget(button, 0, Qt.AlignVCenter)
        tab_layout.addStretch(1)

        self.address = AddressBar(
            objectName="address", placeholderText="Search, enter an address, or a folder path")
        self.address.setClearButtonEnabled(True)
        self.address.returnPressed.connect(self.navigate)
        self.address_icon = self.address.addAction(QIcon(), QLineEdit.LeadingPosition)

        self.downloads_button = self._tool_button(self.downloads_act)
        self.downloads_button.hide()
        self.downloads_panel = DownloadsPanel(self)
        # The panel is its own popup window, so window shortcuts don't reach it otherwise.
        self.downloads_panel.addActions([self.downloads_act, self.quit_act])
        QWebEngineProfile.defaultProfile().downloadRequested.connect(self.on_download_requested)

        self.menu_button = QToolButton()
        self.menu_button.setAutoRaise(True)
        self.menu_button.setFixedSize(34, 34)
        self.menu_button.setIconSize(QSize(18, 18))
        self.menu_button.setToolTip("Menu")
        self.menu_button.setCursor(Qt.PointingHandCursor)
        self.menu_button.clicked.connect(self.show_menu)
        self._iconed.append((self.menu_button, "menu"))

        nav_row = QWidget(objectName="navRow")
        nav = QHBoxLayout(nav_row)
        nav.setContentsMargins(8, 6, 8, 6)
        nav.setSpacing(2)
        for act in (self.back_act, self.forward_act):
            nav.addWidget(self._tool_button(act))
        self.up_button = self._tool_button(self.up_act)
        nav.addWidget(self.up_button)
        for act in (self.reload_act, self.home_act):
            nav.addWidget(self._tool_button(act))
        nav.addSpacing(6)
        nav.addWidget(self.address, 1)
        nav.addSpacing(6)
        nav.addWidget(self.downloads_button)
        nav.addWidget(self.menu_button)

        self.load_bar = QProgressBar(objectName="loadBar", textVisible=False)
        self.load_bar.setRange(0, 100)
        self.load_bar.setFixedHeight(2)

        self.stack = QStackedWidget()
        self.link_hint = QLabel(self.stack, objectName="linkHint")
        self.link_hint.hide()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(tab_row)
        layout.addWidget(nav_row)
        layout.addWidget(self.load_bar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    def _build_menu(self):
        menu = QMenu(self)
        menu.addAction(self.new_tab_act)
        menu.addAction(self.new_files_act)
        menu.addAction(self.new_text_act)
        menu.addAction(self.new_terminal_act)
        menu.addAction(self.open_file_act)
        menu.addAction(self.save_act)
        menu.addAction(self.save_as_act)
        menu.addSeparator()
        menu.addAction(self.zoom_in_act)
        menu.addAction(self.zoom_out_act)
        menu.addAction(self.zoom_reset_act)
        menu.addSeparator()
        menu.addAction(self.hidden_act)
        menu.addAction(self.wrap_act)

        theme_menu = menu.addMenu("Theme")
        group = QActionGroup(self)
        self.theme_actions = {}
        for name in THEMES:
            act = theme_menu.addAction(name)
            act.setCheckable(True)
            group.addAction(act)
            act.triggered.connect(lambda _checked=False, n=name: self.set_theme(n))
            self.theme_actions[name] = act

        menu.addAction(self.settings_act)
        menu.addAction(self.downloads_act)
        menu.addAction(self.clear_act)
        menu.addSeparator()
        menu.addAction(self.about_act)
        menu.addAction(self.quit_act)
        for act in menu.actions():
            act.setIconVisibleInMenu(False)
        self.menu = menu

    def show_menu(self):
        zoom = round(self.current().zoomFactor() * 100)
        self.zoom_reset_act.setText(f"Reset zoom ({zoom}%)")
        self.theme_actions[self.settings.get("theme")].setChecked(True)
        button = self.menu_button
        pos = QPoint(button.width() - self.menu.sizeHint().width(), button.height() + 4)
        self.menu.exec(button.mapToGlobal(pos))

    # ----- settings & theme -------------------------------------------

    def home_url(self) -> QUrl:
        return QUrl.fromUserInput(self.settings.get("home_url"))

    def apply_settings(self):
        web = QWebEngineProfile.defaultProfile().settings()
        attr = QWebEngineSettings.WebAttribute
        web.setAttribute(attr.JavascriptEnabled, self.settings.get("javascript"))
        web.setAttribute(attr.AutoLoadImages, self.settings.get("images"))
        web.setAttribute(attr.PluginsEnabled, True)
        web.setAttribute(attr.PdfViewerEnabled, True)
        if FORCE_DARK is not None:
            web.setAttribute(FORCE_DARK, self.settings.get("force_dark"))
        self.hidden_act.setChecked(self.settings.get("show_hidden"))
        self.wrap_act.setChecked(self.settings.get("word_wrap"))
        for view in self._views:
            view.setZoomFactor(self.settings.get("zoom") / 100)
            if isinstance(view, FilesTab):
                view.apply_filter()
            elif isinstance(view, EditorTab):
                view.set_word_wrap(self.settings.get("word_wrap"))
        self.apply_theme()

    def toggle_hidden(self):
        self.settings.set("show_hidden", not self.settings.get("show_hidden"))
        self.hidden_act.setChecked(self.settings.get("show_hidden"))
        for view in self._views:
            if isinstance(view, FilesTab):
                view.apply_filter()

    def toggle_word_wrap(self):
        wrap = not self.settings.get("word_wrap")
        self.settings.set("word_wrap", wrap)
        self.wrap_act.setChecked(wrap)
        for view in self._views:
            if isinstance(view, EditorTab):
                view.set_word_wrap(wrap)

    def set_theme(self, name: str):
        self.settings.set("theme", name)
        self.apply_theme()

    def apply_theme(self):
        theme = self.settings.get("theme")
        dark = theme == "Dark" or (theme == "System" and system_prefers_dark())
        self.colors = DARK if dark else LIGHT
        app = QApplication.instance()
        app.setPalette(make_palette(self.colors))
        app.setStyleSheet(STYLE.substitute(self.colors))
        for target, name in self._iconed:
            target.setIcon(self.icon(name))
        for i in range(self.tabbar.count()):
            self.tabbar.tabButton(i, QTabBar.RightSide).setIcon(self.icon("close"))
        for view in self._views:
            if not isinstance(view, BrowserTab):
                view.refresh_icons()
        self.downloads_panel.refresh_icons()
        self.update_downloads_button()
        if self._views:
            self.update_load_state()
            self.update_address_icon()

    def icon(self, name: str, muted: bool = False) -> QIcon:
        c = self.colors
        return make_icon(name, c["muted"] if muted else c["icon"], c["disabled"])

    def open_settings(self):
        if SettingsDialog(self.settings, self).exec():
            self.apply_settings()

    def clear_browsing_data(self):
        answer = QMessageBox.question(
            self, "Clear browsing data",
            "Clear cookies, cached files, and back/forward history for all tabs?")
        if answer != QMessageBox.Yes:
            return
        profile = QWebEngineProfile.defaultProfile()
        profile.clearHttpCache()
        profile.cookieStore().deleteAllCookies()
        profile.clearAllVisitedLinks()
        for view in self._views:
            view.clear_history()
        self.update_nav_buttons()
        self.show_hint("Browsing data cleared", timeout=2500)

    def show_about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME}</b><p>A small tabbed web browser, file browser, text editor, "
            "and terminal built with "
            f"PySide6 {PySide6.__version__} and Qt {qVersion()}.</p>")

    # ----- tabs --------------------------------------------------------

    def current(self):
        return self._views[self.tabbar.currentIndex()]

    def _index(self, view) -> int:
        return self._views.index(view) if view in self._views else -1

    def _button_index(self, button: QToolButton) -> int:
        for i in range(self.tabbar.count()):
            if self.tabbar.tabButton(i, QTabBar.RightSide) is button:
                return i
        return -1

    def _new_view(self, url: QUrl | None):
        if url is not None and url.isLocalFile() and os.path.isdir(url.toLocalFile()):
            view = FilesTab(self, url.toLocalFile())
        else:
            view = BrowserTab(self)
        view.setZoomFactor(self.settings.get("zoom") / 100)
        return view

    def _connect_view(self, view):
        view.titleChanged.connect(lambda title, v=view: self.on_title(v, title))
        view.iconChanged.connect(
            lambda icon, v=view: self.tabbar.setTabIcon(self._index(v), icon))
        view.urlChanged.connect(lambda _url, v=view: self.on_url(v))
        if isinstance(view, BrowserTab):
            view.loadStarted.connect(lambda v=view: self.on_load(v, True))
            view.loadProgress.connect(lambda p, v=view: self.on_progress(v, p))
            view.loadFinished.connect(lambda _ok, v=view: self.on_load(v, False))
            view.page().linkHovered.connect(
                lambda link, v=view: v is self.current() and self.show_hint(link))
        else:
            view.refresh_icons()

    def show_view(self, view):
        index = self._index(view)
        if index >= 0:
            self.tabbar.setCurrentIndex(index)

    def add_tab(self, url: QUrl | None = None, focus_address: bool = False, view=None):
        if view is None:
            view = self._new_view(url)
        self.stack.addWidget(view)
        self._views.append(view)
        index = self.tabbar.addTab("New Tab")

        close = QToolButton(objectName="tabClose", autoRaise=True, toolTip="Close tab")
        close.setFixedSize(18, 18)
        close.setIconSize(QSize(12, 12))
        close.setIcon(self.icon("close"))
        close.clicked.connect(lambda _checked=False, b=close: self.close_tab(self._button_index(b)))
        self.tabbar.setTabButton(index, QTabBar.RightSide, close)

        self._connect_view(view)
        self.on_title(view, view.title())
        self.tabbar.setCurrentIndex(index)
        if isinstance(view, BrowserTab) and url is not None:
            view.setUrl(url)
        if focus_address:
            self.focus_address()
        elif not isinstance(view, BrowserTab):
            view.focus_view()
        return view

    def replace_view(self, index: int, view):
        old = self._views[index]
        self._views[index] = view
        self.stack.addWidget(view)
        self.tabbar.setTabIcon(index, QIcon())
        self._connect_view(view)
        self.stack.removeWidget(old)
        old.deleteLater()
        self.on_title(view, view.title())
        if index == self.tabbar.currentIndex():
            self.on_tab_changed(index)

    def close_tab(self, index: int):
        if index < 0:
            return
        if self.tabbar.count() == 1:
            self.close()
            return
        view = self._views[index]
        if isinstance(view, (EditorTab, TerminalTab)) and not view.maybe_close():
            return
        if isinstance(view, TerminalTab):
            view.shutdown()
        self._views.pop(index)
        self.tabbar.removeTab(index)
        self.stack.removeWidget(view)
        view.deleteLater()
        self.schedule_session_save()

    def _on_tab_moved(self, src: int, dst: int):
        self._views.insert(dst, self._views.pop(src))
        self.schedule_session_save()

    def cycle_tab(self, step: int):
        self.tabbar.setCurrentIndex((self.tabbar.currentIndex() + step) % self.tabbar.count())

    def on_tab_changed(self, index: int):
        if not 0 <= index < len(self._views):
            return
        view = self._views[index]
        self.stack.setCurrentWidget(view)
        self.link_hint.hide()
        self.up_button.setVisible(isinstance(view, FilesTab))
        self.save_act.setEnabled(isinstance(view, EditorTab))
        self.save_as_act.setEnabled(isinstance(view, EditorTab))
        self.on_url(view)
        self.on_title(view, view.title())
        self.update_load_state()
        self.schedule_session_save()

    # ----- session -----------------------------------------------------

    def schedule_session_save(self):
        self._session_timer.start()

    def save_session(self):
        tabs, current = [], 0
        active = self.current() if self._views else None
        for view in self._views:
            if view is active:
                current = len(tabs)
            entry = {"zoom": view.zoomFactor()}
            if isinstance(view, FilesTab):
                entry.update(type="files", path=view.path)
            elif isinstance(view, EditorTab):
                if not view.path:
                    continue
                entry.update(type="editor", path=view.path,
                             cursor=view.editor.textCursor().position())
            elif isinstance(view, TerminalTab):
                entry.update(type="terminal", path=view.cwd)
            else:
                url = view.url().toString()
                if not url:
                    continue
                entry.update(type="web", url=url)
            tabs.append(entry)
        self.settings.set_session({"tabs": tabs, "current": current})

    def restore_session(self):
        session = self.settings.get_session()
        restored = []
        for entry in session.get("tabs", []):
            kind, view = entry.get("type"), None
            if kind == "web" and entry.get("url"):
                view = self.add_tab(QUrl(entry["url"]))
            elif kind == "files" and os.path.isdir(entry.get("path", "")):
                view = self.add_tab(QUrl.fromLocalFile(entry["path"]))
            elif kind == "editor" and os.path.isfile(entry.get("path", "")):
                view = self.open_in_editor(entry["path"])
                if isinstance(view, EditorTab):
                    cursor = view.editor.textCursor()
                    cursor.setPosition(min(int(entry.get("cursor", 0)),
                                           view.editor.document().characterCount() - 1))
                    view.editor.setTextCursor(cursor)
                    view.editor.centerCursor()
            elif kind == "terminal":
                folder = entry.get("path", "")
                if not os.path.isdir(folder):
                    folder = QDir.homePath()
                view = self.new_terminal(folder)
            if view is not None:
                view.setZoomFactor(float(entry.get("zoom", 1.0)))
                restored.append(view)
        current = session.get("current", 0)
        if 0 <= current < len(restored):
            self.show_view(restored[current])

    # ----- navigation --------------------------------------------------

    def focus_address(self):
        self.address.setFocus()
        self.address.selectAll()

    def navigate(self):
        self.address.setModified(False)
        self.open_in_tab(to_url(self.address.text(), self.settings), self.tabbar.currentIndex())

    def open_in_tab(self, url: QUrl, index: int):
        """Show `url` in an existing tab, switching it between web page and folder as needed."""
        view = self._views[index]
        if isinstance(view, TerminalTab):
            self.on_url(view)
            if url.isLocalFile() and os.path.isdir(url.toLocalFile()):
                if not view.change_directory(url.toLocalFile()):
                    self.new_terminal(url.toLocalFile())
                return
        if isinstance(view, (EditorTab, TerminalTab)):
            # Keep what's open; show whatever was typed in a new tab instead.
            self.on_url(view)
            if url.isLocalFile() and not os.path.isdir(url.toLocalFile()):
                if os.path.exists(url.toLocalFile()):
                    self.open_file(url.toLocalFile())
                else:
                    self.show_hint(f"Couldn't find {QDir.toNativeSeparators(url.toLocalFile())}",
                                   timeout=3000)
            else:
                self.add_tab(url)
            return
        if url.isLocalFile():
            path = url.toLocalFile()
            if os.path.isdir(path):
                if isinstance(view, FilesTab):
                    view.set_path(path)
                else:
                    self.replace_view(index, self._new_view(url))
                self._views[index].focus_view()
                return
            if not os.path.exists(path):
                self.show_hint(f"Couldn't find {QDir.toNativeSeparators(path)}", timeout=3000)
                self.on_url(view)
                return
            if not is_viewable(path):
                self.on_url(view)
                self.open_file(path)
                return
        if isinstance(view, FilesTab):
            view = self._new_view(None)
            self.replace_view(index, view)
        view.setUrl(url)
        view.setFocus()

    def open_file(self, path: str):
        url = QUrl.fromLocalFile(path)
        if is_viewable(path):
            self.add_tab(url)
        elif is_text(path):
            self.open_in_editor(path)
        else:
            QDesktopServices.openUrl(url)

    def open_in_editor(self, path: str):
        path = os.path.normpath(path)
        for view in self._views:
            if isinstance(view, EditorTab) and view.path == path:
                self.show_view(view)
                return view
        try:
            text, crlf = read_text_file(path)
        except ValueError as error:
            reason = "is too large to edit" if str(error) == "too large" else "isn't a text file"
            QMessageBox.information(
                self, "Open file", f"“{os.path.basename(path)}” {reason}, "
                "so it will open in its default app.")
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            return None
        except OSError as error:
            QMessageBox.warning(self, "Open file", f"Couldn't open “{os.path.basename(path)}"
                                f"”: {error.strerror or error}")
            return None
        return self.add_tab(view=EditorTab(self, path, text, crlf))

    def new_terminal(self, cwd: str | None = None):
        if cwd is None:
            cwd = self._folder_for_terminal()
        return self.add_tab(view=TerminalTab(self, cwd))

    def _folder_for_terminal(self) -> str | None:
        if not self._views:
            return None
        view = self.current()
        if isinstance(view, FilesTab):
            return view.path
        if isinstance(view, TerminalTab):
            return view.cwd
        if isinstance(view, EditorTab) and view.path:
            return os.path.dirname(view.path)
        return None

    def open_file_dialog(self):
        view = self.current()
        if isinstance(view, FilesTab):
            start = view.path
        elif isinstance(view, EditorTab) and view.path:
            start = os.path.dirname(view.path)
        else:
            start = QDir.homePath()
        paths, _filter = QFileDialog.getOpenFileNames(self, "Open file", start)
        for path in paths:
            self.open_file(path)

    def save_current(self):
        view = self.current()
        if isinstance(view, EditorTab):
            view.save()

    def save_current_as(self):
        view = self.current()
        if isinstance(view, EditorTab):
            view.save_as()

    def go_home(self):
        view = self.current()
        if isinstance(view, FilesTab):
            view.set_path(QDir.homePath())
        elif isinstance(view, (EditorTab, TerminalTab)):
            self.add_tab(self.home_url())
        else:
            view.setUrl(self.home_url())

    def go_up(self):
        view = self.current()
        if isinstance(view, FilesTab):
            view.up()

    def reload_or_stop(self):
        view = self.current()
        view.stop() if view.loading else view.reload()

    def step_zoom(self, direction: int):
        view = self.current()
        factor = view.zoomFactor()
        if direction > 0:
            options = [z for z in ZOOM_STEPS if z > factor + 0.001]
            target = options[0] if options else ZOOM_STEPS[-1]
        else:
            options = [z for z in ZOOM_STEPS if z < factor - 0.001]
            target = options[-1] if options else ZOOM_STEPS[0]
        view.setZoomFactor(target)
        self.show_hint(f"Zoom {round(target * 100)}%", timeout=1200)

    def reset_zoom(self):
        self.current().setZoomFactor(self.settings.get("zoom") / 100)
        self.show_hint(f"Zoom {self.settings.get('zoom')}%", timeout=1200)

    # ----- view events -------------------------------------------------

    def on_title(self, view, title: str):
        index = self._index(view)
        if index < 0:
            return
        label = title or "New Tab"
        self.tabbar.setTabText(index, label)
        self.tabbar.setTabToolTip(index, label)
        if view is self.current():
            self.setWindowTitle(f"{label} — {APP_NAME}")

    def on_url(self, view):
        self.schedule_session_save()
        if view is not self.current():
            return
        if not self.address.hasFocus() or not self.address.isModified():
            self.address.setText(view.location())
            self.address.setCursorPosition(0)
        self.update_address_icon()
        self.update_nav_buttons()

    def on_load(self, view: BrowserTab, loading: bool):
        view.loading = loading
        view.progress = 0
        if view is self.current():
            self.update_load_state()

    def on_progress(self, view: BrowserTab, progress: int):
        view.progress = progress
        if view is self.current():
            self.load_bar.setValue(progress)

    def update_load_state(self):
        view = self.current()
        self.load_bar.setValue(view.progress if view.loading else 0)
        self.reload_act.setIcon(self.icon("stop" if view.loading else "reload"))
        self.reload_act.setText("Stop" if view.loading else "Reload")
        self.reload_act.setToolTip("Stop loading" if view.loading else "Reload (F5)")
        self.update_nav_buttons()

    def update_nav_buttons(self):
        view = self.current()
        self.back_act.setEnabled(view.can_go_back())
        self.forward_act.setEnabled(view.can_go_forward())
        self.up_act.setEnabled(isinstance(view, FilesTab) and view.can_go_up())

    def update_address_icon(self):
        name = self.current().address_icon_name()
        self.address_icon.setIcon(self.icon(name, muted=True))
        self.address_icon.setToolTip("Secure connection" if name == "lock" else "")

    def show_hint(self, text: str, timeout: int = 0):
        if not text:
            self.link_hint.hide()
            return
        metrics = self.link_hint.fontMetrics()
        self.link_hint.setText(metrics.elidedText(text, Qt.ElideMiddle, self.stack.width() // 2))
        self.link_hint.adjustSize()
        self.link_hint.move(10, self.stack.height() - self.link_hint.height() - 10)
        self.link_hint.raise_()
        self.link_hint.show()
        if timeout:
            QTimer.singleShot(timeout, self.link_hint.hide)

    # ----- window ------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Forces QTabBar to re-query tabSizeHint so tabs shrink/grow with the window.
        self.tabbar.setElideMode(Qt.ElideRight)
        self.tabbar.updateGeometry()
        self.link_hint.hide()

    # ----- downloads -------------------------------------------------

    def download_folder(self) -> str:
        return self.settings.get("download_dir") or default_download_dir()

    def on_download_requested(self, download: QWebEngineDownloadRequest):
        folder = self.download_folder()
        name = download.downloadFileName() or "download"
        if self.settings.get("ask_download"):
            path, _filter = QFileDialog.getSaveFileName(
                self, "Save file", os.path.join(folder, name))
            if not path:
                download.cancel()
                return
            folder, name = os.path.split(os.path.normpath(path))
        else:
            os.makedirs(folder, exist_ok=True)
            name = unique_name(folder, name)
        download.setDownloadDirectory(folder)
        download.setDownloadFileName(name)
        download.accept()
        self.downloads_panel.add(DownloadItem(self, download))
        self.downloads_button.show()
        if not self.downloads_panel.isVisible():
            self.show_downloads()

    def show_downloads(self):
        if self.downloads_panel.isVisible():
            self.downloads_panel.hide()
            return
        self.downloads_panel.show_below(
            self.downloads_button if self.downloads_button.isVisible() else self.menu_button)

    def active_downloads(self) -> list:
        return [item for item in self.downloads_panel.items if item.is_active()]

    def update_downloads_button(self):
        active = len(self.active_downloads())
        color = self.colors["accent"] if active else self.colors["icon"]
        self.downloads_act.setIcon(make_icon("downloads", color, self.colors["disabled"]))
        self.downloads_act.setToolTip(
            f"{plural(active, 'download')} in progress (Ctrl+J)" if active else "Downloads (Ctrl+J)")

    def reveal_in_files(self, path: str):
        view = self.add_tab(QUrl.fromLocalFile(os.path.dirname(path)))
        if isinstance(view, FilesTab):
            view.reveal(path)

    def closeEvent(self, event):
        self.downloads_panel.hide()
        active = self.active_downloads()
        if active:
            answer = QMessageBox.question(
                self, "Downloads in progress",
                f"{plural(len(active), 'download')} still in progress. Quit and cancel "
                f"{'it' if len(active) == 1 else 'them'}?")
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        for view in list(self._views):
            if isinstance(view, (EditorTab, TerminalTab)) and not view.maybe_close():
                event.ignore()
                return
        for view in self._views:
            if isinstance(view, TerminalTab):
                view.shutdown()
        self._session_timer.stop()
        self.save_session()
        self.settings.store.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    settings = Settings()
    start = to_url(" ".join(sys.argv[1:]), settings) if len(sys.argv) > 1 else None
    window = BrowserWindow(settings, start)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
