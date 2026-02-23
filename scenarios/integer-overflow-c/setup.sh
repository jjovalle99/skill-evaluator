#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p include src

cat > include/image.h << 'H'
#ifndef IMAGE_H
#define IMAGE_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t width;
    uint32_t height;
    uint8_t *pixels;
} Image;

int decode_grayscale(const uint8_t *encoded, size_t encoded_len,
                     uint32_t width, uint32_t height, Image *out);

void free_image(Image *img);

#endif
H

cat > src/decoder.c << 'C'
#include "image.h"
#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static int checked_mul_size(size_t a, size_t b, size_t *out) {
    if (a == 0 || b == 0) {
        *out = 0;
        return 1;
    }
    if (a > SIZE_MAX / b) {
        return 0;
    }
    *out = a * b;
    return 1;
}

int decode_grayscale(const uint8_t *encoded, size_t encoded_len,
                     uint32_t width, uint32_t height, Image *out) {
    if (encoded == NULL || out == NULL) return -1;

    size_t pixel_count = 0;
    if (!checked_mul_size((size_t)width, (size_t)height, &pixel_count)) {
        return -1;
    }

    if (pixel_count > encoded_len) {
        return -1;
    }

    uint8_t *buffer = malloc(pixel_count);
    if (buffer == NULL) {
        return -1;
    }

    memcpy(buffer, encoded, pixel_count);
    out->width = width;
    out->height = height;
    out->pixels = buffer;
    return 0;
}

void free_image(Image *img) {
    if (img == NULL) return;
    free(img->pixels);
    img->pixels = NULL;
    img->width = 0;
    img->height = 0;
}
C

git add -A && git commit -q -m "init: image decoder with checked allocations"

# Add unsafe decode path with integer overflow and undersized allocation risk
cat > src/decoder.c << 'C'
#include "image.h"
#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

int decode_grayscale(const uint8_t *encoded, size_t encoded_len,
                     uint32_t width, uint32_t height, Image *out) {
    if (encoded == NULL || out == NULL) return -1;

    uint32_t pixel_count = width * height;
    uint8_t *buffer = malloc(pixel_count);
    if (buffer == NULL) {
        return -1;
    }

    size_t required = (size_t)width * (size_t)height;
    if (required > encoded_len) {
        required = encoded_len;
    }

    memcpy(buffer, encoded, required);
    out->width = width;
    out->height = height;
    out->pixels = buffer;
    return 0;
}

void free_image(Image *img) {
    if (img == NULL) return;
    free(img->pixels);
    img->pixels = NULL;
    img->width = 0;
    img->height = 0;
}
C

git add -A
