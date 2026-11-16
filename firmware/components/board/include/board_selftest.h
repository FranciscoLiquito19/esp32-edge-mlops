#pragma once

#include <stdbool.h>
#include <stddef.h>

/** Model partition: custom type/subtype, must match partitions.csv. */
#define BOARD_MODEL_PARTITION_TYPE    0x40
#define BOARD_MODEL_PARTITION_SUBTYPE 0x00
#define BOARD_MODEL_PARTITION_LABEL   "model"

/** Print chip, flash, PSRAM and heap information to the log. */
void board_print_info(void);

/** Print the partition table as seen by the running firmware. */
void board_print_partitions(void);

/**
 * Write and read back a pattern in PSRAM.
 *
 * @param bytes Size of the test block.
 * @return true if PSRAM is present and every byte read back correctly.
 */
bool board_psram_selftest(size_t bytes);

/** @return true if the model partition exists in the partition table. */
bool board_model_partition_present(void);
