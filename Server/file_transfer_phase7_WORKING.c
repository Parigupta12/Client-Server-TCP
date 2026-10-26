#include <stdio.h>
#include <string.h>
#include <winsock2.h>

#include "file_transfer.h"


/* ============================================================
 * SEND ALL BYTES
 * ============================================================
 *
 * send() may transmit fewer bytes than requested.
 *
 * Therefore we continue until the entire buffer is sent.
 * ============================================================
 */

int sendAllBytes(
    SOCKET socket,
    const char *data,
    int length
)
{
    int totalSent = 0;


    if (
        socket == INVALID_SOCKET ||
        data == NULL ||
        length < 0
    )
    {
        return FILE_TRANSFER_ERROR;
    }


    while (totalSent < length)
    {
        int sent = send(
            socket,
            data + totalSent,
            length - totalSent,
            0
        );


        if (sent == SOCKET_ERROR)
        {
            return FILE_TRANSFER_ERROR;
        }


        if (sent == 0)
        {
            return FILE_TRANSFER_DISCONNECTED;
        }


        totalSent += sent;
    }


    return totalSent;
}


/* ============================================================
 * FORWARD FILE BYTES
 * ============================================================
 *
 * This is the core of the server-side binary transfer.
 *
 * Example:
 *
 *     fileSize = 10 MB
 *
 * The server repeatedly:
 *
 *     recv(sender)
 *          ↓
 *     send(receiver)
 *
 * until exactly 10 MB has been transferred.
 *
 * No UTF-8 decoding occurs.
 * No string processing occurs.
 * ============================================================
 */

int forwardFileBytes(
    SOCKET senderSocket,
    SOCKET receiverSocket,
    long long fileSize
)
{
    char buffer[
        FILE_TRANSFER_BUFFER_SIZE
    ];


    long long totalReceived = 0;


    if (
        senderSocket == INVALID_SOCKET ||
        receiverSocket == INVALID_SOCKET ||
        fileSize < 0
    )
    {
        return FILE_TRANSFER_ERROR;
    }


    memset(
        buffer,
        0,
        sizeof(buffer)
    );


    while (
        totalReceived < fileSize
    )
    {
        long long remaining =
            fileSize - totalReceived;


        int bytesToReceive =
            FILE_TRANSFER_BUFFER_SIZE;


        if (
            remaining < bytesToReceive
        )
        {
            bytesToReceive =
                (int)remaining;
        }


        int received = recv(
            senderSocket,
            buffer,
            bytesToReceive,
            0
        );


        /* ==================================================
         * SENDER DISCONNECTED
         * ==================================================
         */

        if (received == 0)
        {
            printf(
                "[FILE TRANSFER] "
                "Sender disconnected during transfer.\n"
            );


            return FILE_TRANSFER_DISCONNECTED;
        }


        /* ==================================================
         * RECEIVE ERROR
         * ==================================================
         */

        if (received == SOCKET_ERROR)
        {
            printf(
                "[FILE TRANSFER] "
                "Receive error: %d\n",
                WSAGetLastError()
            );


            return FILE_TRANSFER_ERROR;
        }


        /* ==================================================
         * FORWARD RECEIVED BINARY DATA
         * ==================================================
         */

        int sent = sendAllBytes(
            receiverSocket,
            buffer,
            received
        );


        if (
            sent == FILE_TRANSFER_ERROR
        )
        {
            printf(
                "[FILE TRANSFER] "
                "Failed to forward data.\n"
            );


            return FILE_TRANSFER_ERROR;
        }


        if (
            sent == FILE_TRANSFER_DISCONNECTED
        )
        {
            printf(
                "[FILE TRANSFER] "
                "Receiver disconnected.\n"
            );


            return FILE_TRANSFER_DISCONNECTED;
        }


        totalReceived += received;


        /* ==================================================
         * PROGRESS
         * ==================================================
         *
         * This is server-side progress for debugging.
         *
         * GUI progress will be implemented later.
         * ==================================================
         */

        double progress =
            (
                (double)totalReceived /
                (double)fileSize
            ) * 100.0;


        printf(
            "\r[FILE TRANSFER] "
            "%lld / %lld bytes "
            "(%.1f%%)",
            totalReceived,
            fileSize,
            progress
        );


        fflush(stdout);
    }


    printf(
        "\n[FILE TRANSFER] "
        "Binary data forwarded successfully.\n"
    );


    return FILE_TRANSFER_SUCCESS;
}