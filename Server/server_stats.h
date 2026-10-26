#ifndef SERVER_STATS_H
#define SERVER_STATS_H

#include <stdint.h>

typedef struct
{
    /* Server */
    uint64_t start_time;

    /* Connections */
    uint64_t total_connections;
    uint64_t total_disconnections;
    uint64_t current_clients;
    uint64_t peak_clients;

    /* Messages */
    uint64_t total_messages;
    uint64_t broadcast_messages;
    uint64_t private_messages;

    /* File transfers */
    uint64_t total_file_transfers;
    uint64_t completed_file_transfers;
    uint64_t failed_file_transfers;
    uint64_t active_file_transfers;

    /* Network */
    uint64_t bytes_received;
    uint64_t bytes_sent;
} ServerStats;

void stats_init(void);

void stats_connection_opened(void);
void stats_connection_closed(void);

void stats_message_received(void);
void stats_broadcast(void);
void stats_private(void);

void stats_file_started(void);
void stats_file_completed(void);
void stats_file_failed(void);

void stats_bytes_received(uint64_t bytes);
void stats_bytes_sent(uint64_t bytes);

const ServerStats *stats_get(void);

#endif
