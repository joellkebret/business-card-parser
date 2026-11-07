
#include "VCHelpers.h"
#include "VCParser.h"

void deleteProperty(void* toBeDeleted) { 
    if (toBeDeleted == NULL) return;

    Property* prop = (Property*)toBeDeleted;

    if (prop->name != NULL) {
        free(prop->name);
    }

    if (prop->group != NULL) {
        free(prop->group);
    }

    if (prop->parameters != NULL) {
        clearList(prop->parameters); //free list wasnt working, do
        free(prop->parameters);  
    }

    if (prop->values != NULL) {
        clearList(prop->values);  
        free(prop->values);  // manual free
    }

    free(prop);
}

int compareDates(const void* first, const void* second) {
    return 0; // Dates are not sorted by the parser
}

void deleteDate(void* toBeDeleted) {
    if (toBeDeleted == NULL) {
        return;
    }

    DateTime* vcardDate = (DateTime*)toBeDeleted; //deleting all attributes of date then date

    if (vcardDate->date != NULL) {
        free(vcardDate->date);
    }

    if (vcardDate->time != NULL) {
        free(vcardDate->time);
    }

    if (vcardDate->text != NULL) {
        free(vcardDate->text);
    }

    free(vcardDate);
}

void deleteValue(void* toBeDeleted) {
    if (toBeDeleted == NULL) {
        return; 
    }

    char* value = (char*)toBeDeleted;
    
    if (value != NULL) {
        free(value);
    }
}

void deleteParameter(void* toBeDeleted) {
    if (toBeDeleted == NULL) {
        return;
    }   

    Parameter* param = (Parameter*)toBeDeleted;

    if (param->name != NULL) {
        free(param->name);
    }

    if (param->value != NULL) {
        free(param->value);
    }

    free(param);
}
 
int compareProperties(const void* first, const void* second) {
    if (first == NULL || second == NULL) {
        return (first == second) ? 0 : 1; //ternary operator check if both null
    }

    const Property* prop1 = (const Property*)first;
    const Property* prop2 = (const Property*)second;

    if (strcmp(prop1->name, prop2->name) != 0) {
        return 1;
    }

    if (strcmp(prop1->group, prop2->group) != 0) {
        return 1;
    }

    if (getLength(prop1->values) != getLength(prop2->values)) {
        return 1; // Lists must have the same length
    }

    ListIterator iterator1 = createIterator(prop1->values); //iterate through the values of each property
    ListIterator iterator2 = createIterator(prop2->values);

    void* value1;
    void* value2;

    while ((value1 = nextElement(&iterator1)) != NULL && (value2 = nextElement(&iterator2)) != NULL) { //loop and compare values
        if (compareValues(value1, value2) != 0) {
            return 1; 
        }
    }

    // Compare parameters (list order matters)
    if (getLength(prop1->parameters) != getLength(prop2->parameters)) {
        return 1; // Lists must have the same length
    }

    ListIterator paramater1Iterator = createIterator(prop1->parameters);
    ListIterator parameter2Iterator = createIterator(prop2->parameters);

    void* parameter1;
    void* parameter2;

    while ((parameter1 = nextElement(&paramater1Iterator)) != NULL && (parameter2 = nextElement(&parameter2Iterator)) != NULL) {
        if (compareParameters(parameter1, parameter2) != 0) {
            return 1; // Parameters do not match
        }
    }

    return 0; //equal
}


int compareValues(const void* first, const void* second) {
    if (first == NULL || second == NULL) {
        return (first == second) ? 0 : 1;
    }

    if (((char*)first)[0] == '\0' && ((char*)second)[0] == '\0') {
        return 0; //emptry string is equal
    }

    return strcmp((char*)first, (char*)second); //return 0 if equal
}

int compareParameters(const void* first, const void* second) {
    if (first == NULL || second == NULL) {
        return (first == second) ? 0 : 1;
    }

    const Parameter* parameter1 = (const Parameter*)first;
    const Parameter* parameter2 = (const Parameter*)second; //dont allow any sort of changing of a parameter while compring

    if (parameter1->name[0] == '\0' && parameter2->name[0] == '\0' &&
        parameter1->value[0] == '\0' && parameter2->value[0] == '\0') {
        return 0;  // Empty parameters are equal
    }

    if (strcmp(parameter1->name, parameter2->name) != 0) {
        return 1;
    }

    return strcmp(parameter1->value, parameter2->value);
}


char* valueToString(void* val) {
    if (val == NULL) {
        return strdup("");  //empty string for NULL
    }
    return strdup((char*)val);  //duplicate string dynamically
}

char* dateToString(void* date){
    if (date == NULL){
        return strdup("");
    }

    DateTime* vcardDate = (DateTime*)date;
    char buffer[1000]; //buffer for output
    buffer[0] = '\0'; //give terminator

     if (vcardDate->isText) {
        snprintf(buffer, sizeof(buffer), "Text: %s", vcardDate->text);
    } else {
        snprintf(buffer, sizeof(buffer), "Date: %s Time: %s UTC: %s", vcardDate->date, vcardDate->time, vcardDate->UTC ? "Yes" : "No");
    }

  return strdup(buffer); //return dynamically allocated copy
}

char* parameterToString(void* param){
    if (param == NULL) {
        return strdup("");  //empty string for NULL
    }

    Parameter* parameter = (Parameter*)param;
    char buffer[256];

    if (strlen(parameter->name) > 0 && strlen(parameter->value) > 0) {
        snprintf(buffer, sizeof(buffer), "%s=%s", parameter->name, parameter->value);

    } else if (strlen(parameter->name) > 0) {
        snprintf(buffer, sizeof(buffer), "%s", parameter->name);

    } else if (strlen(parameter->value) > 0) {
        snprintf(buffer, sizeof(buffer), "%s", parameter->value);

    } else {
        return strdup("");  //return empty if both empty
    }

    return strdup(buffer);  //return valid copy
}

char* propertyToString(void* prop) {
    return strdup(prop ? ((Property*)prop)->name : "");
}

int updateFN(Card* card, const char* newFN) {
    if (!card || !card->fn || !newFN || !*newFN) return INV_PROP;
    char* value = strdup(newFN);
    if (!value) return OTHER_ERROR;
    List* values = initializeList(valueToString, deleteValue, compareValues);
    if (!values) { free(value); return OTHER_ERROR; }
    if (!insertBack(values, value)) { free(value); freeList(values); return OTHER_ERROR; }
    freeList(card->fn->values);
    card->fn->values = values;
    return OK;
}
