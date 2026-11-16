set(srcs "main.c")
set(embed "")

if(CONFIG_APP_MODE_BENCH)
    list(APPEND srcs "bench.c")
    list(APPEND embed "golden/g0.jpg" "golden/g1.jpg" "golden/g2.jpg")
endif()

idf_component_register(SRCS ${srcs}
                       INCLUDE_DIRS "."
                       EMBED_FILES ${embed}
                       PRIV_REQUIRES board power capture uplink inference
                                     esp_app_format esp_hw_support esp_timer)
