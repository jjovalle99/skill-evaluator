#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p include src

cat > include/buffer.h << 'H'
#ifndef BUFFER_H
#define BUFFER_H

#include <stddef.h>

int sum_window(const int *values, size_t len);
void copy_tag(char *dst, size_t dst_size, const char *src);

#endif
H

cat > src/buffer.c << 'C'
#include "buffer.h"
#include <stddef.h>

int sum_window(const int *values, size_t len) {
    int total = 0;
    for (size_t i = 0; i < len; ++i) {
        total += values[i];
    }
    return total;
}

void copy_tag(char *dst, size_t dst_size, const char *src) {
    if (dst == NULL || src == NULL || dst_size == 0) return;

    size_t i = 0;
    for (; i + 1 < dst_size && src[i] != '\0'; ++i) {
        dst[i] = src[i];
    }
    dst[i] = '\0';
}
C

git add -A && git commit -q -m "init: safe array and string helpers"

# Introduce off-by-one read and fence-post null-termination error
cat > src/buffer.c << 'C'
#include "buffer.h"
#include <stddef.h>

int sum_window(const int *values, size_t len) {
    int total = 0;
    for (size_t i = 0; i <= len; ++i) {
        total += values[i];
    }
    return total;
}

void copy_tag(char *dst, size_t dst_size, const char *src) {
    if (dst == NULL || src == NULL || dst_size == 0) return;

    size_t i = 0;
    for (; i < dst_size && src[i] != '\0'; ++i) {
        dst[i] = src[i];
    }
    dst[dst_size] = '\0';
}
C

git add -A
