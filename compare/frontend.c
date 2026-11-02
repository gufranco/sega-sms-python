#include <dlfcn.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "libretro.h"

static const char *const STORE = "/tmp";

static const char *const CORE = "/usr/local/lib/genesis_plus_gx_libretro.so";

struct core {
    void (*set_environment)(retro_environment_t);
    void (*set_video_refresh)(retro_video_refresh_t);
    void (*set_audio_sample)(retro_audio_sample_t);
    void (*set_audio_sample_batch)(retro_audio_sample_batch_t);
    void (*set_input_poll)(retro_input_poll_t);
    void (*set_input_state)(retro_input_state_t);
    void (*init)(void);
    bool (*load_game)(const struct retro_game_info *);
    void (*run)(void);
    void (*unload_game)(void);
    void (*deinit)(void);
};

static bool environment(unsigned command, void *data)
{
    if (command == RETRO_ENVIRONMENT_SET_PIXEL_FORMAT) {
        return *(const enum retro_pixel_format *)data == RETRO_PIXEL_FORMAT_RGB565;
    }
    if (command == RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY ||
        command == RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY) {
        *(const char **)data = STORE;
        return true;
    }
    return false;
}

static void put_u16(uint16_t value)
{
    const unsigned char bytes[2] = {(unsigned char)(value & 0xFF), (unsigned char)(value >> 8)};
    fwrite(bytes, 1, sizeof(bytes), stdout);
}

static void video(const void *data, unsigned width, unsigned height, size_t pitch)
{
    put_u16((uint16_t)width);
    put_u16((uint16_t)height);
    for (unsigned row = 0; row < height; row++) {
        const unsigned char *line = (const unsigned char *)data + (size_t)row * pitch;
        fwrite(line, 1, (size_t)width * 2, stdout);
    }
}

static void audio_sample(int16_t left, int16_t right)
{
    (void)left;
    (void)right;
}

static size_t audio_batch(const int16_t *data, size_t frames)
{
    (void)data;
    return frames;
}

static void input_poll(void) {}

static int16_t input_state(unsigned port, unsigned device, unsigned index, unsigned id)
{
    (void)port;
    (void)device;
    (void)index;
    (void)id;
    return 0;
}

static void *symbol(void *library, const char *name, bool *found)
{
    void *held = dlsym(library, name);
    if (held == NULL) {
        fprintf(stderr, "the core has no %s\n", name);
        *found = false;
    }
    return held;
}

static bool bind(void *library, struct core *core)
{
    bool found = true;
    *(void **)&core->set_environment = symbol(library, "retro_set_environment", &found);
    *(void **)&core->set_video_refresh = symbol(library, "retro_set_video_refresh", &found);
    *(void **)&core->set_audio_sample = symbol(library, "retro_set_audio_sample", &found);
    *(void **)&core->set_audio_sample_batch = symbol(library, "retro_set_audio_sample_batch", &found);
    *(void **)&core->set_input_poll = symbol(library, "retro_set_input_poll", &found);
    *(void **)&core->set_input_state = symbol(library, "retro_set_input_state", &found);
    *(void **)&core->init = symbol(library, "retro_init", &found);
    *(void **)&core->load_game = symbol(library, "retro_load_game", &found);
    *(void **)&core->run = symbol(library, "retro_run", &found);
    *(void **)&core->unload_game = symbol(library, "retro_unload_game", &found);
    *(void **)&core->deinit = symbol(library, "retro_deinit", &found);
    return found;
}

static unsigned char *read_all(const char *path, size_t *size)
{
    FILE *in = fopen(path, "rb");
    if (in == NULL) {
        return NULL;
    }
    fseek(in, 0, SEEK_END);
    const long length = ftell(in);
    fseek(in, 0, SEEK_SET);
    unsigned char *held = length > 0 ? malloc((size_t)length) : NULL;
    const bool whole = held != NULL && fread(held, 1, (size_t)length, in) == (size_t)length;
    fclose(in);
    if (!whole) {
        free(held);
        return NULL;
    }
    *size = (size_t)length;
    return held;
}

static int run(const struct core *core, const char *path, unsigned char *image, size_t size,
               long frames)
{
    core->set_environment(environment);
    core->set_video_refresh(video);
    core->set_audio_sample(audio_sample);
    core->set_audio_sample_batch(audio_batch);
    core->set_input_poll(input_poll);
    core->set_input_state(input_state);
    core->init();
    const struct retro_game_info game = {path, image, size, NULL};
    if (!core->load_game(&game)) {
        fprintf(stderr, "the core refused %s\n", path);
        return 1;
    }
    for (long frame = 0; frame < frames; frame++) {
        core->run();
    }
    fflush(stdout);
    core->unload_game();
    core->deinit();
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 3) {
        fprintf(stderr, "usage: gpgx-frames <image.sms|image.gg> <frames>\n");
        return 2;
    }
    size_t size = 0;
    unsigned char *image = read_all(argv[1], &size);
    if (image == NULL) {
        fprintf(stderr, "cannot read %s\n", argv[1]);
        return 2;
    }
    void *library = dlopen(CORE, RTLD_NOW);
    struct core core;
    if (library == NULL || !bind(library, &core)) {
        fprintf(stderr, "cannot load %s\n", CORE);
        free(image);
        return 2;
    }
    const int code = run(&core, argv[1], image, size, strtol(argv[2], NULL, 10));
    free(image);
    return code;
}
