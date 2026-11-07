
#include "VCHelpers.h"
#include "VCParser.h"

VCardErrorCode createCard(char* fileName, Card** newCardObject) {
    if (fileName == NULL || newCardObject == NULL) { 
        return INV_FILE;
    }

    *newCardObject = NULL;

    //check file extension
    char* extension = strrchr(fileName, '.');
    if (!extension || (strcmp(extension, ".vcf") != 0 && strcmp(extension, ".vcard") != 0)) {
        return INV_FILE;
    }

    FILE* file = fopen(fileName, "rb");
    if (file == NULL) {
        return INV_FILE;
    }

    //allocate memory for new card object
    *newCardObject = malloc(sizeof(Card));
    if (*newCardObject == NULL) {
        fclose(file);
        return OTHER_ERROR;
    }

    //Initialize card fields
    (*newCardObject)->fn = NULL;
    (*newCardObject)->birthday = NULL;
    (*newCardObject)->anniversary = NULL;
    (*newCardObject)->optionalProperties = initializeList(propertyToString, deleteProperty, compareProperties);
    if ((*newCardObject)->optionalProperties == NULL) {
        free(*newCardObject);
        *newCardObject = NULL;
        fclose(file);
        return OTHER_ERROR;
    }

    bool foundFN = false, foundVersion = false, foundBegin = false, foundEnd = false;
    double version = 0.0;

    char line[65536];
    while (fgets(line, sizeof(line), file) != NULL) {
        long len = strlen(line);

        // check if CRLF is present
        if (len < 2 || line[len - 2] != '\r' || line[len - 1] != '\n') {
            deleteCard(*newCardObject);
            *newCardObject = NULL;
            fclose(file);
            return INV_CARD;
        }
        line[len - 2] = '\0';
        /* Consume continuations before splitting property names or values. */
        while (1) {
            int next = fgetc(file);
            if (next != ' ' && next != '\t') {
                if (next != EOF) ungetc(next, file);
                break;
            }
            size_t used = strlen(line);
            if (!fgets(line + used, sizeof(line) - used, file)) {
                deleteCard(*newCardObject); *newCardObject = NULL;
                fclose(file); return INV_CARD;
            }
            size_t total = strlen(line);
            if (total < 2 || line[total-2] != '\r' || line[total-1] != '\n') {
                deleteCard(*newCardObject); *newCardObject = NULL;
                fclose(file); return INV_CARD;
            }
            line[total-2] = '\0';
        }

        //skip empty lines
        if (strlen(line) == 0) {
            continue;
        }

        //ensure first line is BEGIN:VCARD
        if (!foundBegin) {
            if (strcmp(line, "BEGIN:VCARD") != 0) {
                deleteCard(*newCardObject);
                *newCardObject = NULL;
                fclose(file);
                return INV_CARD;
            }
            foundBegin = true;
            continue;
        }

        // check if last line is end:vcard
        if (strcmp(line, "END:VCARD") == 0) {
            foundEnd = true;
            int trailing;
            while ((trailing = fgetc(file)) != EOF) {
                if (!isspace((unsigned char)trailing)) {
                    deleteCard(*newCardObject); *newCardObject = NULL;
                    fclose(file); return INV_CARD;
                }
            }
            break;
        }

        //split at colon
        char* colonPosition = strchr(line, ':');
        if (!colonPosition) {
            deleteCard(*newCardObject);
            *newCardObject = NULL;
            fclose(file);
            return INV_PROP;
        }

        *colonPosition = '\0';
        char* entireProperty = line;
        char* propertyValue = colonPosition + 1;

        //if property name or value empty
        if (strlen(entireProperty) == 0 || strlen(propertyValue) == 0) {
            deleteCard(*newCardObject);
            *newCardObject = NULL;
            fclose(file);
            return INV_PROP;
        }

        //parse groups 
        char* propertyGroup = strdup("");
        if (!propertyGroup) {
            deleteCard(*newCardObject);
            *newCardObject = NULL;
            fclose(file);
            return OTHER_ERROR;
        }

        char* scPosition = strchr(entireProperty, ';');
        char* periodPosition = NULL;
        if (scPosition) {
            *scPosition = '\0';
            periodPosition = strchr(entireProperty, '.');
            *scPosition = ';';
        } else {
            periodPosition = strchr(entireProperty, '.');
        }

        char* propName = entireProperty;
        if (periodPosition) {
            *periodPosition = '\0';
            free(propertyGroup);
            propertyGroup = strdup(entireProperty);
            propName = periodPosition + 1;
            if (!propertyGroup) {
                deleteCard(*newCardObject); *newCardObject = NULL;
                fclose(file); return OTHER_ERROR;
            }
        }

        //init params
        List* paramList = initializeList(parameterToString, deleteParameter, compareParameters);
        if (!paramList) {
            free(propertyGroup);
            deleteCard(*newCardObject);
            *newCardObject = NULL;
            fclose(file);
            return OTHER_ERROR;
        }

        bool isValueText = false;

        // parse according to semicolon
        char* scPosition2 = strchr(propName, ';');
        if (scPosition2) {
            *scPosition2 = '\0';
            scPosition2++;
            char* paramToken = strtok(scPosition2, ";");
            while (paramToken != NULL) {
                char* equalPosition = strchr(paramToken, '=');
                if (!equalPosition) {
                    free(propertyGroup);
                    deleteCard(*newCardObject);
                    *newCardObject = NULL;
                    freeList(paramList);
                    fclose(file);
                    return INV_PROP;
                }

                *equalPosition = '\0';
                char* parameterName = paramToken;
                char* parameterVal = equalPosition + 1;

                Parameter* newParam = malloc(sizeof(Parameter));
                if (!newParam) {
                    free(propertyGroup);
                    deleteCard(*newCardObject);
                    *newCardObject = NULL;
                    freeList(paramList);
                    fclose(file);
                    return OTHER_ERROR;
                }
                newParam->name = strdup(parameterName);
                newParam->value = strdup(parameterVal);
                if (!newParam->name || !newParam->value || !insertBack(paramList, newParam)) {
                    deleteParameter(newParam); free(propertyGroup); freeList(paramList);
                    deleteCard(*newCardObject); *newCardObject = NULL;
                    fclose(file); return OTHER_ERROR;
                }

                // Check if VALUE=text
                if (strcasecmp(parameterName, "VALUE") == 0 && strcasecmp(parameterVal, "text") == 0) {
                    isValueText = true;
                }
                paramToken = strtok(NULL, ";");
            }
        }

        // Handle VERSION
        if (strcmp(propName, "VERSION") == 0) {
            if (foundVersion) {
                free(propertyGroup);
                deleteCard(*newCardObject);
                *newCardObject = NULL;
                freeList(paramList);
                fclose(file);
                return INV_CARD;
            }
            foundVersion = true;
            version = strcmp(propertyValue, "4.0") == 0 ? 4.0 : 0.0;
            if (version != 4.0) {
                free(propertyGroup);
                deleteCard(*newCardObject);
                *newCardObject = NULL;
                freeList(paramList);
                fclose(file);
                return INV_CARD;
            }

            freeList(paramList);
            free(propertyGroup);
            continue;
        }
        //ensure fn exists
        else if (strcmp(propName, "FN") == 0) {
            if (foundFN) {
                free(propertyGroup);
                deleteCard(*newCardObject);
                *newCardObject = NULL;
                freeList(paramList);
                fclose(file);
                return INV_CARD;
            }
            foundFN = true;

            Property* fnProp = malloc(sizeof(Property));
            if (!fnProp) {
                free(propertyGroup);
                deleteCard(*newCardObject);
                *newCardObject = NULL;
                freeList(paramList);
                fclose(file);
                return OTHER_ERROR;
            }

            fnProp->name = strdup("FN");
            fnProp->group = propertyGroup;
            fnProp->values = initializeList(valueToString, deleteValue, compareValues);
            fnProp->parameters = paramList;

            if (!fnProp->name || !fnProp->values) {
                deleteProperty(fnProp);
                deleteCard(*newCardObject);
                *newCardObject = NULL;
                fclose(file);
                return OTHER_ERROR;
            }

            char* fnValue = strdup(propertyValue);
            if (!fnValue || !insertBack(fnProp->values, fnValue)) {
                free(fnValue); deleteProperty(fnProp);
                deleteCard(*newCardObject); *newCardObject = NULL;
                fclose(file); return OTHER_ERROR;
            }
            (*newCardObject)->fn = fnProp;
        }
        //create bday
        else if (strcmp(propName, "BDAY") == 0 || strcmp(propName, "ANNIVERSARY") == 0) {
            if ((strcmp(propName, "BDAY") == 0 && (*newCardObject)->birthday) ||
                (strcmp(propName, "ANNIVERSARY") == 0 && (*newCardObject)->anniversary)) {
                free(propertyGroup);
                freeList(paramList);
                deleteCard(*newCardObject);
                *newCardObject = NULL;
                fclose(file);
                return INV_DT;
            }
            DateTime* vcardDate = malloc(sizeof(DateTime));
            if (!vcardDate) {
                free(propertyGroup);
                deleteCard(*newCardObject);
                *newCardObject = NULL;
                freeList(paramList);
                fclose(file);
                return OTHER_ERROR;
            }

            vcardDate->UTC    = false;
            vcardDate->isText = isValueText;
            vcardDate->date   = strdup("");
            vcardDate->time   = strdup("");
            vcardDate->text   = strdup("");

            if (!vcardDate->date || !vcardDate->time || !vcardDate->text) {
                deleteDate(vcardDate); free(propertyGroup); freeList(paramList);
                deleteCard(*newCardObject); *newCardObject = NULL;
                fclose(file); return OTHER_ERROR;
            }

            if (isValueText) {
                //check if dt is text
                free(vcardDate->text);
                vcardDate->text = strdup(propertyValue);
            } else {
                //
                char* timePosition = strchr(propertyValue, 'T');
                if (timePosition) {
                    if (!timePosition[1]) {
                        deleteDate(vcardDate); free(propertyGroup); freeList(paramList);
                        deleteCard(*newCardObject); *newCardObject = NULL;
                        fclose(file); return INV_DT;
                    }
                    *timePosition = '\0';
                    free(vcardDate->date);
                    vcardDate->date = strdup(propertyValue);
                    free(vcardDate->time);
                    vcardDate->time = strdup(timePosition + 1);

                    //check if ends with Z
                    if (vcardDate->time && vcardDate->time[0] && vcardDate->time[strlen(vcardDate->time) - 1] == 'Z') {
                        vcardDate->UTC = true;
                        vcardDate->time[strlen(vcardDate->time) - 1] = '\0';
                    }
                } else {
                    // Just YYYYMMDD
                    free(vcardDate->date);
                    vcardDate->date = strdup(propertyValue);
                }
            }

            free(propertyGroup);
            freeList(paramList);

            if (!vcardDate->date || !vcardDate->time || !vcardDate->text) {
                deleteDate(vcardDate);
                deleteCard(*newCardObject); *newCardObject = NULL;
                fclose(file); return OTHER_ERROR;
            }

            if (strcmp(propName, "BDAY") == 0) {
                // Save as birthday
                (*newCardObject)->birthday = vcardDate;
            } else {
                // Save as anniversary
                (*newCardObject)->anniversary = vcardDate;
            }
        }
        //store as a normal Property in optionalProperties
        else {
            Property* prop = malloc(sizeof(Property));
            if (!prop) {
                free(propertyGroup);
                deleteCard(*newCardObject);
                *newCardObject = NULL;
                freeList(paramList);
                fclose(file);
                return OTHER_ERROR;
            }

            prop->name = strdup(propName);
            prop->group = propertyGroup;
            prop->values = initializeList(valueToString, deleteValue, compareValues);
            prop->parameters = paramList;

            if (!prop->name || !prop->values) {
                deleteProperty(prop);
                deleteCard(*newCardObject);
                *newCardObject = NULL;
                fclose(file);
                return OTHER_ERROR;
            }

            bool valuesOK = true;
            if (strcasecmp(propName, "N") == 0 || strcasecmp(propName, "ADR") == 0) {
                int required = strcasecmp(propName, "N") == 0 ? 5 : 7;
                char* start = propertyValue;
                int count = 0;
                while (1) {
                    char* separator = start;
                    while (*separator) {
                        if (*separator == '\\' && separator[1]) { separator += 2; continue; }
                        if (*separator == ';') break;
                        separator++;
                    }
                    bool more = *separator != '\0';
                    *separator = '\0';
                    char* value = strdup(start);
                    if (!value || !insertBack(prop->values, value)) {
                        free(value); valuesOK = false; break;
                    }
                    count++;
                    if (!more) break;
                    if (count >= required) {
                        deleteProperty(prop); deleteCard(*newCardObject);
                        *newCardObject = NULL; fclose(file); return INV_PROP;
                    }
                    start = separator + 1;
                }
                for (; valuesOK && count < required; count++) {
                    char* value = strdup("");
                    if (!value || !insertBack(prop->values, value)) { free(value); valuesOK = false; }
                }
            } else {
                char* value = strdup(propertyValue);
                if (!value || !insertBack(prop->values, value)) { free(value); valuesOK = false; }
            }
            if (!valuesOK || !insertBack((*newCardObject)->optionalProperties, prop)) {
                deleteProperty(prop); deleteCard(*newCardObject);
                *newCardObject = NULL; fclose(file); return OTHER_ERROR;
            }
        }
    } // end while

    fclose(file);

    // If END:VCARD was never found => invalid
    if (!foundEnd) {
        deleteCard(*newCardObject);
        *newCardObject = NULL;
        return INV_CARD;
    }

    // Must have found FN and version == 4.0
    if (!foundFN || !foundVersion || version != 4.0) {
        deleteCard(*newCardObject);
        *newCardObject = NULL;
        return INV_CARD;
    }

    return OK; //valid card :)
}

void deleteCard(Card* obj) {
    if (obj == NULL) {
        return;
    }

    if (obj->fn != NULL) {
        deleteProperty(obj->fn);
    }

    if (obj->optionalProperties != NULL) {
        freeList(obj->optionalProperties);
    }

    if (obj->birthday != NULL) {
        deleteDate(obj->birthday);
    }

    if (obj->anniversary != NULL) {
        deleteDate(obj->anniversary);
    }

    free(obj); //delete all individuals parts of a v card then card itself.
}

VCardErrorCode writeCard(const char* fileName, const Card* obj) {

    if (validateCard(obj) != OK) return WRITE_ERROR;

    //param checks
    if (obj == NULL || fileName == NULL || fileName[0] == '\0') {
        return WRITE_ERROR;
    }

    // file extension check
    char* extension = strrchr(fileName, '.');
    if (!extension || (strcmp(extension, ".vcf") != 0 && strcmp(extension, ".vcard") != 0)) {
        return WRITE_ERROR;
    }

    FILE *file = fopen(fileName, "wb");
    if (file == NULL) {
        return WRITE_ERROR;
    }

    //mandatory non properties
    fprintf(file, "BEGIN:VCARD\r\n");
    fprintf(file, "VERSION:4.0\r\n");

    writeProperty(file, obj->fn);
    ListIterator iter = createIterator(obj->optionalProperties);
    void* elem;
    while ((elem = nextElement(&iter)) != NULL) writeProperty(file, elem);

    // Handle BDAY
    if (obj->birthday != NULL) {
        fprintf(file, "BDAY");

        if (obj->birthday->isText) {
            // Print text birthday
            fprintf(file, ";VALUE=text:%s\r\n", 
                    (obj->birthday->text != NULL) ? obj->birthday->text : "");
        } else {
            // Print standard date or DT format with UTC check
            fprintf(file, ":%s%s%s%s\r\n", 
                    (obj->birthday->date != NULL) ? obj->birthday->date : "", 
                    (obj->birthday->time != NULL && obj->birthday->time[0] != '\0') ? "T" : "",
                    (obj->birthday->time != NULL) ? obj->birthday->time : "",
                    (obj->birthday->UTC) ? "Z" : "");
        }
    }

    //Handle ANNIVERSARY
    if (obj->anniversary != NULL) {
        fprintf(file, "ANNIVERSARY");

        if (obj->anniversary->isText) {
            // Print text anniversary
            fprintf(file, ";VALUE=text:%s\r\n", 
                    (obj->anniversary->text != NULL) ? obj->anniversary->text : "");
        } else {
            fprintf(file, ":%s%s%s%s\r\n", 
                    (obj->anniversary->date != NULL) ? obj->anniversary->date : "", 
                    (obj->anniversary->time != NULL && obj->anniversary->time[0] != '\0') ? "T" : "",
                    (obj->anniversary->time != NULL) ? obj->anniversary->time : "",
                    (obj->anniversary->UTC) ? "Z" : "");
        }
    }

    // End vCard
    fprintf(file, "END:VCARD\r\n");

    int failed = ferror(file);
    if (fclose(file) != 0) failed = 1;
    return failed ? WRITE_ERROR : OK;
}



VCardErrorCode validateCard(const Card* obj) {
    //check if card null
    if (obj == NULL) {
        return INV_CARD;  
    }

    if (obj->fn == NULL) {   
        return INV_CARD;  // FN must exist
    }
    if (!obj->fn->name || strcasecmp(obj->fn->name, "FN") != 0 ||
        !obj->fn->group || !obj->fn->parameters) return INV_PROP;
    ListIterator fnParameters = createIterator(obj->fn->parameters);
    Parameter* fnParameter;
    while ((fnParameter = nextElement(&fnParameters))) {
        if (!fnParameter->name || !*fnParameter->name ||
            !fnParameter->value || !*fnParameter->value) return INV_PROP;
    }
    if (obj->fn->values == NULL || getLength(obj->fn->values) == 0) {
        return INV_CARD;  //FN has no values
    }
    char* fnValue = (char*)getFromFront(obj->fn->values);
    if (fnValue == NULL || strlen(fnValue) == 0) {
        return INV_CARD;  //FN is empty
    }

    // check optionalProperties list card needs at least one
    if (obj->optionalProperties == NULL) {
        return INV_CARD;
    }

    // occurcence / cardinality tracker
    int kindCount = 0; //KIND cardinality
    int nCount = 0;
    int uidCount = 0;
    int revCount = 0;
    int genderCount = 0;
    int prodidCount = 0;


    // loop through optionalProperties
    ListIterator iter = createIterator(obj->optionalProperties);
    void* elem;
    while ((elem = nextElement(&iter)) != NULL) {
        Property* prop = (Property*)elem;

        if (!prop->name || !*prop->name || !prop->group || !prop->parameters || !prop->values)
            return INV_PROP;

        // version is required
        if (strcasecmp(prop->name, "VERSION") == 0) {
            return INV_CARD;
        }

        // n can only papear at max onece
        if (strcasecmp(prop->name, "N") == 0) {
            nCount++;
            if (nCount > 1) {
                return INV_PROP;  
            }
            if (getLength(prop->values) != 5) {
                return INV_PROP;
            }
        }

        // kind must be unique as well
        if (strcasecmp(prop->name, "KIND") == 0) {
            kindCount++;
            if (kindCount > 1) {
                return INV_PROP; 
            }
        }

        if (strcasecmp(prop->name, "UID") == 0) {
            uidCount++;
            if (uidCount > 1) {
                return INV_PROP; 
            }
        }

        if (strcasecmp(prop->name, "PRODID") == 0) {
            prodidCount++;
            if (prodidCount > 1) {
                return INV_PROP;  
            }
        }

        if (strcasecmp(prop->name, "REV") == 0) {
            revCount++;
            if (revCount > 1) {
                return INV_PROP;  
            }
        }
        


        if (strcasecmp(prop->name, "GENDER") == 0) {
            genderCount++;
            if (genderCount > 1) {
                return INV_PROP;  
            }
        }

        // prop cant be empty
        if (prop->name == NULL || strlen(prop->name) == 0) {
            return INV_PROP;
        }

        // bday or ann should not be in anniversary
        if (strcasecmp(prop->name, "BDAY") == 0 ||
            strcasecmp(prop->name, "ANNIVERSARY") == 0) 
        {
            return INV_DT;  
        }

        //prop has to have 1 val minimum
        if (prop->values == NULL || getLength(prop->values) == 0) {
            return INV_PROP;  // missing property value
        }

        // parameters must also be non empty
        ListIterator paramIter = createIterator(prop->parameters);
        void* paramElem;
        while ((paramElem = nextElement(&paramIter)) != NULL) {
            Parameter* param = (Parameter*)paramElem;
            if (param->name == NULL || strlen(param->name) == 0 ||
                param->value == NULL || strlen(param->value) == 0) {
                return INV_PROP;  // missing param name/value
            }
        }
    }

    if (!validDate(obj->birthday) || !validDate(obj->anniversary)) return INV_DT;

    // validate bday if existing
    if (obj->birthday != NULL) {
        if (obj->birthday->isText) {
            //handle text date
            if (strlen(obj->birthday->date) != 0 ||
                strlen(obj->birthday->time) != 0 ||
                strlen(obj->birthday->text) == 0 ||
                obj->birthday->UTC)
            {
                return INV_DT;
            }
        } else {
            if (strlen(obj->birthday->text) != 0) {
                return INV_DT;
            }

            if (strlen(obj->birthday->date) == 0 && strlen(obj->birthday->time) == 0) {
                return INV_DT;  // must have somethin
            }

            //check utc 
            if (obj->birthday->UTC && strlen(obj->birthday->time) == 0) {
                return INV_DT;
            }
        }
    }

    if (obj->anniversary != NULL) {
        if (obj->anniversary->isText) {
            if (strlen(obj->anniversary->date) != 0 ||
                strlen(obj->anniversary->time) != 0 ||
                strlen(obj->anniversary->text) == 0 ||
                obj->anniversary->UTC)
            {
                return INV_DT;
            }
        } else {
            if (strlen(obj->anniversary->text) != 0) {
                return INV_DT;
            }

            if (strlen(obj->anniversary->date) == 0 && strlen(obj->anniversary->time) == 0) {
                return INV_DT;
            }

            if (obj->anniversary->UTC && strlen(obj->anniversary->time) == 0) {
                return INV_DT;
            }
        }
    }

    // If we reach here, everything is valid :)
    return OK; 
}
