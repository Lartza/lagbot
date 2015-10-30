# coding=utf-8
from plugins.ircplugin import IRCPlugin


class HandlerPlugin(IRCPlugin):

    def __init__(self):
        super().__init__()

    def execute(self, bot, user, channel, message):
        raise NotImplementedError
