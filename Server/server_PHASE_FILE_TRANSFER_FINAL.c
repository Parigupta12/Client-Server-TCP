#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include <winsock2.h>
#include <windows.h>

#include "protocol.h"
#include "file_transfer.h"

#pragma comment(lib, "ws2_32.lib")


/* ==========================================================
   SERVER CONFIGURATION
   ========================================================== */

#define PORT 8080
#define MAX_CLIENTS 10

#define BUFFER_SIZE 4096

/*
 * This buffer is a BYTE buffer, not a string buffer.
 *
 * It allows us to safely preserve:
 *
 * FILE_START...\n
 * + binary file bytes
 * + FILE_END...\n
 *
 * even when TCP combines them into one recv().
 */
#define RECEIVE_BUFFER_SIZE (1024 * 1024)


/* ==========================================================
   CLIENT INFORMATION
   ========================================================== */

typedef struct
{
    SOCKET socket;
    int id;
    int active;

} ClientInfo;


/* ==========================================================
   FILE TRANSFER STATE
   ========================================================== */

typedef struct
{
    int active;

    int transferId;

    int senderId;
    int receiverId;

    SOCKET receiverSocket;

    long long fileSize;
    long long bytesReceived;

    int waitingForEnd;

} FileTransferState;


/* ==========================================================
   GLOBAL CLIENT LIST
   ========================================================== */

ClientInfo clients[MAX_CLIENTS];

CRITICAL_SECTION clientLock;


/* ==========================================================
   SEND ALL
   ========================================================== */

int sendAll(
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
        return -1;
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
            return -1;
        }

        if (sent == 0)
        {
            return -1;
        }

        totalSent += sent;
    }

    return totalSent;
}


/* ==========================================================
   GET ACTIVE CLIENT COUNT
   ========================================================== */

int getActiveClientCount()
{
    int count = 0;

    EnterCriticalSection(&clientLock);

    for (int i = 0; i < MAX_CLIENTS; i++)
    {
        if (clients[i].active)
        {
            count++;
        }
    }

    LeaveCriticalSection(&clientLock);

    return count;
}


/* ==========================================================
   CREATE CLIENT LIST
   ========================================================== */

void createClientList(
    char *list,
    int listSize
)
{
    list[0] = '\0';

    EnterCriticalSection(&clientLock);

    for (int i = 0; i < MAX_CLIENTS; i++)
    {
        if (clients[i].active)
        {
            char idText[20];

            sprintf(
                idText,
                "%d",
                clients[i].id
            );

            if (strlen(list) > 0)
            {
                strncat(
                    list,
                    ",",
                    listSize - (int)strlen(list) - 1
                );
            }

            strncat(
                list,
                idText,
                listSize - (int)strlen(list) - 1
            );
        }
    }

    LeaveCriticalSection(&clientLock);
}


/* ==========================================================
   SEND CLIENT LIST TO ALL CLIENTS
   ========================================================== */

void sendClientList()
{
    char clientList[BUFFER_SIZE];

    char message[BUFFER_SIZE];

    createClientList(
        clientList,
        sizeof(clientList)
    );

    sprintf(
        message,
        "CLIENT_LIST|%s\n",
        clientList
    );

    EnterCriticalSection(&clientLock);

    for (int i = 0; i < MAX_CLIENTS; i++)
    {
        if (clients[i].active)
        {
            sendAll(
                clients[i].socket,
                message,
                (int)strlen(message)
            );
        }
    }

    LeaveCriticalSection(&clientLock);

    printf(
        "[SERVER] Updated client list: %s\n",
        clientList
    );
}


/* ==========================================================
   BROADCAST MESSAGE
   ========================================================== */

void broadcastMessage(
    const char *message,
    SOCKET senderSocket
)
{
    EnterCriticalSection(&clientLock);

    for (int i = 0; i < MAX_CLIENTS; i++)
    {
        if (
            clients[i].active &&
            clients[i].socket != senderSocket
        )
        {
            sendAll(
                clients[i].socket,
                message,
                (int)strlen(message)
            );
        }
    }

    LeaveCriticalSection(&clientLock);
}


/* ==========================================================
   PRIVATE MESSAGE
   ========================================================== */

void privateMessage(
    const char *message,
    int targetID,
    SOCKET senderSocket
)
{
    int found = 0;

    EnterCriticalSection(&clientLock);

    for (int i = 0; i < MAX_CLIENTS; i++)
    {
        if (
            clients[i].active &&
            clients[i].id == targetID
        )
        {
            found = 1;

            if (clients[i].socket != senderSocket)
            {
                sendAll(
                    clients[i].socket,
                    message,
                    (int)strlen(message)
                );
            }

            break;
        }
    }

    LeaveCriticalSection(&clientLock);

    if (!found)
    {
        printf(
            "[ERROR] Client %d not found.\n",
            targetID
        );
    }
}


/* ==========================================================
   FIND CLIENT SOCKET
   ========================================================== */

SOCKET getClientSocket(
    int clientID
)
{
    SOCKET result = INVALID_SOCKET;

    EnterCriticalSection(&clientLock);

    for (int i = 0; i < MAX_CLIENTS; i++)
    {
        if (
            clients[i].active &&
            clients[i].id == clientID
        )
        {
            result = clients[i].socket;
            break;
        }
    }

    LeaveCriticalSection(&clientLock);

    return result;
}


/* ==========================================================
   PROTOCOL BROADCAST
   ========================================================== */

void protocolBroadcast(
    int senderID,
    const char *message
)
{
    char protocolMessage[BUFFER_SIZE];

    SOCKET senderSocket =
        getClientSocket(senderID);

    int result =
        buildBroadcastMessage(
            protocolMessage,
            sizeof(protocolMessage),
            senderID,
            message
        );

    if (result < 0)
    {
        printf(
            "[ERROR] Could not build broadcast protocol message.\n"
        );

        return;
    }

    if (senderSocket == INVALID_SOCKET)
    {
        printf(
            "[ERROR] Sender Client %d not found.\n",
            senderID
        );

        return;
    }

    broadcastMessage(
        protocolMessage,
        senderSocket
    );
}


/* ==========================================================
   PROTOCOL PRIVATE MESSAGE
   ========================================================== */

void protocolPrivate(
    int senderID,
    int targetID,
    const char *message
)
{
    char protocolMessage[BUFFER_SIZE];

    int result =
        buildPrivateMessage(
            protocolMessage,
            sizeof(protocolMessage),
            senderID,
            targetID,
            message
        );

    if (result < 0)
    {
        printf(
            "[ERROR] Could not build private protocol message.\n"
        );

        return;
    }

    SOCKET targetSocket =
        getClientSocket(targetID);

    if (targetSocket == INVALID_SOCKET)
    {
        printf(
            "[ERROR] Client %d not found.\n",
            targetID
        );

        return;
    }

    sendAll(
        targetSocket,
        protocolMessage,
        (int)strlen(protocolMessage)
    );
}


/* ==========================================================
   REMOVE CLIENT
   ========================================================== */

void removeClient(
    SOCKET clientSocket
)
{
    int removed = 0;

    EnterCriticalSection(&clientLock);

    for (int i = 0; i < MAX_CLIENTS; i++)
    {
        if (
            clients[i].active &&
            clients[i].socket == clientSocket
        )
        {
            printf(
                "[SERVER] Removing Client %d.\n",
                clients[i].id
            );

            clients[i].active = 0;

            clients[i].socket =
                INVALID_SOCKET;

            removed = 1;

            break;
        }
    }

    LeaveCriticalSection(&clientLock);

    if (removed)
    {
        printf(
            "[SERVER] Active clients: %d\n",
            getActiveClientCount()
        );

        sendClientList();
    }
}


/* ==========================================================
   SEND FILE ERROR
   ========================================================== */

void sendFileError(
    SOCKET socket,
    int transferId,
    const char *errorMessage
)
{
    char message[BUFFER_SIZE];

    int result =
        buildFileErrorMessage(
            message,
            sizeof(message),
            transferId,
            errorMessage
        );

    if (result < 0)
    {
        return;
    }

    sendAll(
        socket,
        message,
        (int)strlen(message)
    );
}


/* ==========================================================
   PROCESS NORMAL TEXT MESSAGE
   ========================================================== */

void processClientMessage(
    int clientID,
    SOCKET clientSocket,
    char *buffer
)
{
    if (
        buffer == NULL ||
        buffer[0] == '\0'
    )
    {
        return;
    }

    printf(
        "[CLIENT %d] %s\n",
        clientID,
        buffer
    );


    /* ======================================================
       EXIT
       ====================================================== */

    if (
        strcmp(
            buffer,
            "exit"
        ) == 0
    )
    {
        printf(
            "[CLIENT %d] Chat ended.\n",
            clientID
        );

        return;
    }


    /* ======================================================
       BROADCAST
       ====================================================== */

    if (
        strncmp(
            buffer,
            "TEXT|BROADCAST|",
            15
        ) == 0
    )
    {
        int senderID;

        char broadcastText[BUFFER_SIZE];

        memset(
            broadcastText,
            0,
            sizeof(broadcastText)
        );

        int result =
            sscanf(
                buffer,
                "TEXT|BROADCAST|%d|%[^\n]",
                &senderID,
                broadcastText
            );

        if (
            result == 2 &&
            senderID == clientID
        )
        {
            printf(
                "[PROTOCOL BROADCAST] "
                "Client %d: %s\n",
                clientID,
                broadcastText
            );

            protocolBroadcast(
                clientID,
                broadcastText
            );

            return;
        }

        char errorMessage[] =
            "SYSTEM|ERROR|Invalid broadcast message.\n";

        sendAll(
            clientSocket,
            errorMessage,
            (int)strlen(errorMessage)
        );

        return;
    }


    /* ======================================================
       PRIVATE MESSAGE
       ====================================================== */

    if (
        strncmp(
            buffer,
            "TEXT|PRIVATE|",
            13
        ) == 0
    )
    {
        int senderID;

        int targetID;

        char privateText[BUFFER_SIZE];

        memset(
            privateText,
            0,
            sizeof(privateText)
        );

        int result =
            sscanf(
                buffer,
                "TEXT|PRIVATE|%d|%d|%[^\n]",
                &senderID,
                &targetID,
                privateText
            );

        if (
            result == 3 &&
            senderID == clientID
        )
        {
            printf(
                "[PROTOCOL PRIVATE] "
                "Client %d -> Client %d: %s\n",
                clientID,
                targetID,
                privateText
            );

            protocolPrivate(
                clientID,
                targetID,
                privateText
            );

            return;
        }

        char errorMessage[] =
            "SYSTEM|ERROR|Invalid private message.\n";

        sendAll(
            clientSocket,
            errorMessage,
            (int)strlen(errorMessage)
        );

        return;
    }


    /* ======================================================
       LEGACY PRIVATE
       ====================================================== */

    if (
        strncmp(
            buffer,
            "/private ",
            9
        ) == 0
    )
    {
        int targetID;

        char privateText[BUFFER_SIZE];

        memset(
            privateText,
            0,
            sizeof(privateText)
        );

        int result =
            sscanf(
                buffer + 9,
                "%d %[^\n]",
                &targetID,
                privateText
            );

        if (result == 2)
        {
            char privateMessageText[
                BUFFER_SIZE + 100
            ];

            sprintf(
                privateMessageText,
                "[Private from Client %d] %s\n",
                clientID,
                privateText
            );

            privateMessage(
                privateMessageText,
                targetID,
                clientSocket
            );

            printf(
                "[PRIVATE] "
                "Client %d -> Client %d: %s\n",
                clientID,
                targetID,
                privateText
            );
        }
        else
        {
            char errorMessage[] =
                "[SERVER] Invalid private message format.\n"
                "Use: /private <clientID> <message>\n";

            sendAll(
                clientSocket,
                errorMessage,
                (int)strlen(errorMessage)
            );
        }

        return;
    }


    /* ======================================================
       LEGACY BROADCAST
       ====================================================== */

    if (
        strncmp(
            buffer,
            "/broadcast ",
            11
        ) == 0
    )
    {
        char broadcastText[
            BUFFER_SIZE
        ];

        sprintf(
            broadcastText,
            "[Broadcast from Client %d] %s\n",
            clientID,
            buffer + 11
        );

        broadcastMessage(
            broadcastText,
            clientSocket
        );

        printf(
            "[BROADCAST] "
            "Client %d: %s\n",
            clientID,
            buffer + 11
        );

        return;
    }


    /* ======================================================
       UNKNOWN COMMAND
       ====================================================== */

    char helpMessage[] =
        "SYSTEM|HELP|Use:\n"
        "/private <clientID> <message>\n"
        "/broadcast <message>\n"
        "exit\n";

    sendAll(
        clientSocket,
        helpMessage,
        (int)strlen(helpMessage)
    );
}


/* ==========================================================
   PARSE FILE_START HEADER
   ========================================================== */

int parseFileStart(
    const char *message,
    int *transferId,
    int *senderId,
    int *receiverId,
    long long *fileSize,
    char *encodedFilename,
    int filenameSize
)
{
    if (
        message == NULL ||
        transferId == NULL ||
        senderId == NULL ||
        receiverId == NULL ||
        fileSize == NULL ||
        encodedFilename == NULL
    )
    {
        return -1;
    }

    encodedFilename[0] = '\0';

    int result =
        sscanf(
            message,
            "FILE_START|%d|%d|%d|%lld|%511[^\n]",
            transferId,
            senderId,
            receiverId,
            fileSize,
            encodedFilename
        );

    if (result != 5)
    {
        return -1;
    }

    if (*transferId < 0)
    {
        return -1;
    }

    if (*senderId < 1)
    {
        return -1;
    }

    if (*receiverId < 1)
    {
        return -1;
    }

    if (*fileSize < 0)
    {
        return -1;
    }

    encodedFilename[
        filenameSize - 1
    ] = '\0';

    return 0;
}


/* ==========================================================
   PARSE FILE_END
   ========================================================== */

int parseFileEnd(
    const char *message,
    int expectedTransferId
)
{
    int transferId;

    if (message == NULL)
    {
        return -1;
    }

    int result =
        sscanf(
            message,
            "FILE_END|%d",
            &transferId
        );

    if (
        result != 1 ||
        transferId != expectedTransferId
    )
    {
        return -1;
    }

    return 0;
}


/* ==========================================================
   SEND FILE START TO RECEIVER
   ========================================================== */

int sendFileStartToReceiver(
    FileTransferState *transfer,
    const char *encodedFilename
)
{
    if (
        transfer == NULL ||
        encodedFilename == NULL
    )
    {
        return -1;
    }

    if (
        transfer->receiverSocket ==
        INVALID_SOCKET
    )
    {
        return -1;
    }

    char message[BUFFER_SIZE];

    int result =
        buildFileStartMessage(
            message,
            sizeof(message),
            transfer->transferId,
            transfer->senderId,
            transfer->receiverId,
            transfer->fileSize,
            encodedFilename
        );

    if (result < 0)
    {
        return -1;
    }

    return sendAll(
        transfer->receiverSocket,
        message,
        (int)strlen(message)
    );
}


/* ==========================================================
   SEND FILE END TO RECEIVER
   ========================================================== */

int sendFileEndToReceiver(
    FileTransferState *transfer
)
{
    if (
        transfer == NULL ||
        transfer->receiverSocket ==
            INVALID_SOCKET
    )
    {
        return -1;
    }

    char message[BUFFER_SIZE];

    int result =
        buildFileEndMessage(
            message,
            sizeof(message),
            transfer->transferId
        );

    if (result < 0)
    {
        return -1;
    }

    return sendAll(
        transfer->receiverSocket,
        message,
        (int)strlen(message)
    );
}


/* ==========================================================
   HANDLE FILE_START
   ========================================================== */

int startFileTransfer(
    FileTransferState *transfer,
    int clientID,
    SOCKET clientSocket,
    const char *message
)
{
    int transferId;
    int senderId;
    int receiverId;

    long long fileSize;

    char encodedFilename[512];

    if (
        parseFileStart(
            message,
            &transferId,
            &senderId,
            &receiverId,
            &fileSize,
            encodedFilename,
            sizeof(encodedFilename)
        ) < 0
    )
    {
        printf(
            "[FILE] Invalid FILE_START from Client %d.\n",
            clientID
        );

        sendFileError(
            clientSocket,
            0,
            "Invalid FILE_START message"
        );

        return -1;
    }


    /* ======================================================
       VERIFY SENDER
       ====================================================== */

    if (senderId != clientID)
    {
        printf(
            "[FILE] Sender ID mismatch.\n"
        );

        sendFileError(
            clientSocket,
            transferId,
            "Sender ID mismatch"
        );

        return -1;
    }


    /* ======================================================
       PREVENT SENDING TO SELF
       ====================================================== */

    if (receiverId == clientID)
    {
        sendFileError(
            clientSocket,
            transferId,
            "Cannot send a file to yourself"
        );

        return -1;
    }


    /* ======================================================
       FIND RECEIVER
       ====================================================== */

    SOCKET receiverSocket =
        getClientSocket(receiverId);

    if (
        receiverSocket == INVALID_SOCKET
    )
    {
        printf(
            "[FILE] Receiver Client %d not found.\n",
            receiverId
        );

        sendFileError(
            clientSocket,
            transferId,
            "Receiver client not found"
        );

        return -1;
    }


    /* ======================================================
       STORE TRANSFER STATE
       ====================================================== */

    memset(
        transfer,
        0,
        sizeof(FileTransferState)
    );

    transfer->active = 1;

    transfer->transferId =
        transferId;

    transfer->senderId =
        senderId;

    transfer->receiverId =
        receiverId;

    transfer->receiverSocket =
        receiverSocket;

    transfer->fileSize =
        fileSize;

    transfer->bytesReceived =
        0;

    transfer->waitingForEnd = 0;


    /* ======================================================
       SEND FILE_START TO RECEIVER
       ====================================================== */

    if (
        sendFileStartToReceiver(
            transfer,
            encodedFilename
        ) < 0
    )
    {
        printf(
            "[FILE] Could not send FILE_START "
            "to Client %d.\n",
            receiverId
        );

        sendFileError(
            clientSocket,
            transferId,
            "Could not contact receiver"
        );

        transfer->active = 0;

        return -1;
    }


    printf(
        "\n[FILE TRANSFER START]\n"
        "  Transfer ID : %d\n"
        "  Sender      : Client %d\n"
        "  Receiver    : Client %d\n"
        "  File Size   : %lld bytes\n"
        "  Filename    : %s\n",
        transferId,
        senderId,
        receiverId,
        fileSize,
        encodedFilename
    );

    return 0;
}


/* ==========================================================
   HANDLE FILE DATA
   ========================================================== */

int processFileData(
    FileTransferState *transfer,
    SOCKET senderSocket,
    const char *data,
    int dataLength
)
{
    if (
        transfer == NULL ||
        data == NULL ||
        dataLength <= 0
    )
    {
        return 0;
    }

    if (!transfer->active)
    {
        return -1;
    }


    /* ======================================================
       CALCULATE EXACT NUMBER OF FILE BYTES
       ====================================================== */

    long long remaining =
        transfer->fileSize -
        transfer->bytesReceived;

    int bytesToForward =
        dataLength;

    if (
        remaining < bytesToForward
    )
    {
        bytesToForward =
            (int)remaining;
    }


    /* ======================================================
       FORWARD RAW BINARY DATA
       ====================================================== */

    if (bytesToForward > 0)
    {
        int sent =
            sendAllBytes(
                transfer->receiverSocket,
                data,
                bytesToForward
            );

        if (
            sent < 0 ||
            sent != bytesToForward
        )
        {
            printf(
                "\n[FILE] Failed to forward "
                "binary data to Client %d.\n",
                transfer->receiverId
            );

            sendFileError(
                senderSocket,
                transfer->transferId,
                "Failed to forward file data"
            );

            transfer->active = 0;

            return -1;
        }

        transfer->bytesReceived +=
            bytesToForward;


        /* ==================================================
           PROGRESS
           ================================================== */

        if (transfer->fileSize > 0)
        {
            double progress =
                (
                    (double)
                    transfer->bytesReceived
                    /
                    (double)
                    transfer->fileSize
                ) * 100.0;

            printf(
                "\r[FILE TRANSFER] "
                "Client %d -> Client %d : "
                "%lld / %lld bytes (%.1f%%)",
                transfer->senderId,
                transfer->receiverId,
                transfer->bytesReceived,
                transfer->fileSize,
                progress
            );

            fflush(stdout);
        }
    }


    /* ======================================================
       FILE DATA COMPLETE
       ====================================================== */

    if (
        transfer->bytesReceived >=
        transfer->fileSize
    )
    {
        printf(
            "\n[FILE TRANSFER] "
            "All binary data received.\n"
        );

        transfer->waitingForEnd = 1;
    }

    return bytesToForward;
}


/* ==========================================================
   HANDLE CLIENT THREAD
   ========================================================== */

DWORD WINAPI handleClient(
    LPVOID parameter
)
{
    ClientInfo *client =
        (ClientInfo *)parameter;

    SOCKET clientSocket =
        client->socket;

    int clientID =
        client->id;


    /* ======================================================
       BYTE RECEIVE BUFFER
       ====================================================== */

    unsigned char receiveBuffer[
        RECEIVE_BUFFER_SIZE
    ];

    int receiveLength = 0;


    /* ======================================================
       FILE TRANSFER STATE
       ====================================================== */

    FileTransferState transfer;

    memset(
        &transfer,
        0,
        sizeof(FileTransferState)
    );

    transfer.receiverSocket =
        INVALID_SOCKET;


    printf(
        "\n[CLIENT %d] Connected.\n",
        clientID
    );


    /* ======================================================
       SEND CLIENT INFORMATION
       ====================================================== */

    char clientList[BUFFER_SIZE];

    char clientInfoMessage[BUFFER_SIZE];

    createClientList(
        clientList,
        sizeof(clientList)
    );

    sprintf(
        clientInfoMessage,
        "CLIENT_INFO|%d|%s\n",
        clientID,
        clientList
    );

    sendAll(
        clientSocket,
        clientInfoMessage,
        (int)strlen(clientInfoMessage)
    );


    /* ======================================================
       RECEIVE LOOP
       ====================================================== */

    while (1)
    {
        unsigned char tempBuffer[
            BUFFER_SIZE
        ];

        int bytesReceived =
            recv(
                clientSocket,
                (char *)tempBuffer,
                sizeof(tempBuffer),
                0
            );


        /* ==================================================
           DISCONNECTED
           ================================================== */

        if (bytesReceived <= 0)
        {
            printf(
                "[CLIENT %d] Disconnected.\n",
                clientID
            );

            break;
        }


        /* ==================================================
           BUFFER OVERFLOW PROTECTION
           ================================================== */

        if (
            receiveLength +
            bytesReceived >
            RECEIVE_BUFFER_SIZE
        )
        {
            printf(
                "[ERROR] Receive buffer overflow "
                "for Client %d.\n",
                clientID
            );

            char errorMessage[] =
                "SYSTEM|ERROR|Receive buffer overflow.\n";

            sendAll(
                clientSocket,
                errorMessage,
                (int)strlen(errorMessage)
            );

            break;
        }


        /* ==================================================
           APPEND RAW BYTES
           ================================================== */

        memcpy(
            receiveBuffer + receiveLength,
            tempBuffer,
            bytesReceived
        );

        receiveLength +=
            bytesReceived;


        /* ==================================================
           PROCESS BUFFER
           ================================================== */

        while (receiveLength > 0)
        {
            /* ==================================================
               ACTIVE FILE TRANSFER
               ================================================== */

            if (transfer.active)
            {
                /*
                 * We are currently receiving raw binary
                 * file data.
                 */

                if (
                    !transfer.waitingForEnd
                )
                {
                    long long remaining =
                        transfer.fileSize -
                        transfer.bytesReceived;

                    if (remaining > 0)
                    {
                        int bytesToProcess =
                            receiveLength;

                        if (
                            remaining <
                            bytesToProcess
                        )
                        {
                            bytesToProcess =
                                (int)remaining;
                        }

                        int processed =
                            processFileData(
                                &transfer,
                                clientSocket,
                                (const char *)
                                    receiveBuffer,
                                bytesToProcess
                            );

                        if (processed < 0)
                        {
                            transfer.active = 0;

                            receiveLength = 0;

                            break;
                        }

                        if (processed > 0)
                        {
                            int remainingBuffer =
                                receiveLength -
                                processed;

                            if (
                                remainingBuffer > 0
                            )
                            {
                                memmove(
                                    receiveBuffer,
                                    receiveBuffer +
                                        processed,
                                    remainingBuffer
                                );
                            }

                            receiveLength =
                                remainingBuffer;

                            continue;
                        }
                    }

                    /*
                     * File bytes are complete.
                     * Wait for FILE_END.
                     */

                    transfer.waitingForEnd = 1;
                }


                /* ==================================================
                   WAIT FOR FILE_END
                   ================================================== */

                if (
                    transfer.waitingForEnd
                )
                {
                    unsigned char *newlinePosition =
                        memchr(
                            receiveBuffer,
                            '\n',
                            receiveLength
                        );

                    if (
                        newlinePosition == NULL
                    )
                    {
                        /*
                         * FILE_END header has not
                         * completely arrived yet.
                         */

                        break;
                    }


                    int messageLength =
                        (int)(
                            newlinePosition -
                            receiveBuffer
                        );


                    if (
                        messageLength >=
                        BUFFER_SIZE
                    )
                    {
                        printf(
                            "[FILE] Invalid FILE_END "
                            "message.\n"
                        );

                        transfer.active = 0;

                        receiveLength = 0;

                        break;
                    }


                    char endMessage[
                        BUFFER_SIZE
                    ];

                    memcpy(
                        endMessage,
                        receiveBuffer,
                        messageLength
                    );

                    endMessage[
                        messageLength
                    ] = '\0';


                    /*
                     * Remove CR if CRLF is used.
                     */

                    if (
                        messageLength > 0 &&
                        endMessage[
                            messageLength - 1
                        ] == '\r'
                    )
                    {
                        endMessage[
                            messageLength - 1
                        ] = '\0';
                    }


                    /* ==================================================
                       VALIDATE FILE_END
                       ================================================== */

                    if (
                        parseFileEnd(
                            endMessage,
                            transfer.transferId
                        ) == 0
                    )
                    {
                        printf(
                            "[FILE TRANSFER COMPLETE]\n"
                            "  Transfer ID : %d\n"
                            "  Client %d -> Client %d\n"
                            "  Total Bytes : %lld\n",
                            transfer.transferId,
                            transfer.senderId,
                            transfer.receiverId,
                            transfer.bytesReceived
                        );


                        /*
                         * Send FILE_END to receiver.
                         */

                        if (
                            sendFileEndToReceiver(
                                &transfer
                            ) < 0
                        )
                        {
                            printf(
                                "[FILE] Failed to send "
                                "FILE_END to receiver.\n"
                            );
                        }
                    }
                    else
                    {
                        printf(
                            "[FILE] Invalid FILE_END "
                            "for Transfer %d.\n",
                            transfer.transferId
                        );

                        sendFileError(
                            clientSocket,
                            transfer.transferId,
                            "Invalid FILE_END"
                        );
                    }


                    /*
                     * Remove FILE_END from buffer.
                     */

                    int remainingBuffer =
                        receiveLength -
                        (messageLength + 1);

                    if (
                        remainingBuffer > 0
                    )
                    {
                        memmove(
                            receiveBuffer,
                            newlinePosition + 1,
                            remainingBuffer
                        );
                    }

                    receiveLength =
                        remainingBuffer;


                    /*
                     * Reset transfer state.
                     */

                    memset(
                        &transfer,
                        0,
                        sizeof(FileTransferState)
                    );

                    transfer.receiverSocket =
                        INVALID_SOCKET;

                    continue;
                }
            }


            /* ==================================================
               NORMAL TEXT / CONTROL MODE
               ================================================== */

            unsigned char *newlinePosition =
                memchr(
                    receiveBuffer,
                    '\n',
                    receiveLength
                );


            /*
             * No complete line yet.
             */

            if (
                newlinePosition == NULL
            )
            {
                break;
            }


            int messageLength =
                (int)(
                    newlinePosition -
                    receiveBuffer
                );


            /* ==================================================
               MESSAGE TOO LARGE
               ================================================== */

            if (
                messageLength >= BUFFER_SIZE
            )
            {
                printf(
                    "[ERROR] Message from Client %d "
                    "is too large.\n",
                    clientID
                );

                char errorMessage[] =
                    "SYSTEM|ERROR|Message too large.\n";

                sendAll(
                    clientSocket,
                    errorMessage,
                    (int)strlen(errorMessage)
                );


                int remainingBuffer =
                    receiveLength -
                    (messageLength + 1);

                if (
                    remainingBuffer > 0
                )
                {
                    memmove(
                        receiveBuffer,
                        newlinePosition + 1,
                        remainingBuffer
                    );
                }

                receiveLength =
                    remainingBuffer;

                continue;
            }


            /* ==================================================
               COPY MESSAGE
               ================================================== */

            char message[
                BUFFER_SIZE
            ];

            memcpy(
                message,
                receiveBuffer,
                messageLength
            );

            message[
                messageLength
            ] = '\0';


            /* ==================================================
               REMOVE CR
               ================================================== */

            if (
                messageLength > 0 &&
                message[
                    messageLength - 1
                ] == '\r'
            )
            {
                message[
                    messageLength - 1
                ] = '\0';
            }


            /* ==================================================
               REMOVE MESSAGE FROM BUFFER
               ================================================== */

            int remainingBuffer =
                receiveLength -
                (messageLength + 1);

            if (
                remainingBuffer > 0
            )
            {
                memmove(
                    receiveBuffer,
                    newlinePosition + 1,
                    remainingBuffer
                );
            }

            receiveLength =
                remainingBuffer;


            /* ==================================================
               FILE_START
               ================================================== */

            if (
                strncmp(
                    message,
                    "FILE_START|",
                    11
                ) == 0
            )
            {
                /*
                 * A new file transfer begins.
                 *
                 * Important:
                 *
                 * Any bytes already following FILE_START
                 * remain inside receiveBuffer.
                 *
                 * Therefore the next loop iteration will
                 * process those bytes as RAW BINARY data.
                 */

                if (
                    transfer.active
                )
                {
                    printf(
                        "[FILE] Another transfer is "
                        "already active.\n"
                    );

                    sendFileError(
                        clientSocket,
                        0,
                        "Another file transfer is active"
                    );

                    continue;
                }


                startFileTransfer(
                    &transfer,
                    clientID,
                    clientSocket,
                    message
                );

                continue;
            }


            /* ==================================================
               FILE_END WITHOUT ACTIVE TRANSFER
               ================================================== */

            if (
                strncmp(
                    message,
                    "FILE_END|",
                    9
                ) == 0
            )
            {
                printf(
                    "[FILE] Unexpected FILE_END "
                    "from Client %d.\n",
                    clientID
                );

                continue;
            }


            /* ==================================================
               NORMAL APPLICATION MESSAGE
               ================================================== */

            processClientMessage(
                clientID,
                clientSocket,
                message
            );
        }
    }


    /* ==========================================================
       CLOSE CLIENT
       ========================================================== */

    closesocket(
        clientSocket
    );

    removeClient(
        clientSocket
    );

    return 0;
}


/* ==========================================================
   MAIN
   ========================================================== */

int main()
{
    /* ======================================================
       INITIALIZE WINSOCK
       ====================================================== */

    WSADATA wsaData;

    if (
        WSAStartup(
            MAKEWORD(2, 2),
            &wsaData
        ) != 0
    )
    {
        printf(
            "[ERROR] WSAStartup failed.\n"
        );

        return 1;
    }


    printf(
        "========================================\n"
    );

    printf(
        "       MULTI-CLIENT TCP SERVER\n"
    );

    printf(
        "========================================\n"
    );


    /* ======================================================
       INITIALIZE CLIENT ARRAY
       ====================================================== */

    for (int i = 0; i < MAX_CLIENTS; i++)
    {
        clients[i].socket =
            INVALID_SOCKET;

        clients[i].id =
            0;

        clients[i].active =
            0;
    }


    /* ======================================================
       INITIALIZE LOCK
       ====================================================== */

    InitializeCriticalSection(
        &clientLock
    );


    /* ======================================================
       CREATE SERVER SOCKET
       ====================================================== */

    SOCKET serverSocket =
        socket(
            AF_INET,
            SOCK_STREAM,
            0
        );

    if (
        serverSocket ==
        INVALID_SOCKET
    )
    {
        printf(
            "[ERROR] Socket creation failed.\n"
        );

        DeleteCriticalSection(
            &clientLock
        );

        WSACleanup();

        return 1;
    }


    printf(
        "[OK] Server socket created.\n"
    );


    /* ======================================================
       SERVER ADDRESS
       ====================================================== */

    struct sockaddr_in serverAddress;

    serverAddress.sin_family =
        AF_INET;

    serverAddress.sin_addr.s_addr =
        INADDR_ANY;

    serverAddress.sin_port =
        htons(PORT);


    /* ======================================================
       BIND
       ====================================================== */

    if (
        bind(
            serverSocket,
            (struct sockaddr *)&serverAddress,
            sizeof(serverAddress)
        ) == SOCKET_ERROR
    )
    {
        printf(
            "[ERROR] Bind failed.\n"
        );

        closesocket(
            serverSocket
        );

        DeleteCriticalSection(
            &clientLock
        );

        WSACleanup();

        return 1;
    }


    printf(
        "[OK] Server bound to port %d.\n",
        PORT
    );


    /* ======================================================
       LISTEN
       ====================================================== */

    if (
        listen(
            serverSocket,
            MAX_CLIENTS
        ) == SOCKET_ERROR
    )
    {
        printf(
            "[ERROR] Listen failed.\n"
        );

        closesocket(
            serverSocket
        );

        DeleteCriticalSection(
            &clientLock
        );

        WSACleanup();

        return 1;
    }


    printf(
        "[OK] Server is listening.\n"
    );

    printf(
        "----------------------------------------\n"
    );

    printf(
        "Server IP   : 127.0.0.1\n"
    );

    printf(
        "Server Port : %d\n",
        PORT
    );

    printf(
        "----------------------------------------\n"
    );

    printf(
        "Maximum Clients : %d\n",
        MAX_CLIENTS
    );

    printf(
        "----------------------------------------\n"
    );


    /* ======================================================
       ACCEPT CLIENTS
       ====================================================== */

    while (1)
    {
        SOCKET clientSocket =
            accept(
                serverSocket,
                NULL,
                NULL
            );

        if (
            clientSocket ==
            INVALID_SOCKET
        )
        {
            printf(
                "[ERROR] Accept failed.\n"
            );

            continue;
        }


        /* ==================================================
           FIND FREE SLOT
           ================================================== */

        int slot = -1;

        EnterCriticalSection(
            &clientLock
        );

        for (int i = 0; i < MAX_CLIENTS; i++)
        {
            if (!clients[i].active)
            {
                slot = i;

                break;
            }
        }


        /* ==================================================
           SERVER FULL
           ================================================== */

        if (slot == -1)
        {
            LeaveCriticalSection(
                &clientLock
            );

            char fullMessage[] =
                "SYSTEM|ERROR|Server is full. Try again later.\n";

            sendAll(
                clientSocket,
                fullMessage,
                (int)strlen(fullMessage)
            );

            closesocket(
                clientSocket
            );

            continue;
        }


        /* ==================================================
           ASSIGN CLIENT
           ================================================== */

        clients[slot].socket =
            clientSocket;

        clients[slot].id =
            slot + 1;

        clients[slot].active =
            1;

        int assignedID =
            clients[slot].id;

        LeaveCriticalSection(
            &clientLock
        );


        printf(
            "\n[NEW CLIENT] Client %d connected.\n",
            assignedID
        );

        printf(
            "[SERVER] Active clients: %d\n",
            getActiveClientCount()
        );


        /* ==================================================
           CREATE CLIENT THREAD
           ================================================== */

        HANDLE thread =
            CreateThread(
                NULL,
                0,
                handleClient,
                &clients[slot],
                0,
                NULL
            );

        if (thread == NULL)
        {
            printf(
                "[ERROR] Could not create client thread.\n"
            );

            closesocket(
                clientSocket
            );

            removeClient(
                clientSocket
            );

            continue;
        }


        CloseHandle(
            thread
        );


        /* ==================================================
           UPDATE CLIENT LIST
           ================================================== */

        sendClientList();
    }


    /* ======================================================
       CLEANUP
       ====================================================== */

    closesocket(
        serverSocket
    );

    DeleteCriticalSection(
        &clientLock
    );

    WSACleanup();

    return 0;
}