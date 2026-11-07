#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <strings.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "LinkedListAPI.h"
#include "VCParser.h"
int updateFN(Card* card, const char* newFN);
bool validDate(const DateTime* date);
void writeProperty(FILE* file, const Property* property);
