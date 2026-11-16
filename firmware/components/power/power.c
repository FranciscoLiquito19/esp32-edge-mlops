#include "power.h"

#include "driver/gpio.h"
#include "driver/rtc_io.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "esp_system.h"
#include "sdkconfig.h"

#define PIR_GPIO ((gpio_num_t)CONFIG_APP_PIR_GPIO)

static const char *TAG = "power";

power_wake_t power_wake_reason(void)
{
    if (esp_reset_reason() != ESP_RST_DEEPSLEEP) {
        return POWER_WAKE_COLD_BOOT;
    }
    switch (esp_sleep_get_wakeup_cause()) {
    case ESP_SLEEP_WAKEUP_EXT1:
        return POWER_WAKE_PIR;
    case ESP_SLEEP_WAKEUP_TIMER:
        return POWER_WAKE_TIMER;
    default:
        return POWER_WAKE_COLD_BOOT;
    }
}

const char *power_wake_str(power_wake_t wake)
{
    switch (wake) {
    case POWER_WAKE_PIR:   return "pir";
    case POWER_WAKE_TIMER: return "timer";
    default:               return "power_on";
    }
}

void power_init(void)
{
    /* After an EXT1 wake the pin still belongs to the RTC domain. */
    rtc_gpio_deinit(PIR_GPIO);

    const gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << PIR_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE, /* reads low if the sensor is unplugged */
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&cfg);
}

bool power_pir_active(void)
{
    return gpio_get_level(PIR_GPIO) == 1;
}

void power_sleep_until_pir(void)
{
    ESP_LOGI(TAG, "Deep sleep until PIR (GPIO%d) goes high", (int)PIR_GPIO);

    esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
    esp_sleep_enable_ext1_wakeup_io(1ULL << PIR_GPIO, ESP_EXT1_WAKEUP_ANY_HIGH);

    /* Keep the pull-down alive in deep sleep so a disconnected pin cannot wake us. */
    rtc_gpio_pullup_dis(PIR_GPIO);
    rtc_gpio_pulldown_en(PIR_GPIO);
    esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON);

    esp_deep_sleep_start();
}

void power_sleep_for(uint32_t seconds)
{
    ESP_LOGI(TAG, "Deep sleep for %u s (PIR disarmed)", (unsigned)seconds);

    esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
    esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
    esp_deep_sleep_start();
}

void power_sleep_auto(void)
{
    if (power_pir_active()) {
        power_sleep_for(CONFIG_APP_PIR_RECHECK_S);
    }
    power_sleep_until_pir();
}
