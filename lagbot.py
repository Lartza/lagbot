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

config = ConfigObj('config.cfg')


class LagBot(lagirc.IRCClient):
    def __init__(self, network, identity):
        super().__init__()
        self.network = network
        self.nickname = identity['nickname']
        self.username = identity['username']
        self.realname = identity['realname']
        self.manager = None
        self.commands = {}
        self.admincommands = {}
        self.handlers = []
        self.init_plugins()

    def init_plugins(self, reload=False):
        if reload:
            self.commands = {}
            self.admincommands = {}
            self.handlers = []
            for plugin in self.manager.getAllPlugins():
                self.manager.deactivatePluginByName(plugin.name)
        self.manager = PluginManager(
            categories_filter={
                "Command": CommandPlugin,
                "Handler": HandlerPlugin,
            },
            directories_list=["plugins"], )
        self.manager.collectPlugins()
        for plugin in self.manager.getPluginsOfCategory("Command"):
            self.manager.activatePluginByName(plugin.name, "Command")
            try:
                for command in plugin.plugin_object.commands:
                    self.commands[command] = plugin.plugin_object
            except AttributeError:
                pass
            try:
                for command in plugin.plugin_object.admincommands:
                    pluginobject = plugin.plugin_object
                    adminlevel = plugin.plugin_object.adminlevel
                    self.admincommands[command] = pluginobject, adminlevel
            except AttributeError:
                pass
        for plugin in self.manager.getPluginsOfCategory("Handler"):
            self.manager.activatePluginByName(plugin.name, "Handler")
            self.handlers.append(plugin.plugin_object)

    def connected(self):
        print('Connected')
        for channel in config['networks'][self.network].as_list('channels'):
            self.join(channel)
            print('Joined {0}'.format(channel))

    def is_admin(self, user):
        if user == config['global']['admin']:
            return True
        return False

    def privmsg_received(self, user, channel, message):
        if message.startswith('!'):
            cmd = message.split(' ', 1)[0].lstrip('!')
            try:
                plugin = self.commands[cmd]
            except KeyError:
                plugin = None
                if self.is_admin(user):
                    if cmd == 'reload':
                        self.init_plugins(reload=True)
                    else:
                        try:
                            plugin = self.admincommands[cmd][0]
                        except KeyError:
                            pass
            if plugin:
                plugin.execute(self, user, channel, message)
        for handler in self.handlers:
            handler.execute(self, user, channel, message)


loop = asyncio.get_event_loop()
for network in config['networks'].keys():
    identity = config['identities'][config['networks'][network]['identity']]
    client = LagBot(network, identity)
    coro = loop.create_connection(lambda: client, config['networks'][network]['host'],
                                  int(config['networks'][network]['port']))
    loop.run_until_complete(coro)
loop.run_forever()
loop.close()
