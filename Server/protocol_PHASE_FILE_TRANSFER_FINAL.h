#ifndef PROTOCOL_H
#define PROTOCOL_H

/*
 * ============================================================
 * TCP CHAT APPLICATION - APPLICATION PROTOCOL
 * ============================================================
 *
 * TCP itself provides a byte stream.
 *
 * This application protocol defines the meaning of
 * the bytes exchanged between clients and the server.
 *
 * TEXT messages are newline-framed.
 *
 * FILE_START and FILE_END are control messages.
 *
 * FILE_DATA is NOT represented as a C string.
 * The actual file data will be transferred as raw
 * binary bytes in the file-transfer layer.
 */


/* ============================================================
 * MESSAGE TYPES
 * ============================================================
 */

#define MSG_CLIENT_LIST     "CLIENT_LIST"
#define MSG_CLIENT_INFO     "CLIENT_INFO"

#define MSG_TEXT            "TEXT"

#define MSG_FILE_START      "FILE_START"
#define MSG_FILE_DATA       "FILE_DATA"
#define MSG_FILE_END        "FILE_END"
#define MSG_FILE_ERROR      "FILE_ERROR"

#define MSG_SYSTEM          "SYSTEM"


/* ============================================================
 * TEXT MESSAGE MODES
 * ============================================================
 */

#define MODE_BROADCAST      "BROADCAST"
#define MODE_PRIVATE        "PRIVATE"


/* ============================================================
 * PROTOCOL FUNCTIONS
 * ============================================================
 */


/*
 * ------------------------------------------------------------
 * Build broadcast text message
 *
 * Example:
 *
 * TEXT|BROADCAST|1|Hello everyone!
 *
 * Returns:
 * Number of characters written.
 *
 * Returns -1 on invalid input.
 * ------------------------------------------------------------
 */

int buildBroadcastMessage(
    char *buffer,
    int bufferSize,
    int senderId,
    const char *message
);


/*
 * ------------------------------------------------------------
 * Build private text message
 *
 * Example:
 *
 * TEXT|PRIVATE|1|2|Hello Client 2
 *
 * Returns:
 * Number of characters written.
 *
 * Returns -1 on invalid input.
 * ------------------------------------------------------------
 */

int buildPrivateMessage(
    char *buffer,
    int bufferSize,
    int senderId,
    int receiverId,
    const char *message
);


/*
 * ------------------------------------------------------------
 * Build FILE_START message
 *
 * Format:
 *
 * FILE_START|
 * transferId|
 * senderId|
 * receiverId|
 * fileSize|
 * filenameEncoded
 *
 * Example:
 *
 * FILE_START|101|1|2|5242880|cmVwb3J0LnBkZg==
 *
 * The filename is expected to already be encoded safely
 * for the protocol.
 * ------------------------------------------------------------
 */

int buildFileStartMessage(
    char *buffer,
    int bufferSize,
    int transferId,
    int senderId,
    int receiverId,
    long long fileSize,
    const char *encodedFilename
);


/*
 * ------------------------------------------------------------
 * Build FILE_END message
 *
 * Example:
 *
 * FILE_END|101
 * ------------------------------------------------------------
 */

int buildFileEndMessage(
    char *buffer,
    int bufferSize,
    int transferId
);


/*
 * ------------------------------------------------------------
 * Build FILE_ERROR message
 *
 * Example:
 *
 * FILE_ERROR|101|File transfer failed
 * ------------------------------------------------------------
 */

int buildFileErrorMessage(
    char *buffer,
    int bufferSize,
    int transferId,
    const char *errorMessage
);


/*
 * ------------------------------------------------------------
 * Extract the first field from a protocol message.
 *
 * Example:
 *
 * Input:
 *
 * TEXT|BROADCAST|1|Hello
 *
 * Output:
 *
 * TEXT
 *
 * Returns:
 * Number of characters copied.
 * ------------------------------------------------------------
 */

int getProtocolType(
    const char *message,
    char *type,
    int typeSize
);

#endif