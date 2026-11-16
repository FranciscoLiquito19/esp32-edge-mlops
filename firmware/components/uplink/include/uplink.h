#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

/** True when an SSID and an ingest URL have been configured. */
bool uplink_is_configured(void);

/** Start Wi-Fi and begin connecting. Returns immediately. */
esp_err_t uplink_start(void);

/** Block until the station has an IP address, or the timeout expires. */
esp_err_t uplink_wait_connected(uint32_t timeout_ms);

/** Signal strength of the current connection in dBm, 0 if unknown. */
int uplink_rssi(void);

/**
 * POST one event to the ingest service (protocol: docs/PROTOCOL.md).
 *
 * @param meta_json    Single-line JSON metadata, sent in the X-Event-Meta header.
 * @param jpeg         Image body, or NULL to send metadata only.
 * @param jpeg_len     Length of the image body.
 * @param http_status  Receives the HTTP status code (0 if no response).
 * @param server_time  Receives the server's Unix time, 0 if not provided.
 * @return ESP_OK on a 2xx response.
 */
esp_err_t uplink_post_event(const char *meta_json, const uint8_t *jpeg, size_t jpeg_len,
                            int *http_status, int64_t *server_time);

/** Disconnect and stop Wi-Fi. */
void uplink_stop(void);
