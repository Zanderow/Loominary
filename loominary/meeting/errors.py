class MeetingError(Exception):
    pass


class ConfigError(MeetingError):
    pass


class AudioDeviceError(MeetingError):
    pass


class RecorderError(MeetingError):
    pass


class TranscriptionError(MeetingError):
    pass


class ShutdownError(MeetingError):
    pass
