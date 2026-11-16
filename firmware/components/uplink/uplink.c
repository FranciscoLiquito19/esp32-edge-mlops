#include "uplink.h"

#include <stdlib.h>
#include <string.h>

#include "esp_check.h"
#include "esp_crt_bundle.h"
#include "esp_event.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#define CONNECTED_BIT BIT0
#define FAILED_BIT    BIT1
#define MAX_RETRIES   3
#define RESPONSE_MAX  256

static const char *TAG = "uplink";

static EventGroupHandle_t s_events;
static int s_retries;
static bool s_started;

typedef struct {
    char buf[RESPONSE_MAX];
    size_t len;
} response_t;

bool uplink_is_configured(void)
{
    return strlen(CONFIG_APP_WIFI_SSID) > 0 && strlen(CONFIG_APP_INGEST_URL) > 0;
}

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retries < MAX_RETRIES) {
            s_retries++;
            esp_wifi_connect();
        } else {
            xEventGroupSetBits(s_events, FAILED_BIT);
        }
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(s_events, CONNECTED_BIT);
    }
}

esp_err_t uplink_start(void)
{
    if (s_started) {
        return ESP_OK;
    }

    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_RETURN_ON_ERROR(nvs_flash_erase(), TAG, "nvs erase");
        err = nvs_flash_init();
    }
    ESP_RETURN_ON_ERROR(err, TAG, "nvs init");

    s_events = xEventGroupCreate();
    if (s_events == NULL) {
        return ESP_ERR_NO_MEM;
    }

    ESP_RETURN_ON_ERROR(esp_netif_init(), TAG, "netif init");
    ESP_RETURN_ON_ERROR(esp_event_loop_create_default(), TAG, "event loop");
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&init), TAG, "wifi init");

    ESP_RETURN_ON_ERROR(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                                            on_event, NULL, NULL),
                        TAG, "wifi handler");
    ESP_RETURN_ON_ERROR(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                                            on_event, NULL, NULL),
                        TAG, "ip handler");

    wifi_config_t cfg = { 0 };
    strlcpy((char *)cfg.sta.ssid, CONFIG_APP_WIFI_SSID, sizeof(cfg.sta.ssid));
    strlcpy((char *)cfg.sta.password, CONFIG_APP_WIFI_PASSWORD, sizeof(cfg.sta.password));

    /* The device reconnects from scratch on every wake, so nothing is worth persisting. */
    ESP_RETURN_ON_ERROR(esp_wifi_set_storage(WIFI_STORAGE_RAM), TAG, "wifi storage");
    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), TAG, "wifi mode");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &cfg), TAG, "wifi config");
    ESP_RETURN_ON_ERROR(esp_wifi_start(), TAG, "wifi start");

    s_retries = 0;
    s_started = true;
    return ESP_OK;
}

esp_err_t uplink_wait_connected(uint32_t timeout_ms)
{
    if (!s_started) {
        return ESP_ERR_INVALID_STATE;
    }
    EventBits_t bits = xEventGroupWaitBits(s_events, CONNECTED_BIT | FAILED_BIT, pdFALSE, pdFALSE,
                                           pdMS_TO_TICKS(timeout_ms));
    if (bits & CONNECTED_BIT) {
        return ESP_OK;
    }
    ESP_LOGW(TAG, "Wi-Fi not connected (%s)", (bits & FAILED_BIT) ? "refused" : "timeout");
    return (bits & FAILED_BIT) ? ESP_FAIL : ESP_ERR_TIMEOUT;
}

int uplink_rssi(void)
{
    wifi_ap_record_t ap;
    if (s_started && esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
        return ap.rssi;
    }
    return 0;
}

static esp_err_t on_http_event(esp_http_client_event_t *evt)
{
    if (evt->event_id == HTTP_EVENT_ON_DATA && evt->user_data != NULL) {
        response_t *resp = (response_t *)evt->user_data;
        size_t room = sizeof(resp->buf) - 1 - resp->len;
        size_t n = (size_t)evt->data_len < room ? (size_t)evt->data_len : room;
        memcpy(resp->buf + resp->len, evt->data, n);
        resp->len += n;
        resp->buf[resp->len] = '\0';
    }
    return ESP_OK;
}

/* Pull the integer after "server_time": out of a small JSON response. */
static int64_t parse_server_time(const char *body)
{
    const char *key = strstr(body, "\"server_time\"");
    if (key == NULL) {
        return 0;
    }
    const char *colon = strchr(key, ':');
    if (colon == NULL) {
        return 0;
    }
    return strtoll(colon + 1, NULL, 10);
}

esp_err_t uplink_post_event(const char *meta_json, const uint8_t *jpeg, size_t jpeg_len,
                            int *http_status, int64_t *server_time)
{
    response_t resp = { 0 };

    if (http_status != NULL) {
        *http_status = 0;
    }
    if (server_time != NULL) {
        *server_time = 0;
    }

    const esp_http_client_config_t cfg = {
        .url = CONFIG_APP_INGEST_URL,
        .method = HTTP_METHOD_POST,
        .timeout_ms = CONFIG_APP_HTTP_TIMEOUT_MS,
        .event_handler = on_http_event,
        .user_data = &resp,
        .crt_bundle_attach = esp_crt_bundle_attach,
        .buffer_size_tx = 2048, /* request headers include the metadata JSON */
    };

    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    if (client == NULL) {
        return ESP_FAIL;
    }

    esp_http_client_set_header(client, "Authorization", "Bearer " CONFIG_APP_DEVICE_TOKEN);
    esp_http_client_set_header(client, "X-Event-Meta", meta_json);
    if (jpeg != NULL && jpeg_len > 0) {
        esp_http_client_set_header(client, "Content-Type", "image/jpeg");
        esp_http_client_set_post_field(client, (const char *)jpeg, (int)jpeg_len);
    }

    esp_err_t err = esp_http_client_perform(client);
    int status = (err == ESP_OK) ? esp_http_client_get_status_code(client) : 0;
    esp_http_client_cleanup(client);

    if (http_status != NULL) {
        *http_status = status;
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "POST failed: %s", esp_err_to_name(err));
        return err;
    }
    if (status < 200 || status >= 300) {
        ESP_LOGW(TAG, "POST rejected: HTTP %d %s", status, resp.buf);
        return ESP_FAIL;
    }
    if (server_time != NULL) {
        *server_time = parse_server_time(resp.buf);
    }
    return ESP_OK;
}

void uplink_stop(void)
{
    if (s_started) {
        esp_wifi_disconnect();
        esp_wifi_stop();
        s_started = false;
    }
}
