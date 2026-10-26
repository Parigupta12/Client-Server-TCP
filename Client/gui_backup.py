# ==========================================================
# TCP CHAT APPLICATION
# PHASE 7A
#
# GUI client compatible with existing Client/network.py
#
# Features:
#   - Broadcast chat
#   - Private chat
#   - Online client list
#   - Sent messages on RIGHT
#   - Received messages on LEFT
#   - Local message history
#   - Unread counts
#   - Connection status
# ==========================================================

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QTextBrowser,
    QLineEdit,
    QPushButton,
    QLabel,
    QFrame,
    QFileDialog,
    QMessageBox,
)

from .network import NetworkClient


# ==========================================================
# COLORS
# ==========================================================

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

MESSAGE_RECEIVED = "#172235"
MESSAGE_SENT = "#008fa3"


# ==========================================================
# MAIN WINDOW
# ==========================================================

class ChatWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        # ==================================================
        # WINDOW
        # ==================================================

        self.setWindowTitle(
            "TCP Chat Application"
        )

        self.resize(
            1150,
            720
        )

        self.setMinimumSize(
            900,
            600
        )

        # ==================================================
        # NETWORK
        # ==================================================

        self.network = NetworkClient()

        # ==================================================
        # CLIENT STATE
        # ==================================================

        self.my_client_id = None

        self.online_clients = []

        # 0 = Everyone
        # client ID = private conversation
        self.selected_client_id = 0

        self.connected = False
        self.last_file_sender_id = None

        # ==================================================
        # CONVERSATION STORAGE
        # ==================================================

        self.conversations = {}

        self.unread_counts = {}

        self.last_messages = {}

        # ==================================================
        # STYLE
        # ==================================================

        self.setStyleSheet(
            self.get_stylesheet()
        )

        # ==================================================
        # CENTRAL WIDGET
        # ==================================================

        central_widget = QWidget()

        self.setCentralWidget(
            central_widget
        )

        main_layout = QHBoxLayout()

        main_layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        main_layout.setSpacing(
            12
        )

        central_widget.setLayout(
            main_layout
        )

        # ==================================================
        # BUILD UI
        # ==================================================

        self.create_sidebar(
            main_layout
        )

        self.create_chat_area(
            main_layout
        )

        # ==================================================
        # NETWORK SIGNALS
        # ==================================================

        self.network.message_received.connect(
            self.display_received_message
        )

        self.network.connection_changed.connect(
            self.update_connection_status
        )

        self.network.client_info_received.connect(
            self.handle_client_info
        )

        self.network.client_list_received.connect(
            self.update_client_list
        )

        # ==================================================
        # CONNECT
        # ==================================================

        self.network.connect()


    # ======================================================
    # SIDEBAR
    # ======================================================

    def create_sidebar(
        self,
        main_layout
    ):

        sidebar = QFrame()

        sidebar.setObjectName(
            "sidebar"
        )

        sidebar.setFixedWidth(
            320
        )

        sidebar_layout = QVBoxLayout()

        sidebar_layout.setContentsMargins(
            18,
            18,
            18,
            18
        )

        sidebar_layout.setSpacing(
            12
        )

        sidebar.setLayout(
            sidebar_layout
        )

        # ==================================================
        # APP TITLE
        # ==================================================

        app_title = QLabel(
            "◉  TCP CHAT"
        )

        app_title.setObjectName(
            "appTitle"
        )

        sidebar_layout.addWidget(
            app_title
        )

        # ==================================================
        # SUBTITLE
        # ==================================================

        app_subtitle = QLabel(
            "TCP Socket Communication"
        )

        app_subtitle.setObjectName(
            "appSubtitle"
        )

        sidebar_layout.addWidget(
            app_subtitle
        )

        # ==================================================
        # USER CARD
        # ==================================================

        self.user_card = QFrame()

        self.user_card.setObjectName(
            "userCard"
        )

        user_layout = QVBoxLayout()

        user_layout.setContentsMargins(
            14,
            12,
            14,
            12
        )

        user_layout.setSpacing(
            5
        )

        self.user_card.setLayout(
            user_layout
        )

        self.my_id_label = QLabel(
            "Client --"
        )

        self.my_id_label.setObjectName(
            "myId"
        )

        user_layout.addWidget(
            self.my_id_label
        )

        self.status_label = QLabel(
            "●  Connecting..."
        )

        self.status_label.setObjectName(
            "status"
        )

        user_layout.addWidget(
            self.status_label
        )

        sidebar_layout.addWidget(
            self.user_card
        )

        # ==================================================
        # CONVERSATIONS TITLE
        # ==================================================

        conversations_label = QLabel(
            "CONVERSATIONS"
        )

        conversations_label.setObjectName(
            "sectionTitle"
        )

        sidebar_layout.addWidget(
            conversations_label
        )

        # ==================================================
        # CLIENT LIST
        # ==================================================

        self.client_list = QListWidget()

        self.client_list.setObjectName(
            "clientList"
        )

        self.client_list.setSpacing(
            4
        )

        self.client_list.itemClicked.connect(
            self.select_client
        )

        sidebar_layout.addWidget(
            self.client_list
        )

        # ==================================================
        # FOOTER
        # ==================================================

        footer = QLabel(
            "TCP • IPv4 • Port 8080"
        )

        footer.setObjectName(
            "footer"
        )

        footer.setAlignment(
            Qt.AlignCenter
        )

        sidebar_layout.addWidget(
            footer
        )

        main_layout.addWidget(
            sidebar
        )


    # ======================================================
    # CHAT AREA
    # ======================================================

    def create_chat_area(
        self,
        main_layout
    ):

        chat_panel = QFrame()

        chat_panel.setObjectName(
            "chatPanel"
        )

        chat_layout = QVBoxLayout()

        chat_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        chat_layout.setSpacing(
            0
        )

        chat_panel.setLayout(
            chat_layout
        )

        # ==================================================
        # HEADER
        # ==================================================

        header = QFrame()

        header.setObjectName(
            "chatHeader"
        )

        header_layout = QVBoxLayout()

        header_layout.setContentsMargins(
            22,
            16,
            22,
            16
        )

        header_layout.setSpacing(
            4
        )

        header.setLayout(
            header_layout
        )

        self.chat_title = QLabel(
            "🌐  Everyone"
        )

        self.chat_title.setObjectName(
            "chatTitle"
        )

        header_layout.addWidget(
            self.chat_title
        )

        self.chat_subtitle = QLabel(
            "Broadcast message • 0 online"
        )

        self.chat_subtitle.setObjectName(
            "chatSubtitle"
        )

        header_layout.addWidget(
            self.chat_subtitle
        )

        chat_layout.addWidget(
            header
        )

        # ==================================================
        # CHAT DISPLAY
        # ==================================================

        self.chat_display = QTextBrowser()

        self.chat_display.setObjectName(
            "chatDisplay"
        )

        self.chat_display.setReadOnly(
            True
        )

        self.chat_display.setOpenExternalLinks(
            False
        )

        chat_layout.addWidget(
            self.chat_display
        )

        # ==================================================
        # INPUT AREA
        # ==================================================

        input_container = QFrame()

        input_container.setObjectName(
            "inputContainer"
        )

        input_layout = QHBoxLayout()

        input_layout.setContentsMargins(
            15,
            14,
            15,
            14
        )

        input_layout.setSpacing(
            10
        )

        input_container.setLayout(
            input_layout
        )

        # --------------------------------------------------
        # MESSAGE INPUT
        # --------------------------------------------------

        self.message_input = QLineEdit()

        self.message_input.setObjectName(
            "messageInput"
        )

        self.message_input.setPlaceholderText(
            "Message everyone..."
        )

        self.message_input.returnPressed.connect(
            self.send_message
        )

        input_layout.addWidget(
            self.message_input
        )

        # --------------------------------------------------
        # SEND BUTTON
        # --------------------------------------------------

        self.send_button = QPushButton(
            "SEND  ➤"
        )

        self.send_button.setObjectName(
            "sendButton"
        )

        self.send_button.setFixedWidth(
            130
        )

        self.send_button.clicked.connect(
            self.send_message
        )

        input_layout.addWidget(
            self.send_button
        )

        # --------------------------------------------------
        # FILE BUTTON
        # --------------------------------------------------

        self.file_button = QPushButton(
            "📎 FILE"
        )

        self.file_button.setObjectName(
            "fileButton"
        )

        self.file_button.setFixedWidth(
            105
        )

        self.file_button.clicked.connect(
            self.send_file_dialog
        )

        input_layout.addWidget(
            self.file_button
        )

        chat_layout.addWidget(
            input_container
        )

        main_layout.addWidget(
            chat_panel
        )


    # ======================================================
    # CLIENT INFO
    # ======================================================

    def handle_client_info(
        self,
        client_id,
        client_list
    ):

        self.my_client_id = client_id

        self.my_id_label.setText(
            f"Client {client_id}"
        )

        self.online_clients = list(
            client_list or []
        )

        # Create Everyone conversation
        self.ensure_conversation(
            0
        )

        # Create private conversations
        for client in self.online_clients:

            self.ensure_conversation(
                client
            )

        self.update_client_list(
            self.online_clients
        )


    # ======================================================
    # UPDATE CLIENT LIST
    # ======================================================

    def update_client_list(
        self,
        client_ids
    ):

        clean_ids = []

        for client_id in client_ids or []:

            try:
                client_id = int(
                    client_id
                )
            except (
                ValueError,
                TypeError
            ):
                continue

            if client_id not in clean_ids:

                clean_ids.append(
                    client_id
                )

        self.online_clients = clean_ids

        current_selection = (
            self.selected_client_id
        )

        # --------------------------------------------------
        # Ensure conversations
        # --------------------------------------------------

        self.ensure_conversation(
            0
        )

        for client_id in clean_ids:

            self.ensure_conversation(
                client_id
            )

        # --------------------------------------------------
        # Rebuild sidebar
        # --------------------------------------------------

        self.client_list.clear()

        # ==================================================
        # EVERYONE
        # ==================================================

        everyone_item = QListWidgetItem(
            self.build_everyone_text()
        )

        everyone_item.setData(
            Qt.UserRole,
            0
        )

        self.client_list.addItem(
            everyone_item
        )

        # ==================================================
        # OTHER CLIENTS
        # ==================================================

        for client_id in clean_ids:

            if client_id == self.my_client_id:
                continue

            item = QListWidgetItem(
                self.build_client_text(
                    client_id,
                    False
                )
            )

            item.setData(
                Qt.UserRole,
                client_id
            )

            self.client_list.addItem(
                item
            )

        # ==================================================
        # RESTORE SELECTION
        # ==================================================

        if (
            current_selection != 0
            and current_selection in clean_ids
            and current_selection != self.my_client_id
        ):

            self.selected_client_id = (
                current_selection
            )

            self.set_private_header(
                current_selection
            )

        else:

            self.selected_client_id = 0

            self.set_broadcast_header()

        self.select_list_item(
            self.selected_client_id
        )

        self.show_conversation(
            self.selected_client_id
        )


    # ======================================================
    # SELECT CLIENT
    # ======================================================

    def select_client(
        self,
        item
    ):

        client_id = item.data(
            Qt.UserRole
        )

        # ==================================================
        # EVERYONE
        # ==================================================

        if client_id == 0:

            self.selected_client_id = 0

            self.unread_counts[0] = 0

            self.set_broadcast_header()

            self.show_conversation(
                0
            )

            self.refresh_sidebar(
                preserve_selection=True
            )

            self.message_input.setFocus()

            return

        # ==================================================
        # PRIVATE CLIENT
        # ==================================================

        self.selected_client_id = client_id

        self.ensure_conversation(
            client_id
        )

        self.unread_counts[client_id] = 0

        self.set_private_header(
            client_id
        )

        self.show_conversation(
            client_id
        )

        self.refresh_sidebar(
            preserve_selection=True
        )

        self.message_input.setFocus()


    # ======================================================
    # PRIVATE HEADER
    # ======================================================

    def set_private_header(
        self,
        client_id
    ):

        online = (
            client_id in self.online_clients
        )

        if online:

            status = "● Online"

        else:

            status = "○ Offline"

        self.chat_title.setText(
            f"👤  Client {client_id}"
        )

        self.chat_subtitle.setText(
            f"Private conversation • {status}"
        )

        self.message_input.setPlaceholderText(
            f"Message Client {client_id}..."
        )


    # ======================================================
    # BROADCAST HEADER
    # ======================================================

    def set_broadcast_header(
        self
    ):

        self.chat_title.setText(
            "🌐  Everyone"
        )

        self.chat_subtitle.setText(
            "Broadcast message • "
            f"{len(self.online_clients)} online"
        )

        self.message_input.setPlaceholderText(
            "Message everyone..."
        )


    # ======================================================
    # SEND MESSAGE
    # ======================================================

    def send_message(
        self
    ):

        message = (
            self.message_input.text().strip()
        )

        if not message:

            return

        if not self.network.connected:

            self.add_error_message(
                "Not connected to the server."
            )

            return

        success = False

        # ==================================================
        # PRIVATE MESSAGE
        # ==================================================

        if (
            self.selected_client_id != 0
            and
            self.selected_client_id != self.my_client_id
        ):

            target_id = (
                self.selected_client_id
            )

            success = (
                self.network.send_private_message(
                    target_id,
                    message
                )
            )

            # ------------------------------------------------
            # IMPORTANT:
            # Immediately show our own sent message.
            # Server normally sends the private message only
            # to the receiver.
            # ------------------------------------------------

            if success:

                self.add_message_to_conversation(
                    target_id,
                    "sent",
                    message,
                    f"You → Client {target_id}"
                )

                self.last_messages[
                    target_id
                ] = message


        # ==================================================
        # BROADCAST MESSAGE
        # ==================================================

        else:

            success = (
                self.network.send_broadcast_message(
                    message
                )
            )

            # ------------------------------------------------
            # IMPORTANT:
            # Immediately show our own sent message.
            # This creates the RIGHT-SIDE bubble.
            # ------------------------------------------------

            if success:

                self.add_message_to_conversation(
                    0,
                    "sent",
                    message,
                    "You → Everyone"
                )

                self.last_messages[
                    0
                ] = message

        # ==================================================
        # SUCCESS
        # ==================================================

        if success:

            self.message_input.clear()

            self.show_conversation(
                self.selected_client_id
            )

            self.refresh_sidebar(
                preserve_selection=True
            )

            self.message_input.setFocus()

        else:

            self.add_error_message(
                "Message could not be sent."
            )


    # ======================================================
    # SEND FILE
    # ======================================================

    def send_file_dialog(
        self
    ):
        """Open a file picker and send the selected file privately."""

        if not self.network.connected:
            self.add_error_message("Not connected to the server.")
            return

        if self.selected_client_id == 0:
            QMessageBox.warning(
                self,
                "Select a Client",
                "File transfer is private. Select a client from the left sidebar first."
            )
            return

        if self.selected_client_id == self.my_client_id:
            QMessageBox.warning(
                self,
                "Invalid Client",
                "You cannot send a file to yourself."
            )
            return

        if self.selected_client_id not in self.online_clients:
            QMessageBox.warning(
                self,
                "Client Offline",
                f"Client {self.selected_client_id} is not currently online."
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Send",
            "",
            "All Files (*)"
        )

        if not file_path:
            return

        target_id = self.selected_client_id
        filename = file_path.replace("\\", "/").rsplit("/", 1)[-1]

        # Show the outgoing file immediately on the RIGHT.
        self.add_message_to_conversation(
            target_id,
            "sent",
            f"📎 {filename}",
            f"You → Client {target_id}"
        )
        self.last_messages[target_id] = f"📎 {filename}"
        self.show_conversation(target_id)
        self.refresh_sidebar(preserve_selection=True)

        self.file_button.setEnabled(False)
        self.file_button.setText("SENDING...")

        def transfer_file():
            success = self.network.send_file(target_id, file_path)

            from PySide6.QtCore import QTimer

            def finish_ui():
                self.file_button.setEnabled(True)
                self.file_button.setText("📎 FILE")

                if success:
                    self.add_system_message(
                        f"File sent successfully to Client {target_id}: {filename}"
                    )
                else:
                    self.add_error_message(
                        f"File transfer failed: {filename}"
                    )

            QTimer.singleShot(0, finish_ui)

        import threading
        threading.Thread(target=transfer_file, daemon=True).start()


    # ======================================================
    # RECEIVE MESSAGE
    # ======================================================

    def display_received_message(
        self,
        message
    ):

        if not message:

            return

        message = str(
            message
        ).strip()

        # ==================================================
        # PRIVATE MESSAGE
        # ==================================================

        if message.startswith(
            "[Private from Client "
        ):

            sender_id = (
                self.extract_private_sender(
                    message
                )
            )

            if sender_id is None:

                self.add_error_message(
                    "Could not identify private-message sender."
                )

                return

            clean_message = (
                self.extract_private_text(
                    message
                )
            )

            self.add_message_to_conversation(
                sender_id,
                "received",
                clean_message,
                f"Client {sender_id}"
            )

            self.last_messages[
                sender_id
            ] = clean_message

            # ------------------------------------------------
            # Unread count
            # ------------------------------------------------

            if self.selected_client_id != sender_id:

                self.unread_counts[
                    sender_id
                ] = (
                    self.unread_counts.get(
                        sender_id,
                        0
                    ) + 1
                )

            # ------------------------------------------------
            # Refresh currently open conversation
            # ------------------------------------------------

            if (
                self.selected_client_id
                ==
                sender_id
            ):

                self.show_conversation(
                    sender_id
                )

            self.refresh_sidebar(
                preserve_selection=True
            )

            return


        # ==================================================
        # BROADCAST MESSAGE
        # ==================================================

        if message.startswith(
            "[Broadcast from Client "
        ):

            sender_id = (
                self.extract_broadcast_sender(
                    message
                )
            )

            # ------------------------------------------------
            # IMPORTANT:
            # If the C server echoes our own broadcast back,
            # DO NOT add it again.
            #
            # We already added it as a SENT message on the
            # right side inside send_message().
            # ------------------------------------------------

            if (
                sender_id is not None
                and
                self.my_client_id is not None
                and
                sender_id == self.my_client_id
            ):

                return

            clean_message = (
                self.extract_broadcast_text(
                    message
                )
            )

            sender_name = (
                f"Client {sender_id}"
                if sender_id is not None
                else "Client"
            )

            self.add_message_to_conversation(
                0,
                "received",
                clean_message,
                sender_name
            )

            self.last_messages[
                0
            ] = clean_message

            # ------------------------------------------------
            # Unread
            # ------------------------------------------------

            if self.selected_client_id != 0:

                self.unread_counts[
                    0
                ] = (
                    self.unread_counts.get(
                        0,
                        0
                    ) + 1
                )

            else:

                self.unread_counts[
                    0
                ] = 0

                self.show_conversation(
                    0
                )

            self.refresh_sidebar(
                preserve_selection=True
            )

            return


        # ==================================================
        # FILE / SYSTEM MESSAGE
        # ==================================================

        if message.startswith("[FILE] Receiving"):
            # Example: [FILE] Receiving 'sample.pdf' from Client 2...
            try:
                sender_text = message.rsplit("from Client ", 1)[1]
                sender_id = int(sender_text.rstrip("."))
                self.last_file_sender_id = sender_id

                self.add_message_to_conversation(
                    sender_id,
                    "received",
                    message,
                    f"Client {sender_id}"
                )

                if self.selected_client_id == sender_id:
                    self.show_conversation(sender_id)
                else:
                    self.unread_counts[sender_id] = self.unread_counts.get(sender_id, 0) + 1

                self.refresh_sidebar(preserve_selection=True)
            except Exception:
                self.add_system_message(message)
            return

        if message.startswith("[FILE RECEIVED]"):
            filename = message[len("[FILE RECEIVED]"):].strip()
            sender_id = self.last_file_sender_id

            if sender_id is not None:
                self.add_message_to_conversation(
                    sender_id,
                    "received",
                    f"📎 {filename}",
                    f"Client {sender_id}"
                )
                self.last_messages[sender_id] = f"📎 {filename}"

                if self.selected_client_id == sender_id:
                    self.show_conversation(sender_id)
                else:
                    self.unread_counts[sender_id] = self.unread_counts.get(sender_id, 0) + 1

                self.refresh_sidebar(preserve_selection=True)
            else:
                self.add_system_message(message)
            return

        if message.startswith("[FILE] Binary data received"):
            self.add_system_message(message)
            return

        if message.startswith("[FILE ERROR]"):
            self.add_error_message(message)
            return

        if (
            message.startswith("CLIENT_")
            or
            message.startswith("CLIENT_LIST")
            or
            message.startswith("CLIENT_INFO")
        ):
            return

        self.add_system_message(
            message
        )


    # ======================================================
    # EXTRACT PRIVATE SENDER
    # ======================================================

    def extract_private_sender(
        self,
        message
    ):

        prefix = (
            "[Private from Client "
        )

        try:

            start = len(
                prefix
            )

            end = message.index(
                "]",
                start
            )

            return int(
                message[start:end]
            )

        except Exception:

            return None


    # ======================================================
    # EXTRACT PRIVATE TEXT
    # ======================================================

    def extract_private_text(
        self,
        message
    ):

        try:

            return message.split(
                "] ",
                1
            )[1]

        except Exception:

            return message


    # ======================================================
    # EXTRACT BROADCAST SENDER
    # ======================================================

    def extract_broadcast_sender(
        self,
        message
    ):

        prefix = (
            "[Broadcast from Client "
        )

        try:

            start = len(
                prefix
            )

            end = message.index(
                "]",
                start
            )

            return int(
                message[start:end]
            )

        except Exception:

            return None


    # ======================================================
    # EXTRACT BROADCAST TEXT
    # ======================================================

    def extract_broadcast_text(
        self,
        message
    ):

        try:

            return message.split(
                "] ",
                1
            )[1]

        except Exception:

            return message


    # ======================================================
    # ENSURE CONVERSATION
    # ======================================================

    def ensure_conversation(
        self,
        conversation_id
    ):

        if conversation_id not in self.conversations:

            self.conversations[
                conversation_id
            ] = []

        if conversation_id not in self.unread_counts:

            self.unread_counts[
                conversation_id
            ] = 0


    # ======================================================
    # ADD MESSAGE
    # ======================================================

    def add_message_to_conversation(
        self,
        conversation_id,
        message_type,
        message,
        sender
    ):

        self.ensure_conversation(
            conversation_id
        )

        self.conversations[
            conversation_id
        ].append(
            {
                "type": message_type,
                "message": message,
                "sender": sender
            }
        )


    # ======================================================
    # SHOW CONVERSATION
    # ======================================================

    def show_conversation(
        self,
        conversation_id
    ):

        self.ensure_conversation(
            conversation_id
        )

        self.chat_display.clear()

        messages = (
            self.conversations[
                conversation_id
            ]
        )

        for item in messages:

            if item["type"] == "sent":

                self.chat_display.append(
                    self.format_sent_message(
                        item["sender"],
                        item["message"]
                    )
                )

            else:

                self.chat_display.append(
                    self.format_received_message(
                        item["sender"],
                        item["message"]
                    )
                )

        self.scroll_to_bottom()


    # ======================================================
    # SENT MESSAGE — RIGHT SIDE
    # ======================================================

    def format_sent_message(
        self,
        sender,
        message
    ):

        return f'''
        <table width="100%" cellspacing="0" cellpadding="0">
            <tr>
                <td align="right">

                    <table cellspacing="0" cellpadding="0">
                        <tr>

                            <td
                                bgcolor="{MESSAGE_SENT}"
                                style="
                                    padding: 9px 13px;
                                    border-radius: 10px;
                                    color: white;
                                "
                            >

                                <div style="
                                    font-weight: 700;
                                    color: white;
                                ">
                                    {self.escape_html(sender)}
                                </div>

                                <div style="
                                    margin-top: 4px;
                                    color: white;
                                ">
                                    {self.escape_html(message)}
                                </div>

                            </td>

                        </tr>
                    </table>

                </td>
            </tr>
        </table>
        '''


    # ======================================================
    # RECEIVED MESSAGE — LEFT SIDE
    # ======================================================

    def format_received_message(
        self,
        sender,
        message
    ):

        return f'''
        <table width="100%" cellspacing="0" cellpadding="0">
            <tr>
                <td align="left">

                    <table cellspacing="0" cellpadding="0">
                        <tr>

                            <td
                                bgcolor="{MESSAGE_RECEIVED}"
                                style="
                                    padding: 9px 13px;
                                    border-left: 3px solid {ACCENT};
                                    border-radius: 10px;
                                    color: {TEXT};
                                "
                            >

                                <div style="
                                    font-weight: 700;
                                    color: {ACCENT};
                                ">
                                    {self.escape_html(sender)}
                                </div>

                                <div style="
                                    margin-top: 4px;
                                    color: {TEXT};
                                ">
                                    {self.escape_html(message)}
                                </div>

                            </td>

                        </tr>
                    </table>

                </td>
            </tr>
        </table>
        '''


    # ======================================================
    # SYSTEM MESSAGE
    # ======================================================

    def add_system_message(
        self,
        message
    ):

        html = f"""
        <div style="
            margin: 8px 5px;
            padding: 6px;
            color: {TEXT_SECONDARY};
        ">

            <b style="
                color: {ACCENT};
            ">
                SYSTEM
            </b>

            &nbsp;

            {self.escape_html(message)}

        </div>
        """

        self.chat_display.append(
            html
        )

        self.scroll_to_bottom()


    # ======================================================
    # ERROR MESSAGE
    # ======================================================

    def add_error_message(
        self,
        message
    ):

        html = f"""
        <div style="
            margin: 8px 5px;
            padding: 6px;
            color: {DANGER};
        ">

            <b>ERROR</b>

            &nbsp;

            {self.escape_html(message)}

        </div>
        """

        self.chat_display.append(
            html
        )

        self.scroll_to_bottom()


    # ======================================================
    # REFRESH SIDEBAR
    # ======================================================

    def refresh_sidebar(
        self,
        preserve_selection=True
    ):

        current_selection = (
            self.selected_client_id
        )

        self.client_list.clear()

        # ==================================================
        # EVERYONE
        # ==================================================

        everyone_item = QListWidgetItem(
            self.build_everyone_text()
        )

        everyone_item.setData(
            Qt.UserRole,
            0
        )

        self.client_list.addItem(
            everyone_item
        )

        # ==================================================
        # OTHER CLIENTS
        # ==================================================

        for client_id in self.online_clients:

            if client_id == self.my_client_id:

                continue

            item = QListWidgetItem(
                self.build_client_text(
                    client_id,
                    False
                )
            )

            item.setData(
                Qt.UserRole,
                client_id
            )

            self.client_list.addItem(
                item
            )

        # ==================================================
        # RESTORE SELECTION
        # ==================================================

        if preserve_selection:

            self.select_list_item(
                current_selection
            )


    # ======================================================
    # SELECT LIST ITEM
    # ======================================================

    def select_list_item(
        self,
        client_id
    ):

        for index in range(
            self.client_list.count()
        ):

            item = (
                self.client_list.item(
                    index
                )
            )

            if (
                item.data(
                    Qt.UserRole
                )
                ==
                client_id
            ):

                self.client_list.setCurrentItem(
                    item
                )

                return


    # ======================================================
    # EVERYONE SIDEBAR TEXT
    # ======================================================

    def build_everyone_text(
        self
    ):

        unread = (
            self.unread_counts.get(
                0,
                0
            )
        )

        last = (
            self.last_messages.get(
                0,
                ""
            )
        )

        if last:

            preview = self.truncate(
                last,
                28
            )

            text = (
                "🌐   Everyone\n"
                f"     {preview}"
            )

        else:

            text = (
                "🌐   Everyone\n"
                "     Broadcast chat"
            )

        if unread > 0:

            text += (
                f"   • {unread}"
            )

        return text


    # ======================================================
    # CLIENT SIDEBAR TEXT
    # ======================================================

    def build_client_text(
        self,
        client_id,
        is_me
    ):

        icon = "🟢"

        if is_me:

            name = (
                f"Client {client_id} (You)"
            )

        else:

            name = (
                f"Client {client_id}"
            )

        last = (
            self.last_messages.get(
                client_id,
                ""
            )
        )

        unread = (
            self.unread_counts.get(
                client_id,
                0
            )
        )

        if last:

            preview = self.truncate(
                last,
                28
            )

            text = (
                f"{icon}   {name}\n"
                f"     {preview}"
            )

        else:

            text = (
                f"{icon}   {name}"
            )

        if unread > 0:

            text += (
                f"   • {unread}"
            )

        return text


    # ======================================================
    # TRUNCATE
    # ======================================================

    def truncate(
        self,
        text,
        length
    ):

        text = str(
            text
        ).replace(
            "\n",
            " "
        )

        if len(text) <= length:

            return text

        return (
            text[:length - 3]
            + "..."
        )


    # ======================================================
    # CONNECTION STATUS
    # ======================================================

    def update_connection_status(
        self,
        connected
    ):

        self.connected = connected

        if connected:

            self.status_label.setText(
                "●  Connected"
            )

            self.status_label.setStyleSheet(
                f"color: {SUCCESS};"
            )

        else:

            self.status_label.setText(
                "●  Disconnected"
            )

            self.status_label.setStyleSheet(
                f"color: {DANGER};"
            )


    # ======================================================
    # SCROLL
    # ======================================================

    def scroll_to_bottom(
        self
    ):

        scrollbar = (
            self.chat_display.verticalScrollBar()
        )

        scrollbar.setValue(
            scrollbar.maximum()
        )


    # ======================================================
    # HTML ESCAPE
    # ======================================================

    def escape_html(
        self,
        text
    ):

        return (
            str(text)
            .replace(
                "&",
                "&amp;"
            )
            .replace(
                "<",
                "&lt;"
            )
            .replace(
                ">",
                "&gt;"
            )
            .replace(
                '"',
                "&quot;"
            )
        )


    # ======================================================
    # CLOSE WINDOW
    # ======================================================

    def closeEvent(
        self,
        event
    ):

        try:

            self.network.disconnect()

        except Exception:

            pass

        event.accept()


    # ======================================================
    # STYLESHEET
    # ======================================================

    def get_stylesheet(
        self
    ):

        return f"""

        * {{
            font-family: "Segoe UI";
        }}

        QMainWindow {{
            background-color: {BACKGROUND};
        }}

        QWidget {{
            color: {TEXT};
        }}

        /* ==================================================
           SIDEBAR
           ================================================== */

        #sidebar {{
            background-color: {SIDEBAR};
            border: 1px solid {BORDER};
            border-radius: 14px;
        }}

        #appTitle {{
            font-size: 24px;
            font-weight: 700;
            color: {ACCENT};
        }}

        #appSubtitle {{
            font-size: 12px;
            color: {TEXT_SECONDARY};
            padding-bottom: 5px;
        }}

        #userCard {{
            background-color: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 10px;
        }}

        #myId {{
            font-size: 16px;
            font-weight: 600;
            color: {TEXT};
        }}

        #status {{
            font-size: 12px;
            color: {SUCCESS};
        }}

        #sectionTitle {{
            font-size: 12px;
            font-weight: 700;
            color: {TEXT_SECONDARY};
            padding-top: 5px;
        }}

        /* ==================================================
           CLIENT LIST
           ================================================== */

        #clientList {{
            background-color: transparent;
            border: none;
            outline: none;
        }}

        #clientList::item {{
            padding: 12px 10px;
            border-radius: 8px;
            color: {TEXT};
            font-size: 14px;
        }}

        #clientList::item:hover {{
            background-color: {PANEL_LIGHT};
        }}

        #clientList::item:selected {{
            background-color: {ACCENT_DARK};
            color: white;
        }}

        #footer {{
            color: #64748b;
            font-size: 10px;
            padding-top: 5px;
        }}

        /* ==================================================
           CHAT PANEL
           ================================================== */

        #chatPanel {{
            background-color: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 14px;
        }}

        #chatHeader {{
            background-color: {PANEL};
            border-bottom: 1px solid {BORDER};
        }}

        #chatTitle {{
            font-size: 22px;
            font-weight: 700;
            color: {TEXT};
        }}

        #chatSubtitle {{
            font-size: 12px;
            color: {TEXT_SECONDARY};
        }}

        #chatDisplay {{
            background-color: {BACKGROUND};
            border: none;
            padding: 12px;
            font-size: 14px;
        }}

        /* ==================================================
           INPUT
           ================================================== */

        #inputContainer {{
            background-color: {PANEL};
            border-top: 1px solid {BORDER};
        }}

        #messageInput {{
            background-color: {BACKGROUND};
            border: 1px solid {BORDER};
            border-radius: 9px;
            padding: 12px 14px;
            color: {TEXT};
            font-size: 14px;
        }}

        #messageInput:focus {{
            border: 1px solid {ACCENT};
        }}

        #fileButton {{
            background-color: {PANEL_LIGHT};
            border: 1px solid {BORDER};
            border-radius: 9px;
            padding: 12px;
            color: {TEXT};
            font-weight: 700;
            font-size: 13px;
        }}

        #fileButton:hover {{
            background-color: {ACCENT_DARK};
            color: white;
        }}

        #fileButton:disabled {{
            background-color: #334155;
            color: #94a3b8;
        }}

        #sendButton {{
            background-color: {ACCENT};
            border: none;
            border-radius: 9px;
            padding: 12px;
            color: #06121a;
            font-weight: 700;
            font-size: 13px;
        }}

        #sendButton:hover {{
            background-color: #26d0e5;
        }}

        #sendButton:pressed {{
            background-color: {ACCENT_DARK};
        }}

        """


# ==========================================================
# APPLICATION START
# ==========================================================

def main():

    app = QApplication(
        sys.argv
    )

    window = ChatWindow()

    window.show()

    sys.exit(
        app.exec()
    )


# ==========================================================
# PROGRAM ENTRY
# ==========================================================

if __name__ == "__main__":

    main()