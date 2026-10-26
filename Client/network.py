"""
TCP Chat Application
Python Network Client
---------------------

Handles:
1. TCP connection
2. Text messages
3. Broadcast messages
4. Private messages
5. File sending
6. Binary file receiving

File transfer protocol:

    FILE_START|transfer_id|sender|receiver|size|filename\n
    <raw binary bytes>
    FILE_END|transfer_id\n

IMPORTANT:
File contents are handled as RAW BYTES.
They are never decoded as UTF-8 while a transfer
is active.
"""

import os
import socket
import threading
import time

from PySide6.QtCore import QObject, Signal

from Client.protocol import (
    build_broadcast_message,
    build_private_message,
    build_file_start,
    build_file_end,
    parse_message,
)


# ============================================================
# CONFIGURATION
# ============================================================

SERVER_HOST = "10.246.241.9"
SERVER_PORT = 8080
FILE_CHUNK_SIZE = 8192

RECEIVED_FILES_DIR = os.path.join(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    ),
    "received_files"
)


# ============================================================
# NETWORK CLIENT
# ============================================================

class NetworkClient(QObject):

    # --------------------------------------------------------
    # SIGNALS
    # --------------------------------------------------------

    message_received = Signal(str)

    connection_changed = Signal(bool)

    client_info_received = Signal(int, list)

    client_list_received = Signal(list)

    # Emitted when an incoming file is fully saved locally.
    # filename, sender_id, local_path, file_size
    file_received = Signal(str, int, str, int)


    # --------------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------------

    def __init__(self):
        super().__init__()

        self.socket = None

        self.connected = False

        self.receive_thread = None

        self.client_id = None

        self.client_list = []

        # ----------------------------------------------------
        # TCP receive buffer
        # ----------------------------------------------------

        self.receive_buffer = b""

        # ----------------------------------------------------
        # File receive state
        # ----------------------------------------------------

        self.file_receiving = False

        # IMPORTANT:
        # True after all expected binary bytes are received,
        # while we are waiting for FILE_END.
        self.file_waiting_for_end = False

        self.file_transfer_id = None

        self.file_sender_id = None

        self.file_receiver_id = None

        self.file_expected_size = 0

        self.file_received_size = 0

        self.file_name = None

        self.file_path = None

        self.file_handle = None

        # ----------------------------------------------------
        # Create received_files directory
        # ----------------------------------------------------

        os.makedirs(
            RECEIVED_FILES_DIR,
            exist_ok=True
        )


    # ========================================================
    # CONNECT
    # ========================================================

    def connect(self):
        """
        Connect to the C TCP server.
        """

        if self.connected:
            return True

        try:

            print(
                "========================================"
            )

            print(
                "       PYTHON TCP CLIENT"
            )

            print(
                "========================================"
            )

            print(
                "[OK] Socket created."
            )

            print(
                "[INFO] Connecting to C server..."
            )

            self.socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            self.socket.connect(
                (
                    SERVER_HOST,
                    SERVER_PORT
                )
            )

            self.connected = True

            print(
                "[CONNECTED] Successfully connected!"
            )

            print(
                "----------------------------------------"
            )

            self.connection_changed.emit(
                True
            )

            self.receive_thread = threading.Thread(
                target=self.receive_messages,
                daemon=True
            )

            self.receive_thread.start()

            return True

        except Exception as error:

            print(
                f"[ERROR] Connection failed: {error}"
            )

            self.connected = False

            self.connection_changed.emit(
                False
            )

            return False


    # ========================================================
    # RECEIVE LOOP
    # ========================================================

    def receive_messages(self):
        """
        Receive data from the TCP server.

        This function operates on BYTES.

        Normal text/control messages are newline-framed.

        File transfers are processed using exact byte counts.
        """

        while self.connected:

            try:

                data = self.socket.recv(
                    FILE_CHUNK_SIZE
                )

                # ------------------------------------------------
                # Server disconnected
                # ------------------------------------------------

                if not data:

                    print(
                        "[DISCONNECTED] "
                        "Server closed connection."
                    )

                    self.connected = False

                    self.connection_changed.emit(
                        False
                    )

                    break

                # ------------------------------------------------
                # Append raw bytes
                # ------------------------------------------------

                self.receive_buffer += data

                # ------------------------------------------------
                # Process available data
                # ------------------------------------------------

                self.process_receive_buffer()

            except OSError:

                if self.connected:

                    print(
                        "[ERROR] Socket receive failed."
                    )

                break

            except Exception as error:

                print(
                    f"[ERROR] Receive error: {error}"
                )

                break

        self.connected = False

        self.connection_changed.emit(
            False
        )


    # ========================================================
    # PROCESS RECEIVE BUFFER
    # ========================================================

    def process_receive_buffer(self):
        """
        Process the persistent TCP receive buffer.

        State 1:
            Normal text/control message.

        State 2:
            Receiving exact file bytes.

        State 3:
            Waiting for FILE_END.

        IMPORTANT:
        TCP is a byte stream. One recv() call may contain:

            FILE_START
            + part/all of file
            + FILE_END

        Therefore the receive buffer must be processed
        carefully without assuming recv() boundaries.
        """

        while True:

            # =================================================
            # FILE BINARY RECEIVING STATE
            # =================================================

            if self.file_receiving:

                # ------------------------------------------------
                # If all binary bytes have already arrived,
                # switch to WAITING FOR FILE_END state.
                # ------------------------------------------------

                if self.file_received_size >= self.file_expected_size:

                    if not self.file_waiting_for_end:

                        self.finish_file_data()

                    # IMPORTANT:
                    #
                    # Do NOT continue treating the remaining
                    # buffer as binary.
                    #
                    # We now need to process FILE_END as a
                    # normal newline-framed control message.
                    #
                    self.file_receiving = False

                    # Continue below into normal control state.
                    continue

                # ------------------------------------------------
                # No data available
                # ------------------------------------------------

                if not self.receive_buffer:

                    return

                # ------------------------------------------------
                # Determine remaining bytes
                # ------------------------------------------------

                remaining = (
                    self.file_expected_size
                    -
                    self.file_received_size
                )

                # ------------------------------------------------
                # Determine how many bytes to consume
                # ------------------------------------------------

                bytes_to_write = min(
                    remaining,
                    len(self.receive_buffer)
                )

                file_bytes = (
                    self.receive_buffer[
                        :bytes_to_write
                    ]
                )

                # ------------------------------------------------
                # Write RAW BYTES to disk
                # ------------------------------------------------

                try:

                    if self.file_handle is None:

                        print(
                            "[FILE ERROR] "
                            "File handle is unavailable."
                        )

                        self.abort_file_receive(
                            "File handle is unavailable."
                        )

                        return

                    self.file_handle.write(
                        file_bytes
                    )

                    self.file_handle.flush()

                except Exception as error:

                    print(
                        "[FILE ERROR] "
                        f"Could not write file: {error}"
                    )

                    self.abort_file_receive(
                        "Could not write received file."
                    )

                    return

                # ------------------------------------------------
                # Remove consumed bytes from TCP buffer
                # ------------------------------------------------

                self.receive_buffer = (
                    self.receive_buffer[
                        bytes_to_write:
                    ]
                )

                # ------------------------------------------------
                # Update received byte count
                # ------------------------------------------------

                self.file_received_size += (
                    bytes_to_write
                )

                # ------------------------------------------------
                # Progress
                # ------------------------------------------------

                if self.file_expected_size > 0:

                    progress = (
                        self.file_received_size
                        /
                        self.file_expected_size
                    ) * 100

                    print(
                        f"\r[FILE] Receiving: "
                        f"{self.file_received_size} / "
                        f"{self.file_expected_size} "
                        f"bytes "
                        f"({progress:.1f}%)",
                        end="",
                        flush=True
                    )

                # ------------------------------------------------
                # Continue processing
                # ------------------------------------------------

                continue


            # =================================================
            # NORMAL CONTROL/TEXT STATE
            # =================================================

            newline_index = (
                self.receive_buffer.find(
                    b"\n"
                )
            )

            # ------------------------------------------------
            # No complete line yet
            # ------------------------------------------------

            if newline_index == -1:

                return

            # ------------------------------------------------
            # Extract one complete line
            # ------------------------------------------------

            raw_message = (
                self.receive_buffer[
                    :newline_index
                ]
            )

            self.receive_buffer = (
                self.receive_buffer[
                    newline_index + 1:
                ]
            )

            # ------------------------------------------------
            # Empty line
            # ------------------------------------------------

            if not raw_message:

                continue

            # ------------------------------------------------
            # Decode ONLY control/text data
            # ------------------------------------------------

            try:

                message = raw_message.decode(
                    "utf-8"
                )

            except UnicodeDecodeError:

                print(
                    "[ERROR] Invalid UTF-8 control message."
                )

                continue

            # ------------------------------------------------
            # Remove CR if CRLF
            # ------------------------------------------------

            message = message.rstrip(
                "\r"
            )

            # ------------------------------------------------
            # Handle message
            # ------------------------------------------------

            self.handle_server_message(
                message
            )


    # ========================================================
    # HANDLE SERVER MESSAGE
    # ========================================================

    def handle_server_message(
        self,
        message
    ):
        """
        Handle one complete text/control message.
        """

        # Raw protocol messages are not printed here.
        # They are converted into user-friendly messages below.

        # ----------------------------------------------------
        # Parse using protocol layer
        # ----------------------------------------------------

        try:

            parsed = parse_message(
                message
            )

        except Exception as error:

            print(
                f"[WARNING] Could not parse message: "
                f"{error}"
            )

            parsed = None

        if parsed is None:

            return

        message_type = parsed.get(
            "type"
        )


        # ====================================================
        # CLIENT INFO
        # ====================================================

        if message_type == "CLIENT_INFO":

            self.client_id = (
                parsed.get(
                    "client_id"
                )
            )

            self.client_list = (
                parsed.get(
                    "clients",
                    []
                )
            )

            self.client_info_received.emit(
                self.client_id,
                self.client_list
            )

            return


        # ====================================================
        # CLIENT LIST
        # ====================================================

        if message_type == "CLIENT_LIST":

            self.client_list = (
                parsed.get(
                    "clients",
                    []
                )
            )

            self.client_list_received.emit(
                self.client_list
            )

            return


        # ====================================================
        # PRIVATE TEXT
        # ====================================================

        if (
            message_type == "TEXT"
            and
            parsed.get("mode") == "PRIVATE"
        ):

            sender_id = (
                parsed.get(
                    "sender_id"
                )
            )

            receiver_id = (
                parsed.get(
                    "receiver_id"
                )
            )

            message_text = (
                parsed.get(
                    "message",
                    ""
                )
            )

            # ------------------------------------------------
            # Only process messages intended for this client
            # ------------------------------------------------

            if (
                self.client_id is not None
                and
                receiver_id != self.client_id
            ):

                return

            display_message = (
                f"[Private from Client "
                f"{sender_id}] "
                f"{message_text}"
            )

            print()
            print(f"[MESSAGE] {display_message}")
            print("[YOU] ", end="", flush=True)

            print()
            print(f"[MESSAGE] {display_message}")
            print("[YOU] ", end="", flush=True)

            self.message_received.emit(
                display_message
            )

            return


        # ====================================================
        # BROADCAST TEXT
        # ====================================================

        if (
            message_type == "TEXT"
            and
            parsed.get("mode") == "BROADCAST"
        ):

            sender_id = (
                parsed.get(
                    "sender_id"
                )
            )

            message_text = (
                parsed.get(
                    "message",
                    ""
                )
            )

            display_message = (
                f"[Broadcast from Client "
                f"{sender_id}] "
                f"{message_text}"
            )

            self.message_received.emit(
                display_message
            )

            return


        # ====================================================
        # FILE START
        # ====================================================

        if message_type == "FILE_START":

            self.start_file_receive(
                parsed
            )

            return


        # ====================================================
        # FILE END
        # ====================================================

        if message_type == "FILE_END":

            self.handle_file_end(
                parsed
            )

            return


        # ====================================================
        # FILE ERROR
        # ====================================================

        if message_type == "FILE_ERROR":

            transfer_id = (
                parsed.get(
                    "transfer_id"
                )
            )

            error_message = (
                parsed.get(
                    "message",
                    "File transfer failed."
                )
            )

            print(
                f"\n[FILE ERROR] "
                f"Transfer {transfer_id}: "
                f"{error_message}"
            )

            self.message_received.emit(
                f"[FILE ERROR] {error_message}"
            )

            return


        # ====================================================
        # SYSTEM
        # ====================================================

        if message_type == "SYSTEM":

            self.message_received.emit(
                message
            )

            return


        # ====================================================
        # UNKNOWN
        # ====================================================

        self.message_received.emit(
            message
        )


    # ========================================================
    # START FILE RECEIVE
    # ========================================================

    def start_file_receive(
        self,
        file_info
    ):
        """
        Initialize a new incoming file transfer.
        """

        # ----------------------------------------------------
        # Reject another active transfer
        # ----------------------------------------------------

        if self.file_receiving:

            print(
                "[FILE ERROR] "
                "Another file transfer is already active."
            )

            return

        transfer_id = (
            file_info.get(
                "transfer_id"
            )
        )

        sender_id = (
            file_info.get(
                "sender_id"
            )
        )

        receiver_id = (
            file_info.get(
                "receiver_id"
            )
        )

        file_size = (
            file_info.get(
                "file_size"
            )
        )

        filename = (
            file_info.get(
                "filename"
            )
        )


        # ----------------------------------------------------
        # Validate fields
        # ----------------------------------------------------

        if transfer_id is None:

            print(
                "[FILE ERROR] Missing transfer ID."
            )

            return

        if file_size is None:

            print(
                "[FILE ERROR] Missing file size."
            )

            return

        if file_size < 0:

            print(
                "[FILE ERROR] Invalid file size."
            )

            return

        if not filename:

            filename = (
                f"received_{transfer_id}"
            )


        # ----------------------------------------------------
        # Security: use basename only
        # ----------------------------------------------------

        filename = os.path.basename(
            filename
        )


        # ----------------------------------------------------
        # Build destination path
        # ----------------------------------------------------

        destination = os.path.join(
            RECEIVED_FILES_DIR,
            filename
        )


        # ----------------------------------------------------
        # Prevent accidental overwrite
        # ----------------------------------------------------

        destination = (
            self.get_unique_file_path(
                destination
            )
        )


        try:

            file_handle = open(
                destination,
                "wb"
            )

        except Exception as error:

            print(
                f"[FILE ERROR] "
                f"Could not create destination: "
                f"{error}"
            )

            return


        # ----------------------------------------------------
        # Store transfer state
        # ----------------------------------------------------

        self.file_receiving = True

        self.file_waiting_for_end = False

        self.file_transfer_id = (
            transfer_id
        )

        self.file_sender_id = (
            sender_id
        )

        self.file_receiver_id = (
            receiver_id
        )

        self.file_expected_size = (
            file_size
        )

        self.file_received_size = 0

        self.file_name = (
            filename
        )

        self.file_path = (
            destination
        )

        self.file_handle = (
            file_handle
        )


        print(
            "\n========================================"
        )

        print(
            "       INCOMING FILE TRANSFER"
        )

        print(
            "========================================"
        )

        print(
            f"[FILE] Name     : {filename}"
        )

        print(
            f"[FILE] Size     : {file_size} bytes"
        )

        print(
            f"[FILE] Sender   : Client {sender_id}"
        )

        print(
            f"[FILE] Receiver : Client {receiver_id}"
        )

        print(
            f"[FILE] Transfer : {transfer_id}"
        )

        print(
            f"[FILE] Saving to: {destination}"
        )

        print(
            "----------------------------------------"
        )

        self.message_received.emit(
            f"[FILE] Receiving '{filename}' "
            f"from Client {sender_id}..."
        )


        # ----------------------------------------------------
        # Zero-byte file
        # ----------------------------------------------------

        if file_size == 0:

            self.finish_file_data()


    # ========================================================
    # FINISH FILE DATA
    # ========================================================

    def finish_file_data(self):
        """
        Called when exactly file_size bytes have been
        received.

        This closes the file and switches the transfer
        into a WAITING FOR FILE_END state.

        It does NOT complete the transfer yet.
        """

        if not self.file_receiving:

            return

        # Prevent duplicate execution
        if self.file_waiting_for_end:

            return

        print()

        try:

            if self.file_handle is not None:

                self.file_handle.flush()

                self.file_handle.close()

        except Exception:

            pass

        self.file_handle = None

        self.file_waiting_for_end = True

        print(
            "[FILE] All expected binary data received."
        )

        print(
            "[FILE] Waiting for FILE_END..."
        )

        self.message_received.emit(
            f"[FILE] Binary data received for "
            f"'{self.file_name}'. "
            f"Waiting for completion..."
        )


    # ========================================================
    # HANDLE FILE END
    # ========================================================

    def handle_file_end(
        self,
        file_info
    ):
        """
        Complete an incoming file transfer.
        """

        transfer_id = (
            file_info.get(
                "transfer_id"
            )
        )


        # ----------------------------------------------------
        # No active transfer
        # ----------------------------------------------------

        if (
            not self.file_receiving
            and
            not self.file_waiting_for_end
        ):

            print(
                "[FILE ERROR] "
                "Unexpected FILE_END."
            )

            return


        # ----------------------------------------------------
        # Verify transfer ID
        # ----------------------------------------------------

        if (
            transfer_id !=
            self.file_transfer_id
        ):

            print(
                "[FILE ERROR] "
                "FILE_END transfer ID mismatch."
            )

            self.abort_file_receive(
                "Transfer ID mismatch."
            )

            return


        # ----------------------------------------------------
        # Verify byte count
        # ----------------------------------------------------

        if (
            self.file_received_size !=
            self.file_expected_size
        ):

            print(
                "[FILE ERROR] "
                "File size mismatch."
            )

            self.abort_file_receive(
                "Received file size does not match."
            )

            return


        # ----------------------------------------------------
        # Close file if necessary
        # ----------------------------------------------------

        try:

            if self.file_handle is not None:

                self.file_handle.flush()

                self.file_handle.close()

        except Exception:

            pass

        self.file_handle = None


        # ----------------------------------------------------
        # Save information before resetting state
        # ----------------------------------------------------

        filename = (
            self.file_name
        )

        file_path = (
            self.file_path
        )

        file_size = (
            self.file_received_size
        )

        sender_id = (
            self.file_sender_id
        )

        transfer_id = (
            self.file_transfer_id
        )


        # ----------------------------------------------------
        # Reset state
        # ----------------------------------------------------

        self.reset_file_state()


        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        print(
            "\n========================================"
        )

        print(
            "       FILE TRANSFER COMPLETE"
        )

        print(
            "========================================"
        )

        print(
            f"[FILE] Name   : {filename}"
        )

        print(
            f"[FILE] Size   : {file_size} bytes"
        )

        print(
            f"[FILE] Sender : Client {sender_id}"
        )

        print(
            f"[FILE] Saved  : {file_path}"
        )

        print(
            f"[FILE] ID     : {transfer_id}"
        )

        print(
            "========================================\n"
        )

        # Notify the GUI with the ACTUAL local path so the received
        # file can be opened directly from the chat bubble.
        self.file_received.emit(
            filename,
            int(sender_id),
            file_path,
            int(file_size)
        )

        # Keep the textual notification for terminal/log compatibility.
        self.message_received.emit(
            f"[FILE RECEIVED] {filename} "
            f"({file_size} bytes)"
        )


    # ========================================================
    # ABORT FILE RECEIVE
    # ========================================================

    def abort_file_receive(
        self,
        reason
    ):
        """
        Abort the current incoming file transfer.
        """

        print(
            f"[FILE ERROR] {reason}"
        )


        try:

            if self.file_handle is not None:

                self.file_handle.close()

        except Exception:

            pass

        self.file_handle = None


        # ----------------------------------------------------
        # Remove incomplete file
        # ----------------------------------------------------

        if self.file_path:

            try:

                if os.path.exists(
                    self.file_path
                ):

                    os.remove(
                        self.file_path
                    )

            except Exception:

                pass


        self.reset_file_state()

        self.message_received.emit(
            f"[FILE ERROR] {reason}"
        )


    # ========================================================
    # RESET FILE STATE
    # ========================================================

    def reset_file_state(self):
        """
        Reset all file-receiving state.
        """

        self.file_receiving = False

        self.file_waiting_for_end = False

        self.file_transfer_id = None

        self.file_sender_id = None

        self.file_receiver_id = None

        self.file_expected_size = 0

        self.file_received_size = 0

        self.file_name = None

        self.file_path = None

        self.file_handle = None


    # ========================================================
    # UNIQUE FILE PATH
    # ========================================================

    def get_unique_file_path(
        self,
        path
    ):
        """
        Avoid overwriting an existing file.

        Example:

            report.pdf
            report (1).pdf
            report (2).pdf
        """

        if not os.path.exists(path):

            return path


        directory = os.path.dirname(
            path
        )

        filename = os.path.basename(
            path
        )

        name, extension = os.path.splitext(
            filename
        )

        counter = 1

        while True:

            candidate = os.path.join(
                directory,
                f"{name} ({counter}){extension}"
            )

            if not os.path.exists(
                candidate
            ):

                return candidate

            counter += 1


    # ========================================================
    # SEND RAW TEXT
    # ========================================================

    def send_message(
        self,
        message
    ):
        """
        Send a raw text message.
        """

        if not self.connected:

            return False

        if self.socket is None:

            return False

        try:

            if not message.endswith("\n"):

                message += "\n"

            self.socket.sendall(
                message.encode(
                    "utf-8"
                )
            )

            return True

        except Exception as error:

            print(
                f"[ERROR] Send failed: {error}"
            )

            return False


    # ========================================================
    # SEND PRIVATE MESSAGE
    # ========================================================

    def send_private_message(
        self,
        target_id,
        message
    ):
        """
        Send a private text message.
        """

        if not self.connected:

            return False

        if self.client_id is None:

            print(
                "[ERROR] Client ID is not known yet."
            )

            return False

        try:

            protocol_message = (
                build_private_message(
                    self.client_id,
                    int(target_id),
                    message
                )
            )

            self.socket.sendall(
                protocol_message.encode(
                    "utf-8"
                )
            )

            return True

        except Exception as error:

            print(
                f"[ERROR] Private message failed: "
                f"{error}"
            )

            return False


    # ========================================================
    # SEND BROADCAST MESSAGE
    # ========================================================

    def send_broadcast_message(
        self,
        message
    ):
        """
        Send a broadcast text message.
        """

        if not self.connected:

            return False

        if self.client_id is None:

            print(
                "[ERROR] Client ID is not known yet."
            )

            return False

        try:

            protocol_message = (
                build_broadcast_message(
                    self.client_id,
                    message
                )
            )

            self.socket.sendall(
                protocol_message.encode(
                    "utf-8"
                )
            )

            return True

        except Exception as error:

            print(
                f"[ERROR] Broadcast failed: "
                f"{error}"
            )

            return False


    # ========================================================
    # SEND FILE
    # ========================================================

    def send_file(
        self,
        target_id,
        file_path
    ):
        """
        Send a file to another client.

        Sequence:

            FILE_START
            raw binary bytes
            FILE_END

        Returns:

            True  -> transfer data sent
            False -> transfer failed
        """

        if not self.connected:

            print(
                "[FILE ERROR] Client is not connected."
            )

            return False

        if self.socket is None:

            print(
                "[FILE ERROR] Socket is unavailable."
            )

            return False

        if self.client_id is None:

            print(
                "[FILE ERROR] Client ID is unknown."
            )

            return False


        # ----------------------------------------------------
        # Target ID
        # ----------------------------------------------------

        try:

            target_id = int(
                target_id
            )

        except (
            TypeError,
            ValueError
        ):

            print(
                "[FILE ERROR] "
                "Invalid target client ID."
            )

            return False


        if target_id == self.client_id:

            print(
                "[FILE ERROR] "
                "Cannot send a file to yourself."
            )

            return False


        # ----------------------------------------------------
        # File validation
        # ----------------------------------------------------

        if not os.path.isfile(
            file_path
        ):

            print(
                "[FILE ERROR] "
                f"File does not exist: {file_path}"
            )

            return False


        try:

            file_size = os.path.getsize(
                file_path
            )

            filename = os.path.basename(
                file_path
            )


            # ------------------------------------------------
            # Generate transfer ID
            # ------------------------------------------------

            transfer_id = (
                int(
                    time.time() * 1000
                )
                % 2147483647
            )


            print(
                "\n========================================"
            )

            print(
                "          FILE TRANSFER"
            )

            print(
                "========================================"
            )

            print(
                f"[FILE] Name       : {filename}"
            )

            print(
                f"[FILE] Size       : {file_size} bytes"
            )

            print(
                f"[FILE] Sender     : Client {self.client_id}"
            )

            print(
                f"[FILE] Receiver   : Client {target_id}"
            )

            print(
                f"[FILE] Transfer ID: {transfer_id}"
            )

            print(
                "----------------------------------------"
            )


            # =================================================
            # FILE_START
            # =================================================

            start_message = (
                build_file_start(
                    transfer_id,
                    self.client_id,
                    target_id,
                    file_size,
                    filename
                )
            )

            self.socket.sendall(
                start_message.encode(
                    "utf-8"
                )
            )

            print(
                "[FILE] FILE_START sent."
            )


            # =================================================
            # RAW BINARY DATA
            # =================================================

            bytes_sent = 0

            with open(
                file_path,
                "rb"
            ) as file:

                while True:

                    chunk = file.read(
                        FILE_CHUNK_SIZE
                    )

                    if not chunk:

                        break

                    self.socket.sendall(
                        chunk
                    )

                    bytes_sent += len(
                        chunk
                    )

                    if file_size > 0:

                        progress = (
                            bytes_sent
                            /
                            file_size
                        ) * 100

                        print(
                            f"\r[FILE] Sending: "
                            f"{bytes_sent} / "
                            f"{file_size} bytes "
                            f"({progress:.1f}%)",
                            end="",
                            flush=True
                        )

            print()


            # =================================================
            # FILE_END
            # =================================================

            end_message = (
                build_file_end(
                    transfer_id
                )
            )

            self.socket.sendall(
                end_message.encode(
                    "utf-8"
                )
            )

            print(
                "[FILE] FILE_END sent."
            )

            print(
                "[FILE] Transfer data sent successfully."
            )

            print(
                "========================================\n"
            )

            return True


        except Exception as error:

            print(
                f"\n[FILE ERROR] "
                f"Transfer failed: {error}"
            )

            return False


    # ========================================================
    # DISCONNECT
    # ========================================================

    def disconnect(self):
        """
        Close TCP connection.
        """

        self.connected = False


        # ----------------------------------------------------
        # Close an active file
        # ----------------------------------------------------

        if (
            self.file_receiving
            or
            self.file_waiting_for_end
        ):

            self.abort_file_receive(
                "Connection closed during file transfer."
            )


        # ----------------------------------------------------
        # Close socket
        # ----------------------------------------------------

        if self.socket is not None:

            try:

                self.socket.shutdown(
                    socket.SHUT_RDWR
                )

            except Exception:

                pass


            try:

                self.socket.close()

            except Exception:

                pass


            self.socket = None


        self.connection_changed.emit(
            False
        )
        self.socket.sendall(
            end_message.encode(
            "utf-8"
        )
)