#include <stdio.h>
#include <string.h>

#include "protocol.h"


int main()
{
    char buffer[512];


    printf(
        "========================================\n"
    );

    printf(
        "       FILE PROTOCOL LAYER TEST\n"
    );

    printf(
        "========================================\n\n"
    );


    /* ======================================================
     * TEST 1 - FILE START
     * ======================================================
     */

    printf(
        "[TEST 1] FILE_START message\n"
    );


    int length = buildFileStartMessage(
        buffer,
        sizeof(buffer),
        101,
        1,
        2,
        5242880LL,
        "cmVzZWFyY2ggcGFwZXIucGRm"
    );


    if (length < 0)
    {
        printf(
            "Result: FAILED\n\n"
        );
    }
    else
    {
        printf(
            "Result: %s",
            buffer
        );

        printf(
            "Length: %d\n\n",
            length
        );
    }


    /* ======================================================
     * TEST 2 - FILE END
     * ======================================================
     */

    printf(
        "[TEST 2] FILE_END message\n"
    );


    length = buildFileEndMessage(
        buffer,
        sizeof(buffer),
        101
    );


    if (length < 0)
    {
        printf(
            "Result: FAILED\n\n"
        );
    }
    else
    {
        printf(
            "Result: %s",
            buffer
        );

        printf(
            "Length: %d\n\n",
            length
        );
    }


    /* ======================================================
     * TEST 3 - FILE ERROR
     * ======================================================
     */

    printf(
        "[TEST 3] FILE_ERROR message\n"
    );


    length = buildFileErrorMessage(
        buffer,
        sizeof(buffer),
        101,
        "Transfer failed"
    );


    if (length < 0)
    {
        printf(
            "Result: FAILED\n\n"
        );
    }
    else
    {
        printf(
            "Result: %s",
            buffer
        );

        printf(
            "Length: %d\n\n",
            length
        );
    }


    /* ======================================================
     * TEST 4 - PROTOCOL TYPE
     * ======================================================
     */

    printf(
        "[TEST 4] Protocol type\n"
    );


    char type[64];


    length = getProtocolType(
        "FILE_START|101|1|2|5242880|filename\n",
        type,
        sizeof(type)
    );


    if (length < 0)
    {
        printf(
            "Type: FAILED\n"
        );
    }
    else
    {
        printf(
            "Type: %s\n",
            type
        );

        printf(
            "Length: %d\n",
            length
        );
    }


    printf(
        "\n========================================\n"
    );

    printf(
        "          TEST COMPLETED\n"
    );

    printf(
        "========================================\n"
    );


    return 0;
}