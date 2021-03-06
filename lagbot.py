#!/usr/bin/env python3
# coding=utf-8
# lagirc, simple Python irc library
# Copyright (C) 2015  Lari Tikkanen
#
# Released under the GPLv3
# See LICENSE for details.

from configobj import ConfigObj
import logging
import re

import lagirc
import asyncio

from yapsy.PluginManager import PluginManager
from plugins.commandplugin import CommandPlugin
from plugins.handlerplugin import HandlerPlugin
from plugins.triggerplugin import TriggerPlugin

config = ConfigObj('config.cfg')
logging.basicConfig(level=config['global']['loglevel'])
if logging.getLogger().isEnabledFor(logging.DEBUG):
    import warnings
    warnings.resetwarnings()


class LagBot(lagirc.IRCClient):
    def __init__(self):
        super().__init__()
        # Set in load_config
        self.logger = None
        self.nickname = None
        self.username = None
        self.realname = None
        # Set in load_plugins
        self.manager = None
        self.commands = {}
        self.handlers = []
        self.triggers = {}
        # Calls to init methods
        self.load_config()
        self.load_plugins()

    def load_config(self, reload=False):
        if reload:
            config.reload()
        else:
            self.logger = logging.getLogger('LagBot')
            self.nickname = config['global']['nickname']
            self.username = config['global']['username']
            self.realname = config['global']['realname']
        self.logger.setLevel(config['global']['loglevel'])
        self.logger.info('Config loaded')

    def load_plugins(self, reload=False):
        """Loads all plugins"""
        self.logger.info('Start initializing plugins')
        self.logger.debug('Reloading plugins? {}'.format(reload))
        if reload:
            self.commands = {}
            self.handlers = []
            self.triggers = {}
            for plugin in self.manager.getAllPlugins():
                self.manager.deactivatePluginByName(plugin.name)
        self.manager = PluginManager(
            categories_filter={
                'Command': CommandPlugin,
                'Handler': HandlerPlugin,
                'Trigger': TriggerPlugin,
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
        for plugin in self.manager.getPluginsOfCategory('Trigger'):
            self.manager.activatePluginByName(plugin.name, 'Trigger')
            try:
                for trigger in plugin.plugin_object.triggers:
                    self.triggers[re.compile(trigger)] = plugin.plugin_object
            except AttributeError:
                self.logger.warn('Plugin {} does not define any triggers! Disabling')
                self.manager.deactivatePluginByName(plugin.name)
            self.logger.debug('Loaded plugin {}'.format(plugin.name))
        self.logger.info('Finish plugin initialization')
        self.logger.debug('Commands: {}'.format(self.commands))
        self.logger.debug('Handlers: {}'.format(self.handlers))
        self.logger.debug('Triggers: {}'.format(self.triggers))

    async def connected(self):
        self.logger.info('Connected')
        # Join all the channels defined in config
        for channel in config['global'].as_list('channels'):
            self.join(channel)
            self.logger.info('Joined {0}'.format(channel))

    def get_nick(self, user):
        """Return the nick from an irc user nick!user@host"""
        return user.split('!', 1)[0]

    def is_op(self, user, channel):
        """Checks if the user is set to have op permissions to the bot on a channel"""
        try:
            self.logger.debug(config[channel].as_list('ops'))
            if user in config[channel].as_list('ops'):
                self.logger.debug('{} matches {} ops'.format(user, channel))
                return True
        except KeyError:
            self.logger.debug('No ops for channel {}'.format(channel))
            return False
        self.logger.debug("{} doesn't match ops for {}".format(user, channel))
        return False

    def is_owner(self, user):
        """Return whether user matches owner in config"""
        if user == config['global']['owner']:
            return True
        return False

    async def privmsg_received(self, user, channel, message):
        self.logger.info('{} <{}> {}'.format(channel, self.get_nick(user), message))
        if message.startswith('!'):
            cmd = message.split(' ', 1)[0].lstrip('!')
            try:
                plugin = self.commands[cmd]
            except KeyError:
                self.logger.debug('No plugin found for command {}'.format(cmd))
                plugin = None
                if self.is_owner(user):
                    if cmd == 'reload_plugins':
                        self.load_plugins(reload=True)
                    if cmd == 'reload_config':
                        self.load_config(reload=True)
            if plugin:
                self.logger.debug('Excecuting plugin for command {}'.format(cmd))
                plugin.execute(self, user, channel, message)
        else:
            for trigger, plugin in self.triggers.items():
                if re.search(trigger, message) is not None:
                    plugin.execute(self, user, channel, message)
                    break
        for handler in self.handlers:
            self.logger.debug('Excecuting handlers')
            handler.execute(self, user, channel, message)

    def connection_lost(self, exc):
        loop.stop()

loop = asyncio.get_event_loop()
if logging.getLogger().isEnabledFor(logging.DEBUG):
    loop.set_debug(True)
coro = loop.create_connection(lambda: LagBot(), config['global']['host'],
                              int(config['global']['port']))
loop.run_until_complete(coro)
loop.run_forever()
loop.close()
