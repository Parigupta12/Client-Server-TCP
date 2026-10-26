#include "server_stats.h"

#include <windows.h>
#include <time.h>

/* ============================================================
   GLOBAL SERVER STATISTICS
   ============================================================ */

static ServerStats stats;

/* Protect statistics because multiple client threads
   can update them simultaneously. */
static CRITICAL_SECTION statsLock;
static int statsLockInitialized = 0;


/* ============================================================
   INITIALIZE STATISTICS
   ============================================================ */

void stats_init(void)
{
    InitializeCriticalSection(&statsLock);
    statsLockInitialized = 1;

    EnterCriticalSection(&statsLock);

    ZeroMemory(&stats, sizeof(stats));

    stats.start_time = (uint64_t)time(NULL);

    LeaveCriticalSection(&statsLock);
}


/* ============================================================
   CONNECTION STATISTICS
   ============================================================ */

void stats_connection_opened(void)
{
    if (!statsLockInitialized)
        return;

    EnterCriticalSection(&statsLock);

    stats.total_connections++;
    stats.current_clients++;

    if (stats.current_clients > stats.peak_clients)
    {
        stats.peak_clients = stats.current_clients;
    }

    LeaveCriticalSection(&statsLock);
}


void stats_connection_closed(void)
{
    if (!statsLockInitialized)
        return;

    EnterCriticalSection(&statsLock);

    stats.total_disconnections++;

    if (stats.current_clients > 0)
    {
        stats.current_clients--;
    }

    LeaveCriticalSection(&statsLock);
}


/* ============================================================
   MESSAGE STATISTICS
   ============================================================ */

void stats_message_received(void)
{
    if (!statsLockInitialized)
        return;

    EnterCriticalSection(&statsLock);

    stats.total_messages++;

    LeaveCriticalSection(&statsLock);
}


void stats_broadcast(void)
{
    if (!statsLockInitialized)
        return;

    EnterCriticalSection(&statsLock);

    stats.broadcast_messages++;

    LeaveCriticalSection(&statsLock);
}


void stats_private(void)
{
    if (!statsLockInitialized)
        return;

    EnterCriticalSection(&statsLock);

    stats.private_messages++;

    LeaveCriticalSection(&statsLock);
}


/* ============================================================
   FILE TRANSFER STATISTICS
   ============================================================ */

void stats_file_started(void)
{
    if (!statsLockInitialized)
        return;

    EnterCriticalSection(&statsLock);

    stats.total_file_transfers++;
    stats.active_file_transfers++;

    LeaveCriticalSection(&statsLock);
}


void stats_file_completed(void)
{
    if (!statsLockInitialized)
        return;

    EnterCriticalSection(&statsLock);

    stats.completed_file_transfers++;

    if (stats.active_file_transfers > 0)
    {
        stats.active_file_transfers--;
    }

    LeaveCriticalSection(&statsLock);
}


void stats_file_failed(void)
{
    if (!statsLockInitialized)
        return;

    EnterCriticalSection(&statsLock);

    stats.failed_file_transfers++;

    if (stats.active_file_transfers > 0)
    {
        stats.active_file_transfers--;
    }

    LeaveCriticalSection(&statsLock);
}


/* ============================================================
   NETWORK STATISTICS
   ============================================================ */

void stats_bytes_received(uint64_t bytes)
{
    if (!statsLockInitialized)
        return;

    EnterCriticalSection(&statsLock);

    stats.bytes_received += bytes;

    LeaveCriticalSection(&statsLock);
}


void stats_bytes_sent(uint64_t bytes)
{
    if (!statsLockInitialized)
        return;

    EnterCriticalSection(&statsLock);

    stats.bytes_sent += bytes;

    LeaveCriticalSection(&statsLock);
}


/* ============================================================
   GET CURRENT STATISTICS
   ============================================================ */

const ServerStats *stats_get(void)
{
    return &stats;
}
