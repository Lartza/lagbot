# coding=utf-8
from yapsy.IPlugin import IPlugin


class IRCPlugin(IPlugin):

    def __init__(self):
        super().__init__()

    def execute(self, bot, user, channel, message):
        raise NotImplementedError
