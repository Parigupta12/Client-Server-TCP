#include <stdio.h>
#include <string.h>
#include <winsock2.h>
#include <windows.h>

#include "file_transfer.h"


#pragma comment(lib, "ws2_32.lib")


int main()
{
    WSADATA wsaData;


    printf(
        "========================================\n"
    );

    printf(
        "       BINARY TRANSFER ENGINE TEST\n"
    );

    printf(
        "========================================\n\n"
    );


    /* ======================================================
     * WINSOCK INITIALIZATION
     * ======================================================
     */

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
        "[OK] Winsock initialized.\n"
    );


    /* ======================================================
     * TEST sendAllBytes
     * ======================================================
     *
     * This test uses a pair of connected sockets.
     *
     * On Windows we create a local TCP connection.
     * ======================================================
     */

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
            "[ERROR] Could not create server socket.\n"
        );

        WSACleanup();

        return 1;
    }


    struct sockaddr_in address;


    address.sin_family =
        AF_INET;

    address.sin_addr.s_addr =
        inet_addr("127.0.0.1");

    address.sin_port =
        htons(9090);


    if (
        bind(
            serverSocket,
            (struct sockaddr *)&address,
            sizeof(address)
        ) == SOCKET_ERROR
    )
    {
        printf(
            "[ERROR] Bind failed.\n"
        );

        closesocket(
            serverSocket
        );

        WSACleanup();

        return 1;
    }


    if (
        listen(
            serverSocket,
            1
        ) == SOCKET_ERROR
    )
    {
        printf(
            "[ERROR] Listen failed.\n"
        );

        closesocket(
            serverSocket
        );

        WSACleanup();

        return 1;
    }


    printf(
        "[OK] Local test server listening.\n"
    );


    /* ======================================================
     * CREATE CLIENT SOCKET
     * ======================================================
     */

    SOCKET clientSocket =
        socket(
            AF_INET,
            SOCK_STREAM,
            0
        );


    if (
        clientSocket ==
        INVALID_SOCKET
    )
    {
        printf(
            "[ERROR] Client socket creation failed.\n"
        );

        closesocket(
            serverSocket
        );

        WSACleanup();

        return 1;
    }


    if (
        connect(
            clientSocket,
            (struct sockaddr *)&address,
            sizeof(address)
        ) == SOCKET_ERROR
    )
    {
        printf(
            "[ERROR] Test connection failed.\n"
        );

        closesocket(
            clientSocket
        );

        closesocket(
            serverSocket
        );

        WSACleanup();

        return 1;
    }


    SOCKET acceptedSocket =
        accept(
            serverSocket,
            NULL,
            NULL
        );


    if (
        acceptedSocket ==
        INVALID_SOCKET
    )
    {
        printf(
            "[ERROR] Accept failed.\n"
        );

        closesocket(
            clientSocket
        );

        closesocket(
            serverSocket
        );

        WSACleanup();

        return 1;
    }


    printf(
        "[OK] Local sockets connected.\n\n"
    );


    /* ======================================================
     * TEST sendAllBytes
     * ======================================================
     */

    printf(
        "[TEST 1] sendAllBytes\n"
    );


    unsigned char testData[] =
    {
        0x00,
        0x25,
        0x50,
        0x44,
        0x46,
        0x00,
        0xFF,
        0x7F,
        0x10,
        0x20
    };


    int testLength =
        sizeof(testData);


    int sent = sendAllBytes(
        clientSocket,
        (const char *)testData,
        testLength
    );


    if (
        sent != testLength
    )
    {
        printf(
            "Result: FAILED\n"
        );

        printf(
            "Expected: %d\n",
            testLength
        );

        printf(
            "Sent: %d\n\n",
            sent
        );
    }
    else
    {
        printf(
            "Result: PASSED\n"
        );

        printf(
            "Bytes sent: %d\n\n",
            sent
        );
    }


    /* ======================================================
     * RECEIVE TEST DATA
     * ======================================================
     */

    unsigned char receivedData[
        sizeof(testData)
    ];


    int received =
        recv(
            acceptedSocket,
            (char *)receivedData,
            sizeof(receivedData),
            0
        );


    printf(
        "[TEST 2] Binary data integrity\n"
    );


    if (
        received != testLength
    )
    {
        printf(
            "Result: FAILED\n"
        );

        printf(
            "Expected: %d bytes\n",
            testLength
        );

        printf(
            "Received: %d bytes\n\n",
            received
        );
    }
    else
    {
        int match = 1;


        for (
            int i = 0;
            i < testLength;
            i++
        )
        {
            if (
                receivedData[i] !=
                testData[i]
            )
            {
                match = 0;

                break;
            }
        }


        if (match)
        {
            printf(
                "Result: PASSED\n"
            );

            printf(
                "All binary bytes match.\n\n"
            );
        }
        else
        {
            printf(
                "Result: FAILED\n"
            );

            printf(
                "Binary data mismatch.\n\n"
            );
        }
    }


    /* ======================================================
     * CLEANUP
     * ======================================================
     */

    closesocket(
        acceptedSocket
    );

    closesocket(
        clientSocket
    );

    closesocket(
        serverSocket
    );


    WSACleanup();


    printf(
        "========================================\n"
    );

    printf(
        "          TEST COMPLETED\n"
    );

    printf(
        "========================================\n"
    );


    return 0;
}