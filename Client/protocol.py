"""
Application Protocol
--------------------

Defines the messages exchanged between the
Python client and the C TCP server.

TCP itself provides only a byte stream.
This application protocol defines the meaning
of those bytes.
"""

import base64


# ============================================================
# MESSAGE TYPES
# ============================================================

CLIENT_LIST = "CLIENT_LIST"
CLIENT_INFO = "CLIENT_INFO"

TEXT = "TEXT"

FILE_START = "FILE_START"
FILE_DATA = "FILE_DATA"
FILE_END = "FILE_END"
FILE_ERROR = "FILE_ERROR"

SYSTEM = "SYSTEM"


# ============================================================
# TEXT MESSAGE MODES
# ============================================================

BROADCAST = "BROADCAST"
PRIVATE = "PRIVATE"


# ============================================================
# FILE MESSAGE HELPERS
# ============================================================

def encode_filename(filename):
    """
    Encode a filename using Base64.

    The filename is encoded because the application protocol
    uses '|' as a field separator.

    The actual file contents are NOT Base64 encoded.
    Only the filename is encoded.
    """

    if filename is None:
        filename = ""

    filename_bytes = str(filename).encode(
        "utf-8"
    )

    return base64.b64encode(
        filename_bytes
    ).decode(
        "ascii"
    )


def decode_filename(encoded_filename):
    """
    Decode a Base64 encoded filename.
    """

    try:

        filename_bytes = base64.b64decode(
            encoded_filename.encode("ascii"),
            validate=True
        )

        return filename_bytes.decode(
            "utf-8"
        )

    except Exception:

        return ""


# ============================================================
# TEXT MESSAGE BUILDERS
# ============================================================

def build_broadcast_message(sender_id, message):
    """
    Create a broadcast text message.

    Example:

        TEXT|BROADCAST|1|Hello everyone!
    """

    message = str(message).replace(
        "\r",
        " "
    ).replace(
        "\n",
        " "
    )

    return (
        f"{TEXT}|{BROADCAST}|"
        f"{sender_id}|{message}\n"
    )


def build_private_message(
    sender_id,
    receiver_id,
    message
):
    """
    Create a private text message.

    Example:

        TEXT|PRIVATE|1|2|Hello Client 2
    """

    message = str(message).replace(
        "\r",
        " "
    ).replace(
        "\n",
        " "
    )

    return (
        f"{TEXT}|{PRIVATE}|"
        f"{sender_id}|{receiver_id}|"
        f"{message}\n"
    )


# ============================================================
# FILE START BUILDER
# ============================================================

def build_file_start(
    transfer_id,
    sender_id,
    receiver_id,
    file_size,
    filename
):
    """
    Create a FILE_START message.

    Format:

        FILE_START|
        transfer_id|
        sender_id|
        receiver_id|
        file_size|
        filename_base64

    Example:

        FILE_START|101|1|2|5242880|cmVwb3J0LnBkZg==
    """

    filename_encoded = encode_filename(
        filename
    )

    return (
        f"{FILE_START}|"
        f"{transfer_id}|"
        f"{sender_id}|"
        f"{receiver_id}|"
        f"{file_size}|"
        f"{filename_encoded}\n"
    )


# ============================================================
# FILE END BUILDER
# ============================================================

def build_file_end(
    transfer_id
):
    """
    Create a FILE_END message.

    Example:

        FILE_END|101
    """

    return (
        f"{FILE_END}|"
        f"{transfer_id}\n"
    )


# ============================================================
# FILE ERROR BUILDER
# ============================================================

def build_file_error(
    transfer_id,
    error_message
):
    """
    Create a FILE_ERROR message.

    Example:

        FILE_ERROR|101|File transfer failed
    """

    error_message = str(
        error_message
    ).replace(
        "\r",
        " "
    ).replace(
        "\n",
        " "
    ).replace(
        "|",
        "/"
    )

    return (
        f"{FILE_ERROR}|"
        f"{transfer_id}|"
        f"{error_message}\n"
    )


# ============================================================
# MESSAGE PARSING
# ============================================================

def parse_message(message):
    """
    Parse one complete text protocol message.

    IMPORTANT:

    This function is intended for protocol/control
    messages only.

    Raw FILE_DATA bytes must NOT be passed here.
    """

    if message is None:
        return None


    # --------------------------------------------------------
    # Remove only protocol line-ending characters.
    # --------------------------------------------------------

    message = message.rstrip(
        "\r\n"
    )


    if not message:
        return None


    # --------------------------------------------------------
    # Split protocol fields.
    #
    # TEXT messages use the remaining fields as message text.
    # FILE control messages have fixed fields.
    # --------------------------------------------------------

    parts = message.split(
        "|"
    )


    if not parts:
        return None


    message_type = parts[0]


    # ========================================================
    # CLIENT LIST
    # ========================================================

    if message_type == CLIENT_LIST:

        client_ids = []


        if (
            len(parts) > 1
            and parts[1]
        ):

            try:

                client_ids = [
                    int(client_id)
                    for client_id in parts[1].split(",")
                    if client_id
                ]

            except ValueError:

                return None


        return {
            "type": CLIENT_LIST,
            "clients": client_ids
        }


    # ========================================================
    # CLIENT INFO
    # ========================================================

    if message_type == CLIENT_INFO:

        if len(parts) < 3:
            return None


        try:

            client_id = int(
                parts[1]
            )

        except ValueError:

            return None


        clients = []


        if parts[2]:

            try:

                clients = [
                    int(client_id)
                    for client_id in parts[2].split(",")
                    if client_id
                ]

            except ValueError:

                return None


        return {
            "type": CLIENT_INFO,
            "client_id": client_id,
            "clients": clients
        }


    # ========================================================
    # TEXT
    # ========================================================

    if message_type == TEXT:

        if len(parts) < 4:
            return None


        mode = parts[1]


        try:

            sender_id = int(
                parts[2]
            )

        except ValueError:

            return None


        # ----------------------------------------------------
        # BROADCAST
        # ----------------------------------------------------

        if mode == BROADCAST:

            message_text = "|".join(
                parts[3:]
            )


            return {
                "type": TEXT,
                "mode": BROADCAST,
                "sender_id": sender_id,
                "message": message_text
            }


        # ----------------------------------------------------
        # PRIVATE
        # ----------------------------------------------------

        if mode == PRIVATE:

            if len(parts) < 5:
                return None


            try:

                receiver_id = int(
                    parts[3]
                )

            except ValueError:

                return None


            message_text = "|".join(
                parts[4:]
            )


            return {
                "type": TEXT,
                "mode": PRIVATE,
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "message": message_text
            }


        return None


    # ========================================================
    # FILE START
    # ========================================================

    if message_type == FILE_START:

        if len(parts) != 6:
            return None


        try:

            transfer_id = int(
                parts[1]
            )

            sender_id = int(
                parts[2]
            )

            receiver_id = int(
                parts[3]
            )

            file_size = int(
                parts[4]
            )

        except ValueError:

            return None


        filename_encoded = parts[5]


        filename = decode_filename(
            filename_encoded
        )


        if not filename:

            return None


        if file_size < 0:

            return None


        return {
            "type": FILE_START,
            "transfer_id": transfer_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "file_size": file_size,
            "filename": filename,
            "filename_encoded": filename_encoded
        }


    # ========================================================
    # FILE END
    # ========================================================

    if message_type == FILE_END:

        if len(parts) != 2:
            return None


        try:

            transfer_id = int(
                parts[1]
            )

        except ValueError:

            return None


        return {
            "type": FILE_END,
            "transfer_id": transfer_id
        }


    # ========================================================
    # FILE ERROR
    # ========================================================

    if message_type == FILE_ERROR:

        if len(parts) < 3:
            return None


        try:

            transfer_id = int(
                parts[1]
            )

        except ValueError:

            return None


        error_message = "|".join(
            parts[2:]
        )


        return {
            "type": FILE_ERROR,
            "transfer_id": transfer_id,
            "message": error_message
        }


    # ========================================================
    # SYSTEM
    # ========================================================

    if message_type == SYSTEM:

        return {
            "type": SYSTEM,
            "message": "|".join(
                parts[1:]
            )
        }


    # ========================================================
    # UNKNOWN MESSAGE
    # ========================================================

    return {
        "type": "UNKNOWN",
        "raw": message
    }