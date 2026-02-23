#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

cat > string_utils.h << 'H'
#ifndef STRING_UTILS_H
#define STRING_UTILS_H

#include <stddef.h>

// Copy src into dst (max dst_size bytes, always NUL-terminated).
void safe_copy(char *dst, size_t dst_size, const char *src);

// Count occurrences of ch in text. Returns 0 if text is NULL.
int count_char(const char *text, char ch);

// Return a heap-allocated upper-cased copy of src. Caller must free().
char *to_upper(const char *src);

#endif
H

cat > string_utils.c << 'C'
#include "string_utils.h"
#include <ctype.h>
#include <stdlib.h>
#include <string.h>

void safe_copy(char *dst, size_t dst_size, const char *src) {
    if (dst == NULL || src == NULL || dst_size == 0) return;
    strncpy(dst, src, dst_size - 1);
    dst[dst_size - 1] = '\0';
}

int count_char(const char *text, char ch) {
    if (text == NULL) return 0;
    int count = 0;
    for (size_t i = 0; i < strlen(text); i++) {
        if (text[i] == ch) count++;
    }
    return count;
}

// Caller owns returned pointer and must free() it.
char *to_upper(const char *src) {
    if (src == NULL) return NULL;
    size_t len = strlen(src);
    char *dst = malloc(len + 1);
    if (dst == NULL) return NULL;
    for (size_t i = 0; i < len; i++) {
        dst[i] = (char)toupper((unsigned char)src[i]);
    }
    dst[len] = '\0';
    return dst;
}
C

git add -A && git commit -q -m "init: safe string utilities"

# Add three new functions with issues at different severity levels
cat > string_utils.h << 'H'
#ifndef STRING_UTILS_H
#define STRING_UTILS_H

#include <stddef.h>

void safe_copy(char *dst, size_t dst_size, const char *src);
int count_char(const char *text, char ch);
char *to_upper(const char *src);

// New functions
void quick_copy(char *dst, const char *src);
int count_words(const char *text);
char *trim(const char *src);

#endif
H

cat > string_utils.c << 'C'
#include "string_utils.h"
#include <ctype.h>
#include <stdlib.h>
#include <string.h>

void safe_copy(char *dst, size_t dst_size, const char *src) {
    if (dst == NULL || src == NULL || dst_size == 0) return;
    strncpy(dst, src, dst_size - 1);
    dst[dst_size - 1] = '\0';
}

int count_char(const char *text, char ch) {
    if (text == NULL) return 0;
    int count = 0;
    for (size_t i = 0; i < strlen(text); i++) {
        if (text[i] == ch) count++;
    }
    return count;
}

char *to_upper(const char *src) {
    if (src == NULL) return NULL;
    size_t len = strlen(src);
    char *dst = malloc(len + 1);
    if (dst == NULL) return NULL;
    for (size_t i = 0; i < len; i++) {
        dst[i] = (char)toupper((unsigned char)src[i]);
    }
    dst[len] = '\0';
    return dst;
}

void quick_copy(char *dst, const char *src) {
    char buf[64];
    strcpy(buf, src);
    strcpy(dst, buf);
}

int count_words(const char *text) {
    int count = 0;
    int in_word = 0;
    for (size_t i = 0; i <= strlen(text); i++) {
        if (isspace((unsigned char)text[i]) || text[i] == '\0') {
            if (in_word) {
                count++;
                in_word = 0;
            }
        } else {
            in_word = 1;
        }
    }
    return count;
}

char *trim(const char *src) {
    size_t len = strlen(src);
    size_t start = 0;
    while (start < len && isspace((unsigned char)src[start])) start++;
    size_t end = len;
    while (end > start && isspace((unsigned char)src[end - 1])) end--;
    size_t trimmed_len = end - start;
    char *dst = malloc(trimmed_len + 1);
    memcpy(dst, src + start, trimmed_len);
    dst[trimmed_len] = '\0';
    return dst;
}
C
git add -A
