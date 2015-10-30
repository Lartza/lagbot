#!/usr/bin/env python3
# coding=utf-8
# lagirc, simple Python irc library
# Copyright (C) 2015  Lari Tikkanen
#
# Released under the GPLv3
# See LICENSE for details.

from configobj import ConfigObj
import logging

import lagirc
import asyncio

from yapsy.PluginManager import PluginManager
from plugins.commandplugin import CommandPlugin
from plugins.handlerplugin import HandlerPlugin

config = ConfigObj('config.cfg')
logging.basicConfig(level=config['global']['loglevel'])
if logging.getLogger().isEnabledFor(logging.DEBUG):
    import warnings
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
        self.logger = logging.getLogger('LagBot')
        self.logger.setLevel(config['global']['loglevel'])
        self.init_plugins()

    def init_plugins(self, reload=False):
        self.logger.info('Start initializing plugins')
        self.logger.debug('Reloading plugins? {}'.format(reload))
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
                self.logger.warn('Plugin {} does not define any commands! Disabling')
                self.manager.deactivatePluginByName(plugin.name)
            self.logger.debug('Loaded plugin {}'.format(plugin.name))
        for plugin in self.manager.getPluginsOfCategory('Handler'):
            self.manager.activatePluginByName(plugin.name, 'Handler')
            self.handlers.append(plugin.plugin_object)
            self.logger.debug('Loaded plugin {}'.format(plugin.name))
        self.logger.info('Finish plugin initialization')
        self.logger.debug('Commands: {}'.format(self.commands))
        self.logger.debug('Handlers: {}'.format(self.handlers))

    def connected(self):
        self.logger.info('Connected')
        for channel in config['global'].as_list('channels'):
            self.join(channel)
            self.logger.info('Joined {0}'.format(channel))

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
        self.logger.info('{} <{}> {}'.format(channel, self.get_nick(user), message))
        if message.startswith('!'):
            cmd = message.split(' ', 1)[0].lstrip('!')
            try:
                plugin = self.commands[cmd]
            except KeyError:
                self.logger.debug('No plugin found for command {}'.format(cmd))
                plugin = None
                if self.is_owner(user):
                    if cmd == 'reload':
                        self.init_plugins(reload=True)
            if plugin:
                self.logger.debug('Excecuting plugin for command {}'.format(cmd))
                plugin.execute(self, user, channel, message)
        for handler in self.handlers:
            self.logger.debug('Excecuting handlers')
            handler.execute(self, user, channel, message)

loop = asyncio.get_event_loop()
if logging.getLogger().isEnabledFor(logging.DEBUG):
    loop.set_debug(True)
coro = loop.create_connection(lambda: LagBot(), config['global']['host'],
                              int(config['global']['port']))
loop.run_until_complete(coro)
loop.run_forever()
loop.close()
