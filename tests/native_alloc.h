#ifndef NATIVE_ALLOC_TEST_H
#define NATIVE_ALLOC_TEST_H
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
void* test_malloc(size_t size);
void* test_realloc(void* pointer, size_t size);
char* test_strdup(const char* text);
void test_free(void* pointer);
extern long allocation_fail_after;
extern long live_allocations;
#define malloc test_malloc
#define realloc test_realloc
#define strdup test_strdup
#define free test_free
#endif
