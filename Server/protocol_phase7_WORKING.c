#include <stdio.h>
#include <string.h>

#include "protocol.h"


/* ============================================================
 * BUILD BROADCAST MESSAGE
 * ============================================================
 */

int buildBroadcastMessage(
    char *buffer,
    int bufferSize,
    int senderId,
    const char *message
)
{
    int result;


    if (
        buffer == NULL ||
        message == NULL ||
        bufferSize <= 0
    )
    {
        return -1;
    }


    result = snprintf(
        buffer,
        bufferSize,
        "%s|%s|%d|%s\n",
        MSG_TEXT,
        MODE_BROADCAST,
        senderId,
        message
    );


    /*
     * snprintf returns the number of characters that
     * would have been written, excluding '\0'.
     *
     * If that value is >= bufferSize, the message
     * was truncated.
     */

    if (result < 0)
    {
        return -1;
    }


    if (result >= bufferSize)
    {
        return -1;
    }


    return result;
}


/* ============================================================
 * BUILD PRIVATE MESSAGE
 * ============================================================
 */

int buildPrivateMessage(
    char *buffer,
    int bufferSize,
    int senderId,
    int receiverId,
    const char *message
)
{
    int result;


    if (
        buffer == NULL ||
        message == NULL ||
        bufferSize <= 0
    )
    {
        return -1;
    }


    result = snprintf(
        buffer,
        bufferSize,
        "%s|%s|%d|%d|%s\n",
        MSG_TEXT,
        MODE_PRIVATE,
        senderId,
        receiverId,
        message
    );


    if (result < 0)
    {
        return -1;
    }


    if (result >= bufferSize)
    {
        return -1;
    }


    return result;
}


/* ============================================================
 * BUILD FILE START MESSAGE
 * ============================================================
 *
 * Format:
 *
 * FILE_START|transferId|senderId|receiverId|fileSize|filename
 *
 * Example:
 *
 * FILE_START|101|1|2|5242880|cmVwb3J0LnBkZg==
 *
 * NOTE:
 *
 * The filename is already encoded before it reaches
 * this function.
 *
 * The actual file bytes are NOT handled here.
 * ============================================================
 */

int buildFileStartMessage(
    char *buffer,
    int bufferSize,
    int transferId,
    int senderId,
    int receiverId,
    long long fileSize,
    const char *encodedFilename
)
{
    int result;


    if (
        buffer == NULL ||
        encodedFilename == NULL ||
        bufferSize <= 0
    )
    {
        return -1;
    }


    if (fileSize < 0)
    {
        return -1;
    }


    result = snprintf(
        buffer,
        bufferSize,
        "%s|%d|%d|%d|%lld|%s\n",
        MSG_FILE_START,
        transferId,
        senderId,
        receiverId,
        fileSize,
        encodedFilename
    );


    if (result < 0)
    {
        return -1;
    }


    if (result >= bufferSize)
    {
        return -1;
    }


    return result;
}


/* ============================================================
 * BUILD FILE END MESSAGE
 * ============================================================
 */

int buildFileEndMessage(
    char *buffer,
    int bufferSize,
    int transferId
)
{
    int result;


    if (
        buffer == NULL ||
        bufferSize <= 0
    )
    {
        return -1;
    }


    result = snprintf(
        buffer,
        bufferSize,
        "%s|%d\n",
        MSG_FILE_END,
        transferId
    );


    if (result < 0)
    {
        return -1;
    }


    if (result >= bufferSize)
    {
        return -1;
    }


    return result;
}


/* ============================================================
 * BUILD FILE ERROR MESSAGE
 * ============================================================
 */

int buildFileErrorMessage(
    char *buffer,
    int bufferSize,
    int transferId,
    const char *errorMessage
)
{
    int result;


    if (
        buffer == NULL ||
        errorMessage == NULL ||
        bufferSize <= 0
    )
    {
        return -1;
    }


    result = snprintf(
        buffer,
        bufferSize,
        "%s|%d|%s\n",
        MSG_FILE_ERROR,
        transferId,
        errorMessage
    );


    if (result < 0)
    {
        return -1;
    }


    if (result >= bufferSize)
    {
        return -1;
    }


    return result;
}


/* ============================================================
 * GET PROTOCOL TYPE
 * ============================================================
 */

int getProtocolType(
    const char *message,
    char *type,
    int typeSize
)
{
    int i = 0;


    if (
        message == NULL ||
        type == NULL ||
        typeSize <= 0
    )
    {
        return -1;
    }


    /*
     * Copy characters until:
     *
     * 1. '|' is found
     * 2. '\n' is found
     * 3. end of string is reached
     * 4. output buffer is full
     */

    while (
        message[i] != '\0' &&
        message[i] != '|' &&
        message[i] != '\n' &&
        i < typeSize - 1
    )
    {
        type[i] = message[i];

        i++;
    }


    type[i] = '\0';


    return i;
}