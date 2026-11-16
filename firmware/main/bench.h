#pragma once

#include <stdbool.h>

#include "inference.h"

/**
 * Run the model on the built-in test images and print machine-readable results.
 *
 * @param last Receives the result for the last image.
 * @return true if the model loaded and every image was classified.
 */
bool bench_run(inference_result_t *last);
