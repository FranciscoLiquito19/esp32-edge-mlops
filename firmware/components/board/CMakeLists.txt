idf_component_register(SRCS "board_selftest.c"
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES esp_partition esp_psram spi_flash esp_hw_support)
