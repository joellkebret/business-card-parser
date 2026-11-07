class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class NativeError(ServiceError):
    MESSAGES = {
        1: ('invalid_file', 'The native parser could not open the vCard file.'),
        2: ('invalid_card', 'Expected one vCard 4.0 with VERSION and a nonempty FN.'),
        3: ('invalid_property', 'The vCard contains an invalid property.'),
        4: ('invalid_datetime', 'The vCard contains an invalid or unsupported date/time.'),
        5: ('write_error', 'The native parser could not write the vCard.'),
        6: ('native_error', 'The native parser failed.'),
    }

    def __init__(self, result: int):
        self.native_code = result
        code, message = self.MESSAGES.get(result, self.MESSAGES[6])
        super().__init__(code, message, 500 if result >= 5 else 422)
