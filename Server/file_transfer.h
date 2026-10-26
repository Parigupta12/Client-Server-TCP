#ifndef FILE_TRANSFER_H
#define FILE_TRANSFER_H

#include <winsock2.h>

/*
 * ============================================================
 * TCP CHAT APPLICATION - FILE TRANSFER ENGINE
 * ============================================================
 *
 * Handles raw binary file data.
 *
 * File contents are NEVER converted to text.
 */


/* ============================================================
 * CONSTANTS
 * ============================================================
 */

#define FILE_TRANSFER_BUFFER_SIZE 8192


/* ============================================================
 * RESULT CODES
 * ============================================================
 */

#define FILE_TRANSFER_SUCCESS        0
#define FILE_TRANSFER_ERROR          -1
#define FILE_TRANSFER_DISCONNECTED   -2


/* ============================================================
 * SEND ALL BYTES
 * ============================================================
 */

int sendAllBytes(
    SOCKET socket,
    const char *data,
    int length
);


/* ============================================================
 * FORWARD FILE BYTES
 * ============================================================
 *
 * Receives exactly fileSize bytes from senderSocket
 * and forwards them directly to receiverSocket.
 */

int forwardFileBytes(
    SOCKET senderSocket,
    SOCKET receiverSocket,
    long long fileSize
);


#endif