#include "storage.h"
#include "basic.h"

#include <string.h>
#include <zephyr/sys/printk.h>

#define FILE_NAME "greeting.txt"

static const char greeting[] = "Hello from Crux File API!";

int main(void)
{
    /* Platform composition first: mount the volume and bind it as the File root. */
    if (storage_init() != 0) {
        printk("CRUX_FILE_WRITE_READ_FAILED step=storage\n");
        return -1;
    }

    /* From here on, only the public File API is used. */
    const size_t length = sizeof(greeting) - 1;
    size_t written = 0;
    crux_file_result_t result = write_text(FILE_NAME, greeting, length, &written);
    if (result != CRUX_FILE_OK) {
        printk("CRUX_FILE_WRITE_READ_FAILED step=write result=%d\n", (int)result);
        return -1;
    }
    printk("Wrote %u bytes to %s\n", (unsigned int)written, FILE_NAME);

    char buffer[64];
    size_t read = 0;
    result = read_text(FILE_NAME, buffer, sizeof(buffer) - 1, &read);
    if (result != CRUX_FILE_OK) {
        printk("CRUX_FILE_WRITE_READ_FAILED step=read result=%d\n", (int)result);
        return -1;
    }
    buffer[read] = '\0';
    printk("Read %u bytes: %s\n", (unsigned int)read, buffer);

    if (read != length || memcmp(buffer, greeting, length) != 0) {
        printk("CRUX_FILE_WRITE_READ_FAILED step=compare\n");
        return -1;
    }
    printk("CRUX_FILE_WRITE_READ_OK provider=%s\n", storage_provider_name);
    return 0;
}
