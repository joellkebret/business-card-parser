/* Allocation accounting and fault injection for native ownership paths. */
#include "native_alloc.h"
#include "VCParser.h"
#include "VCHelpers.h"
#include <assert.h>
#undef malloc
#undef realloc
#undef strdup
#undef free

long allocation_fail_after = -1;
long live_allocations = 0;
static void* allocations[65536];

void* test_malloc(size_t size) {
    if (allocation_fail_after == 0) { allocation_fail_after = -1; return NULL; }
    if (allocation_fail_after > 0) allocation_fail_after--;
    void* pointer = malloc(size);
    if (!pointer) return NULL;
    for (size_t i = 0; i < 65536; i++) if (!allocations[i]) {
        allocations[i] = pointer; live_allocations++; return pointer;
    }
    abort();
}

void test_free(void* pointer) {
    if (!pointer) return;
    for (size_t i = 0; i < 65536; i++) if (allocations[i] == pointer) {
        allocations[i] = NULL; live_allocations--; free(pointer); return;
    }
    /* Detect double frees and freeing pointers not owned by this library. */
    abort();
}

char* test_strdup(const char* text) {
    size_t length = strlen(text) + 1;
    char* copy = test_malloc(length);
    if (copy) memcpy(copy, text, length);
    return copy;
}

void* test_realloc(void* pointer, size_t size) {
    if (!pointer) return test_malloc(size);
    for (size_t i = 0; i < 65536; i++) if (allocations[i] == pointer) {
        if (allocation_fail_after == 0) { allocation_fail_after = -1; return NULL; }
        if (allocation_fail_after > 0) allocation_fail_after--;
        void* resized = realloc(pointer, size);
        if (resized) allocations[i] = resized;
        return resized;
    }
    abort();
}

int main(int argc, char** argv) {
    assert(argc >= 2);
    for (int file = 1; file < argc; file++) {
        for (int failure = -1; failure < 350; failure++) {
            allocation_fail_after = failure;
            Card* card = NULL;
            VCardErrorCode result = createCard(argv[file], &card);
            if (result == OK) {
                assert(card);
                if (validateCard(card) == OK) {
                    updateFN(card, "Updated name");
                    validateCard(card);
                }
                deleteCard(card);
            } else assert(card == NULL);
            assert(live_allocations == 0);
        }
    }
    puts("Native allocation accounting and fault injection passed");
    return 0;
}
