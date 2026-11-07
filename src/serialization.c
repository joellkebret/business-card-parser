#include "VCHelpers.h"

void writeProperty(FILE* file, const Property* property) {
    if (property->group[0]) fprintf(file, "%s.", property->group);
    fprintf(file, "%s", property->name);
    ListIterator parameters = createIterator(property->parameters);
    Parameter* parameter;
    while ((parameter = nextElement(&parameters)))
        fprintf(file, ";%s=%s", parameter->name, parameter->value);
    fputc(':', file);
    ListIterator values = createIterator(property->values);
    char* value;
    int first = 1;
    while ((value = nextElement(&values))) {
        if (!first) fputc(';', file);
        fputs(value, file);
        first = 0;
    }
    fputs("\r\n", file);
}

static int digits(const char* text, size_t count) {
    int result = 0;
    for (size_t i = 0; i < count; i++) {
        if (!isdigit((unsigned char)text[i])) return -1;
        result = result * 10 + text[i] - '0';
    }
    return result;
}

/* Basic and reduced vCard dates and basic local/UTC times. */
bool validDate(const DateTime* dt) {
    if (!dt) return true;
    if (!dt->date || !dt->time || !dt->text) return false;
    if (dt->isText) return *dt->text && !*dt->date && !*dt->time && !dt->UTC;
    if (*dt->text || (!*dt->date && !*dt->time)) return false;
    size_t length = strlen(dt->date);
    int year = 2000, month = 0, day = 0;
    if (length == 8) {
        year = digits(dt->date, 4);
        month = digits(dt->date + 4, 2); day = digits(dt->date + 6, 2);
        if (year <= 0) return false;
    } else if (length == 6 && strncmp(dt->date, "--", 2) == 0) {
        month = digits(dt->date + 2, 2); day = digits(dt->date + 4, 2);
    } else if (length == 5 && strncmp(dt->date, "---", 3) == 0) {
        day = digits(dt->date + 3, 2);
        if (day < 1 || day > 31) return false;
    } else if (length == 4 && strncmp(dt->date, "--", 2) == 0) {
        month = digits(dt->date + 2, 2);
        if (month < 1 || month > 12) return false;
    } else if (length == 4) {
        if (digits(dt->date, 4) <= 0) return false;
    } else if (length) return false;
    if (length == 8 || length == 6) {
        static const int days[] = {0,31,28,31,30,31,30,31,31,30,31,30,31};
        if (month < 1 || month > 12) return false;
        int maximum = days[month] + (month == 2 && year % 4 == 0 && (year % 100 != 0 || year % 400 == 0));
        if (day < 1 || day > maximum) return false;
    }
    length = strlen(dt->time);
    if (!length) return !dt->UTC;
    if (length != 2 && length != 4 && length != 6) return false;
    int hour = digits(dt->time, 2);
    if (hour < 0 || hour > 23) return false;
    if (length >= 4) {
        int minute = digits(dt->time + 2, 2);
        if (minute < 0 || minute > 59) return false;
    }
    if (length == 6) {
        int second = digits(dt->time + 4, 2);
        if (second < 0 || second > 60) return false;
    }
    return true;
}
