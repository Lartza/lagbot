#!/usr/bin/env python3
# coding=utf-8
# lagirc, simple Python irc library
# Copyright (C) 2015  Lari Tikkanen
#
# Released under the GPLv3
# See LICENSE for details.

from configobj import ConfigObj

import lagirc
import asyncio

from yapsy.PluginManager import PluginManager
from plugins.commandplugin import CommandPlugin
from plugins.handlerplugin import HandlerPlugin

debug = False
config = ConfigObj('config.cfg')
if debug:
    import logging
    import warnings
    logging.basicConfig(level=logging.DEBUG)
    warnings.resetwarnings()


class LagBot(lagirc.IRCClient):
    def __init__(self):
        super().__init__()
        self.nickname = config['global']['nickname']
        self.username = config['global']['username']
        self.realname = config['global']['realname']
        self.manager = None
        self.commands = {}
        self.handlers = []
        self.init_plugins()

    def init_plugins(self, reload=False):
        if reload:
            self.commands = {}
            self.handlers = []
            for plugin in self.manager.getAllPlugins():
                self.manager.deactivatePluginByName(plugin.name)
        self.manager = PluginManager(
            categories_filter={
                'Command': CommandPlugin,
                'Handler': HandlerPlugin,
            },
            directories_list=['plugins'], )
        self.manager.collectPlugins()
        for plugin in self.manager.getPluginsOfCategory('Command'):
            self.manager.activatePluginByName(plugin.name, 'Command')
            try:
                for command in plugin.plugin_object.commands:
                    self.commands[command] = plugin.plugin_object
            except AttributeError:
                print('Plugin {} does not define any commands! Disabling')
                self.manager.deactivatePluginByName(plugin.name)
        for plugin in self.manager.getPluginsOfCategory('Handler'):
            self.manager.activatePluginByName(plugin.name, 'Handler')
            self.handlers.append(plugin.plugin_object)

    def connected(self):
        print('Connected')
        for channel in config['global'].as_list('channels'):
            self.join(channel)
            print('Joined {0}'.format(channel))

    def is_owner(self, user):
        if user == config['global']['owner']:
            return True
        return False

    def is_op(self, user, channel):
        if user in config[channel].as_list('ops'):
            return True
        return False

    def get_nick(self, user):
        return user.split('!', 1)[0]

    def privmsg_received(self, user, channel, message):
        if message.startswith('!'):
            cmd = message.split(' ', 1)[0].lstrip('!')
            try:
                plugin = self.commands[cmd]
            except KeyError:
                plugin = None
                if self.is_owner(user):
                    if cmd == 'reload':
                        self.init_plugins(reload=True)
            if plugin:
                plugin.execute(self, user, channel, message)
        for handler in self.handlers:
            handler.execute(self, user, channel, message)

loop = asyncio.get_event_loop()
if debug:
    loop.set_debug(True)
coro = loop.create_connection(lambda: LagBot(), config['global']['host'],
                              int(config['global']['port']))
loop.run_until_complete(coro)
loop.run_forever()
loop.close()
