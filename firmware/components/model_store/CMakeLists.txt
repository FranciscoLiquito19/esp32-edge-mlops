idf_component_register(SRCS "model_manifest.c" "model_store.c"
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES esp_partition mbedtls spi_flash)
