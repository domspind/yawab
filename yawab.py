# -*- coding: utf-8 -*-

import os
import re

import calendar
import configparser
from enum import Enum
import locale
import logging
import qrcode


def setup_logger():
    # define custom log level TRACE
    logging.TRACE = 5
    logging.addLevelName(logging.TRACE, "TRACE")
    logging.basicConfig(level=logging.DEBUG)


def setup_locale():
    config = Configuration()
    locale_string = config.get_locale()
    locale.setlocale(locale.LC_ALL, locale_string)


def main():
    setup_logger()
    setup_locale()

    chat_parser = ChatParser()
    latex_generator = LatexGenerator()

    messages = chat_parser.parse()

    for message in messages:
        latex_generator.process_message(message)

    return


class Configuration:
    _config = configparser.ConfigParser()
    _config_already_read = False

    def __init__(self):
        # read config only once
        if not Configuration._config_already_read:
            Configuration._config.read('config.ini', encoding='utf-8')
            Configuration._config_already_read = True

    @staticmethod
    def get_chat_dir():
        return Configuration._config.get('General', 'ChatDir')

    @staticmethod
    def get_chat_filename():
        return Configuration._config.get('General', 'ChatFile')

    @staticmethod
    def get_output_dir():
        return Configuration._config.get('General', 'OutputDir')

    @staticmethod
    def get_media_server_url():
        return Configuration._config.get('Media', 'ServerUrl')

    @staticmethod
    def get_locale():
        return Configuration._config.get('Localization', 'Locale')

    @staticmethod
    def get_localizable_string(key):
        return Configuration._config.get('Localization', key)


class QrCodeGenerator:
    _qr_code_index = 0
    _config = Configuration()

    @staticmethod
    def generate_url_qr_code(url):
        qr_img_filename = "qrImage_" + str(QrCodeGenerator._qr_code_index) + ".png"
        qr_img_path = os.path.join(QrCodeGenerator._config.get_output_dir(), qr_img_filename)

        qr_img = qrcode.make(url)
        qr_img.save(qr_img_path)

        QrCodeGenerator._qr_code_index += 1

        return qr_img_filename

    def generate_media_qr_code(self, media_name):
        media_url = QrCodeGenerator._config.get_media_server_url() + media_name

        return self.generate_url_qr_code(media_url), media_url


class LineType(Enum):
    SKIP = 0
    TEXT = 1
    IMAGE = 2
    VIDEO = 3
    AUDIO = 4
    LINK = 5


class Line:
    _config = Configuration()

    def __init__(self, content):
        self.type = LineType.SKIP
        self.content = None
        self.file_name = None

        self.parse_line_content(content)

    def parse_line_content(self, content):

        # handle videos
        vid = re.search("([a-zA-Z0-9-_]+).mp4", content)
        if vid:
            self.type = LineType.VIDEO
            self.file_name = vid.group(0)
            self.content = Line._config.get_localizable_string('VideoPlaceholder')
            return

        # handle voice messages
        voice = re.search("([a-zA-Z0-9-_]+).opus", content)
        if voice:
            self.type = LineType.AUDIO
            self.file_name = voice.group(0)
            self.content = Line._config.get_localizable_string('VoicePlaceholder')
            return

        # handle images
        image = re.search("([a-zA-Z0-9-_]+).jpg", content)
        if image:
            self.type = LineType.IMAGE
            self.file_name = image.group(0)
            self.content = Line._config.get_localizable_string('ImagePlaceholder')
            return

        # remove unsupported attachments
        if Line._config.get_localizable_string('Attached') in content:
            logging.getLogger("Line").warning("Found and removed unsupported attachment: " + content)
            return

        # handle URLs
        # TODO

        # if it's none of the above it's probably just text
        self.type = LineType.TEXT
        self.content = content

        # handle unknown phone numbers
        # TODO find @<phone-number> in text (unknown number) and replace

        return


class Message:
    _msgIndex = 0

    def __init__(self, date, time, sender, line: Line):
        self.index = Message._msgIndex
        Message._msgIndex += 1
        self.date = date
        self.time = time
        self.sender = sender
        self.lines = []
        self.lines.append(line)

    def add_additional_line(self, line: Line):
        self.lines.append(line)


#
# This chat parser is optimized for german WhatsApp chat backups.
# It is probably not directly suitable for other backups due to localized strings
# and/or different date/time formats. However it can be adapted relatively easy.
#
class ChatParser:
    _config = Configuration()
    _logger = logging.getLogger("ChatParser")
    _timestampRegex = r"\d{2}.\d{2}.\d{2},\s\d{2}:\d{2}\s-\s"

    def __init__(self):
        self.__message = None

    def log_message(self):
        log_string = "Message #" + str(self.__message.index)
        log_string += "\n  Date: " + self.__message.date
        log_string += "\n  Time: " + self.__message.time
        log_string += "\n  Sender: " + self.__message.sender
        for line in self.__message.lines:
            if line.type is not LineType.SKIP:
                log_string += "\n  Line: " + line.content

        ChatParser._logger.log(logging.TRACE, log_string)

    def process_line(self, line):
        # find timestamp
        if re.search(ChatParser._timestampRegex, line):
            # timestamp found, this is a new chat message

            # process the previous message
            if self.__message is not None:
                self.log_message()
                yield self.__message
                self.__message = None

            # remove and store date
            date, line = line.split(",", 1)
            date = date.strip()

            # remove the store time
            time, line = line.split("-", 1)
            time = time.strip()

            # remove and store sender
            sender, line = line.split(":", 1)
            sender = sender.strip()

            # remove leading whitespaces from line
            line = line.lstrip()

            # create new message
            self.__message = Message(date, time, sender, Line(line))

        else:
            # no timestamp, there was a linebreak in the chat line
            self.__message.add_additional_line(Line(line))

    def parse(self):
        chat_path = os.path.join(self._config.get_chat_dir(), self._config.get_chat_filename())

        with open(chat_path, encoding='utf-8', mode='r') as fileObj:
            for line in fileObj.readlines():
                # strip all superfluous whitespaces from the line
                line = line.strip()

                # skip empty lines
                if line in ["", "\n", "\r\n", "\r"]:
                    continue

                yield from self.process_line(line)

            # process the last message
            if self.__message is not None:
                self.log_message()
                yield self.__message
                self.__message = None


class LatexGenerator:
    def process_message(self, message):
        # TODO process messages
        # for line in message.lines:
        #    self.process_line(line)
        return


if __name__ == '__main__':
    main()
