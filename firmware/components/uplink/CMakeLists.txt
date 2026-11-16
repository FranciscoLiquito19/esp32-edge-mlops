idf_component_register(SRCS "uplink.c"
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES esp_wifi esp_netif esp_event nvs_flash esp_http_client mbedtls)
