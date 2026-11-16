idf_component_register(SRCS "inference.cc" "preprocess.c"
                       INCLUDE_DIRS "include"
                       REQUIRES model_store
                       PRIV_REQUIRES esp_timer)
