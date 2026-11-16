#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    POWER_WAKE_COLD_BOOT, /* power-on, reset button, crash: RTC state is not trusted */
    POWER_WAKE_PIR,       /* deep-sleep wake from the PIR pin */
    POWER_WAKE_TIMER,     /* deep-sleep wake from the timer */
} power_wake_t;

/** Why the chip started this time. Call once, early in app_main. */
power_wake_t power_wake_reason(void);

/** Short name for metadata and logs: "power_on", "pir" or "timer". */
const char *power_wake_str(power_wake_t wake);

/** Hand the PIR pin back to the digital GPIO driver so it can be read. */
void power_init(void);

/** Current level of the PIR output. */
bool power_pir_active(void);

/** Deep sleep until the PIR output goes high. Does not return. */
void power_sleep_until_pir(void) __attribute__((noreturn));

/** Deep sleep for a fixed time with the PIR wake-up disarmed. Does not return. */
void power_sleep_for(uint32_t seconds) __attribute__((noreturn));

/**
 * Sleep in the way that avoids an immediate re-trigger: if the PIR output is
 * still high, sleep on the timer and check again later; otherwise arm the PIR.
 */
void power_sleep_auto(void) __attribute__((noreturn));
