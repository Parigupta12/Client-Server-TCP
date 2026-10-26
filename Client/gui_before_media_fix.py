# ============================================================
# TCP CHAT APPLICATION
# PHASE 9 - FILE / MEDIA + VOICE MESSAGES
# ============================================================
# Full replacement for Client/gui.py
#
# Features
#   - Private chat
#   - Broadcast chat
#   - Online client list
#   - Text messages
#   - Arbitrary file/document sending
#   - Images with preview
#   - Audio/video/document cards
#   - Voice-message recording from microphone
#   - Recorded voice message sent through the existing FILE protocol
#   - Built-in audio playback for voice/audio cards
#   - OPEN FILE / OPEN FOLDER
#   - No QTextBrowser hyperlinks
#   - No QUrl.queryItemValue
#   - No video call
#   - No voice call
#   - Thread-safe transfer completion UI
#   - Duplicate incoming file-card protection
#
# Compatibility
#   Existing Client/network.py API:
#       send_private_message(target_id, message)
#       send_broadcast_message(message)
#       send_file(target_id, file_path)
#       message_received signal
#       connection_changed signal
#       client_info_received signal
#       client_list_received signal
#       optional file_received signal
#
# Voice recording uses Qt Multimedia QAudioSource. It records raw
# PCM into a WAV file and then sends that WAV through send_file().
# ============================================================

import os
import re
import sys
import struct
import subprocess
import threading
import time
import wave

from PySide6.QtCore import Qt, Signal, QObject, QUrl, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QLabel,
    QFrame,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QMenu,
    QSizePolicy,
)

from PySide6.QtCore import QFile, QIODevice

try:
    from PySide6.QtMultimedia import (
        QAudioSource,
        QMediaDevices,
        QAudioFormat,
        QMediaPlayer,
        QAudioOutput,
    )
    MULTIMEDIA_AVAILABLE = True
except Exception:
    QAudioSource = None
    QMediaDevices = None
    QAudioFormat = None
    QMediaPlayer = None
    QAudioOutput = None
    MULTIMEDIA_AVAILABLE = False

try:
    from .network import NetworkClient
except ImportError:
    from network import NetworkClient


# ============================================================
# COLORS
# ============================================================

BACKGROUND = "#0b1120"
SIDEBAR = "#111827"
PANEL = "#151f32"
PANEL_LIGHT = "#1c2940"

ACCENT = "#00bcd4"
ACCENT_DARK = "#008fa3"

TEXT = "#e5e7eb"
TEXT_SECONDARY = "#94a3b8"
BORDER = "#26344d"
SUCCESS = "#22c55e"
DANGER = "#ef4444"
WARNING = "#f59e0b"

MESSAGE_RECEIVED = "#172235"
MESSAGE_SENT = "#008fa3"


# ============================================================
# MEDIA EXTENSIONS
# ============================================================

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
    ".tif", ".tiff", ".ico",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm",
    ".m4v", ".3gp", ".mpeg", ".mpg",
}

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg",
    ".wma", ".opus",
}

DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt",
    ".pptx", ".txt", ".csv", ".json", ".xml", ".zip",
    ".rar", ".7z", ".py", ".c", ".cpp", ".java", ".html",
    ".css", ".js", ".md",
}


# ============================================================
# HELPERS
# ============================================================


def file_category(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return "IMAGE"
    if ext in VIDEO_EXTENSIONS:
        return "VIDEO"
    if ext in AUDIO_EXTENSIONS:
        return "AUDIO"
    if ext in DOCUMENT_EXTENSIONS:
        return "DOCUMENT"
    return "FILE"


def file_icon(path):
    category = file_category(path)
    return {
        "IMAGE": "🖼️",
        "VIDEO": "🎬",
        "AUDIO": "🎵",
        "DOCUMENT": "📄",
        "FILE": "📎",
    }[category]


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def format_size(size):
    size = safe_int(size)
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.2f} KB"
    if size < 1024 ** 3:
        return f"{size / (1024 ** 2):.2f} MB"
    return f"{size / (1024 ** 3):.2f} GB"


def unique_path(path):
    if not os.path.exists(path):
        return path

    directory = os.path.dirname(path)
    filename = os.path.basename(path)
    stem, ext = os.path.splitext(filename)

    index = 1
    while True:
        candidate = os.path.join(
            directory,
            f"{stem} ({index}){ext}",
        )
        if not os.path.exists(candidate):
            return candidate
        index += 1


def open_local_path(path):
    path = os.path.normpath(path)

    if not os.path.isfile(path) and not os.path.isdir(path):
        raise FileNotFoundError(path)

    if sys.platform.startswith("win"):
        os.startfile(path)
        return

    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
        return

    subprocess.Popen(["xdg-open", path])


def open_folder_select(path):
    folder = os.path.dirname(os.path.abspath(path))

    if not os.path.isdir(folder):
        raise FileNotFoundError(folder)

    if sys.platform.startswith("win"):
        subprocess.Popen([
            "explorer",
            "/select,",
            os.path.normpath(path),
        ])
        return

    if sys.platform == "darwin":
        subprocess.Popen(["open", folder])
        return

    subprocess.Popen(["xdg-open", folder])


def escape_html(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ============================================================
# FILE / MEDIA CARD
# ============================================================

class FileCard(QFrame):
    """Real Qt widget for a file/media message."""

    def __init__(self, data, parent=None):
        super().__init__(parent)

        self.data = dict(data or {})
        self.path = self.data.get("path", "")
        self.filename = self.data.get("filename", os.path.basename(self.path))
        self.size = safe_int(self.data.get("size", 0))
        self.direction = self.data.get("direction", "received")
        self.is_voice = bool(self.data.get("is_voice", False))

        self.player = None
        self.audio_output = None

        self.setObjectName("fileCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)

        icon_label = QLabel(
            "🎤" if self.is_voice else file_icon(self.path)
        )
        icon_label.setObjectName("fileIcon")
        icon_label.setFixedWidth(34)
        icon_label.setAlignment(Qt.AlignCenter)
        top.addWidget(icon_label)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        name_label = QLabel(self.filename)
        name_label.setObjectName("fileName")
        name_label.setWordWrap(True)
        title_layout.addWidget(name_label)

        if self.is_voice:
            subtitle = "VOICE MESSAGE"
        else:
            subtitle = file_category(self.path)

        meta_label = QLabel(
            f"{subtitle} • {format_size(self.size)}"
        )
        meta_label.setObjectName("fileMeta")
        title_layout.addWidget(meta_label)

        top.addLayout(title_layout, 1)
        outer.addLayout(top)

        if file_category(self.path) == "IMAGE":
            self.add_image_preview(outer)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        if self.is_voice or file_category(self.path) == "AUDIO":
            self.play_button = QPushButton("▶  PLAY")
            self.play_button.clicked.connect(self.toggle_audio)
            buttons.addWidget(self.play_button)

        open_button = QPushButton("OPEN FILE ↗")
        open_button.clicked.connect(self.open_file)
        buttons.addWidget(open_button)

        folder_button = QPushButton("OPEN FOLDER")
        folder_button.clicked.connect(self.open_folder)
        buttons.addWidget(folder_button)

        outer.addLayout(buttons)

    def add_image_preview(self, layout):
        try:
            pixmap = QPixmap(self.path)
            if pixmap.isNull():
                return

            preview = QLabel()
            preview.setAlignment(Qt.AlignCenter)
            preview.setMaximumSize(QSize(520, 300))

            preview.setPixmap(
                pixmap.scaled(
                    520,
                    300,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

            layout.addWidget(preview)
        except Exception:
            pass

    def toggle_audio(self):
        if not self.path or not os.path.isfile(self.path):
            QMessageBox.warning(
                self,
                "Audio Not Found",
                f"The audio file does not exist:\n\n{self.path}",
            )
            return

        if not MULTIMEDIA_AVAILABLE:
            try:
                open_local_path(self.path)
            except Exception as error:
                QMessageBox.critical(self, "Playback Error", str(error))
            return

        try:
            if self.player is None:
                self.audio_output = QAudioOutput()
                self.player = QMediaPlayer()
                self.player.setAudioOutput(self.audio_output)
                self.player.mediaStatusChanged.connect(self._media_status_changed)
                self.player.errorOccurred.connect(self._player_error)

            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()
                self.play_button.setText("▶  PLAY")
                return

            self.player.setSource(QUrl.fromLocalFile(self.path))
            self.player.play()
            self.play_button.setText("⏸  PAUSE")

        except Exception as error:
            QMessageBox.warning(
                self,
                "Playback Error",
                str(error),
            )

    def _media_status_changed(self, status):
        if not self.player:
            return

        if status in (
            QMediaPlayer.MediaStatus.EndOfMedia,
            QMediaPlayer.MediaStatus.InvalidMedia,
        ):
            if hasattr(self, "play_button"):
                self.play_button.setText("▶  PLAY")

    def _player_error(self, error, error_string):
        if error_string:
            print(f"[AUDIO] Playback error: {error_string}")
        if hasattr(self, "play_button"):
            self.play_button.setText("▶  PLAY")

    def open_file(self):
        try:
            open_local_path(self.path)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Could Not Open File",
                f"Could not open:\n\n{self.path}\n\n{error}",
            )

    def open_folder(self):
        try:
            open_folder_select(self.path)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Could Not Open Folder",
                str(error),
            )

    def close_player(self):
        try:
            if self.player:
                self.player.stop()
        except Exception:
            pass


# ============================================================
# VOICE RECORDER
# ============================================================

class VoiceRecorder(QObject):
    """Record microphone PCM to a WAV file using Qt Multimedia."""

    recording_started = Signal(str)
    recording_stopped = Signal(str, int)
    recording_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.audio_source = None
        self.audio_file = None
        self.path = None
        self.audio_format = None
        self.data_offset = 44
        self.started_at = None

    def is_recording(self):
        return self.audio_source is not None

    def _choose_format(self):
        if not MULTIMEDIA_AVAILABLE:
            raise RuntimeError(
                "Qt Multimedia is not available. "
                "Install PySide6 with Qt Multimedia support."
            )

        device = QMediaDevices.defaultAudioInput()

        if device.isNull():
            raise RuntimeError("No microphone/audio input device was found.")

        # Prefer a standard voice-recording format.
        preferred = QAudioFormat()
        preferred.setSampleRate(44100)
        preferred.setChannelCount(1)
        preferred.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        if device.isFormatSupported(preferred):
            return device, preferred

        # Fall back to the system's preferred microphone format.
        fallback = device.preferredFormat()
        if fallback.sampleRate() <= 0 or fallback.channelCount() <= 0:
            raise RuntimeError("The microphone returned an invalid audio format.")

        return device, fallback

    def start(self, path):
        if self.is_recording():
            return False

        try:
            device, fmt = self._choose_format()

            directory = os.path.dirname(os.path.abspath(path))
            os.makedirs(directory, exist_ok=True)

            # We reserve the first 44 bytes for the WAV header.
            with open(path, "wb") as raw:
                raw.write(b"\x00" * 44)

            qfile = QFile(path)
            if not qfile.open(QIODevice.OpenModeFlag.WriteOnly | QIODevice.OpenModeFlag.Append):
                raise RuntimeError(
                    f"Could not open recording file: {qfile.errorString()}"
                )

            source = QAudioSource(device, fmt)
            source.start(qfile)

            self.audio_source = source
            self.audio_file = qfile
            self.path = path
            self.audio_format = fmt
            self.started_at = time.monotonic()

            self.recording_started.emit(path)
            return True

        except Exception as error:
            self._cleanup_failed()
            self.recording_error.emit(str(error))
            return False

    def stop(self):
        if not self.is_recording():
            return None

        path = self.path

        try:
            self.audio_source.stop()
        except Exception:
            pass

        try:
            if self.audio_file is not None:
                self.audio_file.flush()
                self.audio_file.close()
        except Exception:
            pass

        try:
            duration_ms = self._write_wav_header(path, self.audio_format)
        except Exception as error:
            self._cleanup_failed()
            self.recording_error.emit(str(error))
            return None

        self.audio_source = None
        self.audio_file = None
        self.path = None
        self.audio_format = None
        self.started_at = None

        self.recording_stopped.emit(path, duration_ms)
        return path

    def _cleanup_failed(self):
        try:
            if self.audio_source is not None:
                self.audio_source.stop()
        except Exception:
            pass

        try:
            if self.audio_file is not None:
                self.audio_file.close()
        except Exception:
            pass

        if self.path:
            try:
                if os.path.exists(self.path):
                    os.remove(self.path)
            except Exception:
                pass

        self.audio_source = None
        self.audio_file = None
        self.path = None
        self.audio_format = None
        self.started_at = None

    @staticmethod
    def _write_wav_header(path, fmt):
        if not path or not os.path.isfile(path):
            raise RuntimeError("Recording file was not created.")

        file_size = os.path.getsize(path)
        data_size = max(0, file_size - 44)

        sample_rate = safe_int(fmt.sampleRate(), 44100)
        channels = safe_int(fmt.channelCount(), 1)
        bits = safe_int(fmt.bytesPerSample(), 2) * 8

        sample_format = fmt.sampleFormat()

        if sample_format == QAudioFormat.SampleFormat.UInt8:
            wav_format_code = 1
            bits = 8
        elif sample_format == QAudioFormat.SampleFormat.Int16:
            wav_format_code = 1
            bits = 16
        elif sample_format == QAudioFormat.SampleFormat.Int32:
            wav_format_code = 1
            bits = 32
        elif sample_format == QAudioFormat.SampleFormat.Float:
            wav_format_code = 3
            bits = 32
        else:
            raise RuntimeError(
                f"Unsupported microphone sample format: {sample_format}"
            )

        block_align = channels * (bits // 8)
        byte_rate = sample_rate * block_align

        riff_size = 36 + data_size

        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            riff_size,
            b"WAVE",
            b"fmt ",
            16,
            wav_format_code,
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bits,
            b"data",
            data_size,
        )

        if len(header) != 44:
            raise RuntimeError("Internal WAV header size error.")

        with open(path, "r+b") as output:
            output.seek(0)
            output.write(header)

        # Approximate duration from the actual audio payload.
        duration_ms = 0
        if byte_rate > 0:
            duration_ms = int((data_size / byte_rate) * 1000)

        return duration_ms


# ============================================================
# FILE TRANSFER SIGNAL BRIDGE
# ============================================================

class TransferSignals(QObject):
    finished = Signal(bool, int, str, str, bool)


# ============================================================
# MAIN CHAT WINDOW
# ============================================================

class ChatWindow(QMainWindow):

    transfer_finished = Signal(bool, int, str, str, bool)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("TCP Chat Application")
        self.resize(1200, 760)
        self.setMinimumSize(950, 620)

        self.network = NetworkClient()

        self.my_client_id = None
        self.online_clients = []
        self.selected_client_id = 0
        self.connected = False

        self.conversations = {}
        self.unread_counts = {}
        self.last_messages = {}

        self.transfer_busy = False
        self.transfer_target = None
        self.transfer_filename = None

        # Incoming-file dedupe keys. This prevents a file card from
        # appearing twice if both file_received and [FILE RECEIVED]
        # arrive for the same transfer.
        self.shown_file_keys = set()
        self.last_file_sender_id = None
        self.pending_file_names = {}

        self.voice_recorder = VoiceRecorder(self)
        self.voice_recorder.recording_error.connect(self.on_recording_error)
        self.voice_recorder.recording_started.connect(self.on_recording_started)
        self.voice_recorder.recording_stopped.connect(self.on_recording_stopped)

        self.setStyleSheet(self.get_stylesheet())

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        self.create_sidebar(main_layout)
        self.create_chat_area(main_layout)

        # Network signals already provided by the existing client.
        self.network.message_received.connect(self.display_received_message)
        self.network.connection_changed.connect(self.update_connection_status)
        self.network.client_info_received.connect(self.handle_client_info)
        self.network.client_list_received.connect(self.update_client_list)

        # Some versions of network.py expose file_received. We support
        # it when present, but the GUI also handles [FILE RECEIVED] text.
        if hasattr(self.network, "file_received"):
            try:
                self.network.file_received.connect(self.handle_file_received)
            except Exception:
                pass

        self.transfer_finished.connect(self.on_transfer_finished)

        self.network.connect()

    # ========================================================
    # SIDEBAR
    # ========================================================

    def create_sidebar(self, main_layout):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(320)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("◉  TCP CHAT")
        title.setObjectName("appTitle")
        layout.addWidget(title)

        subtitle = QLabel("TCP Socket Communication")
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(subtitle)

        self.user_card = QFrame()
        self.user_card.setObjectName("userCard")
        user_layout = QVBoxLayout(self.user_card)
        user_layout.setContentsMargins(14, 12, 14, 12)
        user_layout.setSpacing(5)

        self.my_id_label = QLabel("Client --")
        self.my_id_label.setObjectName("myId")
        user_layout.addWidget(self.my_id_label)

        self.status_label = QLabel("●  Connecting...")
        self.status_label.setObjectName("status")
        user_layout.addWidget(self.status_label)

        layout.addWidget(self.user_card)

        section = QLabel("CONVERSATIONS")
        section.setObjectName("sectionTitle")
        layout.addWidget(section)

        self.client_list = QListWidget()
        self.client_list.setObjectName("clientList")
        self.client_list.setSpacing(4)
        self.client_list.itemClicked.connect(self.select_client)
        layout.addWidget(self.client_list, 1)

        footer = QLabel("TCP • IPv4 • Port 8080 • Files / Images / Audio / Voice / Video")
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)
        layout.addWidget(footer)

        main_layout.addWidget(sidebar)

    # ========================================================
    # CHAT AREA
    # ========================================================

    def create_chat_area(self, main_layout):
        panel = QFrame()
        panel.setObjectName("chatPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("chatHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        header_layout.setSpacing(4)

        self.chat_title = QLabel("🌐  Everyone")
        self.chat_title.setObjectName("chatTitle")
        header_layout.addWidget(self.chat_title)

        self.chat_subtitle = QLabel("Broadcast conversation • 0 online")
        self.chat_subtitle.setObjectName("chatSubtitle")
        header_layout.addWidget(self.chat_subtitle)

        layout.addWidget(header)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("chatScroll")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.chat_container = QWidget()
        self.chat_container.setObjectName("chatContainer")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(18, 18, 18, 18)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch(1)

        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll, 1)

        input_container = QFrame()
        input_container.setObjectName("inputContainer")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(15, 14, 15, 14)
        input_layout.setSpacing(10)

        self.message_input = QLineEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Message everyone...")
        self.message_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.message_input, 1)

        self.send_button = QPushButton("SEND  ➤")
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedWidth(120)
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)

        self.file_button = QPushButton("📎 FILE / MEDIA")
        self.file_button.setObjectName("fileButton")
        self.file_button.setFixedWidth(145)
        self.file_button.clicked.connect(self.show_media_menu)
        input_layout.addWidget(self.file_button)

        self.voice_button = QPushButton("🎤 VOICE")
        self.voice_button.setObjectName("voiceButton")
        self.voice_button.setFixedWidth(125)
        self.voice_button.clicked.connect(self.toggle_voice_recording)
        input_layout.addWidget(self.voice_button)

        layout.addWidget(input_container)
        main_layout.addWidget(panel, 1)

    # ========================================================
    # MEDIA MENU
    # ========================================================

    def show_media_menu(self):
        if self.voice_recorder.is_recording():
            self.toggle_voice_recording()
            return

        menu = QMenu(self)

        send_action = menu.addAction("📎  Send File / Media")
        send_action.triggered.connect(self.send_file_dialog)

        record_action = menu.addAction("🎤  Record Voice Message")
        record_action.triggered.connect(self.toggle_voice_recording)

        menu.addSeparator()
        info_action = menu.addAction("Voice messages are sent as audio files")
        info_action.setEnabled(False)

        menu.exec(self.file_button.mapToGlobal(self.file_button.rect().bottomLeft()))

    # ========================================================
    # CLIENT INFO / SIDEBAR
    # ========================================================

    def handle_client_info(self, client_id, client_list):
        self.my_client_id = safe_int(client_id, None)
        self.my_id_label.setText(
            f"Client {self.my_client_id}" if self.my_client_id is not None else "Client --"
        )

        self.online_clients = [safe_int(x) for x in (client_list or [])]
        self.ensure_conversation(0)

        for client in self.online_clients:
            self.ensure_conversation(client)

        self.update_client_list(self.online_clients)

    def update_client_list(self, client_ids):
        cleaned = []
        for value in client_ids or []:
            cid = safe_int(value, -1)
            if cid >= 0 and cid not in cleaned:
                cleaned.append(cid)

        self.online_clients = cleaned
        self.refresh_sidebar(True)

        count = len([x for x in cleaned if x != self.my_client_id])
        if self.selected_client_id == 0:
            self.chat_subtitle.setText(
                f"Broadcast conversation • {count} online"
            )

    def refresh_sidebar(self, preserve_selection=True):
        current = self.selected_client_id
        self.client_list.clear()

        everyone = QListWidgetItem(self.build_everyone_text())
        everyone.setData(Qt.ItemDataRole.UserRole, 0)
        self.client_list.addItem(everyone)

        for cid in self.online_clients:
            if cid == self.my_client_id:
                continue

            item = QListWidgetItem(self.build_client_text(cid))
            item.setData(Qt.ItemDataRole.UserRole, cid)
            self.client_list.addItem(item)

        if preserve_selection:
            self.select_list_item(current)

    def select_list_item(self, client_id):
        for i in range(self.client_list.count()):
            item = self.client_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == client_id:
                self.client_list.setCurrentItem(item)
                return

    def build_everyone_text(self):
        unread = self.unread_counts.get(0, 0)
        last = self.last_messages.get(0, "")
        preview = self.truncate(last, 28) if last else "Broadcast chat"
        text = f"🌐   Everyone\n     {preview}"
        if unread:
            text += f"   • {unread}"
        return text

    def build_client_text(self, client_id):
        unread = self.unread_counts.get(client_id, 0)
        last = self.last_messages.get(client_id, "")
        preview = self.truncate(last, 28) if last else "No messages yet"
        text = f"🟢   Client {client_id}\n     {preview}"
        if unread:
            text += f"   • {unread}"
        return text

    def select_client(self, item):
        cid = safe_int(item.data(Qt.ItemDataRole.UserRole), 0)
        self.selected_client_id = cid
        self.unread_counts[cid] = 0

        if cid == 0:
            self.set_broadcast_header()
        else:
            self.set_private_header(cid)

        self.show_conversation(cid)
        self.refresh_sidebar(True)
        self.message_input.setFocus()

    def set_private_header(self, client_id):
        online = client_id in self.online_clients
        status = "● Online" if online else "○ Offline"
        self.chat_title.setText(f"👤  Client {client_id}")
        self.chat_subtitle.setText(f"Private conversation • {status}")
        self.message_input.setPlaceholderText(f"Message Client {client_id}...")

    def set_broadcast_header(self):
        count = len([x for x in self.online_clients if x != self.my_client_id])
        self.chat_title.setText("🌐  Everyone")
        self.chat_subtitle.setText(f"Broadcast conversation • {count} online")
        self.message_input.setPlaceholderText("Message everyone...")

    # ========================================================
    # TEXT MESSAGE SENDING
    # ========================================================

    def send_message(self):
        message = self.message_input.text().strip()
        if not message:
            return

        if not self.network.connected:
            self.add_error_message("Not connected to the server.")
            return

        success = False

        if self.selected_client_id != 0 and self.selected_client_id != self.my_client_id:
            target = self.selected_client_id
            success = self.network.send_private_message(target, message)
            if success:
                self.add_message_to_conversation(
                    target,
                    "sent",
                    message,
                    f"You → Client {target}",
                )
                self.last_messages[target] = message
        else:
            success = self.network.send_broadcast_message(message)
            if success:
                self.add_message_to_conversation(
                    0,
                    "sent",
                    message,
                    "You → Everyone",
                )
                self.last_messages[0] = message

        if success:
            self.message_input.clear()
            self.show_conversation(self.selected_client_id)
            self.refresh_sidebar(True)
            self.message_input.setFocus()
        else:
            self.add_error_message("Message could not be sent.")

    # ========================================================
    # FILE / MEDIA SENDING
    # ========================================================

    def _validate_private_target(self):
        if not self.network.connected:
            self.add_error_message("Not connected to the server.")
            return None

        if self.selected_client_id == 0:
            QMessageBox.warning(
                self,
                "Select a Client",
                "File and voice messages are private. Select a client first.",
            )
            return None

        if self.selected_client_id == self.my_client_id:
            QMessageBox.warning(
                self,
                "Invalid Client",
                "You cannot send a file or voice message to yourself.",
            )
            return None

        if self.selected_client_id not in self.online_clients:
            QMessageBox.warning(
                self,
                "Client Offline",
                f"Client {self.selected_client_id} is not currently online.",
            )
            return None

        if self.transfer_busy:
            QMessageBox.information(
                self,
                "Transfer In Progress",
                "Please wait for the current file transfer to finish.",
            )
            return None

        return self.selected_client_id

    def send_file_dialog(self):
        target = self._validate_private_target()
        if target is None:
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File / Media to Send",
            "",
            "All Files (*)",
        )

        if not path:
            return

        self.start_file_transfer(
            target,
            path,
            is_voice=False,
        )

    def start_file_transfer(self, target_id, file_path, is_voice=False):
        if not os.path.isfile(file_path):
            self.add_error_message(f"File not found: {file_path}")
            return False

        if self.transfer_busy:
            self.add_error_message("Another file transfer is already running.")
            return False

        target_id = safe_int(target_id, -1)
        if target_id <= 0:
            self.add_error_message("Invalid target client.")
            return False

        filename = os.path.basename(file_path)
        size = os.path.getsize(file_path)

        self.transfer_busy = True
        self.transfer_target = target_id
        self.transfer_filename = filename

        self.file_button.setEnabled(False)
        self.voice_button.setEnabled(False)
        self.file_button.setText("SENDING...")
        self.voice_button.setText("SENDING...")

        self.add_message_to_conversation(
            target_id,
            "file",
            {
                "filename": filename,
                "path": file_path,
                "size": size,
                "sender": f"You → Client {target_id}",
                "direction": "sent",
                "is_voice": bool(is_voice),
            },
            f"You → Client {target_id}",
        )

        self.last_messages[target_id] = (
            f"🎤 {filename}" if is_voice else f"📎 {filename}"
        )

        self.show_conversation(target_id)
        self.refresh_sidebar(True)

        def worker():
            try:
                ok = bool(self.network.send_file(target_id, file_path))
                self.transfer_finished.emit(
                    ok,
                    target_id,
                    filename,
                    file_path,
                    bool(is_voice),
                )
            except Exception as error:
                print(f"[TRANSFER ERROR] {error}")
                self.transfer_finished.emit(
                    False,
                    target_id,
                    filename,
                    file_path,
                    bool(is_voice),
                )

        threading.Thread(target=worker, daemon=True).start()
        return True

    def on_transfer_finished(self, success, target_id, filename, file_path, is_voice):
        self.transfer_busy = False
        self.transfer_target = None
        self.transfer_filename = None

        self.file_button.setEnabled(True)
        self.voice_button.setEnabled(True)
        self.file_button.setText("📎 FILE / MEDIA")
        self.voice_button.setText("🎤 VOICE")

        if success:
            kind = "Voice message" if is_voice else "File / media"
            self.add_system_message(
                f"{kind} sent successfully to Client {target_id}: {filename}"
            )
        else:
            self.add_error_message(
                f"Transfer failed: {filename}"
            )

        self.show_conversation(self.selected_client_id)
        self.refresh_sidebar(True)
        self.message_input.setFocus()

    # ========================================================
    # VOICE RECORDING
    # ========================================================

    def toggle_voice_recording(self):
        if self.voice_recorder.is_recording():
            self.stop_voice_recording()
        else:
            self.start_voice_recording()

    def start_voice_recording(self):
        target = self._validate_private_target()
        if target is None:
            return

        if not MULTIMEDIA_AVAILABLE:
            QMessageBox.critical(
                self,
                "Voice Recording Unavailable",
                "Qt Multimedia is not available in this PySide6 installation.",
            )
            return

        voice_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "voice_messages",
        )
        os.makedirs(voice_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"Voice message {timestamp}.wav"
        path = unique_path(os.path.join(voice_dir, filename))

        self.recording_target_id = target
        self.recording_path = path

        if not self.voice_recorder.start(path):
            self.recording_target_id = None
            self.recording_path = None

    def stop_voice_recording(self):
        path = self.recording_path
        target = getattr(self, "recording_target_id", None)

        self.voice_recorder.stop()

        # Do not clear recording_target_id here.
        # VoiceRecorder emits recording_stopped after the WAV header has
        # been written, and on_recording_stopped() needs this target.
        if path and target and os.path.isfile(path):
            return

    def on_recording_started(self, path):
        self.file_button.setEnabled(False)
        self.voice_button.setText("⏹  STOP & SEND")
        self.voice_button.setEnabled(True)
        self.send_button.setEnabled(False)
        self.message_input.setEnabled(False)

        self.add_system_message(
            "🎤 Recording voice message... Click STOP & SEND when finished."
        )

    def on_recording_stopped(self, path, duration_ms):
        target = getattr(self, "recording_target_id", None)

        self.send_button.setEnabled(True)
        self.file_button.setEnabled(True)
        self.voice_button.setEnabled(True)
        self.voice_button.setText("🎤 VOICE")
        self.message_input.setEnabled(True)

        if not path or not os.path.isfile(path):
            self.add_error_message("Voice recording file was not created.")
            return

        if not target:
            self.add_error_message("Voice message target was lost.")
            return

        seconds = max(0, int(round(duration_ms / 1000.0)))
        if seconds == 0:
            # A tiny recording is usually an accidental click.
            try:
                os.remove(path)
            except Exception:
                pass
            self.add_system_message("Voice recording was too short.")
            return

        self.recording_target_id = None
        self.recording_path = None

        self.start_file_transfer(
            target,
            path,
            is_voice=True,
        )

    def on_recording_error(self, error):
        self.recording_target_id = None
        self.recording_path = None
        self.send_button.setEnabled(True)
        self.file_button.setEnabled(True)
        self.voice_button.setEnabled(True)
        self.voice_button.setText("🎤 VOICE")
        self.message_input.setEnabled(True)
        self.add_error_message(f"Voice recording failed: {error}")

    # ========================================================
    # INCOMING MESSAGES
    # ========================================================

    def display_received_message(self, message):
        if not message:
            return

        message = str(message).strip()

        if message.startswith("[Private from Client "):
            sender_id = self.extract_private_sender(message)
            if sender_id is None:
                return

            clean = self.extract_private_text(message)
            self.add_message_to_conversation(
                sender_id,
                "received",
                clean,
                f"Client {sender_id}",
            )
            self.last_messages[sender_id] = clean

            if self.selected_client_id != sender_id:
                self.unread_counts[sender_id] = self.unread_counts.get(sender_id, 0) + 1
            else:
                self.show_conversation(sender_id)

            self.refresh_sidebar(True)
            return

        if message.startswith("[Broadcast from Client "):
            sender_id = self.extract_broadcast_sender(message)

            # Do not duplicate our own broadcast.
            if sender_id is not None and sender_id == self.my_client_id:
                return

            clean = self.extract_broadcast_text(message)
            sender_name = f"Client {sender_id}" if sender_id is not None else "Client"

            self.add_message_to_conversation(
                0,
                "received",
                clean,
                sender_name,
            )
            self.last_messages[0] = clean

            if self.selected_client_id != 0:
                self.unread_counts[0] = self.unread_counts.get(0, 0) + 1
            else:
                self.unread_counts[0] = 0
                self.show_conversation(0)

            self.refresh_sidebar(True)
            return

        # --------------------------------------------------------
        # FILE START / PROGRESS
        # --------------------------------------------------------
        if message.startswith("[FILE] Receiving"):
            # IMPORTANT: Do NOT add this transient status to the chat.
            # It was the first half of the old duplicate-file problem.
            sender_id = self.extract_sender_from_file_receiving(message)
            if sender_id is not None:
                self.last_file_sender_id = sender_id
                self.pending_file_names[sender_id] = self.extract_receiving_filename(message)
            return

        # --------------------------------------------------------
        # FILE COMPLETE
        # --------------------------------------------------------
        if message.startswith("[FILE RECEIVED]"):
            self.handle_file_received_text(message)
            return

        if message.startswith("[FILE] Binary data received"):
            # Transient network status. Do not put it into the chat.
            return

        if message.startswith("[FILE ERROR]"):
            self.add_error_message(message)
            return

        if message.startswith("CLIENT_") or message.startswith("CLIENT_LIST") or message.startswith("CLIENT_INFO"):
            return

        self.add_system_message(message)

    # ========================================================
    # INCOMING FILE CARD
    # ========================================================

    def handle_file_received(self, filename, sender_id, file_path, file_size):
        self._add_received_file_card(
            filename,
            sender_id,
            file_path,
            file_size,
        )

    def handle_file_received_text(self, message):
        # [FILE RECEIVED] name (123 bytes)
        body = message[len("[FILE RECEIVED]"):].strip()

        match = re.match(r"^(.*?)\s*\((\d+)\s+bytes\)$", body)
        if match:
            filename = match.group(1).strip()
            size = safe_int(match.group(2), 0)
        else:
            filename = body
            size = 0

        sender_id = self.last_file_sender_id
        if sender_id is None:
            # If the network implementation has no file_received signal,
            # the most recently announced receiving client is our best
            # available protocol-level sender information.
            sender_id = self.find_sender_for_filename(filename)

        if sender_id is None:
            self.add_system_message(message)
            return

        path = self.find_received_file(filename, size)
        if not path:
            self.add_system_message(
                f"Received {filename}, but its saved path could not be located yet."
            )
            return

        self._add_received_file_card(
            filename,
            sender_id,
            path,
            os.path.getsize(path),
        )

    def _add_received_file_card(self, filename, sender_id, file_path, file_size):
        sender_id = safe_int(sender_id, -1)
        if sender_id < 0:
            return

        normalized = os.path.normcase(os.path.abspath(file_path or ""))
        key = normalized or f"{sender_id}|{filename}|{safe_int(file_size)}"

        if key in self.shown_file_keys:
            return

        self.shown_file_keys.add(key)

        is_voice = os.path.splitext(filename)[1].lower() == ".wav" and filename.lower().startswith("voice message")

        self.add_message_to_conversation(
            sender_id,
            "file",
            {
                "filename": filename,
                "path": file_path,
                "size": safe_int(file_size),
                "sender": f"Client {sender_id}",
                "direction": "received",
                "is_voice": is_voice,
            },
            f"Client {sender_id}",
        )

        self.last_messages[sender_id] = (
            f"🎤 {filename}" if is_voice else f"📎 {filename}"
        )

        if self.selected_client_id == sender_id:
            self.show_conversation(sender_id)
        else:
            self.unread_counts[sender_id] = self.unread_counts.get(sender_id, 0) + 1

        self.refresh_sidebar(True)

        # Allow a future transfer with the same filename to be shown.
        self.last_file_sender_id = sender_id

    def find_sender_for_filename(self, filename):
        for cid, pending_name in list(self.pending_file_names.items()):
            if pending_name == filename:
                return cid
        return self.last_file_sender_id

    def find_received_file(self, filename, expected_size=0):
        root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "received_files",
        )

        if not os.path.isdir(root):
            return None

        candidates = []
        for name in os.listdir(root):
            path = os.path.join(root, name)
            if not os.path.isfile(path):
                continue

            # Current network.py may rename duplicates to "(1)" etc.
            if name == filename or name.startswith(os.path.splitext(filename)[0] + " ("):
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue

                if expected_size and size != expected_size:
                    continue

                candidates.append((os.path.getmtime(path), path))

        if not candidates:
            return None

        candidates.sort(reverse=True)
        return candidates[0][1]

    # ========================================================
    # CONVERSATIONS
    # ========================================================

    def ensure_conversation(self, conversation_id):
        conversation_id = safe_int(conversation_id, 0)
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        if conversation_id not in self.unread_counts:
            self.unread_counts[conversation_id] = 0

    def add_message_to_conversation(self, conversation_id, message_type, message, sender):
        self.ensure_conversation(conversation_id)
        self.conversations[conversation_id].append({
            "type": message_type,
            "message": message,
            "sender": sender,
        })

    def show_conversation(self, conversation_id):
        self.ensure_conversation(conversation_id)

        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                try:
                    if isinstance(widget, FileCard):
                        widget.close_player()
                except Exception:
                    pass
                widget.deleteLater()

        for item in self.conversations[conversation_id]:
            if item["type"] == "file":
                self.add_file_widget(
                    item["message"],
                    item["sender"],
                    item["message"].get("direction", "received"),
                )
            elif item["type"] == "sent":
                self.add_text_bubble(
                    item["message"],
                    item["sender"],
                    sent=True,
                )
            elif item["type"] == "received":
                self.add_text_bubble(
                    item["message"],
                    item["sender"],
                    sent=False,
                )

        self.chat_layout.addStretch(1)
        self.scroll_to_bottom()

    def add_text_bubble(self, message, sender, sent=False):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        bubble = QFrame()
        bubble.setObjectName("sentBubble" if sent else "receivedBubble")
        bubble.setMaximumWidth(680)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 9, 12, 9)
        bubble_layout.setSpacing(4)

        sender_label = QLabel(str(sender))
        sender_label.setObjectName("bubbleSender")
        bubble_layout.addWidget(sender_label)

        text_label = QLabel(str(message))
        text_label.setObjectName("bubbleText")
        text_label.setWordWrap(True)
        bubble_layout.addWidget(text_label)

        if sent:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
        else:
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)

        self.chat_layout.insertWidget(
            max(0, self.chat_layout.count() - 1),
            row,
        )

    def add_file_widget(self, data, sender, direction):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        card = FileCard(data)

        if direction == "sent":
            row_layout.addStretch(1)
            row_layout.addWidget(card)
        else:
            row_layout.addWidget(card)
            row_layout.addStretch(1)

        self.chat_layout.insertWidget(
            max(0, self.chat_layout.count() - 1),
            row,
        )

    def add_system_message(self, message):
        label = QLabel(f"SYSTEM  {message}")
        label.setObjectName("systemMessage")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        self.chat_layout.insertWidget(
            max(0, self.chat_layout.count() - 1),
            label,
        )
        self.scroll_to_bottom()

    def add_error_message(self, message):
        label = QLabel(f"ERROR  {message}")
        label.setObjectName("errorMessage")
        label.setWordWrap(True)
        self.chat_layout.insertWidget(
            max(0, self.chat_layout.count() - 1),
            label,
        )
        self.scroll_to_bottom()

    # ========================================================
    # PARSING
    # ========================================================

    @staticmethod
    def extract_private_sender(message):
        prefix = "[Private from Client "
        try:
            start = len(prefix)
            end = message.index("]", start)
            return int(message[start:end])
        except Exception:
            return None

    @staticmethod
    def extract_private_text(message):
        try:
            return message.split("] ", 1)[1]
        except Exception:
            return message

    @staticmethod
    def extract_broadcast_sender(message):
        prefix = "[Broadcast from Client "
        try:
            start = len(prefix)
            end = message.index("]", start)
            return int(message[start:end])
        except Exception:
            return None

    @staticmethod
    def extract_broadcast_text(message):
        try:
            return message.split("] ", 1)[1]
        except Exception:
            return message

    @staticmethod
    def extract_sender_from_file_receiving(message):
        match = re.search(r"from Client\s+(\d+)", message)
        return int(match.group(1)) if match else None

    @staticmethod
    def extract_receiving_filename(message):
        match = re.search(r"Receiving\s+'(.*?)'\s+from Client", message)
        return match.group(1) if match else ""

    # ========================================================
    # SIDEBAR / STATUS
    # ========================================================

    def truncate(self, text, length):
        text = str(text).replace("\n", " ")
        return text if len(text) <= length else text[:length - 3] + "..."

    def update_connection_status(self, connected):
        self.connected = bool(connected)

        if self.connected:
            self.status_label.setText("●  Connected")
            self.status_label.setStyleSheet(f"color: {SUCCESS};")
        else:
            self.status_label.setText("●  Disconnected")
            self.status_label.setStyleSheet(f"color: {DANGER};")

    def scroll_to_bottom(self):
        from PySide6.QtCore import QTimer
        QTimer.singleShot(
            0,
            lambda: self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            ),
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def closeEvent(self, event):
        try:
            if self.voice_recorder.is_recording():
                self.voice_recorder.stop()
        except Exception:
            pass

        try:
            self.network.disconnect()
        except Exception:
            pass

        event.accept()

    # ========================================================
    # STYLESHEET
    # ========================================================

    def get_stylesheet(self):
        return f"""
        QMainWindow {{
            background: {BACKGROUND};
        }}

        QWidget {{
            color: {TEXT};
            font-family: Segoe UI, Arial;
            font-size: 13px;
        }}

        #sidebar {{
            background: {SIDEBAR};
            border: 1px solid {BORDER};
            border-radius: 14px;
        }}

        #appTitle {{
            color: {ACCENT};
            font-size: 25px;
            font-weight: 800;
        }}

        #appSubtitle {{
            color: {TEXT_SECONDARY};
            margin-bottom: 6px;
        }}

        #userCard {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 10px;
        }}

        #myId {{
            font-size: 16px;
            font-weight: 700;
        }}

        #status {{
            color: {TEXT_SECONDARY};
        }}

        #sectionTitle {{
            color: {TEXT_SECONDARY};
            font-size: 12px;
            font-weight: 800;
        }}

        #clientList {{
            background: transparent;
            border: none;
            outline: none;
        }}

        #clientList::item {{
            background: transparent;
            border-radius: 9px;
            padding: 10px;
            margin: 2px 0;
        }}

        #clientList::item:selected {{
            background: {ACCENT_DARK};
        }}

        #clientList::item:hover {{
            background: {PANEL_LIGHT};
        }}

        #footer {{
            color: #64748b;
            font-size: 11px;
        }}

        #chatPanel {{
            background: {BACKGROUND};
            border: 1px solid {BORDER};
            border-radius: 14px;
        }}

        #chatHeader {{
            background: {PANEL};
            border-bottom: 1px solid {BORDER};
            border-top-left-radius: 14px;
            border-top-right-radius: 14px;
        }}

        #chatTitle {{
            font-size: 23px;
            font-weight: 800;
        }}

        #chatSubtitle {{
            color: {TEXT_SECONDARY};
        }}

        #chatScroll {{
            background: {BACKGROUND};
            border: none;
        }}

        #chatContainer {{
            background: {BACKGROUND};
        }}

        #sentBubble {{
            background: {MESSAGE_SENT};
            border-radius: 10px;
            border-right: 3px solid #26d0e5;
        }}

        #receivedBubble {{
            background: {MESSAGE_RECEIVED};
            border-radius: 10px;
            border-left: 3px solid {ACCENT};
        }}

        #bubbleSender {{
            color: white;
            font-weight: 800;
        }}

        #bubbleText {{
            color: {TEXT};
            font-size: 14px;
        }}

        #fileCard {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 10px;
            min-width: 300px;
            max-width: 650px;
        }}

        #fileIcon {{
            font-size: 24px;
        }}

        #fileName {{
            color: {TEXT};
            font-weight: 700;
            font-size: 14px;
        }}

        #fileMeta {{
            color: {TEXT_SECONDARY};
            font-size: 11px;
        }}

        #fileCard QPushButton {{
            background: {PANEL_LIGHT};
            border: 1px solid {BORDER};
            border-radius: 8px;
            padding: 8px 10px;
            color: {TEXT};
            font-weight: 700;
        }}

        #fileCard QPushButton:hover {{
            background: {ACCENT_DARK};
            color: white;
        }}

        #inputContainer {{
            background: {PANEL};
            border-top: 1px solid {BORDER};
            border-bottom-left-radius: 14px;
            border-bottom-right-radius: 14px;
        }}

        #messageInput {{
            background: #0d1627;
            border: 1px solid {BORDER};
            border-radius: 9px;
            padding: 11px 13px;
            color: {TEXT};
            font-size: 14px;
        }}

        #messageInput:focus {{
            border: 1px solid {ACCENT};
        }}

        #sendButton {{
            background: {ACCENT};
            border: none;
            border-radius: 9px;
            padding: 11px;
            color: #00151a;
            font-weight: 800;
        }}

        #sendButton:hover {{
            background: #26d0e5;
        }}

        #sendButton:disabled {{
            background: #334155;
            color: #94a3b8;
        }}

        #fileButton, #voiceButton {{
            background: {PANEL_LIGHT};
            border: 1px solid {BORDER};
            border-radius: 9px;
            padding: 11px;
            color: {TEXT};
            font-weight: 800;
        }}

        #fileButton:hover, #voiceButton:hover {{
            background: {ACCENT_DARK};
            color: white;
        }}

        #fileButton:disabled, #voiceButton:disabled {{
            background: #334155;
            color: #94a3b8;
        }}

        #systemMessage {{
            color: {TEXT_SECONDARY};
            padding: 5px;
        }}

        #errorMessage {{
            color: {DANGER};
            background: #2b1720;
            border: 1px solid #4b202c;
            border-radius: 7px;
            padding: 7px 10px;
        }}

        QScrollBar:vertical {{
            background: {SIDEBAR};
            width: 10px;
            margin: 2px;
            border-radius: 5px;
        }}

        QScrollBar::handle:vertical {{
            background: {BORDER};
            min-height: 30px;
            border-radius: 5px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {ACCENT_DARK};
        }}
        """


# ============================================================
# MAIN
# ============================================================

def main():
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
