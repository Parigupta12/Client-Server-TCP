#include <stdio.h>
#include <string.h>
#include <winsock2.h>
#include <windows.h>

#pragma comment(lib, "ws2_32.lib")

#define PORT 8080
#define BUFFER_SIZE 1024

// --------------------------------------------------
// Receive thread
// --------------------------------------------------

DWORD WINAPI receiveMessages(LPVOID parameter)
{
    SOCKET clientSocket = *(SOCKET *)parameter;

    char buffer[BUFFER_SIZE];

    while (1)
    {
        int bytesReceived = recv(
            clientSocket,
            buffer,
            BUFFER_SIZE - 1,
            0
        );

        if (bytesReceived <= 0)
        {
            printf("\n[INFO] Server disconnected.\n");
            break;
        }

        buffer[bytesReceived] = '\0';

        printf("\n%s\n", buffer);
        printf("[YOU] ");
        fflush(stdout);
    }

    return 0;
}


// --------------------------------------------------
// Main
// --------------------------------------------------

int main()
{
    // --------------------------------------------------
    // 1. Initialize Winsock
    // --------------------------------------------------

    WSADATA wsaData;

    if (WSAStartup(
        MAKEWORD(2, 2),
        &wsaData
    ) != 0)
    {
        printf("WSAStartup failed.\n");

        return 1;
    }

    printf("========================================\n");
    printf("       MULTI-CLIENT TCP CHAT\n");
    printf("========================================\n");


    // --------------------------------------------------
    // 2. Create socket
    // --------------------------------------------------

    SOCKET clientSocket = socket(
        AF_INET,
        SOCK_STREAM,
        0
    );

    if (clientSocket == INVALID_SOCKET)
    {
        printf("Socket creation failed.\n");

        WSACleanup();

        return 1;
    }

    printf("[OK] Client socket created.\n");


    // --------------------------------------------------
    // 3. Configure server address
    // --------------------------------------------------

    struct sockaddr_in serverAddress;

    serverAddress.sin_family = AF_INET;

    serverAddress.sin_port = htons(PORT);

    serverAddress.sin_addr.s_addr =
        inet_addr("127.0.0.1");


    // --------------------------------------------------
    // 4. Connect to server
    // --------------------------------------------------

    printf("[INFO] Connecting to server...\n");

    if (connect(
        clientSocket,
        (struct sockaddr *)&serverAddress,
        sizeof(serverAddress)
    ) == SOCKET_ERROR)
    {
        printf("[ERROR] Connection failed.\n");

        closesocket(clientSocket);

        WSACleanup();

        return 1;
    }

    printf("[CONNECTED] Successfully connected!\n");


    // --------------------------------------------------
    // 5. Create receive thread
    // --------------------------------------------------

    HANDLE receiveThread = CreateThread(
        NULL,
        0,
        receiveMessages,
        &clientSocket,
        0,
        NULL
    );

    if (receiveThread == NULL)
    {
        printf("[ERROR] Could not create receive thread.\n");

        closesocket(clientSocket);

        WSACleanup();

        return 1;
    }


    // --------------------------------------------------
    // 6. Send messages
    // --------------------------------------------------

    char message[BUFFER_SIZE];

    while (1)
    {
        printf("\n[YOU] ");

        if (fgets(
            message,
            sizeof(message),
            stdin
        ) == NULL)
        {
            break;
        }

        // Remove newline
        message[
            strcspn(message, "\n")
        ] = '\0';


        // Ignore empty message
        if (strlen(message) == 0)
        {
            continue;
        }


        // Send message
        int bytesSent = send(
            clientSocket,
            message,
            strlen(message),
            0
        );

        if (bytesSent == SOCKET_ERROR)
        {
            printf("[ERROR] Failed to send message.\n");
            break;
        }


        // Exit
        if (strcmp(message, "exit") == 0)
        {
            printf("[INFO] Leaving chat...\n");
            break;
        }
    }


    // --------------------------------------------------
    // 7. Cleanup
    // --------------------------------------------------

    closesocket(clientSocket);

    WaitForSingleObject(
        receiveThread,
        1000
    );

    CloseHandle(receiveThread);

    WSACleanup();

    printf("[CLIENT] Shutdown complete.\n");

    return 0;
}